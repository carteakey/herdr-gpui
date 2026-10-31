# Team coordination in Herdr UI

## Experience

The team lives in the existing Herdr UI window. The user chooses or launches a
supervisor and gives it a goal. Workers appear alongside their current Herdr
terminals. A Team view shows the supervisor, workers and their actual Herdr
status, task ownership, messages, and shared findings. Selecting a worker
opens or focuses its terminal; selecting a task or message shows the evidence
and conversation. The user can address the supervisor and inspect the team
without switching to a separate dashboard.

The existing Orchestrator tab is an integration candidate, but is currently
repository-scoped and built around issues and pull requests. A Team view must
also work for investigations with no Git repository, such as reverse
engineering a binary. Its final placement should not make repository access a
requirement or conflate a repository issue with a team task.

## Data and control

- Keep the Herdr daemon responsible for terminals and live agent state. The
  coordination layer stores team membership, task state, messages, and
  findings; a selected ordinary agent acts as supervisor.
- Load data asynchronously. Do not read SQLite or run external processes in
  GPUI rendering or input handlers. Follow the existing service/snapshot
  pattern and keep requests and queues bounded.
- The Python experiment uses an explicitly selected local SQLite file. It is
  an experimental data source, not yet an app service, stable schema, or
  authenticated multi-user protocol. Decide ownership, migration, and storage
  location before exposing it as a supported application feature.
- Register panes using explicit session and agent identifiers. Pane names or
  IDs alone do not uniquely identify a worker across machines.
- Messages remain queued until acknowledged. UI delivery controls must never
  claim that a message was read merely because terminal input was sent. A
  busy, blocked, disconnected, or unknown agent must not be assumed ready;
  automatic nudging needs a race-safe Herdr capability and explicit failure
  and uncertain-delivery handling.
- A task result is evidence for the supervisor, not an automatic approval.
  Parallel editing requires an explicit workspace/worktree strategy.
- Provide corresponding app control commands, documentation, and tests for
  new UI-owned capabilities, as required by this repository's instructions.

## First integrated milestone

1. Add a local Team view in the native window that works without a Git repo.
2. Connect it to one explicitly chosen local team database using a background
   service. Display roster, tasks and messages, with loading and error states.
3. Let a user inspect a worker's actual Herdr pane and send a message to its
   inbox. Show queued and acknowledged states accurately.
4. Allow selection of a supervisor and make its role visible. An agent becomes
   a functioning supervisor only after it has access to the coordination CLI
   or equivalent tools and is instructed to use them.
5. Test with an isolated Herdr session and two real agent CLIs, including a
   worker receiving a message while busy. Validate the native view at narrow
   and normal widths, and in light and dark themes.

Later milestones can add race-safe wake-up, agent launch and configuration,
workspace isolation, remote workers, and an optional A2A adapter. No terminal
input interception or automatic command execution is assumed.
