# CI Mode

`impact-preview-ci` provides a deterministic, non-interactive evaluator for CI gate integrations.

It consumes a list of `ActionRequest` objects, evaluates risk + scanner findings, applies a policy,
and emits a machine-readable JSON report with stable exit codes.

## Inputs

`--actions-file` must be JSON in one of these forms:

1) A list of `ActionRequest` objects
2) An object with an `"actions"` list

Example:

```json
{
  "actions": [
    {
      "action_type": "file_write",
      "description": "Update config",
      "target": "src/app.py",
      "payload": {"content": "print('hello')"},
      "context": "Requested by agent planning step",
      "auto_approve_if_low_risk": false
    }
  ]
}
```

## Policies / Presets

Use `--policy-preset` to select a bundled preset:

- `startup`: balanced defaults
- `fintech`: strict defaults (denies critical-risk actions)
- `games`: iterative defaults (allows low/medium asset changes)

## Outputs

By default, the report is written to stdout. Use `--output` to write a file.

Report schema: `docs/CI_REPORT_SCHEMA.md`.

## Exit Codes

- `0`: all actions `allow`
- `2`: at least one action `require_approval`
- `3`: at least one action `deny`
- `4`: invalid input / unexpected error (error JSON is printed)

## GitHub Actions Example

```yaml
name: Impact Preview Gate

on:
  pull_request:

jobs:
  impact-preview:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install impact-preview
        run: pip install impact-preview

      - name: Run CI evaluation
        run: |
          impact-preview-ci \\
            --actions-file .ci/actions.json \\
            --policy-preset fintech \\
            --working-directory . \\
            --output impact-preview-report.json

      - name: Upload report artifact
        uses: actions/upload-artifact@v4
        with:
          name: impact-preview-report
          path: impact-preview-report.json
```

