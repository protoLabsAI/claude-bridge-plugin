# claude-bridge-plugin

A [protoAgent](https://github.com/protoLabsAI/protoAgent) plugin that bridges
**Claude Code** state into protoAgent, for seamless pivoting between the two:
ask your agent what Claude Code knows about a project — its persistent memory,
past sessions, scratchpads, Cowork runs, and installed customizations.

Pairs with protoAgent's ACP runtime (ADR 0033/0082): ACP lets protoAgent *run*
Claude Code as a coding agent; this plugin lets it *read* Claude Code's
accumulated state.

## The three stores

| Store | Where | What |
|---|---|---|
| CLI | `~/.claude` | `projects/<slug>/` — session transcripts + persistent `memory/`; user `skills/`, `agents/`, `commands/`, `plugins/`, `settings.json` |
| Scratchpads | `/private/tmp/claude-<uid>` | per-session working files (ephemeral, wiped on reboot) |
| Cowork | `~/Library/Application Support/Claude/local-agent-mode-sessions` | desktop local-agent-mode sessions: metadata, `outputs/`, `uploads/`, `audit.jsonl` (transcripts stay in the sandbox VM) |

## Tools (v0.1 — explore, read-only)

- `claude_projects` — list projects or resolve a directory to its project
- `claude_memory` — MEMORY.md index + individual memory files for a directory
- `claude_sessions` — recent session transcripts; tail one by id
- `claude_scratchpad` — list/read a project's session scratchpads
- `claude_cowork` — list Cowork sessions; metadata + outputs + audit tail; read files
- `claude_inventory` — user- and project-level skills/subagents/commands/plugins/MCP
  servers (secret values redacted) and hooks

All reads go through a path fence (no absolute paths, no `..`, symlink escapes
refused) and are byte-capped. MCP env/header **values are never echoed** — key
names only.

## Roadmap

- v0.2 — translators: Claude skills → protoAgent skills (same open SKILL.md
  standard), slash commands → `user_facing`/`slash` skills, MCP servers →
  `mcp.servers` via `apply_settings`, subagent markdown → `SubagentConfig`;
  hooks report-only (protoAgent's equivalent is middleware, not a hook table).
- Later — console rail view for browsing memory; export a translated bundle as
  a standalone plugin repo.

## Install

```
plugin install https://github.com/protoLabsAI/claude-bridge-plugin
```

Then enable `claude_bridge` in the console (ships disabled — enabling is the
operator's trust decision). No pip deps, no network access.

## Development

```
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt ruff
.venv/bin/pytest -q          # host-free: no protoAgent checkout required
.venv/bin/ruff check .
```
