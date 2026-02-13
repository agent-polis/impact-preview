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
            },
            {
                "id": "allow-docs-and-tests-low-medium",
                "decision": "allow",
                "priority": 50,
                "action_types": ["file_write", "file_create"],
                "path_globs": ["docs/*", "tests/*"],
                "max_risk_level": "medium",
            },
            {
                "id": "require-approval-shell",
                "decision": "require_approval",
                "priority": 75,
                "action_types": ["shell_command"],
            },
        ],
    },
    "fintech": {
        "version": "preset-fintech-1",
        "defaults": {"decision": "require_approval"},
        "rules": [
            {
                "id": "deny-secrets-and-keys",
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
            },
            {
                "id": "deny-critical-risk",
                "decision": "deny",
                "priority": 5,
                "min_risk_level": "critical",
            },
            {
                "id": "require-approval-db-execute",
                "decision": "require_approval",
                "priority": 10,
                "action_types": ["db_execute"],
            },
            {
                "id": "allow-docs-low",
                "decision": "allow",
                "priority": 50,
                "action_types": ["file_write", "file_create"],
                "path_globs": ["docs/*"],
                "max_risk_level": "low",
            },
        ],
    },
    "games": {
        "version": "preset-games-1",
        "defaults": {"decision": "require_approval"},
        "rules": [
            {
                "id": "deny-secrets-and-keys",
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
            },
            {
                "id": "allow-assets-and-docs-low-medium",
                "decision": "allow",
                "priority": 50,
                "action_types": ["file_write", "file_create"],
                "path_globs": ["assets/*", "docs/*"],
                "max_risk_level": "medium",
            },
            {
                "id": "allow-tests-low-medium",
                "decision": "allow",
                "priority": 55,
                "action_types": ["file_write", "file_create"],
                "path_globs": ["tests/*"],
                "max_risk_level": "medium",
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

