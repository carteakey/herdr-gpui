# Herdr team experiment

A small, local coordination layer for agents already running in Herdr. It gives
one agent a supervisor role, a shared task board, and durable direct messages.
It requires Python 3 and SQLite from the Python standard library; it does not
modify Herdr or its configuration.

This is an early prototype. The intended native UI integration is described in
[`UI-DESIGN.md`](UI-DESIGN.md); it has not been implemented yet. Agents participate by running the CLI and checking
their inbox. It does **not** intercept terminal input, start agents, nudge idle
agents, provide a UI, or implement A2A. A queued message is not proof that the
recipient has read it. Agents need a shared local filesystem and database.
Names and roles are conventions, not authenticated identities or permissions.

## Try it

Use an absolute path to `team.py` and an absolute database path accessible to
all participating agents. These examples assume `team.py` is in the current
directory. Give each agent the same database path, for example:

```sh
export HERDR_TEAM_DB=/tmp/example-herdr-team/team.sqlite3
python3 team.py register lead --role supervisor
python3 team.py register analyst --role worker --pane w1:p2
python3 team.py create --by lead --to analyst --description 'Record evidence and confidence.' 'Map the input parser'
python3 team.py send --from lead --to analyst --task 1 'Please claim task 1 and report findings here.'
python3 team.py inbox analyst
python3 team.py ack analyst 1
python3 team.py claim analyst 1
python3 team.py send --from analyst --to lead --task 1 'Parser appears at 0x1234; verifying callers.'
python3 team.py complete analyst 1 --result 'Evidence and analysis: /path/to/report.md'
python3 team.py board
python3 team.py inbox lead
```

For real sessions use a private directory with appropriate filesystem
permissions and project-specific paths, not the illustrative `/tmp` path.
Pane IDs are optional metadata; they are not used as delivery addresses and
must be rediscovered if panes move. Every command returns JSON; errors go to
stderr with a nonzero status. `--db` overrides `HERDR_TEAM_DB`.

## Agent instructions

Give each participant its registered name, the shared database path, and the
absolute path to `team.py`. The supervisor creates and assigns tasks, checks
its inbox and the board, sends follow-up questions, and synthesizes results.
Workers check their inbox and assigned tasks, claim work, message peers when
useful, and complete tasks with evidence. Acknowledge a message only after
reading it; `inbox --all` includes acknowledged messages. Since nothing wakes
an idle agent, the user must prompt it to check or arrange an explicit polling
workflow. Results are shared as messages or referenced files.

`claim` atomically accepts an open unassigned task or one assigned to the
claimant; only the claimant may complete it. This does not isolate file access
or enforce read-only roles. Use separate worktrees when agents edit code.

## Next steps

Validate this workflow with real agents before adding Herdr delivery. A future
adapter needs explicit session targeting, an atomic idle check where supported,
and an honest uncertain-delivery state: successful terminal input does not
prove that an agent processed a message. Intercepting arbitrary `@` text inside
another application's PTY is deliberately not part of this experiment. Remote
workers, notifications, UI, and any standards bridge are separate decisions.
