"""Deterministic CI evaluation mode (no prompts) and report output.

This module is designed for PR gate integrations. It produces a stable,
machine-readable JSON report and exits with deterministic status codes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from agent_polis.actions.analyzer import ImpactAnalyzer
from agent_polis.actions.models import ActionPreview, ActionRequest
from agent_polis.governance.policy import PolicyConfig, PolicyDecision, PolicyEvaluator
from agent_polis.governance.presets import load_policy_preset
from agent_polis.governance.prompt_scanner import PromptInjectionScanner

REPORT_SCHEMA_VERSION = "1"


class CIActionReport(BaseModel):
    """Per-action report entry."""

    index: int = Field(ge=0)
    action_type: str
    target: str
    risk_level: str
    policy_decision: str
    policy_matched_rule_id: str | None = None
    scanner_max_severity: str
    scanner_reason_ids: list[str] = Field(default_factory=list)


class CIReasonCount(BaseModel):
    reason: str
    count: int = Field(ge=1)


class CIPolicyReport(BaseModel):
    """Top-level CI report output."""

    schema_version: Literal["1"] = REPORT_SCHEMA_VERSION
    policy_version: str
    totals: dict[str, int]
    top_blocking_reasons: list[CIReasonCount] = Field(default_factory=list)
    actions: list[CIActionReport] = Field(default_factory=list)


def _decision_exit_code(decisions: list[PolicyDecision]) -> int:
    """
    Stable exit codes for CI integrations.

    - 0: all actions allowed
    - 2: at least one action requires approval
    - 3: at least one action denied
    """
    if any(d == PolicyDecision.DENY for d in decisions):
        return 3
    if any(d == PolicyDecision.REQUIRE_APPROVAL for d in decisions):
        return 2
    return 0


async def generate_ci_report(
    actions: list[ActionRequest],
    policy: PolicyConfig,
    *,
    working_directory: str | None = None,
) -> tuple[CIPolicyReport, int]:
    """Evaluate actions deterministically and return (report, exit_code)."""
    analyzer = ImpactAnalyzer(working_directory=working_directory)
    evaluator = PolicyEvaluator()
    scanner = PromptInjectionScanner()

    action_reports: list[CIActionReport] = []
    decisions: list[PolicyDecision] = []

    # Aggregation for blocking reasons.
    reason_counts: dict[str, int] = {}
    totals = {"allow": 0, "require_approval": 0, "deny": 0}

    for idx, request in enumerate(actions):
        preview: ActionPreview = await analyzer.analyze(request)
        scan = scanner.scan_action_request(request)
        policy_result = evaluator.evaluate(policy, request, risk_level=preview.risk_level)

        decisions.append(policy_result.decision)
        totals[policy_result.decision.value] += 1

        scanner_reason_ids = sorted({f.reason_id for f in scan.findings})

        if policy_result.decision != PolicyDecision.ALLOW:
            policy_reason = (
                f"policy:{policy_result.matched_rule_id}"
                if policy_result.matched_rule_id
                else "policy:default"
            )
            reason_counts[policy_reason] = reason_counts.get(policy_reason, 0) + 1
            for rid in scanner_reason_ids:
                key = f"scanner:{rid}"
                reason_counts[key] = reason_counts.get(key, 0) + 1

        action_reports.append(
            CIActionReport(
                index=idx,
                action_type=request.action_type.value,
                target=request.target,
                risk_level=preview.risk_level.value,
                policy_decision=policy_result.decision.value,
                policy_matched_rule_id=policy_result.matched_rule_id,
                scanner_max_severity=scan.max_severity().value,
                scanner_reason_ids=scanner_reason_ids,
            )
        )

    top_reasons = sorted(
        (CIReasonCount(reason=reason, count=count) for reason, count in reason_counts.items()),
        key=lambda item: (-item.count, item.reason),
    )[:10]

    report = CIPolicyReport(
        policy_version=policy.version,
        totals=totals,
        top_blocking_reasons=top_reasons,
        actions=action_reports,
    )
    return report, _decision_exit_code(decisions)


def _load_actions_from_json(path: str | Path) -> list[ActionRequest]:
    raw = Path(path).read_text(encoding="utf-8")
    payload = json.loads(raw)

    if isinstance(payload, list):
        action_list = payload
    elif isinstance(payload, dict) and isinstance(payload.get("actions"), list):
        action_list = payload["actions"]
    else:
        raise ValueError("Actions file must be a JSON list or an object with an 'actions' list")

    actions: list[ActionRequest] = []
    for idx, item in enumerate(action_list):
        if not isinstance(item, dict):
            raise ValueError(f"Action at index {idx} must be an object")
        actions.append(ActionRequest.model_validate(item))
    return actions


def _write_report(report: CIPolicyReport, output_path: str | None) -> None:
    data = report.model_dump()
    rendered = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if output_path:
        Path(output_path).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="impact-preview-ci", add_help=True)
    parser.add_argument(
        "--actions-file",
        required=True,
        help="Path to JSON file containing a list of ActionRequest objects",
    )
    parser.add_argument(
        "--policy-preset",
        default="startup",
        choices=["startup", "fintech", "games"],
        help="Bundled policy preset to use",
    )
    parser.add_argument(
        "--working-directory",
        default=None,
        help="Base directory for resolving relative paths during analysis",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write JSON report to this path (default: stdout)",
    )

    args = parser.parse_args(argv)

    try:
        actions = _load_actions_from_json(args.actions_file)
        policy = load_policy_preset(args.policy_preset)
        report, exit_code = asyncio.run(
            generate_ci_report(
                actions,
                policy,
                working_directory=args.working_directory,
            )
        )
        _write_report(report, args.output)
        return exit_code
    except Exception as exc:
        # CI consumers need stable failure output.
        error_payload: dict[str, Any] = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "error": str(exc),
        }
        sys.stdout.write(json.dumps(error_payload, indent=2, sort_keys=True) + "\n")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
