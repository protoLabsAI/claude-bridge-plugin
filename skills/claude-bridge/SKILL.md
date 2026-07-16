---
name: claude-bridge
description: Explore Claude Code's on-disk state — persistent memory, session transcripts, scratchpads, Cowork sessions, and installed skills/agents/plugins/MCP servers — for this machine or a specific directory. Use when asked what Claude Code knows/remembers about a project, to find a past Claude Code session or its outputs, or to inventory Claude Code customizations before migrating them to protoAgent.
---

# Claude Bridge — exploring Claude Code state

Claude Code keeps its state in three host-local stores. The `claude_*` tools read
them (read-only, fenced):

| Store | Where | What |
|---|---|---|
| CLI | `~/.claude` | `projects/<slug>/` — session transcripts (`<uuid>.jsonl`) + persistent `memory/`; plus user `skills/`, `agents/`, `commands/`, `plugins/`, `settings.json` |
| Scratchpads | `/private/tmp/claude-<uid>/<slug>/<session>/scratchpad` | per-session working files — **ephemeral**, wiped on reboot |
| Cowork | `~/Library/Application Support/Claude/local-agent-mode-sessions` | desktop "local agent mode" sessions: metadata sidecar, `outputs/`, `uploads/`, `audit.jsonl` |

A *project* is keyed by slug: the absolute path with every non-alphanumeric
character replaced by `-`. Pass plain directory paths — the tools handle slugs.

## Tool cheat sheet

- `claude_projects` — list projects (`query` filters) or resolve a directory (pass a path starting with `/` or `~`).
- `claude_memory(directory)` — the MEMORY.md index; add `file=` for one memory file.
- `claude_sessions(directory)` — recent transcripts; add `session_id=` to tail one.
- `claude_scratchpad(directory[, session_id[, path]])` — list → files → read.
- `claude_cowork([session_id[, path]])` — list sessions → metadata/outputs/audit → read a file.
- `claude_inventory([project_dir])` — skills, subagents, commands, plugins, MCP servers (secret values redacted), hooks; project-level too when a dir is given.

## Caveats

- Cowork conversation transcripts live inside the sandbox VM, **not** on the host —
  metadata, outputs, and the audit log are all that can be read.
- Scratchpads are temp files; never treat them as durable, never suggest syncing them.
- Memory files reflect what was true when written — verify claims against the live
  repo before acting on them.
