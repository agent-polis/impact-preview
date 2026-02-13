"""MCP descriptor integrity checks with hash pinning and allowlist enforcement."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

_HASH_PREFIX = "sha256:"
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def normalize_hash_pin(pin: str) -> str:
    """Normalize and validate a descriptor hash pin as `sha256:<hex>`."""
    value = pin.strip().lower()
    if value.startswith(_HASH_PREFIX):
        value = value[len(_HASH_PREFIX):]
    if not _HASH_RE.fullmatch(value):
        raise ValueError(
            "Invalid hash pin format; expected a 64-character SHA-256 hex digest"
        )
    return f"{_HASH_PREFIX}{value}"


def canonicalize_descriptor(descriptor: Mapping[str, Any]) -> str:
    """Serialize descriptor to deterministic JSON used for hashing."""
    try:
        return json.dumps(
            descriptor,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    except TypeError as exc:
        raise ValueError(
            "Descriptor contains non-JSON-serializable values"
        ) from exc


def compute_descriptor_hash(descriptor: Mapping[str, Any]) -> str:
    """Compute canonical SHA-256 hash for a descriptor payload."""
    canonical = canonicalize_descriptor(descriptor)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{_HASH_PREFIX}{digest}"


class DescriptorIntegrityPolicy(BaseModel):
    """Policy controlling descriptor integrity validation behavior."""

    allowlist: dict[str, set[str]] = Field(default_factory=dict)
    fail_closed: bool = Field(default=True)
    enforce_allowlist: bool = Field(default=True)

    @field_validator("allowlist", mode="before")
    @classmethod
    def validate_allowlist(cls, value: Any) -> dict[str, set[str]]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("allowlist must be an object of descriptor-name -> hash pins")

        normalized: dict[str, set[str]] = {}
        for name, pins in value.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("allowlist descriptor names must be non-empty strings")

            if isinstance(pins, str):
                pin_values = [pins]
            elif isinstance(pins, list | set | tuple):
                pin_values = list(pins)
            else:
                raise ValueError(
                    f"allowlist entry for '{name}' must be a string or list of strings"
                )

            normalized[name.strip()] = {
                normalize_hash_pin(str(pin)) for pin in pin_values
            }

        return normalized


class DescriptorIntegrityResult(BaseModel):
    """Result payload for descriptor integrity evaluation."""

    allowed: bool
    descriptor_name: str | None = None
    descriptor_hash: str
    matched_pin: str | None = None
    reason: str


class DescriptorIntegrityChecker:
    """Evaluate descriptor integrity using explicit pins and allowlist."""

    def evaluate(
        self,
        policy: DescriptorIntegrityPolicy,
        descriptor: Mapping[str, Any],
        expected_hash: str | None = None,
    ) -> DescriptorIntegrityResult:
        descriptor_name_obj = descriptor.get("name")
        descriptor_name = (
            descriptor_name_obj.strip()
            if isinstance(descriptor_name_obj, str) and descriptor_name_obj.strip()
            else None
        )
        descriptor_hash = compute_descriptor_hash(descriptor)

        normalized_expected: str | None = None
        if expected_hash is not None:
            normalized_expected = normalize_hash_pin(expected_hash)
            if descriptor_hash != normalized_expected:
                return DescriptorIntegrityResult(
                    allowed=False,
                    descriptor_name=descriptor_name,
                    descriptor_hash=descriptor_hash,
                    reason=(
                        f"Hash pin mismatch: expected {normalized_expected}, "
                        f"got {descriptor_hash}"
                    ),
                )

        if policy.enforce_allowlist:
            if descriptor_name is None:
                return DescriptorIntegrityResult(
                    allowed=False,
                    descriptor_name=None,
                    descriptor_hash=descriptor_hash,
                    reason="Descriptor is missing required 'name'; cannot enforce allowlist",
                )

            allowed_hashes = policy.allowlist.get(descriptor_name, set())
            if not allowed_hashes:
                return DescriptorIntegrityResult(
                    allowed=False,
                    descriptor_name=descriptor_name,
                    descriptor_hash=descriptor_hash,
                    reason=(
                        f"No allowlist hash pins configured for descriptor "
                        f"'{descriptor_name}'"
                    ),
                )

            if descriptor_hash not in allowed_hashes:
                pins = ", ".join(sorted(allowed_hashes))
                return DescriptorIntegrityResult(
                    allowed=False,
                    descriptor_name=descriptor_name,
                    descriptor_hash=descriptor_hash,
                    reason=(
                        f"Descriptor hash mismatch for '{descriptor_name}': "
                        f"expected one of [{pins}], got {descriptor_hash}"
                    ),
                )

            return DescriptorIntegrityResult(
                allowed=True,
                descriptor_name=descriptor_name,
                descriptor_hash=descriptor_hash,
                matched_pin=descriptor_hash,
                reason=f"Descriptor hash matched allowlist pin for '{descriptor_name}'",
            )

        if normalized_expected is not None:
            return DescriptorIntegrityResult(
                allowed=True,
                descriptor_name=descriptor_name,
                descriptor_hash=descriptor_hash,
                matched_pin=normalized_expected,
                reason="Descriptor hash matched explicit pin",
            )

        if policy.fail_closed:
            return DescriptorIntegrityResult(
                allowed=False,
                descriptor_name=descriptor_name,
                descriptor_hash=descriptor_hash,
                reason=(
                    "No integrity pin could be validated "
                    "(allowlist enforcement disabled and no expected hash provided)"
                ),
            )

        return DescriptorIntegrityResult(
            allowed=True,
            descriptor_name=descriptor_name,
            descriptor_hash=descriptor_hash,
            reason="Descriptor integrity checks skipped by policy configuration",
        )

    def evaluate_file(
        self,
        policy: DescriptorIntegrityPolicy,
        descriptor_path: str | Path,
        expected_hash: str | None = None,
    ) -> DescriptorIntegrityResult:
        path = Path(descriptor_path)
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Descriptor file must deserialize to an object")
        return self.evaluate(policy=policy, descriptor=payload, expected_hash=expected_hash)


def load_descriptor_integrity_policy_from_dict(
    data: dict[str, Any],
) -> DescriptorIntegrityPolicy:
    """Parse descriptor integrity policy from a dictionary."""
    try:
        return DescriptorIntegrityPolicy.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Invalid descriptor integrity policy: {exc}") from exc


def load_descriptor_integrity_policy_from_file(path: str | Path) -> DescriptorIntegrityPolicy:
    """Load descriptor integrity policy from JSON or YAML file."""
    policy_path = Path(path)
    raw = policy_path.read_text(encoding="utf-8")
    suffix = policy_path.suffix.lower()

    if suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise ValueError(
                "PyYAML is required to parse YAML descriptor policy files"
            ) from exc
        parsed = yaml.safe_load(raw)
    else:
        parsed = json.loads(raw)

    if not isinstance(parsed, dict):
        raise ValueError("Descriptor policy file must deserialize to an object")

    return load_descriptor_integrity_policy_from_dict(parsed)
