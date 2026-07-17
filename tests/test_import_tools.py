"""The import tools end-to-end against the fake stores — dry-run discipline,
apply paths through faked host modules, and the license refusal."""

from __future__ import annotations

import sys
import types

import pytest

from tests.conftest import PROJECT_DIR, SECRET


@pytest.fixture
def import_tools(fake_home):
    from claude_bridge.tools_import import build_import_tools

    return {t.name: t for t in build_import_tools(fake_home)}


@pytest.fixture
def fake_host(monkeypatch, tmp_path):
    """Fake every host seam the importer touches; return the capture dict."""
    captured: dict = {"applied": []}

    target = tmp_path / "user-skills"
    target.mkdir()
    captured["skills_root"] = target
    monkeypatch.setitem(sys.modules, "infra.paths", types.ModuleType("infra.paths"))
    sys.modules["infra.paths"].user_skills_dir = lambda: target
    monkeypatch.setitem(sys.modules, "infra", types.ModuleType("infra"))

    state_mod = types.ModuleType("runtime.state")
    state_mod.STATE = types.SimpleNamespace(skills_index=None)
    monkeypatch.setitem(sys.modules, "runtime.state", state_mod)
    monkeypatch.setitem(sys.modules, "runtime", types.ModuleType("runtime"))

    host_mod = types.ModuleType("graph.plugins.host")

    class _Host:
        config = staticmethod(
            lambda: types.SimpleNamespace(
                mcp_servers=[{"name": "existing", "transport": "stdio", "command": "x"}],
                plugin_config={"claude_bridge": {}},
            )
        )

        @staticmethod
        def apply_settings(patch):
            captured["applied"].append(patch)
            return True, ["reloaded"]

    host_mod.HOST = _Host
    monkeypatch.setitem(sys.modules, "graph.plugins.host", host_mod)

    sdk_mod = types.ModuleType("graph.sdk")

    async def _knowledge_add(content, *, domain="general", heading=None, epoch=None):
        captured.setdefault("chunks", []).append((domain, heading, content))
        return len(captured["chunks"])

    sdk_mod.knowledge_add = _knowledge_add
    monkeypatch.setitem(sys.modules, "graph.sdk", sdk_mod)
    monkeypatch.setitem(sys.modules, "graph", types.ModuleType("graph"))
    monkeypatch.setitem(sys.modules, "graph.plugins", types.ModuleType("graph.plugins"))
    return captured


def test_scan_finds_everything_and_excludes_anthropic(import_tools):
    out = import_tools["claude_import_scan"].invoke({"project_dir": PROJECT_DIR})
    assert "demo-skill" in out
    assert "my-writing-style" in out
    assert "docx" in out and "excluded (Anthropic-licensed" in out
    assert "standup" in out and "reviewer" in out and "github" in out
    assert "memory: 1 topic" in out


async def test_skills_dry_run_writes_nothing(import_tools, fake_host):
    out = await import_tools["claude_import_skills"].ainvoke({"names": "all", "source": "cowork"})
    assert "DRY RUN" in out and "my-writing-style" in out
    assert not list(fake_host["skills_root"].iterdir())


async def test_skills_apply_imports_user_authored_only(import_tools, fake_host):
    out = await import_tools["claude_import_skills"].ainvoke({"names": "all", "source": "cowork", "apply": True})
    assert "imported skill 'my-writing-style'" in out
    assert (fake_host["skills_root"] / "my-writing-style" / "SKILL.md").is_file()
    # the Anthropic-licensed cowork skill never entered the candidate list
    assert "docx" not in out
    assert not (fake_host["skills_root"] / "docx").exists()


async def test_skills_apply_never_overwrites(import_tools, fake_host):
    (fake_host["skills_root"] / "my-writing-style").mkdir()
    out = await import_tools["claude_import_skills"].ainvoke({"names": "all", "source": "cowork", "apply": True})
    assert "skipped 'my-writing-style'" in out


async def test_commands_become_slash_skills(import_tools, fake_host):
    out = await import_tools["claude_import_commands"].ainvoke({"names": "standup", "apply": True})
    assert "imported skill 'standup'" in out
    text = (fake_host["skills_root"] / "standup" / "SKILL.md").read_text()
    assert "slash: standup" in text and "user_facing: true" in text


async def test_subagents_persist_via_plugin_config(import_tools, fake_host):
    out = await import_tools["claude_import_subagents"].ainvoke({"names": "reviewer", "apply": True})
    assert "reviewer" in out and "next config reload" in out
    patch = fake_host["applied"][-1]
    entry = patch["claude_bridge"]["imported_subagents"][0]
    assert entry["name"] == "reviewer"
    assert entry["tools"] == ["read_file", "run_command", "search_files"]


async def test_mcp_dry_run_redacts_and_apply_merges(import_tools, fake_host):
    dry = await import_tools["claude_import_mcp"].ainvoke({"names": "github"})
    assert "DRY RUN" in dry and SECRET not in dry and "env keys=['GH_TOKEN']" in dry

    out = await import_tools["claude_import_mcp"].ainvoke({"names": "github", "apply": True})
    assert "applied and reloaded" in out
    servers = fake_host["applied"][-1]["mcp"]["servers"]
    names = [s["name"] for s in servers]
    assert "existing" in names and "github" in names  # merge, not replace-all


async def test_memory_import_ingests_with_provenance(import_tools, fake_host):
    dry = await import_tools["claude_import_memory"].ainvoke({"directory": PROJECT_DIR})
    assert "DRY RUN" in dry and "1 topic" in dry
    out = await import_tools["claude_import_memory"].ainvoke({"directory": PROJECT_DIR, "apply": True})
    assert "ingested 1/1" in out
    domain, heading, content = fake_host["chunks"][0]
    assert domain == "claude-import" and "imported from claude-code" in content


def test_hooks_are_report_only(import_tools):
    out = import_tools["claude_hooks_report"].invoke({})
    assert "PreToolUse" in out and "NOT translated" in out


def test_imported_subagents_register_on_load(registry):
    import claude_bridge

    sub_mod = types.ModuleType("graph.subagents.config")

    class SubagentConfig:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    sub_mod.SubagentConfig = SubagentConfig
    sys.modules["graph.subagents.config"] = sub_mod
    sys.modules.setdefault("graph.subagents", types.ModuleType("graph.subagents"))
    sys.modules.setdefault("graph", types.ModuleType("graph"))

    captured = []
    registry.register_subagent = lambda cfg: captured.append(cfg)
    registry.config = {
        "imported_subagents": [{"name": "reviewer", "description": "d", "system_prompt": "p", "tools": []}]
    }
    try:
        claude_bridge.register(registry)
    finally:
        for mod in ("graph.subagents.config", "graph.subagents", "graph"):
            sys.modules.pop(mod, None)
    assert captured and captured[0].name == "reviewer"
