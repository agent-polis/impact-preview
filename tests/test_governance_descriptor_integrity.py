"""Tests for MCP descriptor integrity checks and hash pinning."""

import json

import pytest

from agent_polis.governance import (
    DescriptorIntegrityChecker,
    compute_descriptor_hash,
    load_descriptor_integrity_policy_from_dict,
)


def _descriptor_payload() -> dict:
    return {
        "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
        "name": "io.github.agent-polis/impact-preview",
        "description": "Impact preview for AI agents",
        "version": "0.2.2",
        "packages": [
            {
                "registryType": "pypi",
                "identifier": "impact-preview",
                "version": "0.2.2",
                "transport": {"type": "stdio"},
            }
        ],
    }


def test_descriptor_integrity_allows_pinned_allowlist_hash() -> None:
    descriptor = _descriptor_payload()
    descriptor_hash = compute_descriptor_hash(descriptor)
    policy = load_descriptor_integrity_policy_from_dict(
        {"allowlist": {descriptor["name"]: [descriptor_hash]}}
    )
    checker = DescriptorIntegrityChecker()

    result = checker.evaluate(policy=policy, descriptor=descriptor)

    assert result.allowed
    assert result.matched_pin == descriptor_hash
    assert "matched allowlist pin" in result.reason


def test_descriptor_integrity_blocks_tampered_descriptor() -> None:
    descriptor = _descriptor_payload()
    pinned_hash = compute_descriptor_hash(descriptor)
    policy = load_descriptor_integrity_policy_from_dict(
        {"allowlist": {descriptor["name"]: [pinned_hash]}}
    )
    checker = DescriptorIntegrityChecker()

    descriptor["description"] = "Tampered descriptor content"
    result = checker.evaluate(policy=policy, descriptor=descriptor)

    assert not result.allowed
    assert "Descriptor hash mismatch" in result.reason


def test_descriptor_integrity_blocks_missing_allowlist_pin() -> None:
    descriptor = _descriptor_payload()
    policy = load_descriptor_integrity_policy_from_dict({"allowlist": {}})
    checker = DescriptorIntegrityChecker()

    result = checker.evaluate(policy=policy, descriptor=descriptor)

    assert not result.allowed
    assert "No allowlist hash pins configured" in result.reason


def test_descriptor_integrity_reports_explicit_pin_mismatch() -> None:
    descriptor = _descriptor_payload()
    policy = load_descriptor_integrity_policy_from_dict(
        {"allowlist": {descriptor["name"]: [compute_descriptor_hash(descriptor)]}}
    )
    checker = DescriptorIntegrityChecker()
    bad_hash = "sha256:" + ("f" * 64)

    result = checker.evaluate(
        policy=policy,
        descriptor=descriptor,
        expected_hash=bad_hash,
    )

    assert not result.allowed
    assert "Hash pin mismatch" in result.reason


def test_descriptor_integrity_file_evaluation(tmp_path) -> None:
    descriptor = _descriptor_payload()
    descriptor_path = tmp_path / "descriptor.json"
    descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")
    policy = load_descriptor_integrity_policy_from_dict(
        {"allowlist": {descriptor["name"]: [compute_descriptor_hash(descriptor)]}}
    )
    checker = DescriptorIntegrityChecker()

    result = checker.evaluate_file(policy=policy, descriptor_path=descriptor_path)

    assert result.allowed
    assert result.descriptor_name == descriptor["name"]


def test_descriptor_policy_rejects_invalid_hash_pin_format() -> None:
    with pytest.raises(ValueError, match="Invalid hash pin format"):
        load_descriptor_integrity_policy_from_dict(
            {"allowlist": {"io.github.agent-polis/impact-preview": ["not-a-sha"]}}
        )
