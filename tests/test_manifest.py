"""Manifest sanity: data-only contract the host relies on."""

from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _manifest() -> dict:
    return yaml.safe_load((ROOT / "protoagent.plugin.yaml").read_text())


def test_identity_and_trust_defaults():
    m = _manifest()
    assert m["id"] == "claude_bridge"
    assert m["enabled"] is False, "plugins ship disabled — enabling is the operator's call"
    assert m["config_section"] == "claude_bridge"
    assert isinstance(m["config_section"], str)


def test_version_lockstep_with_pyproject():
    m = _manifest()
    py = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert m["version"] == py["project"]["version"]


def test_capabilities_are_honest():
    m = _manifest()
    assert m["capabilities"]["network"] == []
    assert m["capabilities"]["filesystem"] == "scoped"


def test_config_defaults_cover_all_store_roots():
    cfg = _manifest()["config"]
    for key in ("cli_root", "scratchpad_root", "cowork_root", "max_read_bytes", "transcript_tail"):
        assert key in cfg
