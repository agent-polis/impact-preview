# CI Report Schema (v1)

This document defines the machine-readable JSON report emitted by `impact-preview-ci`.

## Versioning

- `schema_version`: `"1"` (string)

Any incompatible change must bump `schema_version`.

## Top-Level Shape

```json
{
  "schema_version": "1",
  "policy_version": "preset-startup-1",
  "totals": {
    "allow": 0,
    "require_approval": 0,
    "deny": 0
  },
  "top_blocking_reasons": [
    {"reason": "policy:deny-critical-risk", "count": 2},
    {"reason": "scanner:prompt_injection.ignore_instructions", "count": 1}
  ],
  "actions": [
    {
      "index": 0,
      "action_type": "file_write",
      "target": "src/app.py",
      "risk_level": "critical",
      "policy_decision": "deny",
      "policy_matched_rule_id": "deny-critical-risk",
      "scanner_max_severity": "critical",
      "scanner_reason_ids": ["prompt_injection.ignore_instructions"]
    }
  ]
}
```

## Exit Codes

`impact-preview-ci` uses stable exit codes:

- `0`: all actions `allow`
- `2`: at least one action `require_approval`
- `3`: at least one action `deny`
- `4`: invalid input / unexpected error (an error JSON payload is printed)

