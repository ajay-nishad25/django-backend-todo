# AI Agent Memory — Todo Application

> **Status: Design specification only. No memory system has been implemented.**
>
> This document defines the memory and conversation-context strategy for the Todo AI agent. See `AI_AGENT.md` for the high-level architecture and `AI_AGENT_TOOLS.md` for the tool contract.

---

## 1. Purpose

A conversational AI agent is not useful if it treats every message as completely isolated. Users naturally refer to earlier parts of a conversation, and without any access to that context the agent becomes frustrating to interact with.

Consider this simple exchange:

```
User:  "Create a task for learning Django."
Agent: "Sure. When is it due?"
User:  "Tomorrow."
```

The agent cannot understand the word "tomorrow" without knowing what came before it. It needs the prior turn to understand that "tomorrow" is the due date for the task currently being created. Without that context, it would have to ask the user to repeat themselves — which defeats the purpose of a conversational interface.

### Two Distinct Concepts

This document uses two terms carefully:

**Context** — Information available to the agent during the current, active conversation. It exists for the duration of a session and is discarded when the conversation ends. It helps the agent understand what the user is referring to right now.

**Memory** — Information intentionally stored and retrieved across separate conversations. It persists beyond a single session. It requires deliberate design decisions around storage, privacy, and user control.

These are not the same thing. Conflating them leads to unnecessary complexity. This document treats them separately throughout.

---

## 2. Memory Strategy for the Initial Version

The initial agent should follow this principle:

> **Stateless between separate conversations, but context-aware within an active conversation.**

This means:

- Within a single conversation, the agent has access to the recent exchange — messages, responses, tool calls, and tool results — and can use this to understand references and resolve ambiguity.
- When a conversation ends and a new one begins, the agent starts fresh. It does not automatically recall what the user said in a previous session.

This is the simplest correct design for this project at its current stage. It avoids the complexity, privacy implications, and storage requirements of persistent memory while still enabling natural multi-turn conversations.

### Why Not Persistent Memory From the Start

- The existing backend has no memory storage infrastructure.
- The user's Todos already exist in the database and can be retrieved through tools at any time — this provides meaningful continuity without needing AI memory.
- Persistent memory adds database complexity, privacy concerns, and token management overhead.
- A stateless-between-sessions design is easier to debug and reason about.
- Most of the value a user needs can be delivered through the tool layer alone.

Persistent memory can be added later as a deliberate decision when there is a concrete requirement for it. That decision is deferred — not ruled out.

---

## 3. Short-Term Conversation Context

Within an active conversation, the agent may use the following as context:

| Context Item | Description |
|---|---|
| Recent user messages | What the user has said in the current session |
| Recent agent responses | What the agent has replied so far |
| Tool calls made | Which tools were invoked during the conversation |
| Tool results returned | What data the tools produced |
| Current task being discussed | The specific Todo the user and agent are actively working on |
| Clarifications provided | Any disambiguating information the user volunteered |

### Why This Context Is Necessary

Without short-term context, the agent cannot:
- Resolve pronouns ("that one", "it", "the first one")
- Connect follow-up answers to prior questions ("Tomorrow" → due date for the task just created)
- Avoid re-asking questions the user already answered
- Chain a read operation into a write operation naturally

### Example — Relative Date

```
User:  "Create a task called Prepare presentation."
Agent: "When is it due?"
User:  "Friday."
```

The agent uses the conversation context to understand that "Friday" is the `due_date` for the "Prepare presentation" task it is in the process of creating. Without the previous turn in context, "Friday" is meaningless.

### Example — Pronoun/Reference

```
User:  "Show me my Django tasks."
Agent: "Here are your Django tasks:
        1. Learn Django (due Sep 8)
        2. Django REST Framework tutorial"
User:  "Mark the first one as complete."
```

The agent uses the previous tool result — which is part of the current conversation context — to resolve "the first one" to Todo #42 ("Learn Django"). It can then call `complete_todo(user=request.user, todo_id=42)` without asking the user to repeat the task name.

### Example — Multi-turn Creation

```
User:  "Add a task for preparing for my interview."
Agent: "Got it. Any due date?"
User:  "Next Monday."
Agent: "Should I add a tag?"
User:  "Yes, work."
```

Each turn builds on the prior context to assemble the full `create_todo` call. The agent holds the in-progress creation state in the conversation context until it has enough information to call the tool.

---

## 4. Conversation Context vs Database State

This is an important distinction that must be respected throughout the agent's design.

**The Todo database is the source of truth for all Todo data.**

Conversation context is useful for understanding references and resolving ambiguity within a session. It is not authoritative for:

| Data | Source of Truth |
|---|---|
| Whether a Todo exists | Database |
| A Todo's current title | Database |
| A Todo's completion status | Database |
| A Todo's due date | Database |
| A Todo's ownership | Database |
| Whether a Todo was deleted | Database |

### Example — Stale Context

```
User:  "Mark my Learn Django task as completed."
Agent: calls complete_todo → success → tells user "Done."
User:  "Actually, I deleted that task. Can you re-create it?"
```

In this scenario, the agent's conversation context says the task was completed. But the database state may differ if the user deleted the task through the regular UI after completing it via the agent. Before acting, the agent should use its tools to verify current state rather than relying on what it "remembers" from earlier in the conversation.

**Rule:** When a write operation depends on the current state of a Todo, the agent should retrieve the current state from the database through a tool, not assume it matches what was discussed earlier in the conversation.

---

## 5. Persistent Memory

Persistent memory means storing information — user preferences, interaction history, behavioral patterns — in a database or storage system, and retrieving it in future conversations.

### Decision for the Initial Version

> **No general-purpose persistent user memory in the initial implementation.**

This is an intentional design decision, not an oversight.

**Why:**

1. **Simplicity.** No new models, migrations, storage layer, or retrieval logic needed.
2. **Privacy.** Storing conversation content raises questions about data retention, user consent, and access control that are outside the scope of a portfolio project.
3. **Redundancy.** The user's Todos are already in the application database. The agent can retrieve them at any time through `list_todos` and `get_todo`. This makes AI memory of Todo content unnecessary.
4. **Debugging.** A stateless agent is significantly easier to test, debug, and reason about than one with a persistent memory layer.
5. **No identified requirement.** There is no concrete user need that cannot be met with conversation context and tools.

Do not add a memory model to the database until there is a specific, justified requirement for one.

---

## 6. What the Agent Should NOT Remember

Regardless of what memory capabilities are added in the future, the following categories of information must never be stored as AI memory:

- **Passwords and authentication tokens** — the agent never handles these; they belong to the authentication layer only
- **API keys or secrets** — these are never part of the conversation
- **Sensitive personal information** — beyond what is necessary to perform the requested Todo operation
- **Internal system details** — Django settings, database credentials, server configuration, tool implementation details
- **Hidden prompt content** — system prompts, tool descriptions, and internal agent instructions must not be surfaced or stored as user-facing memory
- **Arbitrary conversation content** — not every user message should be retained indefinitely; only structured, clearly defined data should ever enter a persistent store
- **Another user's information** — memory is always scoped to the authenticated user; cross-user data must never be stored or retrieved through the memory layer

### The LLM Is Not a Secure Storage Mechanism

The LLM's context window is ephemeral and not a reliable or secure store. Sensitive information passed to the LLM in a prompt exists only for the duration of that inference call. It must never be treated as persisted or retrievable.

---

## 7. Todo Data Is Not AI Memory

This distinction is critical.

The user's Todos already exist in the application's relational database. They are managed by the existing `todo` app — created, updated, and deleted through the existing API views and, eventually, through the AI agent's tools.

```
Todo database
      ↓
Source of truth for all Todo content
```

This is different from:

```
AI memory layer
      ↓
Conversation context or user preference storage
```

These two systems serve different purposes:

| Todo Database | AI Memory |
|---|---|
| Stores `Todo` and `Tag` records | Stores conversation context or preferences |
| Written through existing API or AI tools | Written by the memory system |
| Is the source of truth | Supplements agent understanding |
| Already exists | Not implemented yet |

**The agent should never attempt to memorize the user's Todo list.** Instead, it should retrieve Todo information through its tools (`list_todos`, `get_todo`) when it needs current data. This ensures the agent always works with fresh, accurate information from the real database rather than stale context.

---

## 8. Context Management

Sending the entire conversation history to the LLM on every request is not practical. LLMs have finite context windows, and longer contexts increase cost and latency. For this project, the conversation history is expected to be short, but a clear approach should be defined from the start.

### Recommended Approach for the Initial Version

- **Include only the recent exchange** — typically the last several turns (e.g., the last 5–10 messages). The exact number can be tuned during implementation.
- **Include relevant tool calls and results** — when the user is referring to something the agent retrieved earlier in the same conversation (e.g., "the first one"), the corresponding tool result should be in the context.
- **Do not send the entire Todo database as context** — Todo data should be retrieved through tools on demand, not loaded wholesale into the prompt.
- **Do not pad the context with unnecessary system information** — keep the system prompt and context as concise as possible while still giving the agent what it needs.
- **Do not implement a complex context compression or summarization pipeline initially** — for a small Todo project with short conversations, simple truncation of older messages is sufficient to start.

### What Triggers a New Context Window

A new conversation (new session, new page load, explicit restart) begins with a fresh context. No prior conversation content is carried over automatically.

---

## 9. Tool Results and Context

Tool results produced during a conversation can temporarily become part of the active context. This is what enables natural follow-up references.

### Example Flow

```
User:  "Show my incomplete tasks."

Agent
  ↓
list_todos(user=request.user, is_completed=False)

Tool result:
[
  { "id": 12, "title": "Learn Django", "due_date": "2026-09-08" },
  { "id": 15, "title": "Prepare interview", "due_date": "2026-09-10" }
]

Agent:  "You have two incomplete tasks:
         1. Learn Django (due Sep 8)
         2. Prepare interview (due Sep 10)"

User:  "Complete the first one."
```

The tool result — specifically the fact that item #1 in the list is Todo #12 — is present in the conversation context. The agent can resolve "the first one" to `todo_id=12` and call `complete_todo(user=request.user, todo_id=12)`.

### When to Re-verify From the Database

Tool results in context reflect the state of the database at the time the tool was called. If there is any reason to believe the state may have changed — particularly before a destructive or write operation — the agent should call the appropriate tool again to confirm current state before proceeding.

For example, before deleting a Todo that was retrieved several turns ago, the agent may call `get_todo` to confirm the Todo still exists as expected.

---

## 10. Handling References to Previous Messages

Users naturally use shorthand references within a conversation. The agent must handle these gracefully.

### Common Reference Patterns

| Expression | Expected Agent Behavior |
|---|---|
| "the task I just mentioned" | Resolve from the most recent message where a task was named |
| "that one" | Resolve from the most recent Todo discussed in context |
| "the first one" | Resolve from the ordered list returned by the most recent `list_todos` call |
| "move it to Friday" | Resolve "it" to the most recently discussed Todo; resolve "Friday" to an absolute date |
| "mark that as completed" | Resolve "that" to the most recently mentioned Todo |
| "delete the one we discussed" | Resolve from recent context; if ambiguous, ask for clarification |

### When Context Is Insufficient

If the agent cannot confidently resolve a reference from the available conversation context, it must ask a clarifying question:

```
User:  "Delete the one we discussed."
Agent: "I want to make sure I delete the right task. Are you referring to
        'Learn Django' (due Sep 8), or a different task?"
```

The agent must **never randomly select a Todo** when a reference is ambiguous. Guessing is not acceptable — especially for destructive operations like deletion.

---

## 11. Conversation Boundaries

When a conversation ends and a new one begins, the agent starts with a completely fresh context.

```
New conversation starts
        ↓
  Fresh context (empty)
        ↓
  No automatic memory of prior sessions
        ↓
Agent works only from:
  - Current user message
  - Todo database (via tools)
```

### Continuity Without Persistent Memory

Even without AI memory, the user's experience is not disrupted between sessions because:

- Their Todos persist in the application database.
- The agent can retrieve current Todos at any time through `list_todos` and `get_todo`.
- The user can re-state their request naturally, and the agent will call the appropriate tool.

This provides meaningful continuity of application data — the things that actually matter — without requiring any AI memory layer.

### Example

A user ends a conversation after creating a task. The next day they start a new conversation:

```
User:  "What tasks do I have due this week?"
Agent: calls list_todos(user=request.user, due_date_range=...)
Agent: "You have 2 tasks due this week: ..."
```

The agent has no memory of the previous session, but it does not need any — the Todos are in the database and the tools retrieve them accurately.

---

## 12. Future Persistent Memory

The following memory capabilities are possible future additions. **None of these are part of the initial implementation.**

| Future Capability | Description |
|---|---|
| **User preferences** | Preferred default sort order, preferred tag for new tasks, etc. |
| **Task patterns** | Frequently created task types that could be suggested |
| **Conversation summaries** | Compressed summaries of past sessions stored for long-term context |
| **Productivity preferences** | Time of day preferences, urgency signals, focus areas |

### Requirements Before Introducing Persistent Memory

If persistent memory is added in a future phase, it must include:

- **Explicitly defined data structure** — only specific, justified fields should be stored, not arbitrary conversation text
- **Clear retention rules** — how long is memory retained? Is it session-based or permanent?
- **User visibility and control** — the user should be able to see what is remembered and request deletion
- **Strict user scoping** — memory must be associated with and retrievable only by the correct authenticated user
- **Security review** — see `AI_AGENT_SECURITY.md` for the security rules that apply to any future memory layer
- **Clear separation from Todo records** — memory storage must not be conflated with the `Todo` or `Tag` models

The database schema, storage strategy, and API for persistent memory are not designed here. These are deliberate decisions for a future implementation phase.

---

## 13. Memory and Security

Any memory system — current or future — must operate within the same authentication and authorization constraints as the rest of the application.

### Core Rules

- **Memory is always user-scoped.** Any memory retrieved during a conversation must belong to the authenticated `request.user`. The agent never retrieves memory for another user.
- **User identity comes from `request.user`, not from the LLM.** The LLM must never supply a `user_id` to a memory lookup. The authenticated user from the Django view is the only valid source of identity.
- **Memory does not grant authorization.** Even if the agent "remembers" that a user previously discussed a particular Todo, memory does not replace the ownership check performed by the tool. Every tool still verifies `Todo.objects.get(id=todo_id, user=user)` independently.
- **Memory does not override the database.** If a memory record says a Todo is completed but the database says it is not, the database wins. Memory is a supplement to understanding, not an authoritative data store.
- **Remembered information cannot be used to bypass tool boundaries.** The agent cannot use memory as a shortcut to skip validation, ownership checks, or tool invocation.

### Example — Memory Cannot Replace Ownership

```
# WRONG — agent "remembers" the todo_id and skips the ownership check
todo = Todo.objects.get(id=remembered_id)

# CORRECT — ownership always checked regardless of where todo_id came from
todo = Todo.objects.get(id=todo_id, user=user)
```

For detailed security rules governing the AI layer, see `AI_AGENT_SECURITY.md`.

---

## 14. Recommended Initial Architecture

The following diagram shows how memory and context fit into the overall agent architecture for the initial version:

```
User
  ↓
React Frontend
  ↓
Django AI Endpoint  (POST /api/ai/chat/)
  ↓
Authenticated User  (request.user from TokenAuthentication)
  ↓
AI Agent
  ├── Conversation Context  ←── recent messages, tool results, current session only
  │
  └── Todo Tools
            ↓
        Todo Database  ←── source of truth
```

### How Each Layer Contributes

| Layer | Role |
|---|---|
| **Conversation Context** | Holds the recent exchange for the current session. Enables pronoun resolution, follow-up understanding, and multi-turn creation. Discarded at session end. |
| **Todo Tools** | Retrieve and modify actual Todo data from the database on demand. Always user-scoped. Always return current state. |
| **Todo Database** | The authoritative source for all Todo records. Never replaced by context or memory. |
| **No persistent AI memory layer** | Not present in the initial version. The database provides application continuity; context provides conversational continuity. |

---

## 15. Implementation Status

- **Memory is currently a design specification only.**
- No memory system, context storage, or session store has been implemented.
- No new models, migrations, or database tables have been created.
- The initial implementation should use **conversation context only** — passing recent turns of the conversation to the LLM as part of each request.
- **Persistent user memory is intentionally deferred.** It is not part of the first implementation phase.

When the agent is first implemented, the context strategy will be:

1. Accept the current user message at the `POST /api/ai/chat/` endpoint.
2. Optionally accept a `history` array of recent turns from the frontend.
3. Pass the history and current message to the LLM along with the tool definitions.
4. Return the agent's response.
5. The frontend is responsible for maintaining and sending back the short conversation history on each subsequent request.

This keeps the backend stateless with respect to conversation history in the initial version, which is the simplest correct approach.

---

## 16. Related Documentation

### [`AI_AGENT.md`](./AI_AGENT.md)

The high-level architecture document. Defines the overall agent design, execution flow, and system boundaries. Memory and context fit into Step 3 (passing user context into the agent) and Step 4 (the agent understanding user intent) of the execution flow defined there.

### [`AI_AGENT_TOOLS.md`](./AI_AGENT_TOOLS.md)

The tool contract specification. Tools produce the results that temporarily become part of conversation context (Section 9 of this document). The `list_todos` and `get_todo` tools are the primary mechanism for retrieving current Todo state rather than relying on memory.

### [`AI_AGENT_SECURITY.md`](./AI_AGENT_SECURITY.md)

The security specification (planned). Defines the detailed security rules for the AI layer, including rules that govern any future memory system: user scoping, preventing cross-user access, and ensuring that memory cannot be used to bypass authorization.
