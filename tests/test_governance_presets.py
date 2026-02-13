"""Tests for bundled policy presets and loader."""

import pytest

from agent_polis.governance import (
    get_policy_preset_metadata,
    list_policy_presets,
    load_policy_preset,
)


def test_list_policy_presets_contains_required_ids() -> None:
    presets = list_policy_presets()
    ids = {p.id for p in presets}

    assert {"startup", "fintech", "games"}.issubset(ids)


def test_get_policy_preset_metadata_invalid_id() -> None:
    with pytest.raises(ValueError, match="Unknown preset id"):
        get_policy_preset_metadata("does-not-exist")


def test_load_policy_preset_invalid_id() -> None:
    with pytest.raises(ValueError, match="Unknown preset id"):
        load_policy_preset("does-not-exist")


def test_load_policy_preset_validates_schema() -> None:
    policy = load_policy_preset("startup")
    assert policy.version.startswith("preset-")


def test_load_policy_preset_surfaces_validation_errors(monkeypatch) -> None:
    from agent_polis.governance import presets as presets_module

    monkeypatch.setitem(
        presets_module._PRESET_POLICIES,  # type: ignore[attr-defined]
        "broken",
        {"version": "1", "rules": [{"id": "", "decision": "allow"}]},
    )

    with pytest.raises(ValueError, match="Invalid policy configuration"):
        load_policy_preset("broken")

