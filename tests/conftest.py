"""Test bootstrap — the plugin must import and run with NO protoAgent host.

Registers a synthetic ``claude_bridge`` package (mirroring how the host loads
plugins) so relative imports resolve, then provides fixtures: a fake registry
and a fake three-store Claude Code home built in tmp_path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = "claude_bridge"

if PKG not in sys.modules:
    _spec = importlib.util.spec_from_file_location(PKG, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    assert _spec and _spec.loader
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[PKG] = _mod
    _spec.loader.exec_module(_mod)


class FakeRegistry:
    def __init__(self):
        self.config = {}
        self.tools = []
        self.skill_dirs = []

    def register_tool(self, t):
        self.tools.append(t)

    def register_tools(self, tools):
        self.tools.extend(tools)

    def register_skill_dir(self, path):
        self.skill_dirs.append(path)


@pytest.fixture
def registry():
    return FakeRegistry()


PROJECT_DIR = "/Users/kj/dev/myproj"
SLUG = "-Users-kj-dev-myproj"
SESSION = "11111111-2222-3333-4444-555555555555"
COWORK_SESSION = "local_abcdef12-3456"
SECRET = "sk-super-secret-value"


@pytest.fixture
def fake_home(tmp_path):
    """A fake trio of Claude Code stores + the plugin cfg pointing at them."""
    cli = tmp_path / "dot-claude"
    proj = cli / "projects" / SLUG
    memory = proj / "memory"
    memory.mkdir(parents=True)
    (memory / "MEMORY.md").write_text("# Memory index\n- [A fact](a-fact.md) — hook\n")
    (memory / "a-fact.md").write_text("---\nname: a-fact\n---\n\nThe fact body.\n")
    transcript = [
        {"type": "user", "message": {"role": "user", "content": "hello there"}},
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "hi — answering"}]},
        },
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Bash", "input": {}}]},
        },
    ]
    (proj / f"{SESSION}.jsonl").write_text("\n".join(json.dumps(r) for r in transcript))

    (cli / "skills" / "demo-skill").mkdir(parents=True)
    (cli / "skills" / "demo-skill" / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: A demo skill for testing.\n---\n\nBody.\n"
    )
    (cli / "agents").mkdir()
    (cli / "agents" / "helper.md").write_text(
        "---\nname: helper\ndescription: A helper subagent.\ntools: Read, Grep\n---\n\nYou are a helper.\n"
    )
    (cli / "plugins").mkdir()
    (cli / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": {"some-marketplace/tool-pack": [{"scope": "user"}]}})
    )
    (cli / "settings.json").write_text(
        json.dumps(
            {
                "model": "opus",
                "enabledPlugins": ["tool-pack"],
                "mcpServers": {"github": {"command": "gh-mcp", "args": ["serve"], "env": {"GH_TOKEN": SECRET}}},
            }
        )
    )

    scratch = tmp_path / "scratch"
    pad = scratch / SLUG / SESSION / "scratchpad"
    pad.mkdir(parents=True)
    (pad / "notes.md").write_text("scratch notes content\n")

    cowork = tmp_path / "cowork"
    sess_parent = cowork / "acct-uuid" / "org-uuid"
    outputs = sess_parent / COWORK_SESSION / "outputs"
    outputs.mkdir(parents=True)
    (outputs / "report.md").write_text("cowork report body\n")
    (sess_parent / COWORK_SESSION / "audit.jsonl").write_text(
        json.dumps({"type": "exec", "message": {"role": "system", "content": "ran a command"}}) + "\n"
    )
    (sess_parent / f"{COWORK_SESSION}.json").write_text(
        json.dumps(
            {
                "createdAt": "2026-07-01T00:00:00Z",
                "lastActivityAt": "2026-07-02T00:00:00Z",
                "model": "claude-opus-4-7",
                "permissionMode": "default",
                "cwd": str(outputs),
                "memoryEnabled": False,
                "isArchived": False,
                "cliSessionId": "dead-beef",
                "initialMessage": "organize my files please",
            }
        )
    )

    # v0.2 import sources: slash commands, subagents, MCP servers, and Cowork
    # skills (one user-authored, one Anthropic-licensed that must be refused).
    (cli / "commands").mkdir(exist_ok=True)
    (cli / "commands" / "standup.md").write_text(
        "---\ndescription: Structured progress report.\n---\n\nReport progress on $ARGUMENTS.\n"
    )
    (cli / "agents" / "reviewer.md").write_text(
        "---\nname: reviewer\ndescription: Reviews changes.\ntools: Read, Grep, Bash, TodoWrite\nmodel: opus\n---\n\nYou review code changes carefully.\n"
    )
    settings = json.loads((cli / "settings.json").read_text())
    settings["hooks"] = {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]}]}
    (cli / "settings.json").write_text(json.dumps(settings))

    acct = cowork / "skills-plugin" / "org-uuid" / "acct-uuid"
    (acct / "skills" / "my-writing-style").mkdir(parents=True)
    (acct / "skills" / "my-writing-style" / "SKILL.md").write_text(
        "---\nname: my-writing-style\ndescription: The operator's voice profile.\n---\n\nWrite tersely.\n"
    )
    (acct / "skills" / "docx").mkdir(parents=True)
    (acct / "skills" / "docx" / "SKILL.md").write_text(
        "---\nname: docx\ndescription: Word documents.\n---\n\nProprietary body.\n"
    )
    (acct / "skills" / "docx" / "LICENSE.txt").write_text("(c) 2025 Anthropic, PBC. All rights reserved.\n")
    (acct / "manifest.json").write_text(
        json.dumps(
            {
                "skills": [
                    {"name": "my-writing-style", "creatorType": "user"},
                    {"name": "docx", "creatorType": "anthropic"},
                ]
            }
        )
    )

    cfg = {
        "cli_root": str(cli),
        "scratchpad_root": str(scratch),
        "cowork_root": str(cowork),
        "max_read_bytes": 65536,
        "transcript_tail": 20,
    }
    return cfg


@pytest.fixture
def tools(fake_home):
    from claude_bridge.explore import build_explore_tools

    return {t.name: t for t in build_explore_tools(fake_home)}
