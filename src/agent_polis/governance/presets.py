"""Policy preset registry and loader.

Presets are bundled policies intended to make adoption easier across common
environments (startup, fintech, games). They are validated via the policy schema
at load time, so callers get deterministic diagnostics on failure.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agent_polis.governance.policy import PolicyConfig, load_policy_from_dict


class PolicyPresetMetadata(BaseModel):
    """Metadata for downstream UX (selection lists, descriptions)."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


_PRESET_METADATA: dict[str, PolicyPresetMetadata] = {
    "startup": PolicyPresetMetadata(
        id="startup",
        name="Startup",
        description="Balanced defaults for fast-moving teams with basic safety guardrails.",
        tags=["balanced", "general"],
    ),
    "fintech": PolicyPresetMetadata(
        id="fintech",
        name="Fintech",
        description="Stricter defaults for regulated environments (secrets/prod changes).",
        tags=["strict", "regulated"],
    ),
    "games": PolicyPresetMetadata(
        id="games",
        name="Games",
        description="Iterative defaults tuned for content/assets heavy workflows.",
        tags=["iterative", "content"],
    ),
}


_PRESET_POLICIES: dict[str, dict[str, Any]] = {
    "startup": {
        "version": "preset-startup-1",
        "defaults": {"decision": "require_approval"},
        "rules": [
            {
                "id": "deny-secrets-and-keys",
                "description": "Block actions that appear to touch secrets/keys by target heuristics.",
                "decision": "deny",
                "priority": 0,
                "target_contains": [
                    ".env",
                    ".ssh",
                    "id_rsa",
                    "credentials",
                    "secrets",
                    "password",
                    ".pem",
                ],
                "metadata": {
                    "rationale": (
                        "Secrets/key material should never be modified or exfiltrated via agent actions "
                        "without explicit, out-of-band review."
                    ),
                },
            },
            {
                "id": "allow-docs-and-tests-low-medium",
                "description": "Allow low/medium risk edits to docs/tests to keep iteration speed high.",
                "decision": "allow",
                "priority": 50,
                "action_types": ["file_write", "file_create"],
                "path_globs": ["docs/*", "tests/*"],
                "max_risk_level": "medium",
                "metadata": {
                    "rationale": (
                        "Documentation and tests are typically low blast-radius and can be safely "
                        "iterated on with lighter approval."
                    ),
                },
            },
            {
                "id": "require-approval-shell",
                "description": "Require explicit approval for shell commands.",
                "decision": "require_approval",
                "priority": 75,
                "action_types": ["shell_command"],
                "metadata": {
                    "rationale": (
                        "Shell commands can have system-wide side effects and are hard to preview "
                        "safely."
                    ),
                },
            },
        ],
    },
    "fintech": {
        "version": "preset-fintech-1",
        "defaults": {"decision": "require_approval"},
        "rules": [
            {
                "id": "deny-secrets-and-keys",
                "description": "Block actions that appear to touch secrets/keys by target heuristics.",
                "decision": "deny",
                "priority": 0,
                "target_contains": [
                    ".env",
                    ".ssh",
                    "id_rsa",
                    "credentials",
                    "secrets",
                    "password",
                    ".pem",
                    "api_key",
                    "secret_key",
                ],
                "metadata": {
                    "rationale": (
                        "Fintech environments typically treat secrets handling as a regulated control "
                        "surface."
                    ),
                },
            },
            {
                "id": "deny-critical-risk",
                "description": "Deny any action assessed as CRITICAL risk.",
                "decision": "deny",
                "priority": 5,
                "min_risk_level": "critical",
                "metadata": {
                    "rationale": (
                        "Critical-risk changes are not allowed through automated workflows in this "
                        "preset."
                    ),
                },
            },
            {
                "id": "require-approval-db-execute",
                "description": "Require explicit approval for database write operations.",
                "decision": "require_approval",
                "priority": 10,
                "action_types": ["db_execute"],
                "metadata": {
                    "rationale": (
                        "Database writes can cause irreversible data loss or compliance issues."
                    ),
                },
            },
            {
                "id": "allow-docs-low",
                "description": "Allow low-risk documentation edits.",
                "decision": "allow",
                "priority": 50,
                "action_types": ["file_write", "file_create"],
                "path_globs": ["docs/*"],
                "max_risk_level": "low",
                "metadata": {
                    "rationale": (
                        "Documentation updates are safe, but this preset keeps a tighter threshold."
                    ),
                },
            },
        ],
    },
    "games": {
        "version": "preset-games-1",
        "defaults": {"decision": "require_approval"},
        "rules": [
            {
                "id": "deny-secrets-and-keys",
                "description": "Block actions that appear to touch secrets/keys by target heuristics.",
                "decision": "deny",
                "priority": 0,
                "target_contains": [
                    ".env",
                    ".ssh",
                    "id_rsa",
                    "credentials",
                    "secrets",
                    "password",
                    ".pem",
                ],
                "metadata": {
                    "rationale": (
                        "Even in creative workflows, credentials and key material remain sensitive."
                    ),
                },
            },
            {
                "id": "allow-assets-and-docs-low-medium",
                "description": "Allow low/medium risk edits to assets and docs to support iteration.",
                "decision": "allow",
                "priority": 50,
                "action_types": ["file_write", "file_create"],
                "path_globs": ["assets/*", "docs/*"],
                "max_risk_level": "medium",
                "metadata": {
                    "rationale": (
                        "Assets/docs changes are common and usually reversible; allow with medium "
                        "risk cap."
                    ),
                },
            },
            {
                "id": "allow-tests-low-medium",
                "description": "Allow low/medium risk edits to tests.",
                "decision": "allow",
                "priority": 55,
                "action_types": ["file_write", "file_create"],
                "path_globs": ["tests/*"],
                "max_risk_level": "medium",
                "metadata": {
                    "rationale": (
                        "Tests are low blast-radius and should not slow down iteration."
                    ),
                },
            },
        ],
    },
}


def list_policy_presets() -> list[PolicyPresetMetadata]:
    """Return metadata for all bundled policy presets."""
    return sorted(_PRESET_METADATA.values(), key=lambda m: m.id)


def get_policy_preset_metadata(preset_id: str) -> PolicyPresetMetadata:
    """Return metadata for a preset ID."""
    if preset_id not in _PRESET_METADATA:
        available = ", ".join(sorted(_PRESET_METADATA.keys()))
        raise ValueError(f"Unknown preset id '{preset_id}'. Available: {available}")
    return _PRESET_METADATA[preset_id]


def load_policy_preset(preset_id: str) -> PolicyConfig:
    """Load and validate a bundled policy preset by ID."""
    if preset_id not in _PRESET_POLICIES:
        available = ", ".join(sorted(_PRESET_POLICIES.keys()))
        raise ValueError(f"Unknown preset id '{preset_id}'. Available: {available}")
    return load_policy_from_dict(_PRESET_POLICIES[preset_id])
