"""Tests for bundled policy presets and loader."""

import pytest

from agent_polis.actions.models import ActionType, RiskLevel
from agent_polis.governance import (
    get_policy_preset_metadata,
    list_policy_presets,
    load_policy_preset,
)
from agent_polis.governance.policy import PolicyDecision, PolicyEvaluationInput, PolicyEvaluator


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


def test_presets_include_rule_rationale_metadata() -> None:
    for preset_id in ("startup", "fintech", "games"):
        policy = load_policy_preset(preset_id)
        assert policy.rules, f"{preset_id} should define rules"
        for rule in policy.rules:
            assert rule.description, f"{preset_id}:{rule.id} missing description"
            assert (
                rule.metadata.get("rationale")
            ), f"{preset_id}:{rule.id} missing rationale metadata"


def test_presets_differ_on_critical_risk_behavior() -> None:
    evaluator = PolicyEvaluator()
    fintech = load_policy_preset("fintech")
    startup = load_policy_preset("startup")

    input_data = PolicyEvaluationInput(
        action_type=ActionType.FILE_WRITE,
        target="src/app.py",
        risk_level=RiskLevel.CRITICAL,
    )

    fintech_result = evaluator.evaluate(fintech, input_data)
    startup_result = evaluator.evaluate(startup, input_data)

    assert fintech_result.decision == PolicyDecision.DENY
    assert startup_result.decision != PolicyDecision.DENY


def test_games_allows_assets_medium_while_fintech_requires_approval() -> None:
    evaluator = PolicyEvaluator()
    games = load_policy_preset("games")
    fintech = load_policy_preset("fintech")

    input_data = PolicyEvaluationInput(
        action_type=ActionType.FILE_WRITE,
        target="assets/hero.png",
        risk_level=RiskLevel.MEDIUM,
    )

    games_result = evaluator.evaluate(games, input_data)
    fintech_result = evaluator.evaluate(fintech, input_data)

    assert games_result.decision == PolicyDecision.ALLOW
    assert fintech_result.decision != PolicyDecision.ALLOW
