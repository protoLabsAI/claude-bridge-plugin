---
name: claude-bridge
description: Explore Claude Code's on-disk state (memory, sessions, scratchpads, Cowork, installed customizations) AND import it — translate user-authored skills, slash commands, subagents, MCP servers, and project memory into this agent. Use when asked what Claude Code knows about a project, or to migrate/import Claude Code state into protoAgent.
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

## Importing (v0.2)

All import tools are **dry-run by default** — show the operator the dry run,
get approval, then re-run with `apply=True`. Existing material is never
overwritten; re-imports skip and report.

- `claude_import_scan([project_dir])` — inventory everything importable first.
- `claude_import_skills(names, source)` — source: `user`, `cowork`, or a project dir.
- `claude_import_commands(names[, project_dir])` — become `/slash` skills.
- `claude_import_subagents(names[, project_dir])` — live after the next config reload.
- `claude_import_mcp(names[, project_dir])` — merges into `mcp.servers` by name.
- `claude_import_memory(directory)` — knowledge domain `claude-import`; undo with `knowledge_purge('claude-import')`.
- `claude_hooks_report([project_dir])` — hooks are REPORT-ONLY (protoAgent's equivalent is middleware, never auto-ported).

**License rule (never bend it):** Anthropic-authored skills (Cowork's
`creatorType: anthropic`, or Anthropic license text in the skill dir) are
refused by the importer and must stay refused — their license prohibits
redistribution. Only user-authored material migrates.

## Caveats

- Cowork conversation transcripts live inside the sandbox VM, **not** on the host —
  metadata, outputs, and the audit log are all that can be read.
- Scratchpads are temp files; never treat them as durable, never suggest syncing them.
- Memory files reflect what was true when written — verify claims against the live
  repo before acting on them.
