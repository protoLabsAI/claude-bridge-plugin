"""The path fence and the slug mapping — the security-relevant core."""

from __future__ import annotations

import pytest

from claude_bridge.stores import ClaudeStores, FencedRoot, project_slug_candidates


def test_slug_replaces_every_non_alphanumeric():
    assert project_slug_candidates("/Users/kj/dev/protoAgent")[0] == "-Users-kj-dev-protoAgent"
    # dots collapse to dashes exactly like slashes (observed: /Users/kj/.protoagent-dev-workspace)
    assert project_slug_candidates("/Users/kj/.protoagent-dev-workspace")[0] == "-Users-kj--protoagent-dev-workspace"


def test_slug_offers_underscore_preserving_fallback():
    candidates = project_slug_candidates("/Users/kj/dev/my_proj")
    assert candidates[0] == "-Users-kj-dev-my-proj"
    assert "-Users-kj-dev-my_proj" in candidates


def test_fence_refuses_dotdot_and_absolute(tmp_path):
    fence = FencedRoot("t", tmp_path)
    for bad in ("../outside", "a/../../outside", "/etc/passwd", "~/other"):
        with pytest.raises(ValueError):
            fence.resolve(bad)


def test_fence_refuses_symlink_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("nope")
    (root / "link").symlink_to(outside)
    fence = FencedRoot("t", root)
    with pytest.raises(ValueError):
        fence.resolve("link/secret.txt")


def test_fence_reads_inside_with_cap(tmp_path):
    (tmp_path / "f.txt").write_text("x" * 100)
    fence = FencedRoot("t", tmp_path)
    text, truncated = fence.read_text("f.txt", max_bytes=10)
    assert text == "x" * 10 and truncated


def test_find_project_resolves_directory(fake_home):
    stores = ClaudeStores(fake_home)
    found = stores.find_project("/Users/kj/dev/myproj")
    assert found is not None
    slug, path = found
    assert slug == "-Users-kj-dev-myproj" and path.is_dir()
    assert stores.find_project("/no/such/dir") is None
