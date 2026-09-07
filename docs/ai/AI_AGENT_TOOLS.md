# AI Agent Tools — Todo Application

> **Status: Design specification only. No tools have been implemented yet.**
>
> This document defines the technical contract for the tools the future AI agent will use to interact with the Todo application. See `AI_AGENT.md` for the high-level architecture.

---

## 1. Purpose

### What an AI Tool Is in This Project

An AI tool is a Python function with a well-defined contract:

- It accepts a specific set of validated arguments.
- It receives the authenticated Django `User` explicitly.
- It performs exactly one documented operation against the database.
- It returns a structured result the agent can reliably interpret.

In this project, a tool is the only way the AI agent is permitted to interact with Todo data. The LLM has no other access path to the database.

### Why Controlled Tools Instead of Direct Database Access

The LLM produces text. If an LLM were given unrestricted access to the database, it could be manipulated — through prompt injection, misinterpretation, or hallucination — into executing unintended or dangerous operations. A tool layer eliminates this risk by restricting what can happen:

- The LLM can only call operations that have been explicitly implemented as tools.
- Each tool validates its inputs before any ORM call is made.
- Each tool enforces ownership regardless of what arguments the LLM passes.
- The LLM cannot construct arbitrary SQL or bypass Django's data layer.

### How Tools Provide a Controlled Boundary

```
User message (natural language)
          ↓
    AI Agent / LLM
          ↓
   Tool function call
   (validated args + request.user)
          ↓
   Django ORM query
   (always user-scoped)
          ↓
      Database
          ↓
   Structured result
          ↓
    Agent response
```

The LLM sits entirely above the tool boundary. Everything below it — the ORM, models, serializers, and database — is outside the LLM's direct reach.

---

## 2. Tool Design Principles

Every tool in this project must follow these rules. These are non-negotiable requirements, not suggestions.

### Authenticated User

Every tool must receive the authenticated Django `User` object as an explicit argument. This object must originate from DRF's `request.user` — resolved by `TokenAuthentication` in the Django view before the agent is invoked.

**The user identity must NEVER come from:**

- User-supplied text in the natural-language message
- An LLM-generated argument
- A `user_id` parameter accepted from the LLM

The tool signature must make this clear. For example:

```python
# Correct
def create_todo(user: User, title: str, ...) -> ToolResult:
    ...

# WRONG — user_id from LLM is never acceptable
def create_todo(user_id: int, title: str, ...) -> ToolResult:
    ...
```

### Ownership

Every Todo read or write operation must enforce that the requested Todo belongs to the authenticated user. No exceptions.

```python
# Listing
Todo.objects.filter(user=user)

# Fetching a specific Todo by ID
Todo.objects.get(id=todo_id, user=user)
```

If the `user=user` condition is not present, the lookup is incorrect.

### Input Validation

Tools must validate their arguments before executing any database operation. This includes:

- Checking that required fields are present and non-empty.
- Checking that field types are correct (e.g., `due_date` is a valid date string).
- Checking that values are within acceptable bounds (e.g., `tag_code` refers to an existing `Tag`).

Validation failures must return a structured error result — they must not raise unhandled exceptions to the agent.

### Limited Responsibility

Each tool does exactly one thing. A tool that creates a Todo does not also list Todos. A tool that marks a Todo as completed does not simultaneously delete it. Side effects that are not explicitly documented for a tool must not occur.

### Structured Results

Every tool returns a result in the same predictable format. The agent must be able to determine from the result whether the operation succeeded, and if it failed, why. See [Section 11 — Tool Result Format](#11-tool-result-format) for the defined structure.

### No Arbitrary SQL

Tools must never accept SQL strings, ORM filter expressions constructed from user input, or any mechanism that allows the LLM to influence the query beyond the tool's defined parameters.

### No Hidden Side Effects

A `delete_todo` tool must only delete the target Todo. A `complete_todo` tool must only set `is_completed = True`. Tools must not trigger unrelated operations.

---

## 3. Initial Tool Set

The following six tools make up the initial agent capability. These are the only tools the agent is permitted to call in the first implementation phase.

| # | Tool Name | Operation |
|---|-----------|-----------|
| 1 | `create_todo` | Create a new Todo for the authenticated user |
| 2 | `list_todos` | List/search the authenticated user's Todos |
| 3 | `get_todo` | Retrieve a single Todo by ID or title match |
| 4 | `update_todo` | Update fields on an existing Todo |
| 5 | `complete_todo` | Mark a specific Todo as completed |
| 6 | `delete_todo` | Permanently delete a specific Todo |

No additional tools should be introduced until the existing tool set has been implemented and tested.

---

## 4. Tool Specification Format

Each tool below is documented using a consistent structure:

- **Purpose** — what the tool does
- **When to use / not use** — guidance for the agent
- **Arguments** — input contract
- **Validation** — rules checked before ORM calls
- **Authentication & Ownership** — access control requirements
- **Database Operation** — what ORM call is made
- **Success Result** — what is returned on success
- **Failure Results** — possible error codes and conditions
- **Edge Cases** — non-obvious behavior
- **Example** — agent invocation context

---

## 5. `create_todo`

### Purpose

Creates a new Todo record for the authenticated user. The `user` field on the new `Todo` is set directly from the authenticated user — it is not an LLM argument.

### When the Agent Should Use It

When the user explicitly asks to create, add, or record a new task.

Examples:
- *"Create a task called Learn Django."*
- *"Add a new todo: prepare for interview."*
- *"Remind me to call the doctor on Friday."*

### When the Agent Should NOT Use It

- When the user is asking to view or find Todos — use `list_todos` or `get_todo`.
- When the user is updating an existing Todo — use `update_todo`.
- When the user's intent is ambiguous and could be either a new Todo or an update — ask for clarification first.

### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `user` | `User` | ✅ Yes | Authenticated Django user. Must come from `request.user`. **Never an LLM argument.** |
| `title` | `str` | ✅ Yes | The title of the Todo. Maps to `Todo.title` (max 255 characters). |
| `description` | `str` | ❌ Optional | Additional detail about the task. Maps to `Todo.description`. Defaults to `""`. |
| `due_date` | `str` (ISO 8601 date) | ❌ Optional | Target completion date. Maps to `Todo.due_date`. Format: `YYYY-MM-DD`. |
| `tag_code` | `int` | ❌ Optional | The `tag_code` of an existing `Tag`. See Tag Note below. |

### Tag Note — Known Implementation Decision Required

The existing `TodoSerializer` has an inconsistency that must be resolved before coding this tool:

- In `TodoSerializer.create()`, the tag is looked up using `Tag.objects.get(id=tag_id)` — that is, by the `Tag` primary key.
- In `TodoSerializer.update()`, the tag is looked up using `Tag.objects.get(tag_code=tag_id)` — that is, by the `tag_code` field.

These two methods use different lookup fields for what appears to be the same input value.

**For the AI tool, the recommended approach is to use `tag_code` consistently** (since `tag_code` is the natural user-facing identifier), but this requires using the `update()` lookup logic (`tag_code`) rather than the `create()` lookup logic (`id`). This is an implementation decision that must be made explicitly before coding the tool, and the existing serializer may need minor correction.

Until this is resolved:
- The `create_todo` tool should accept an optional `tag_code` integer.
- The tool documentation should note that the tag lookup approach must be confirmed at implementation time.

**The LLM should not be expected to know tag codes.** In practice, the agent will need to present the user's available tags in human-readable form and resolve the `tag_code` internally before calling the tool.

### Validation Rules

- `title` must be present and non-empty after stripping whitespace.
- `title` must not exceed 255 characters.
- If `due_date` is provided, it must be a valid ISO 8601 date string (`YYYY-MM-DD`).
- If `due_date` is in the past, the tool should accept it (valid use case: logging overdue tasks) but the agent may optionally warn the user.
- If `tag_code` is provided, it must correspond to an existing `Tag` record. If not found, return `VALIDATION_ERROR`.

### Authentication & Ownership

The `user` argument is the authenticated user. The new `Todo` is created with `user=user`. No ownership check is needed beyond this — creation implicitly assigns ownership.

### Database Operation

```python
# Conceptual — not final implementation
Todo.objects.create(
    user=user,
    title=title,
    description=description or "",
    due_date=due_date or None,
    tag=resolved_tag or None,
)
```

### Success Result

```json
{
  "success": true,
  "data": {
    "id": 42,
    "title": "Learn Django",
    "description": "",
    "is_completed": false,
    "is_archived": false,
    "due_date": "2026-09-08",
    "tag": null,
    "created_at": "2026-09-07T12:00:00Z"
  },
  "error": null
}
```

### Failure Results

| Error Code | Condition |
|------------|-----------|
| `VALIDATION_ERROR` | `title` is missing or empty |
| `VALIDATION_ERROR` | `title` exceeds 255 characters |
| `VALIDATION_ERROR` | `due_date` is not a valid date string |
| `VALIDATION_ERROR` | `tag_code` does not match any existing `Tag` |
| `TOOL_ERROR` | Unexpected database or runtime error |

### Edge Cases

- If the user says *"Create a task called 'done'"*, the tool should create it — do not interpret the word "done" as meaning `is_completed = true`. The agent should not set `is_completed` on creation.
- `is_completed` and `is_archived` should always default to `false` on creation. These must not be LLM arguments for `create_todo`.
- If `due_date` resolves to "tomorrow" or "Friday", the agent must resolve the relative date to an absolute `YYYY-MM-DD` value before calling the tool. The tool expects an absolute date, not a relative expression.

### Example Agent Invocation

**User request:** *"Create a task called Learn Django with a deadline tomorrow."*

```
Agent resolves "tomorrow" → "2026-09-08"
Agent calls: create_todo(user=request.user, title="Learn Django", due_date="2026-09-08")
Tool creates the Todo and returns success result.
Agent responds: "Done! I've created 'Learn Django' with a deadline of September 8th."
```

---

## 6. `list_todos`

### Purpose

Retrieves the authenticated user's Todos, with optional filtering and sorting. The query is always scoped to the authenticated user — the tool cannot return another user's Todos under any circumstances.

### When the Agent Should Use It

When the user wants to browse, find, or search their Todos.

Examples:
- *"Show me my incomplete tasks."*
- *"What tasks are due this week?"*
- *"Find my tasks tagged as 'work'."*
- *"List everything I've archived."*

Also used as a preliminary lookup step before a write operation when a Todo title is ambiguous.

### When the Agent Should NOT Use It

- When the user has provided a specific Todo ID — use `get_todo` instead.
- When the user is clearly creating a new Todo — use `create_todo`.

### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `user` | `User` | ✅ Yes | Authenticated Django user. **Never an LLM argument.** |
| `search` | `str` | ❌ Optional | Case-insensitive substring match on `title`. Maps to `title__icontains`. |
| `is_completed` | `bool` | ❌ Optional | Filter by completion status. |
| `is_archived` | `bool` | ❌ Optional | Filter by archive status. Defaults to `False` if not specified (see Edge Cases). |
| `tag_code` | `int` | ❌ Optional | Filter by tag. Maps to `tag__tag_code`. |
| `due_date` | `str` (ISO 8601) | ❌ Optional | Filter for Todos with this exact due date. |
| `sort_order` | `str` | ❌ Optional | `"latest"` (default) or `"oldest"`. Maps to `"-created_at"` / `"created_at"`. |
| `limit` | `int` | ❌ Optional | Maximum number of results to return. Recommended default: `20`. |

### Pagination

The existing `TodoListView` supports full pagination via `page` and `pagination_batch_size` parameters. For the AI tool, exposing raw pagination parameters to the LLM adds unnecessary complexity — the LLM cannot meaningfully paginate through results.

**Recommended approach:** The tool should accept a `limit` parameter and return up to that many results. If the total result count exceeds `limit`, the tool should include the count in the result so the agent can inform the user that there are more results. The agent can then refine the request (e.g., ask the user to narrow their search) rather than paginating blindly.

### Validation Rules

- If `due_date` is provided, it must be a valid `YYYY-MM-DD` date string.
- `sort_order`, if provided, must be `"latest"` or `"oldest"`.
- `limit`, if provided, must be a positive integer. A sensible maximum (e.g., 50) may be enforced by the tool.

### Authentication & Ownership

All queries are scoped with `user=user` as the first filter. This is non-negotiable.

```python
todos = Todo.objects.filter(user=user)
```

All subsequent filters are applied on top of this base queryset.

### Database Operation

```python
# Conceptual — not final implementation
todos = Todo.objects.filter(user=user)

if search:
    todos = todos.filter(title__icontains=search)
if is_completed is not None:
    todos = todos.filter(is_completed=is_completed)
if is_archived is not None:
    todos = todos.filter(is_archived=is_archived)
if tag_code:
    todos = todos.filter(tag__tag_code=tag_code)
if due_date:
    todos = todos.filter(due_date=due_date)

todos = todos.order_by("-created_at" if sort_order != "oldest" else "created_at")
todos = todos[:limit]
```

### Success Result

```json
{
  "success": true,
  "data": {
    "total_count": 12,
    "returned_count": 5,
    "limit": 5,
    "results": [
      {
        "id": 42,
        "title": "Learn Django",
        "description": "",
        "is_completed": false,
        "is_archived": false,
        "due_date": "2026-09-08",
        "tag": "work",
        "created_at": "2026-09-07T12:00:00Z"
      }
    ]
  },
  "error": null
}
```

### Failure Results

| Error Code | Condition |
|------------|-----------|
| `VALIDATION_ERROR` | `due_date` is not a valid date string |
| `VALIDATION_ERROR` | `sort_order` is not `"latest"` or `"oldest"` |
| `TOOL_ERROR` | Unexpected database or runtime error |

### Edge Cases

- **No results is not a failure.** If the query returns zero Todos, the tool should return `success: true` with an empty `results` array. The agent should inform the user that no matching tasks were found.
- **Archived Todos.** In the existing `TodoListView`, if `is_archived` is not specified, all Todos (archived and non-archived) are returned. For the agent, it may be more natural to default to `is_archived=False` (active tasks only) unless the user explicitly asks for archived tasks. This default behavior should be a deliberate implementation decision.
- The tool must never return Todos belonging to another user, even if the `search` term would match them.

---

## 7. `get_todo`

### Purpose

Retrieves a single specific Todo belonging to the authenticated user. This tool is used either when the user provides a specific Todo ID, or as a preliminary lookup step when the agent needs to confirm a target Todo before a destructive or ambiguous operation.

### When the Agent Should Use It

- When the user references a specific Todo by name or ID.
- Before calling `update_todo`, `complete_todo`, or `delete_todo` when the target Todo has not been confirmed.
- When the agent needs to verify that a Todo exists before acting on it.

### When the Agent Should NOT Use It

- When the user wants a list of multiple Todos — use `list_todos`.
- When the agent already has a confirmed `todo_id` from the current conversation — the agent may call `update_todo` or `complete_todo` directly.

### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `user` | `User` | ✅ Yes | Authenticated Django user. **Never an LLM argument.** |
| `todo_id` | `int` | ❌ Optional* | The primary key of the Todo. |
| `search` | `str` | ❌ Optional* | Text to match against `title` (case-insensitive). |

*At least one of `todo_id` or `search` must be provided.

### Handling Ambiguity

This is the most important behavioral rule for `get_todo`.

When `search` is used:
1. The tool queries `Todo.objects.filter(user=user, title__icontains=search)`.
2. **If exactly one Todo matches** — return it.
3. **If zero Todos match** — return `TODO_NOT_FOUND`.
4. **If multiple Todos match** — return `AMBIGUOUS_TODO` with the list of matching Todos so the agent can present the choices to the user and ask for clarification.

The agent must **never randomly select** from multiple matches. If the result is `AMBIGUOUS_TODO`, the agent must stop and ask the user to be more specific before proceeding.

### Authentication & Ownership

```python
# By ID
Todo.objects.get(id=todo_id, user=user)

# By title match
Todo.objects.filter(user=user, title__icontains=search)
```

The `user=user` condition is always present.

### Database Operation

```python
# Conceptual — not final implementation

# If todo_id provided
try:
    todo = Todo.objects.get(id=todo_id, user=user)
    return single result
except Todo.DoesNotExist:
    return TODO_NOT_FOUND

# If search provided
matches = Todo.objects.filter(user=user, title__icontains=search)
if matches.count() == 0:
    return TODO_NOT_FOUND
elif matches.count() == 1:
    return single result
else:
    return AMBIGUOUS_TODO with list of matches
```

### Success Result

```json
{
  "success": true,
  "data": {
    "id": 42,
    "title": "Learn Django",
    "description": "Study Django REST Framework",
    "is_completed": false,
    "is_archived": false,
    "due_date": "2026-09-08",
    "tag": "work",
    "created_at": "2026-09-07T12:00:00Z"
  },
  "error": null
}
```

### Failure Results

| Error Code | Condition |
|------------|-----------|
| `VALIDATION_ERROR` | Neither `todo_id` nor `search` was provided |
| `TODO_NOT_FOUND` | No Todo matching the criteria was found for this user |
| `AMBIGUOUS_TODO` | Multiple Todos matched the `search` term — agent must ask for clarification |
| `TOOL_ERROR` | Unexpected database or runtime error |

#### `AMBIGUOUS_TODO` Result Shape

```json
{
  "success": false,
  "data": {
    "matches": [
      { "id": 15, "title": "Prepare for interview — Google", "due_date": "2026-09-10" },
      { "id": 23, "title": "Prepare for interview — Amazon", "due_date": "2026-09-12" }
    ]
  },
  "error": {
    "code": "AMBIGUOUS_TODO",
    "message": "Multiple tasks matched 'interview'. Please clarify which one you mean."
  }
}
```

### Edge Cases

- If the user provides a `todo_id` that belongs to a different user, `Todo.objects.get(id=todo_id, user=user)` will raise `DoesNotExist`, which is returned as `TODO_NOT_FOUND`. The tool must not reveal whether the Todo exists but belongs to someone else.
- Exact title matching is not required — `icontains` is intentional. If this causes too many false matches in practice, a stricter match strategy can be added at implementation time.

---

## 8. `update_todo`

### Purpose

Updates one or more fields on an existing Todo belonging to the authenticated user. The target Todo must be identified before any update is applied.

### When the Agent Should Use It

When the user wants to change a property of an existing Todo that is not simply marking it as completed.

Examples:
- *"Change the title of my Learn Django task to Master Django."*
- *"Move my interview task to next Friday."*
- *"Add a description to my grocery task."*
- *"Archive my completed project."*

### When the Agent Should NOT Use It

- When the only change is marking the Todo as completed — use `complete_todo` instead.
- When the target Todo has not been identified — use `get_todo` or `list_todos` first.

### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `user` | `User` | ✅ Yes | Authenticated Django user. **Never an LLM argument.** |
| `todo_id` | `int` | ✅ Yes | The primary key of the Todo to update. Must be confirmed before calling. |
| `title` | `str` | ❌ Optional | New title. Max 255 characters. |
| `description` | `str` | ❌ Optional | New description text. |
| `due_date` | `str` or `null` | ❌ Optional | New due date (`YYYY-MM-DD`). Pass `null` to clear the date. |
| `is_completed` | `bool` | ❌ Optional | Completion status. Prefer `complete_todo` for this. |
| `is_archived` | `bool` | ❌ Optional | Archive status. |
| `tag_code` | `int` or `null` | ❌ Optional | New tag by `tag_code`. Pass `null` to remove the tag. |

At least one optional field must be provided. An update call with no fields to change is a `VALIDATION_ERROR`.

### Validation Rules

- `todo_id` must be a positive integer.
- `title`, if provided, must be non-empty and no longer than 255 characters.
- `due_date`, if provided (and not `null`), must be a valid `YYYY-MM-DD` date string.
- `tag_code`, if provided (and not `null`), must match an existing `Tag.tag_code`.
- At least one optional field must differ from its current value (or at minimum be specified).

### Authentication & Ownership

The Todo is always retrieved with both `id` and `user` conditions:

```python
todo = Todo.objects.get(id=todo_id, user=user)
```

If the Todo does not exist for this user, the tool returns `TODO_NOT_FOUND`. The tool must never update a Todo owned by another user.

### Handling Ambiguous Targets

`update_todo` requires a confirmed `todo_id`. The agent must not pass a guessed or ambiguous ID. The standard pattern when the user's target is unclear:

1. Call `get_todo(user=user, search="<user's description>")`.
2. If the result is `AMBIGUOUS_TODO`, present the choices to the user and ask for clarification.
3. Once the user identifies the correct Todo, call `update_todo` with the confirmed `todo_id`.

### Database Operation

```python
# Conceptual — not final implementation
todo = Todo.objects.get(id=todo_id, user=user)

# Apply only the fields that were provided
if title is not None:
    todo.title = title
if description is not None:
    todo.description = description
if due_date is EXPLICITLY_NULL:
    todo.due_date = None
elif due_date is not None:
    todo.due_date = due_date
# ... etc.

todo.save()
```

The existing `TodoSerializer` with `partial=True` (used in `TodoUpdateView`) follows this same partial-update pattern and can be reused by the tool at implementation time.

### Success Result

```json
{
  "success": true,
  "data": {
    "id": 42,
    "title": "Master Django",
    "description": "",
    "is_completed": false,
    "is_archived": false,
    "due_date": "2026-09-12",
    "tag": "work",
    "created_at": "2026-09-07T12:00:00Z"
  },
  "error": null
}
```

### Failure Results

| Error Code | Condition |
|------------|-----------|
| `VALIDATION_ERROR` | No fields provided to update |
| `VALIDATION_ERROR` | `title` is empty or exceeds 255 characters |
| `VALIDATION_ERROR` | `due_date` is not a valid date string |
| `VALIDATION_ERROR` | `tag_code` does not match any existing `Tag` |
| `TODO_NOT_FOUND` | No Todo with this `todo_id` exists for this user |
| `TOOL_ERROR` | Unexpected database or runtime error |

### Edge Cases

- Relative dates (e.g., "Friday", "next week") must be resolved to `YYYY-MM-DD` by the agent before calling the tool.
- Setting `due_date = null` is a valid operation (removing a deadline). The tool must distinguish between "not provided" and "explicitly set to null."

---

## 9. `complete_todo`

### Purpose

Marks a specific Todo as completed by setting `is_completed = True`. This is a focused, single-purpose tool for the most common write operation in a Todo application.

### Why a Dedicated Tool Instead of `update_todo`

While `update_todo` could technically set `is_completed = True`, having a dedicated tool for this operation:

- Makes the agent's intent explicit and auditable.
- Reduces the risk of the LLM constructing a complex update payload for a simple completion.
- Gives the tool a clear, verifiable contract: it does one thing.
- Allows future behavior (e.g., recording a `completed_at` timestamp) to be added without changing `update_todo`.

### When the Agent Should Use It

When the user clearly wants to mark a task as done/completed/finished.

Examples:
- *"Mark my Learn Django task as done."*
- *"I've finished the interview preparation."*
- *"Complete my grocery task."*

### When the Agent Should NOT Use It

- When the user wants to undo a completion (set `is_completed` back to `False`) — use `update_todo`.
- When the target Todo has not been confirmed — use `get_todo` first.

### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `user` | `User` | ✅ Yes | Authenticated Django user. **Never an LLM argument.** |
| `todo_id` | `int` | ✅ Yes | The primary key of the Todo to mark as completed. Must be confirmed. |

### Validation Rules

- `todo_id` must be a positive integer.
- The tool should check whether the Todo is already completed and return an informative result if so (not an error, but a note in the response).

### Authentication & Ownership

```python
todo = Todo.objects.get(id=todo_id, user=user)
```

Same pattern as all other tools. The `user=user` condition is always present.

### Database Operation

```python
# Conceptual — not final implementation
todo = Todo.objects.get(id=todo_id, user=user)
todo.is_completed = True
todo.save()
```

### Success Result

```json
{
  "success": true,
  "data": {
    "id": 42,
    "title": "Learn Django",
    "is_completed": true
  },
  "error": null
}
```

### Failure Results

| Error Code | Condition |
|------------|-----------|
| `TODO_NOT_FOUND` | No Todo with this `todo_id` exists for this user |
| `TOOL_ERROR` | Unexpected database or runtime error |

### Edge Cases

- If the Todo is already marked `is_completed = True`, the tool should still succeed (idempotent behavior) and the agent can note: *"That task was already marked as completed."*
- Completing a Todo does not automatically archive it. `is_archived` is a separate field and must not be modified by this tool.

---

## 10. `delete_todo`

### Purpose

Permanently deletes a specific Todo belonging to the authenticated user.

> **Warning:** This is a hard delete. The existing `TodoDeleteView` calls `todo.delete()`, which removes the database row permanently. There is no recycle bin, no soft-delete flag, and no undo mechanism in the current application.

### When the Agent Should Use It

Only after the target Todo has been positively identified and the user's intent to delete is clear.

Examples (after target confirmation):
- *"Delete my grocery task."*
- *"Remove the Learn Django todo."*
- *"Get rid of that old interview task."*

### When the Agent Should NOT Use It

- When the target Todo has not been confirmed — use `get_todo` first.
- When the user's intent is ambiguous — ask for clarification before calling this tool.
- When the agent matched multiple Todos for the user's description — present the choices and wait for the user to specify.

### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `user` | `User` | ✅ Yes | Authenticated Django user. **Never an LLM argument.** |
| `todo_id` | `int` | ✅ Yes | The primary key of the Todo to delete. Must be confirmed before calling. |

### Validation Rules

- `todo_id` must be a positive integer.

### Authentication & Ownership

```python
todo = Todo.objects.get(id=todo_id, user=user)
todo.delete()
```

If the Todo does not belong to the authenticated user, `get()` raises `DoesNotExist` — returned as `TODO_NOT_FOUND`. The operation never proceeds.

### Database Operation

This is a permanent deletion. The existing `TodoDeleteView` performs:

```python
todo.delete()
```

No cascade effects are expected given the current schema. The `Tag` FK uses `SET_NULL`, so deleting a Todo does not affect the referenced `Tag`.

### Success Result

```json
{
  "success": true,
  "data": {
    "id": 42,
    "title": "Learn Django",
    "deleted": true
  },
  "error": null
}
```

The deleted Todo's title is returned so the agent can confirm to the user which task was removed.

### Failure Results

| Error Code | Condition |
|------------|-----------|
| `TODO_NOT_FOUND` | No Todo with this `todo_id` exists for this user |
| `TOOL_ERROR` | Unexpected database or runtime error |

### Edge Cases

- **No soft delete.** Do not tell users the task was "moved to trash" or "archived." It is gone.
- **Pre-deletion confirmation flow.** Because deletion is irreversible, the recommended agent behavior is:
  1. Use `get_todo` to identify the target.
  2. Present the Todo title to the user and confirm: *"I found 'Learn Django'. Are you sure you want to delete it?"*
  3. Only after explicit user confirmation, call `delete_todo`.
  This confirmation step is agent-level behavior, not enforced by the tool itself. The tool deletes immediately when called.
- **Ambiguous target.** The agent must never guess. If `get_todo` returns `AMBIGUOUS_TODO`, the agent must ask the user to clarify before proceeding to deletion.

---

## 11. Tool Result Format

All tools return results in a consistent structure. This consistency allows the agent to handle responses uniformly.

### Success Shape

```json
{
  "success": true,
  "data": { },
  "error": null
}
```

The `data` field contains the result payload relevant to the operation. Its specific shape varies per tool (documented in each tool's section above).

### Failure Shape

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description of what went wrong."
  }
}
```

For `AMBIGUOUS_TODO`, `data` may contain the list of matching Todos even on failure:

```json
{
  "success": false,
  "data": {
    "matches": [
      { "id": 15, "title": "Interview — Google", "due_date": "2026-09-10" },
      { "id": 23, "title": "Interview — Amazon", "due_date": "2026-09-12" }
    ]
  },
  "error": {
    "code": "AMBIGUOUS_TODO",
    "message": "Multiple tasks matched. Please specify which one."
  }
}
```

### Error Codes

| Code | Meaning |
|------|---------|
| `VALIDATION_ERROR` | One or more arguments failed validation. No database operation was attempted. |
| `TODO_NOT_FOUND` | The requested Todo does not exist for the authenticated user. |
| `OWNERSHIP_ERROR` | An explicit ownership violation was detected (distinct from not found). Reserved for future use. |
| `AMBIGUOUS_TODO` | The search term matched multiple Todos. The agent must ask for clarification. |
| `TOOL_ERROR` | An unexpected error occurred during execution (database error, runtime exception, etc.). |

### Rules for Error Messages

- Error messages must be informative but must not expose Django exception details, stack traces, SQL, or internal field names.
- `TOOL_ERROR` messages shown to the user should be generic (e.g., *"Something went wrong. Please try again."*). Full details should be logged server-side.

---

## 12. Tool Selection Guidelines

The agent uses user intent to select the appropriate tool. The following examples illustrate the expected decision process.

```
"Create a task to study Django tomorrow"
    → create_todo(title="Study Django", due_date="2026-09-08")

"Show my incomplete tasks"
    → list_todos(is_completed=False)

"What tasks are due today?"
    → list_todos(due_date="2026-09-07")

"Mark Learn Django as completed"
    → get_todo(search="Learn Django")       [confirm exactly one match]
    → complete_todo(todo_id=<confirmed_id>)

"Move my interview task to Friday"
    → get_todo(search="interview")          [may return AMBIGUOUS_TODO]
    → [if ambiguous, ask user to clarify]
    → update_todo(todo_id=<confirmed_id>, due_date="2026-09-12")

"Delete my old grocery task"
    → get_todo(search="grocery")            [confirm exactly one match]
    → [present title to user, ask for confirmation]
    → delete_todo(todo_id=<confirmed_id>)

"Update my task"
    → [ambiguous — no title, no field specified]
    → Agent asks: "Which task, and what would you like to change?"
    → [no tool called yet]
```

### Read Before Write

When a write operation targets a Todo the agent has not yet confirmed in the current conversation, the agent should:

1. Call `get_todo` or `list_todos` to identify the target.
2. Handle `AMBIGUOUS_TODO` by asking the user to clarify.
3. Only after a single confirmed Todo is identified, call the write tool.

This pattern prevents the agent from accidentally modifying or deleting the wrong Todo.

---

## 13. Tool Safety Rules

These rules apply to every tool without exception.

1. **Never trust user identity from the LLM.** The `user` argument must always come from `request.user`.
2. **Never accept `user_id` from the LLM.** There is no `user_id` parameter in any tool.
3. **Never access another user's Todo.** Every ORM query includes `user=user`.
4. **Never execute arbitrary SQL.** Tools use the Django ORM exclusively.
5. **Never bypass serializer or model validation where it is applicable.** The existing `TodoSerializer` validation rules (e.g., field max lengths, required fields) should be respected.
6. **Never claim success unless the operation actually succeeded.** A tool that fails must return `success: false`.
7. **Never silently choose between multiple matching Todos.** `AMBIGUOUS_TODO` must be surfaced to the agent, which must surface it to the user.
8. **Treat delete as destructive and irreversible.** The agent should apply a confirmation step before calling `delete_todo`.
9. **Validate all arguments.** No tool should reach the ORM layer with invalid inputs.
10. **Keep tool scope narrow.** Tools do not perform operations beyond what is explicitly documented for them.

---

## 14. Existing Backend Integration

### Current State

The existing Django backend does not have a service layer. Business logic is written directly in the view methods:

- [`TodoCreateView`](../../todo/views.py) — `POST /api/create-todo/` — creates via `TodoSerializer.save(user=request.user)`
- [`TodoListView`](../../todo/views.py) — `GET /api/get-todos/` — filters `Todo.objects.filter(user=request.user)` with multiple query param filters
- [`TodoUpdateView`](../../todo/views.py) — `PATCH /api/update-todo/` — looks up `Todo.objects.get(id=todo_id, user=request.user)`, applies partial serializer update
- [`TodoDeleteView`](../../todo/views.py) — `DELETE /api/delete-todo/` — looks up `Todo.objects.get(id=todo_id, user=request.user)`, calls `.delete()`

### How the Tools Will Integrate

The tools will use the Django ORM and `TodoSerializer` directly — mirroring what the existing views already do. This means:

- No new models or migrations are needed for the initial tool set.
- The existing `Todo`, `Tag`, and `TodoSerializer` from the `todo` app are the building blocks.
- The tools will live in a new module (e.g., `ai/tools.py` or `todo/ai_tools.py`) that is separate from the existing view layer.

### No Service Layer Assumption

This documentation does not assume the existence of a service layer. If code sharing between the tools and existing views becomes a problem (e.g., identical ORM logic duplicated), extracting a shared service module is an explicit implementation decision for a later phase — not something to design around now.

### Relevant Existing Code

| File | Relevance |
|------|-----------|
| [`todo/models.py`](../../todo/models.py) | `Todo` and `Tag` model definitions |
| [`todo/serializers.py`](../../todo/serializers.py) | `TodoSerializer` — handles field validation, tag resolution, create, partial update |
| [`todo/views.py`](../../todo/views.py) | Reference implementations for ORM query patterns |
| [`accounts/models.py`](../../accounts/models.py) | `User` model — email-based, no username |
| [`todo_project/settings.py`](../../todo_project/settings.py) | `AUTH_USER_MODEL = 'accounts.User'`, Token auth config |

---

## 15. Example End-to-End Tool Usage

### Example 1 — Create

**User:** *"Create a task called Learn Django with a deadline tomorrow."*

```
User
 "Create a task called Learn Django with a deadline tomorrow."
 ↓
Agent
 Resolves "tomorrow" → "2026-09-08"
 Selects tool: create_todo
 ↓
create_todo(
    user=request.user,
    title="Learn Django",
    due_date="2026-09-08"
)
 ↓
Django ORM
 Todo.objects.create(
     user=user,
     title="Learn Django",
     due_date=date(2026, 9, 8)
 )
 ↓
Result
 { "success": true, "data": { "id": 42, "title": "Learn Django", ... } }
 ↓
Agent response
 "Done! I've created 'Learn Django' with a deadline of September 8th."
```

---

### Example 2 — Read

**User:** *"Show me my incomplete tasks."*

```
User
 "Show me my incomplete tasks."
 ↓
Agent
 Selects tool: list_todos
 ↓
list_todos(
    user=request.user,
    is_completed=False
)
 ↓
Django ORM
 Todo.objects.filter(user=user, is_completed=False).order_by("-created_at")[:20]
 ↓
Result
 { "success": true, "data": { "total_count": 3, "results": [...] } }
 ↓
Agent response
 "You have 3 incomplete tasks:
  • Learn Django (due Sep 8)
  • Buy groceries
  • Prepare for interview (due Sep 10)"
```

---

### Example 3 — Update

**User:** *"Move my Learn Django task to Friday."*

```
User
 "Move my Learn Django task to Friday."
 ↓
Agent
 Resolves "Friday" → "2026-09-12"
 Needs to confirm the target Todo first.
 Selects tool: get_todo
 ↓
get_todo(
    user=request.user,
    search="Learn Django"
)
 ↓
Django ORM
 Todo.objects.filter(user=user, title__icontains="Learn Django")
 → 1 result: { "id": 42, "title": "Learn Django", ... }
 ↓
Agent confirms single match → proceeds to update
 ↓
update_todo(
    user=request.user,
    todo_id=42,
    due_date="2026-09-12"
)
 ↓
Django ORM
 todo = Todo.objects.get(id=42, user=user)
 todo.due_date = date(2026, 9, 12)
 todo.save()
 ↓
Result
 { "success": true, "data": { "id": 42, "title": "Learn Django", "due_date": "2026-09-12", ... } }
 ↓
Agent response
 "Done! I've moved 'Learn Django' to Friday, September 12th."
```

---

### Example 4 — Ambiguous Update

**User:** *"Update my interview task."*

```
User
 "Update my interview task."
 ↓
Agent
 The user has not specified what to change.
 Does not call any tool yet.
 ↓
Agent response
 "Which task would you like to update, and what change should I make?
  For example: rename it, change the due date, add a description?"
 ↓
User
 "Change the due date of my Google interview to next Monday."
 ↓
Agent
 Resolves "next Monday" → "2026-09-14"
 Calls: get_todo(user=request.user, search="Google interview")
 ↓
Django ORM
 Todo.objects.filter(user=user, title__icontains="Google interview")
 → 1 result: { "id": 15, "title": "Interview — Google", ... }
 ↓
Agent confirms single match.
 Calls: update_todo(user=request.user, todo_id=15, due_date="2026-09-14")
 ↓
Agent response
 "Done! I've moved 'Interview — Google' to Monday, September 14th."
```

---

### Example 5 — Delete

**User:** *"Delete my old grocery task."*

```
User
 "Delete my old grocery task."
 ↓
Agent
 Calls: get_todo(user=request.user, search="grocery")
 ↓
Django ORM
 Todo.objects.filter(user=user, title__icontains="grocery")
 → 1 result: { "id": 7, "title": "Buy groceries", "due_date": null }
 ↓
Agent presents match and confirms intent before deleting.
 ↓
Agent response
 "I found 'Buy groceries'. Are you sure you want to permanently delete it?
  This action cannot be undone."
 ↓
User
 "Yes, delete it."
 ↓
Agent calls: delete_todo(user=request.user, todo_id=7)
 ↓
Django ORM
 todo = Todo.objects.get(id=7, user=user)
 todo.delete()
 ↓
Result
 { "success": true, "data": { "id": 7, "title": "Buy groceries", "deleted": true } }
 ↓
Agent response
 "Done. 'Buy groceries' has been permanently deleted."
```

---

## 16. Implementation Status

> **These tools are currently design specifications only.**

None of the tools defined in this document have been implemented. No Python code, Django app, API endpoint, or database migration exists for the AI agent layer.

The next implementation phase will:

1. Create a new Django app or module to house the AI agent and tool functions.
2. Translate each tool specification in this document into a Python function with the defined signature, validation, ORM logic, and result format.
3. Create a new `POST /api/ai/chat/` endpoint backed by an `APIView` using the existing `IsAuthenticated` + `TokenAuthentication` setup.
4. Integrate the LLM (e.g., Google Gemini or OpenAI GPT) with the tool set using its native function-calling or tool-use API.
5. Resolve the outstanding implementation decision regarding `tag_id` vs `tag_code` in `TodoSerializer.create()`.

---

*See also: [`AI_AGENT.md`](./AI_AGENT.md) — High-level architecture and agent design.*
*See also: [`AI_AGENT_MEMORY.md`](./AI_AGENT_MEMORY.md) — Conversation context and memory design (planned).*
*See also: [`AI_AGENT_SECURITY.md`](./AI_AGENT_SECURITY.md) — Security considerations for the AI layer (planned).*
