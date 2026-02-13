"""Tests for governance policy parsing and deterministic evaluation."""

import json

import pytest

from agent_polis.actions.models import ActionRequest, ActionType, RiskLevel
from agent_polis.governance import (
    PolicyDecision,
    PolicyEvaluator,
    load_policy_from_dict,
    load_policy_from_file,
)


def _request(
    action_type: ActionType = ActionType.FILE_WRITE,
    target: str = "src/app.py",
) -> ActionRequest:
    return ActionRequest(
        action_type=action_type,
        description="test action",
        target=target,
        payload={},
    )


def test_load_policy_from_dict_parses_rules() -> None:
    policy = load_policy_from_dict(
        {
            "version": "1",
            "defaults": {"decision": "require_approval"},
            "rules": [
                {
                    "id": "allow-docs",
                    "decision": "allow",
                    "priority": 50,
                    "action_types": ["file_write"],
                    "path_globs": ["docs/*"],
                    "max_risk_level": "medium",
                },
            ],
        }
    )

    assert policy.version == "1"
    assert policy.rules[0].id == "allow-docs"
    assert policy.rules[0].action_types == {ActionType.FILE_WRITE}
    assert policy.rules[0].max_risk_level == RiskLevel.MEDIUM


def test_load_policy_from_file_json(tmp_path) -> None:
    policy_data = {
        "version": "1",
        "defaults": {"decision": "deny"},
        "rules": [{"id": "allow-safe", "decision": "allow", "max_risk_level": "low"}],
    }
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy_data), encoding="utf-8")

    policy = load_policy_from_file(policy_path)

    assert policy.defaults.decision == PolicyDecision.DENY
    assert policy.rules[0].id == "allow-safe"


def test_load_policy_rejects_duplicate_rule_ids() -> None:
    with pytest.raises(ValueError, match="Duplicate rule IDs are not allowed: dup"):
        load_policy_from_dict(
            {
                "version": "1",
                "rules": [
                    {"id": "dup", "decision": "allow"},
                    {"id": "dup", "decision": "deny"},
                ],
            }
        )


def test_load_policy_rejects_invalid_risk_bounds() -> None:
    with pytest.raises(
        ValueError,
        match="max_risk_level cannot be lower than min_risk_level",
    ):
        load_policy_from_dict(
            {
                "version": "1",
                "rules": [
                    {
                        "id": "bad-bounds",
                        "decision": "allow",
                        "min_risk_level": "high",
                        "max_risk_level": "low",
                    },
                ],
            }
        )


def test_evaluator_returns_default_when_no_rule_matches() -> None:
    policy = load_policy_from_dict(
        {
            "version": "1",
            "defaults": {"decision": "deny"},
            "rules": [
                {
                    "id": "shell-only",
                    "decision": "allow",
                    "action_types": ["shell_command"],
                }
            ],
        }
    )
    evaluator = PolicyEvaluator()

    result = evaluator.evaluate(policy, _request(), risk_level=RiskLevel.LOW)

    assert result.decision == PolicyDecision.DENY
    assert result.matched_rule_id is None
    assert "default:deny:no-matching-rules" in result.trace


def test_evaluator_requires_risk_for_action_request() -> None:
    policy = load_policy_from_dict({"version": "1"})
    evaluator = PolicyEvaluator()

    with pytest.raises(
        ValueError,
        match="risk_level is required when evaluating an ActionRequest",
    ):
        evaluator.evaluate(policy, _request())


def test_evaluator_prefers_lower_priority_rule() -> None:
    policy = load_policy_from_dict(
        {
            "version": "1",
            "rules": [
                {
                    "id": "approve-general",
                    "decision": "require_approval",
                    "priority": 30,
                    "action_types": ["file_write"],
                },
                {
                    "id": "deny-priority",
                    "decision": "deny",
                    "priority": 10,
                    "action_types": ["file_write"],
                },
            ],
        }
    )
    evaluator = PolicyEvaluator()

    result = evaluator.evaluate(policy, _request(), risk_level=RiskLevel.MEDIUM)

    assert result.decision == PolicyDecision.DENY
    assert result.matched_rule_id == "deny-priority"
    assert result.matched_rule_priority == 10


def test_evaluator_prefers_more_specific_rule_for_equal_priority() -> None:
    policy = load_policy_from_dict(
        {
            "version": "1",
            "rules": [
                {
                    "id": "allow-generic",
                    "decision": "allow",
                    "priority": 20,
                    "action_types": ["file_write"],
                },
                {
                    "id": "deny-src",
                    "decision": "deny",
                    "priority": 20,
                    "action_types": ["file_write"],
                    "path_globs": ["src/*"],
                },
            ],
        }
    )
    evaluator = PolicyEvaluator()

    result = evaluator.evaluate(
        policy,
        _request(target="src/settings.py"),
        risk_level=RiskLevel.MEDIUM,
    )

    assert result.decision == PolicyDecision.DENY
    assert result.matched_rule_id == "deny-src"
    assert result.matched_rule_specificity == 2


def test_evaluator_uses_rule_order_as_tie_breaker() -> None:
    policy = load_policy_from_dict(
        {
            "version": "1",
            "rules": [
                {
                    "id": "first-match",
                    "decision": "allow",
                    "priority": 20,
                    "action_types": ["file_write"],
                },
                {
                    "id": "second-match",
                    "decision": "deny",
                    "priority": 20,
                    "action_types": ["file_write"],
                },
            ],
        }
    )
    evaluator = PolicyEvaluator()

    result = evaluator.evaluate(policy, _request(), risk_level=RiskLevel.MEDIUM)

    assert result.decision == PolicyDecision.ALLOW
    assert result.matched_rule_id == "first-match"
