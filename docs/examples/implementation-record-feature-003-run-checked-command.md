# Implementation Record

- Record ID: feature-003-run-checked-command
- Task/Issue ID: feature-003-run-checked-command
- Title: Add checked command execution behind execution policy
- Created At (UTC): 2026-04-20T00:00:00Z
- Updated At (UTC): 2026-04-20T00:00:00Z
- Verification Status: passed
- Final Status: accept

## Goal

Execute one proposed command only after policy approval and return explicit structured evidence about the execution result.

## Scope

- Add a checked-command execution surface to the CLI.
- Reuse policy evaluation before any subprocess call.
- Capture stdout, stderr, exit code, and timeout behavior in structured output.
- Cover success, refusal, failure, and timeout paths with unit tests.

## Non-Goals

- Do not add autonomous retries.
- Do not add background execution.
- Do not add multi-step workflows or worker orchestration.

## Files Changed

- src/agent_dev_swarm/cli.py
- src/agent_dev_swarm/execution_policy.py
- docs/execution-policy.md
- specs/002-check-command-policy.yaml
- specs/003-run-checked-command.yaml
- tests/test_execution_policy.py
- tests/test_run_checked_command.py

## Structured Evidence

- Embedded excerpt from the current checked-command result shape:

```json
{
  "status": "success",
  "command_text": "python -c print('hello from checked command')",
  "execution_performed": true,
  "exit_code": 0,
  "timed_out": false
}
```

- Unit coverage for refusal, failure, and timeout cases is captured in `tests/test_execution_policy.py` and `tests/test_run_checked_command.py`.

## Commands Run

### Command 1

- Command: python -m unittest discover -s tests -v
- Purpose: Verify the execution-policy and checked-command flows end to end through the current unit suite.
- Outcome: success
- Evidence: The suite covers allow, refuse, failure, timeout, text output, and JSON output paths for the checked-command surfaces.

## Observed Results

- The CLI exposes both `check-command-policy` and `run-checked-command`.
- Policy evaluation happens before subprocess execution.
- Refused commands do not execute.
- Successful commands capture stdout and exit code 0.
- Failing commands preserve stdout, stderr, and the child exit code.
- Timeout is reported explicitly rather than being treated as a normal failure.

## Unresolved Issues

- Saved JSON evidence files are not yet written automatically by the framework; callers must persist structured outputs themselves when needed.

## Escalation Notes

- None.