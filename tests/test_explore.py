"""Each explore tool exercised against the fake three-store home."""

from __future__ import annotations

from tests.conftest import COWORK_SESSION, PROJECT_DIR, SECRET, SESSION, SLUG


def test_projects_lists_and_resolves(tools):
    listing = tools["claude_projects"].invoke({"query": ""})
    assert SLUG in listing and "memory=yes" in listing

    resolved = tools["claude_projects"].invoke({"query": PROJECT_DIR})
    assert f"project: {SLUG}" in resolved
    assert "sessions: 1" in resolved
    assert "a-fact.md" in resolved


def test_projects_handles_unknown_dir(tools):
    out = tools["claude_projects"].invoke({"query": "/no/such/dir"})
    assert out.startswith("error:")


def test_memory_index_and_file(tools):
    index = tools["claude_memory"].invoke({"directory": PROJECT_DIR})
    assert "# Memory index" in index and "a-fact.md" in index

    fact = tools["claude_memory"].invoke({"directory": PROJECT_DIR, "file": "a-fact.md"})
    assert "The fact body." in fact


def test_memory_file_cannot_escape(tools):
    out = tools["claude_memory"].invoke({"directory": PROJECT_DIR, "file": "../../../settings.json"})
    assert out.startswith("error:")


def test_sessions_list_and_tail(tools):
    listing = tools["claude_sessions"].invoke({"directory": PROJECT_DIR})
    assert SESSION in listing

    tail = tools["claude_sessions"].invoke({"directory": PROJECT_DIR, "session_id": SESSION})
    assert "hello there" in tail
    assert "hi — answering" in tail
    assert "[tool_use: Bash]" in tail


def test_scratchpad_list_files_read(tools):
    sessions = tools["claude_scratchpad"].invoke({"directory": PROJECT_DIR})
    assert SESSION in sessions

    files = tools["claude_scratchpad"].invoke({"directory": PROJECT_DIR, "session_id": SESSION})
    assert "notes.md" in files

    body = tools["claude_scratchpad"].invoke({"directory": PROJECT_DIR, "session_id": SESSION, "path": "notes.md"})
    assert "scratch notes content" in body


def test_cowork_list_detail_read(tools):
    listing = tools["claude_cowork"].invoke({})
    assert COWORK_SESSION in listing and "organize my files" in listing

    detail = tools["claude_cowork"].invoke({"session_id": COWORK_SESSION})
    assert "claude-opus-4-7" in detail
    assert "outputs/report.md" in detail
    assert "audit tail:" in detail

    body = tools["claude_cowork"].invoke({"session_id": COWORK_SESSION, "path": "outputs/report.md"})
    assert "cowork report body" in body


def test_inventory_lists_and_redacts_secrets(tools):
    out = tools["claude_inventory"].invoke({})
    assert "demo-skill" in out
    assert "helper" in out
    assert "some-marketplace/tool-pack" in out
    assert "github" in out and "GH_TOKEN" in out
    assert SECRET not in out, "MCP env values must never be echoed"


def test_inventory_project_level(tools, tmp_path):
    proj = tmp_path / "someproj"
    (proj / ".claude" / "agents").mkdir(parents=True)
    (proj / ".claude" / "agents" / "local.md").write_text(
        "---\nname: local\ndescription: Project-scoped agent.\n---\n\nPrompt.\n"
    )
    (proj / ".claude" / "settings.json").write_text('{"hooks": {"PreToolUse": []}}')
    (proj / ".mcp.json").write_text('{"mcpServers": {"docs": {"url": "https://x.test/mcp?key=abc"}}}')
    (proj / "CLAUDE.md").write_text("# My project\n")

    out = tools["claude_inventory"].invoke({"project_dir": str(proj)})
    assert "local" in out
    assert "PreToolUse" in out
    assert "docs" in out and "key=abc" not in out, "URL query strings are stripped"
    assert "CLAUDE.md: present" in out
