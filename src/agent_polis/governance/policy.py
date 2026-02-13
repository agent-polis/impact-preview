"""Policy schema, parser, and deterministic evaluator."""

from __future__ import annotations

import fnmatch
import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator

from agent_polis.actions.models import ActionRequest, ActionType, RiskLevel


class PolicyDecision(str, Enum):
    """Policy decisions available to enforcement clients."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


_RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


def _risk_severity(level: RiskLevel) -> int:
    return _RISK_ORDER[level]


class PolicyDefaults(BaseModel):
    """Default behavior when no rules match."""

    decision: PolicyDecision = Field(default=PolicyDecision.REQUIRE_APPROVAL)


class PolicyRule(BaseModel):
    """Single policy rule with optional match predicates."""

    id: str = Field(min_length=1)
    description: str | None = None
    decision: PolicyDecision
    priority: int = Field(default=100)
    enabled: bool = Field(default=True)

    action_types: set[ActionType] = Field(default_factory=set)
    path_globs: list[str] = Field(default_factory=list)
    target_contains: list[str] = Field(default_factory=list)
    min_risk_level: RiskLevel | None = None
    max_risk_level: RiskLevel | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_risk_bounds(self) -> PolicyRule:
        if self.min_risk_level and self.max_risk_level:
            if _risk_severity(self.max_risk_level) < _risk_severity(self.min_risk_level):
                raise ValueError("max_risk_level cannot be lower than min_risk_level")
        return self

    def specificity(self) -> int:
        """Higher values indicate more constrained rules."""
        return (
            (1 if self.action_types else 0)
            + (1 if self.path_globs else 0)
            + (1 if self.target_contains else 0)
            + (1 if self.min_risk_level is not None else 0)
            + (1 if self.max_risk_level is not None else 0)
        )


class PolicyConfig(BaseModel):
    """Versioned policy configuration."""

    version: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    defaults: PolicyDefaults = Field(default_factory=PolicyDefaults)
    rules: list[PolicyRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_rule_ids(self) -> PolicyConfig:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for rule in self.rules:
            if rule.id in seen:
                duplicates.add(rule.id)
            seen.add(rule.id)
        if duplicates:
            dupes = ", ".join(sorted(duplicates))
            raise ValueError(f"Duplicate rule IDs are not allowed: {dupes}")
        return self


class PolicyEvaluationInput(BaseModel):
    """Input payload for policy evaluation."""

    action_type: ActionType
    target: str
    risk_level: RiskLevel
    context: str | None = None

    @classmethod
    def from_request(
        cls,
        request: ActionRequest,
        risk_level: RiskLevel,
    ) -> PolicyEvaluationInput:
        return cls(
            action_type=request.action_type,
            target=request.target,
            risk_level=risk_level,
            context=request.context,
        )


class PolicyEvaluationResult(BaseModel):
    """Result payload for policy evaluation."""

    decision: PolicyDecision
    matched_rule_id: str | None = None
    matched_rule_priority: int | None = None
    matched_rule_specificity: int | None = None
    trace: list[str] = Field(default_factory=list)


class PolicyEvaluator:
    """Deterministic policy evaluator with trace output."""

    def evaluate(
        self,
        policy: PolicyConfig,
        request_or_input: ActionRequest | PolicyEvaluationInput,
        risk_level: RiskLevel | None = None,
    ) -> PolicyEvaluationResult:
        if isinstance(request_or_input, ActionRequest):
            if risk_level is None:
                raise ValueError(
                    "risk_level is required when evaluating an ActionRequest"
                )
            eval_input = PolicyEvaluationInput.from_request(request_or_input, risk_level)
        else:
            eval_input = request_or_input

        candidates: list[tuple[int, int, int, PolicyRule]] = []
        trace: list[str] = []

        for idx, rule in enumerate(policy.rules):
            if not rule.enabled:
                trace.append(f"skip:{rule.id}:disabled")
                continue
            if self._matches(rule, eval_input):
                spec = rule.specificity()
                candidates.append((rule.priority, -spec, idx, rule))
                trace.append(
                    f"match:{rule.id}:priority={rule.priority}:specificity={spec}"
                )
            else:
                trace.append(f"skip:{rule.id}:no-match")

        if not candidates:
            trace.append(
                f"default:{policy.defaults.decision.value}:no-matching-rules"
            )
            return PolicyEvaluationResult(
                decision=policy.defaults.decision,
                trace=trace,
            )

        priority, neg_spec, _, rule = min(candidates)
        specificity = -neg_spec
        trace.append(
            f"selected:{rule.id}:priority={priority}:specificity={specificity}"
        )
        return PolicyEvaluationResult(
            decision=rule.decision,
            matched_rule_id=rule.id,
            matched_rule_priority=priority,
            matched_rule_specificity=specificity,
            trace=trace,
        )

    def _matches(self, rule: PolicyRule, data: PolicyEvaluationInput) -> bool:
        if rule.action_types and data.action_type not in rule.action_types:
            return False

        if rule.path_globs and not any(
            fnmatch.fnmatch(data.target, pattern) for pattern in rule.path_globs
        ):
            return False

        if rule.target_contains:
            target_lower = data.target.lower()
            if not any(fragment.lower() in target_lower for fragment in rule.target_contains):
                return False

        if rule.min_risk_level is not None:
            if _risk_severity(data.risk_level) < _risk_severity(rule.min_risk_level):
                return False

        if rule.max_risk_level is not None:
            if _risk_severity(data.risk_level) > _risk_severity(rule.max_risk_level):
                return False

        return True


def load_policy_from_dict(data: dict[str, Any]) -> PolicyConfig:
    """Parse and validate policy data from a dictionary."""
    try:
        return PolicyConfig.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Invalid policy configuration: {exc}") from exc


def load_policy_from_file(path: str | Path) -> PolicyConfig:
    """Load a policy from JSON or YAML file."""
    policy_path = Path(path)
    raw = policy_path.read_text(encoding="utf-8")
    suffix = policy_path.suffix.lower()

    if suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise ValueError("PyYAML is required to parse YAML policy files") from exc
        parsed = yaml.safe_load(raw)
    else:
        parsed = json.loads(raw)

    if not isinstance(parsed, dict):
        raise ValueError("Policy file must deserialize to an object")

    return load_policy_from_dict(parsed)
