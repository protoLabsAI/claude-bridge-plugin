"""Apply layer: write translated artifacts into the protoAgent instance.

Every host import (infra.paths, runtime.state, graph.*) is lazy so the test
suite fakes them via sys.modules. Semantics follow the bundle-overlay
philosophy: one-shot imports, provenance-tagged, existing operator material is
never overwritten — re-imports skip and report instead of clobbering.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from .translate import TranslatedSkill, TranslatedSubagent

log = logging.getLogger("protoagent.plugins.claude_bridge")


def skills_target_root() -> Path:
    """The instance's writable skills root (wins last in seeding — user tier)."""
    from infra.paths import user_skills_dir

    return Path(user_skills_dir())


def write_skill(translated: TranslatedSkill, target_root: Path) -> str:
    """Write a translated skill directory. Additive-only: an existing skill of
    the same name is skipped (never overwritten), mirroring save_skill."""
    target = target_root / translated.name
    if target.exists():
        return f"skipped {translated.name!r} — already exists at {target}"
    for rel, content in translated.files.items():
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    _index_live(translated)
    return f"imported skill {translated.name!r} → {target}"


def _index_live(translated: TranslatedSkill) -> None:
    """Best-effort: make the skill available THIS session (the disk copy seeds
    on every boot regardless — replace_disk_skills refreshes the disk tier)."""
    try:
        from runtime.state import STATE

        idx = getattr(STATE, "skills_index", None)
        if idx is None:
            return
        existing = {(s.get("name") or "").strip().lower() for s in idx.all_skills()}
        if translated.name.lower() in existing:
            return
        from graph.extensions.skills import SkillV1Artifact

        body = translated.skill_md.split("---", 2)[-1].strip()
        idx.add_skill(
            SkillV1Artifact(name=translated.name, description=translated.description, prompt_template=body),
            source="disk",
        )
    except Exception:  # noqa: BLE001 — live indexing is a convenience, never a failure
        log.debug("[claude_bridge] live skill indexing skipped", exc_info=True)


async def apply_mcp_entries(entries: list[dict]) -> tuple[bool, list[str]]:
    """Merge translated MCP servers into ``mcp.servers`` (replace-by-name, same
    semantics as the console's add form) via the host's apply_settings."""
    from graph.plugins.host import HOST

    if HOST.config is None or HOST.apply_settings is None:
        return False, ["host services unavailable — is the plugin running in a live server?"]
    cfg = HOST.config()
    current = [dict(s) for s in (getattr(cfg, "mcp_servers", []) or [])]
    names = {e["name"] for e in entries}
    merged = [s for s in current if s.get("name") not in names] + entries
    ok, messages = await asyncio.to_thread(HOST.apply_settings, {"mcp": {"enabled": True, "servers": merged}})
    return ok, list(messages or [])


async def apply_subagents(subs: list[TranslatedSubagent]) -> tuple[bool, list[str]]:
    """Persist imported subagents into the plugin's own config section; they're
    registered on every plugin load by register() (config-driven, survives
    restarts). Existing entries of the same name are kept, not replaced."""
    from graph.plugins.host import HOST

    if HOST.config is None or HOST.apply_settings is None:
        return False, ["host services unavailable — is the plugin running in a live server?"]
    cfg = HOST.config()
    section = dict((getattr(cfg, "plugin_config", {}) or {}).get("claude_bridge") or {})
    existing = {s.get("name") for s in (section.get("imported_subagents") or [])}
    added = [
        {
            "name": s.name,
            "description": s.description,
            "system_prompt": s.system_prompt,
            "tools": s.tools,
            "original_model": s.original_model,
        }
        for s in subs
        if s.name not in existing
    ]
    if not added:
        return True, ["nothing new to add — all names already imported"]
    merged = list(section.get("imported_subagents") or []) + added
    ok, messages = await asyncio.to_thread(HOST.apply_settings, {"claude_bridge": {"imported_subagents": merged}})
    return ok, list(messages or []) + [f"registered {len(added)} subagent(s); live on the next config reload"]


def register_imported_subagents(registry, cfg: dict) -> int:
    """Called from register(): turn persisted imports into live SubagentConfigs."""
    entries = cfg.get("imported_subagents") or []
    if not entries:
        return 0
    from graph.subagents.config import SubagentConfig

    count = 0
    for e in entries:
        try:
            registry.register_subagent(
                SubagentConfig(
                    name=str(e["name"]),
                    description=str(e.get("description", "")),
                    system_prompt=str(e.get("system_prompt", "")),
                    tools=list(e.get("tools") or []),
                )
            )
            count += 1
        except Exception:  # noqa: BLE001 — one bad import must not sink the rest
            log.exception("[claude_bridge] registering imported subagent %r failed", e.get("name"))
    return count


async def ingest_memory(chunks: list[tuple[str, str]], source_label: str) -> tuple[int, list[str]]:
    """Ingest (heading, content) chunks into the knowledge graph with
    provenance. Domain ``claude-import`` keeps them inspectable/purgeable as a
    unit (knowledge_purge('claude-import') undoes an import)."""
    from graph import sdk

    added = 0
    problems: list[str] = []
    for heading, content in chunks:
        try:
            chunk_id = await sdk.knowledge_add(
                f"[imported from {source_label}] {content}", domain="claude-import", heading=heading
            )
            if chunk_id is not None:
                added += 1
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{heading}: {exc}")
    return added, problems
