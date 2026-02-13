"""Prompt-injection and risky-instruction scanner.

This module is intentionally conservative and bounded:
- Avoids recursive payload walking (prevents recursion-depth crashes).
- Caps the amount of text scanned to reduce CPU abuse risk.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from agent_polis.actions.models import ActionRequest, RiskLevel


class ScanSeverity(str, Enum):
    """Scanner severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_SEVERITY_ORDER = {
    ScanSeverity.LOW: 0,
    ScanSeverity.MEDIUM: 1,
    ScanSeverity.HIGH: 2,
    ScanSeverity.CRITICAL: 3,
}

_SEVERITY_TO_RISK = {
    ScanSeverity.LOW: RiskLevel.LOW,
    ScanSeverity.MEDIUM: RiskLevel.MEDIUM,
    ScanSeverity.HIGH: RiskLevel.HIGH,
    ScanSeverity.CRITICAL: RiskLevel.CRITICAL,
}


def severity_to_risk_level(severity: ScanSeverity) -> RiskLevel:
    """Map scanner severity to action risk level."""
    return _SEVERITY_TO_RISK[severity]


class ScanFinding(BaseModel):
    """A single scanner finding with machine-readable reason ID."""

    reason_id: str = Field(min_length=1)
    severity: ScanSeverity
    message: str = Field(min_length=1)
    field: str = Field(min_length=1)
    snippet: str = Field(min_length=1)


class ScanResult(BaseModel):
    """Scanner result payload."""

    findings: list[ScanFinding] = Field(default_factory=list)

    def max_severity(self) -> ScanSeverity:
        """Return the highest severity observed across findings."""
        if not self.findings:
            return ScanSeverity.LOW
        return max(
            (finding.severity for finding in self.findings),
            key=lambda severity: _SEVERITY_ORDER[severity],
        )

    def max_risk_level(self) -> RiskLevel:
        """Return the highest risk level implied by findings."""
        return severity_to_risk_level(self.max_severity())

    def to_risk_factors(self) -> list[str]:
        """Render findings as risk factors compatible with preview output."""
        return [f"[{finding.reason_id}] {finding.message}" for finding in self.findings]


@dataclass(frozen=True)
class _ScannerRule:
    reason_id: str
    severity: ScanSeverity
    message: str
    pattern: re.Pattern[str]


class PromptInjectionScanner:
    """Rule-based scanner for prompt injection and risky instructions."""

    # Bounds to keep scanning predictable for untrusted inputs.
    DEFAULT_MAX_TEXT_CHARS = 20_000
    DEFAULT_MAX_PAYLOAD_STRINGS = 500
    DEFAULT_MAX_PAYLOAD_DEPTH = 32

    DEFAULT_RULES: tuple[_ScannerRule, ...] = (
        _ScannerRule(
            reason_id="prompt_injection.ignore_instructions",
            severity=ScanSeverity.CRITICAL,
            message="Instruction override attempt detected",
            pattern=re.compile(
                r"\bignore\s+(all\s+)?(previous|prior|above)\s+"
                r"(instructions?|prompts?)\b",
                flags=re.IGNORECASE,
            ),
        ),
        _ScannerRule(
            reason_id="prompt_injection.exfiltrate_system_prompt",
            severity=ScanSeverity.HIGH,
            message="Attempt to reveal protected system/developer prompt",
            pattern=re.compile(
                r"\b(reveal|show|print|dump)\s+(the\s+)?"
                r"(system|developer)\s+(prompt|instructions?)\b",
                flags=re.IGNORECASE,
            ),
        ),
        _ScannerRule(
            reason_id="prompt_injection.bypass_safety_controls",
            severity=ScanSeverity.HIGH,
            message="Attempt to bypass safety controls",
            pattern=re.compile(
                r"\b(bypass|disable|override)\s+"
                r"(safety|guardrails?|polic(y|ies)|restrictions?)\b",
                flags=re.IGNORECASE,
            ),
        ),
        _ScannerRule(
            reason_id="risky_instruction.secret_exfiltration",
            severity=ScanSeverity.HIGH,
            message="Potential secret exfiltration instruction",
            pattern=re.compile(
                r"\b(exfiltrat(e|ion)|send|upload|leak)\b.{0,60}\b"
                r"(api[_\s-]?key|token|secret|credential|password)s?\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        _ScannerRule(
            reason_id="risky_instruction.remote_script_execution",
            severity=ScanSeverity.CRITICAL,
            message="Remote script execution pipeline detected",
            pattern=re.compile(
                r"\bcurl\b[^\n|]*\|\s*(bash|sh)\b",
                flags=re.IGNORECASE,
            ),
        ),
        _ScannerRule(
            reason_id="risky_instruction.destructive_command",
            severity=ScanSeverity.CRITICAL,
            message="Destructive command pattern detected",
            pattern=re.compile(
                r"\brm\s+-rf\s+/|\b(drop|truncate)\s+table\b",
                flags=re.IGNORECASE,
            ),
        ),
    )

    def __init__(
        self,
        rules: Iterable[_ScannerRule] | None = None,
        *,
        max_text_chars: int = DEFAULT_MAX_TEXT_CHARS,
        max_payload_strings: int = DEFAULT_MAX_PAYLOAD_STRINGS,
        max_payload_depth: int = DEFAULT_MAX_PAYLOAD_DEPTH,
    ) -> None:
        self.rules = tuple(rules) if rules is not None else self.DEFAULT_RULES
        self.max_text_chars = max(1, max_text_chars)
        self.max_payload_strings = max(0, max_payload_strings)
        self.max_payload_depth = max(0, max_payload_depth)

    def scan_action_request(self, request: ActionRequest) -> ScanResult:
        """Scan action request inputs and payload metadata."""
        findings: list[ScanFinding] = []
        findings.extend(self.scan_text(request.description, field="description"))
        findings.extend(self.scan_text(request.target, field="target"))

        if request.context:
            findings.extend(self.scan_text(request.context, field="context"))

        findings.extend(self.scan_payload(request.payload))
        return ScanResult(findings=self._dedupe_findings(findings))

    def scan_text(self, text: str, field: str) -> list[ScanFinding]:
        """Scan a text segment and return matching findings."""
        if not text.strip():
            return []

        text_to_scan = text[: self.max_text_chars]

        findings: list[ScanFinding] = []
        for rule in self.rules:
            match = rule.pattern.search(text_to_scan)
            if not match:
                continue
            snippet = match.group(0).strip()[:160]
            findings.append(
                ScanFinding(
                    reason_id=rule.reason_id,
                    severity=rule.severity,
                    message=rule.message,
                    field=field,
                    snippet=snippet,
                )
            )
        return findings

    def scan_payload(self, payload: dict[str, Any]) -> list[ScanFinding]:
        """Scan payload for risky strings in metadata/instructions.

        Uses an explicit stack instead of recursion to avoid recursion-depth crashes.
        """
        findings: list[ScanFinding] = []
        for field, value in self._iter_string_fields(payload, prefix="payload"):
            findings.extend(self.scan_text(value, field=field))
        return findings

    def _iter_string_fields(
        self,
        value: Any,
        prefix: str,
    ) -> Iterable[tuple[str, str]]:
        stack: list[tuple[Any, str, int]] = [(value, prefix, 0)]
        yielded_strings = 0

        while stack:
            current, current_prefix, depth = stack.pop()

            if self.max_payload_depth and depth > self.max_payload_depth:
                continue

            if isinstance(current, str):
                yield current_prefix, current
                yielded_strings += 1
                if self.max_payload_strings and yielded_strings >= self.max_payload_strings:
                    return
                continue

            if isinstance(current, dict):
                # Push in reverse to preserve a stable-ish traversal order.
                for key, nested in reversed(list(current.items())):
                    key_name = str(key)
                    stack.append((nested, f"{current_prefix}.{key_name}", depth + 1))
                continue

            if isinstance(current, list | tuple | set):
                for idx, nested in reversed(list(enumerate(current))):
                    stack.append((nested, f"{current_prefix}[{idx}]", depth + 1))

    def _dedupe_findings(self, findings: list[ScanFinding]) -> list[ScanFinding]:
        deduped: list[ScanFinding] = []
        seen: set[tuple[str, str, str]] = set()

        for finding in findings:
            key = (
                finding.reason_id,
                finding.field,
                finding.snippet.lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(finding)

        return deduped
