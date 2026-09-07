# AI Agent — Todo Application

## 1. Purpose

This document describes the plan for introducing an AI agent capability into the existing Todo application. The goal is to let users interact with their Todos using natural language while the agent safely performs supported operations through a controlled set of tools.

### Traditional Todo CRUD

In the current application, users interact with Todos through explicit UI actions — clicking buttons, filling forms, selecting filters. Every operation maps directly to a specific REST API endpoint. The user must know what they want to do and how to do it within the interface.

### AI-Assisted Todo Interaction

With AI assistance, the user can express intent in plain language. Instead of navigating to a filter and selecting "incomplete," the user might type: *"Show me what I haven't finished yet."* The AI translates this intent into the appropriate operation.

### Agentic AI Behavior

An agentic system goes a step further. The agent does not just translate a single instruction — it can reason about what steps are needed, select the right tool, execute an operation, inspect the result, and respond meaningfully. If the user's request is ambiguous, the agent asks for clarification rather than guessing.

For this Todo project, the scope is intentionally small. The agent will be responsible only for interacting with the authenticated user's own Todos, using a defined set of tools. No external APIs, no background automation, no access beyond the user's own data.

---

## 2. Current Application Architecture

The existing backend is a Django REST API. It currently has no AI component. This section documents the architecture as it stands.

### Framework

- **Django 5.2.9** — web framework and ORM
- **Django REST Framework 3.16.1** — API layer

### Django Apps

**`accounts` app**

Handles all user-related functionality:
- Custom `User` model extending `AbstractUser`, with `email` as the `USERNAME_FIELD` (no `username` field)
- Custom `UserManager` with `create_user` and `create_superuser`
- A `theme` field on the user (`1` = light, `2` = dark)
- Views: `SignupView`, `LoginView`, `LogoutView`, `ResetPasswordView`, `UpdateThemeView`

**`todo` app**

Handles all Todo-related functionality:
- `Tag` model: `name` (CharField), `tag_code` (unique IntegerField)
- `Todo` model: `user` (FK to `AUTH_USER_MODEL`), `title`, `description`, `is_completed`, `is_archived`, `due_date`, `tag` (FK to `Tag`, nullable), `created_at`
- Views: `TodoCreateView`, `TodoListView`, `TodoUpdateView`, `TodoDeleteView`
- `TodoSerializer` handles both create and update, with custom `tag_id` write logic

### Authentication

- **DRF Token Authentication** (`rest_framework.authtoken`)
- Tokens are created or retrieved on login via `Token.objects.get_or_create(user=user)`
- Tokens are deleted on logout (`request.user.auth_token.delete()`)
- All protected endpoints require `Authorization: Token <token>` in the request header
- `djangorestframework_simplejwt` is installed in `requirements.txt` but is currently commented out and not in active use

### API Views

All views use DRF's `APIView` base class (class-based views). There is no `ViewSet`, `Router`, or `ModelViewSet` in use. There is no dedicated service or business logic layer — view methods interact directly with the ORM and serializers.

### URL Structure

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/signup/` | Register a new user |
| POST | `/api/login/` | Log in, receive token |
| POST | `/api/logout/` | Delete the current token |
| POST | `/api/reset-password/` | Change password |
| POST | `/api/update-theme/` | Update UI theme preference |
| POST | `/api/create-todo/` | Create a new Todo |
| GET | `/api/get-todos/` | List Todos (with filtering, search, sorting, pagination) |
| PATCH | `/api/update-todo/` | Update an existing Todo |
| DELETE | `/api/delete-todo/` | Delete a Todo |

### `TodoListView` Filtering Capabilities

`GET /api/get-todos/` supports the following query parameters:
- `search` — title text search (`icontains`)
- `is_completed` — filter by completion status (`true`/`false`)
- `is_archived` — filter by archive status (`true`/`false`)
- `tag_id` — filter by tag code
- `due_date` — filter by exact date
- `sort_order` — `1` (latest first, default) or `2` (oldest first)
- `page` and `pagination_batch_size` — pagination controls

### Database

- **SQLite** (`db.sqlite3`) — used for local development
- `psycopg2-binary` is listed in `requirements.txt`, suggesting PostgreSQL is intended for production (e.g., deployment on Render/Railway via `Procfile` with `gunicorn`)

### CORS

- `CORS_ALLOW_ALL_ORIGINS = True` is set, meaning any origin can call the API. This is typical for a development-stage portfolio project.

---

## 3. Proposed AI Agent

### What the Agent Will Be Responsible For

The AI agent will accept natural-language input from the authenticated user and use it to perform Todo operations on their behalf. Examples of intended capabilities (not yet implemented):

- *"Create a task to learn Django tomorrow."* — Creates a new Todo with a relevant title and due date.
- *"Show me my incomplete tasks."* — Lists Todos where `is_completed` is `false`.
- *"Mark my Django task as completed."* — Updates the matching Todo to set `is_completed = true`.
- *"Move my interview preparation task to Friday."* — Updates the `due_date` of the matching Todo.
- *"Delete this task."* — Asks which task if ambiguous; deletes the specified Todo.
- *"Archive everything I've already completed."* — Iterates completed Todos and sets `is_archived = true`.

### What the Agent Is NOT Responsible For

The agent will not:

- Handle user registration, login, or password management
- Manage tags (Tag creation/deletion is not a current user-facing API)
- Perform bulk operations outside of what individual tools support
- Access another user's Todos
- Operate without an authenticated user context
- Replace the existing REST API — the existing endpoints remain unchanged

---

## 4. High-Level AI Architecture

The proposed architecture keeps the AI layer inside the existing Django application. No new services, message queues, or infrastructure are introduced.

```
React Frontend
      |
      | (natural-language message + Token auth header)
      v
Django AI Endpoint  (new APIView, e.g. POST /api/ai/chat/)
      |
      | (validates token, resolves request.user)
      v
Authenticated User Context
      |
      | (user object passed explicitly into agent)
      v
AI Agent / LLM  (e.g. Google Gemini, OpenAI GPT)
      |
      | (decides which operation is needed)
      v
Tool Selection  (agent selects one of the defined Todo tools)
      |
      | (tool receives user + validated arguments)
      v
Todo Tools  (Python functions, one per supported operation)
      |
      | (tool uses Django ORM directly)
      v
Existing Todo Models / ORM  (Todo.objects.filter, .get, .create, etc.)
      |
      v
SQLite / Database
```

### Component Descriptions

| Component | Description |
|-----------|-------------|
| **React Frontend** | Sends the user's natural-language message to the new AI endpoint, authenticated with the existing token |
| **Django AI Endpoint** | A new `APIView` (e.g. `POST /api/ai/chat/`) that accepts a message, validates the token, and invokes the agent. Uses the same `IsAuthenticated` permission class as all other views |
| **Authenticated User Context** | `request.user` — the resolved Django `User` instance — is passed explicitly into the agent's execution context |
| **AI Agent / LLM** | A large language model (LLM) that receives the user's message and the list of available tools. It determines whether a tool is needed and which one to call |
| **Tool Selection** | The LLM selects the most appropriate tool for the user's intent, or asks a clarifying question if the intent is unclear |
| **Todo Tools** | A set of Python functions, each performing one specific Todo operation. Each tool receives `user` and validated arguments. Tools enforce ownership and validate inputs independently of the LLM |
| **Existing Django ORM** | Tools interact with `Todo.objects` directly — the same ORM used by the existing views. No bypass of Django's data layer |
| **Database** | The same SQLite (dev) or PostgreSQL (production) database already in use |

---

## 5. Agent Execution Flow

The following describes the expected flow from a user message to a final response.

1. **User sends a natural-language request.**
   The React frontend sends a `POST` request to `/api/ai/chat/` with the user's message and the existing `Authorization: Token <token>` header.

2. **Django authenticates the request.**
   DRF's `TokenAuthentication` validates the token and populates `request.user`. If the token is invalid or missing, the request is rejected with `401 Unauthorized` before the agent is invoked.

3. **The authenticated user is passed into the agent context.**
   The view retrieves `request.user` and passes it explicitly to the agent. The agent and all tools receive this user object — they do not independently resolve or accept a user identity.

4. **The agent understands the user's intent.**
   The LLM processes the message. It has access to the user's message and a description of available tools.

5. **The agent determines whether a tool is required.**
   - If the message clearly maps to a Todo operation, the agent selects a tool.
   - If the message is ambiguous, the agent asks the user a clarifying question before proceeding.
   - If the message is outside the agent's scope, the agent politely declines.

6. **The agent selects an appropriate Todo tool.**
   The agent calls the selected tool with the arguments it inferred from the user's message, plus the authenticated user object.

7. **The tool validates the request and user ownership.**
   The tool validates all inputs and enforces that the requested Todo belongs to the authenticated user (e.g., `Todo.objects.get(id=todo_id, user=user)`). The LLM is never given direct database access.

8. **The operation is executed.**
   The tool performs the Django ORM operation — create, read, update, or delete.

9. **The result is returned to the agent.**
   The tool returns a structured result (success data or an error description) back to the agent.

10. **The agent produces a natural-language response.**
    The agent translates the tool result into a clear, user-facing reply and returns it to the frontend.

> **Important:** The LLM itself must not have unrestricted database access. All database interaction happens through the tool layer. The LLM can only trigger operations that are explicitly implemented as tools.

---

## 6. Authentication and User Context

### Core Rule

> **The AI agent must always operate on behalf of the authenticated user.**

`request.user` — resolved by DRF's `TokenAuthentication` in the Django view — must be passed explicitly through the agent and into each tool call. The agent and tools do not accept an arbitrary user ID from the LLM.

### Why This Matters

The existing `Todo` model enforces per-user data isolation via the `user` ForeignKey:

```python
# todo/models.py
class Todo(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="todos"
    )
```

The existing views consistently filter by `request.user`:

```python
# TodoListView — user-scoped queryset
todos = Todo.objects.filter(user=request.user)

# TodoUpdateView — ownership enforced on lookup
todo = Todo.objects.get(id=todo_id, user=request.user)

# TodoDeleteView — ownership enforced on lookup
todo = Todo.objects.get(id=todo_id, user=request.user)
```

The AI tools must follow the same pattern. Accepting a `user_id` from the LLM instead of from `request.user` would allow a compromised or misbehaving LLM to operate on another user's data — a critical security flaw.

### What the Agent Must Never Do

- Accept a user identity provided by the LLM output
- Allow the LLM to specify a `user_id` as a tool argument
- Skip user ownership checks on Todo lookups
- Return another user's Todo data in any response

---

## 7. Todo Operations the Agent May Eventually Support

The following capabilities are proposed for the initial version. Detailed tool schemas (argument definitions, return types, error codes) will be documented separately in `AI_AGENT_TOOLS.md`.

| Capability | Description |
|------------|-------------|
| **Create Todo** | Creates a new Todo for the authenticated user. The agent infers `title`, optional `description`, optional `due_date`, and optional `tag` from the user's message |
| **List / Search Todos** | Retrieves the user's Todos. Supports filtering by completion status, archive status, due date, tag, and text search — mirroring the existing `TodoListView` query parameters |
| **Get a Specific Todo** | Retrieves a single Todo by ID or by matching title. Useful when the agent needs to confirm the exact record before performing a write operation |
| **Update Todo** | Updates one or more fields on an existing Todo — title, description, due date, tag, or archived status. The agent must confirm the target Todo before applying changes if the match is ambiguous |
| **Complete Todo** | A focused update that sets `is_completed = true` on a specific Todo. Treated as a separate tool because it is the most common single-field update |
| **Delete Todo** | Permanently deletes a specific Todo belonging to the authenticated user. The agent should confirm the target Todo before deletion |

---

## 8. Tool-Based Design

### Why Tools Instead of Direct Database Access

Allowing an LLM to write arbitrary database queries would be dangerous and unpredictable. Instead, each supported operation is encapsulated in a dedicated Python tool function. The LLM can only call operations that have been explicitly implemented.

This approach:
- Limits the blast radius of any LLM error or misinterpretation
- Enforces per-user data isolation at the tool level, independent of the LLM
- Makes the agent's capabilities explicit and auditable
- Allows each tool to validate inputs before any database operation occurs

### Tool Contract

Each tool must:

- **Receive the authenticated user explicitly** — as a positional or keyword argument, not inferred from LLM output
- **Validate inputs** — check types, required fields, and acceptable values before touching the database
- **Enforce Todo ownership** — always filter or look up Todos using `user=user` alongside any ID or title match
- **Perform only the operation it is designed for** — no side effects beyond its documented purpose
- **Return structured results** — a consistent format the agent can interpret (e.g. a success payload or a typed error)
- **Handle errors safely** — catch `Todo.DoesNotExist`, validation failures, and unexpected exceptions; return useful error descriptions without exposing stack traces or internal details to the LLM

### Note on the Existing Codebase

The current codebase does not have a dedicated service layer. Business logic is written directly in view methods. The tools will therefore interact with the ORM directly — similar to how existing views do — rather than through an intermediate service class. If shared logic grows to a point where duplication becomes a problem, extracting a service layer can be addressed as an explicit implementation decision at that time.

---

## 9. AI Agent Boundaries

### The Agent Should

- Work **only** with the authenticated user's Todo data
- Use the defined tools for all Todo operations
- Ask for clarification when the user's request is ambiguous (e.g., multiple Todos match a vague description)
- Accurately report the outcome of every tool call
- **Never fabricate a successful operation** — if the tool did not succeed, the agent must not tell the user it did

### The Agent Must Not

- Access another user's Todos or account data
- Execute arbitrary database queries or raw SQL
- Modify Django settings, URL configuration, or application code
- Perform operations not covered by an implemented tool (e.g., creating Tags, managing users)
- Bypass authentication or authorization — the agent only receives a pre-authenticated user object
- Accept instructions from the user that would circumvent ownership checks (e.g., *"Get todos for user ID 5"*)

---

## 10. Example Interactions

### Successful Read Operation

**User:** *"Show me my incomplete tasks."*

**Expected behavior:**
1. The agent identifies this as a list/search request with `is_completed = false`.
2. The agent calls the list tool with `user=request.user, is_completed=False`.
3. The tool queries `Todo.objects.filter(user=user, is_completed=False)`.
4. The tool returns the matching Todos as structured data.
5. The agent produces a readable response, e.g.: *"You have 3 incomplete tasks: 'Learn Django', 'Buy groceries', 'Prepare interview questions'."*

---

### Successful Write Operation

**User:** *"Create a task called Learn Django."*

**Expected behavior:**
1. The agent identifies this as a create request with `title = "Learn Django"`.
2. The agent calls the create tool with `user=request.user, title="Learn Django"`.
3. The tool validates the input and calls `Todo.objects.create(user=user, title="Learn Django")`.
4. The tool returns the created Todo's ID and title.
5. The agent responds: *"Done! I've created a task called 'Learn Django'."*

---

### Ambiguous Request

**User:** *"Update my task."*

**Expected behavior:**
1. The agent cannot determine which task the user means or what should be changed.
2. Instead of guessing, the agent asks: *"Which task would you like to update, and what changes should I make to it?"*
3. The user clarifies, and the agent proceeds with the update tool.

The agent must never select a random Todo to update when the request is underspecified.

---

### Unauthorized Request

**User:** *"Show me another user's tasks."*

**Expected behavior:**
1. The agent recognizes this is outside its permitted scope.
2. The agent refuses: *"I can only access your own tasks. I'm not able to retrieve another user's data."*
3. No tool is called. No database query is made.

---

### Failed Operation — Todo Not Found

**User:** *"Mark my 'Buy groceries' task as completed."*

**Expected behavior (if no matching Todo exists):**
1. The agent calls the appropriate tool to look up a Todo titled "Buy groceries" for the authenticated user.
2. The tool finds no matching record and returns a not-found error.
3. The agent reports honestly: *"I couldn't find a task called 'Buy groceries' in your list. Would you like me to create it, or did you mean a different task?"*

The agent must not claim the operation succeeded, and must not attempt to complete a Todo that was not found.

---

## 11. Error Handling Philosophy

The agent must handle errors gracefully without exposing internal implementation details to the user.

| Error Type | Agent Behavior |
|------------|----------------|
| **Invalid user input** | Ask the user to correct or clarify their input |
| **Missing information** | Ask a targeted clarifying question before calling any tool |
| **Todo not found** | Report honestly that the task was not found; offer alternatives if sensible |
| **Permission / ownership failure** | Refuse the operation; do not confirm or deny whether the requested resource belongs to another user |
| **Tool failure** | Report that something went wrong and ask the user to try again; do not surface Django exceptions, tracebacks, or ORM errors |
| **LLM failure** | Return a generic error to the user; log the failure server-side for debugging |
| **Unsupported request** | Explain politely that the request is outside the agent's current capabilities |

Detailed error-handling implementation — including error response schemas, logging strategy, and retry behavior — will be added when the agent is implemented.

---

## 12. Future AI Capabilities

The following are possible future enhancements. **None of these are part of the initial implementation.**

- **Natural-language Todo search** — semantic search across titles and descriptions, beyond keyword matching
- **Smart prioritization** — agent suggests which tasks to tackle first based on due dates and recency
- **Deadline suggestions** — when a user creates a task without a due date, the agent can suggest one based on context
- **Task summarization** — summarize the user's current Todo list into a brief status overview
- **Productivity insights** — track completion patterns over time and surface simple observations
- **Conversation memory** — remember context from earlier in a session (e.g., *"the task I just mentioned"*)
- **Multi-step task planning** — break a large goal into smaller subtasks and create them as individual Todos

These capabilities would require additional design decisions — potentially conversation history storage, semantic search infrastructure, or richer user data — and are out of scope for the initial agent.

---

## 13. Related AI Documentation

The following documents are planned to accompany this specification. They do not yet exist.

### `AI_AGENT_TOOLS.md`

Detailed specification for each Todo tool the agent can call. Covers:
- Tool names and descriptions
- Input argument schemas (types, required vs optional, validation rules)
- Return value schemas
- Error codes and error return formats
- ORM queries used by each tool
- Edge cases

### `AI_AGENT_MEMORY.md`

Design document for conversation context and memory. Covers:
- Whether and how conversation history is stored (e.g., in-memory per request vs persisted per session)
- How much history is passed to the LLM per request
- How the agent handles references to earlier messages (e.g., *"the task I just mentioned"*)
- Trade-offs between stateless and stateful agent designs

### `AI_AGENT_SECURITY.md`

Security considerations specific to the AI layer. Covers:
- Prompt injection risks and mitigations
- Why user identity must come from `request.user`, not LLM output
- Input sanitization before passing to tools
- Rate limiting on the AI endpoint
- What the LLM is and is not permitted to receive (e.g., no raw database IDs in prompts where avoidable)
- Logging and auditability of agent actions
