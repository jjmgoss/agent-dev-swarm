# Handoff And Adjudication

## Purpose

This document defines the first explicit control loop contract in `agent-dev-swarm`:

task spec
-> worker handoff payload
-> worker result payload
-> adjudication decision

This slice is contract-driven and file-based. It does not add a live orchestrator runtime, model-provider APIs, or autonomous execution.

## Worker Input Contract

The orchestrator derives one normalized worker handoff payload from one validated task spec.

The first version uses:

- `task_id`
- `title`
- `goal`
- `scope`
- `non_goals`
- `required_outputs`
- `success_criteria`
- `project_root`
- `worker_role`
- `expected_result_fields`

Optional fields carried through when present:

- `notes`
- `allowed_roots`
- `suggested_commands`
- `verification_commands`
- `implementation_record_path`
- `policy_reference`
- `handoff_version`

The handoff is intentionally declarative. It tells the worker what bounded task it is being asked to complete and what result shape it must return.

## Worker Output Contract

The worker result payload is a JSON object.

Required fields:

- `task_id`: non-empty string
- `worker_role`: non-empty string
- `status`: one of `success`, `failure`, `partial`, `blocked`
- `summary`: non-empty string
- `actions_performed`: list of strings
- `files_read`: list of strings
- `files_changed`: list of strings
- `commands_run`: list of strings
- `command_results`: list of command result objects
- `verification_status`: one of `not_run`, `passed`, `failed`, `mixed`
- `required_outputs_status`: non-empty list of output status objects
- `success_criteria_status`: non-empty list of success-criteria status objects
- `unresolved_issues`: list of strings
- `escalation_notes`: list of strings

### Command Result Objects

Each `command_results` entry must include:

- `command`: non-empty string
- `outcome`: one of `success`, `failure`, `refused`, `timeout`, `not_run`

Optional command result fields:

- `exit_code`: integer
- `summary`: non-empty string
- `evidence_ref`: non-empty string

### Output And Criteria Status Objects

Each `required_outputs_status` and `success_criteria_status` entry must include:

- `name`: non-empty string
- `status`: one of `satisfied`, `missing`, `partial`, `not_evaluated`

Optional field:

- `details`: non-empty string

`success_criteria_status` is required in this first contract even though earlier notes only implied it. The adjudication loop needs an explicit success-criteria signal to stay deterministic.

## Adjudication Decision Contract

The adjudicator validates the worker result payload before making any decision.

The adjudication output includes:

- `task_id`
- `decision`
- `reason`
- `status`
- `required_outputs_satisfied`
- `success_criteria_satisfied`
- `unresolved_issues_present`
- `escalation_requested`
- `next_action`

`decision` must be one of:

- `accept`
- `reject`
- `retry`
- `escalate`

## Deterministic Decision Rules

### Accept

Use `accept` when all of the following are true:

- worker result `status` is `success`
- every `required_outputs_status` entry is `satisfied`
- every `success_criteria_status` entry is `satisfied`
- `unresolved_issues` is empty
- `escalation_notes` is empty

### Reject

Use `reject` when the worker result payload is invalid or cannot be trusted as a bounded completion artifact.

Examples:

- required fields are missing
- field types are wrong
- enum values are invalid
- the JSON file is missing or malformed

### Retry

Use `retry` when the payload is valid but the bounded task is not complete and no escalation is requested.

Examples:

- worker result status is `failure` or `partial`
- required outputs are not yet satisfied
- success criteria are not yet satisfied
- unresolved issues remain, but the worker did not request escalation

### Escalate

Use `escalate` when either of these is true:

- worker result `status` is `blocked`
- `escalation_notes` is non-empty

This keeps escalation explicit and avoids hidden decision heuristics.

## CLI Surfaces

### Build Worker Handoff

```text
swarm build-worker-handoff --project <path> --task <id-or-path> --worker-role <role>
```

This command:

- loads and validates the task spec
- builds the normalized worker handoff payload
- returns text or JSON output

### Adjudicate Worker Result

```text
swarm adjudicate-worker-result --input <worker-result.json>
```

This command:

- reads a worker result JSON file
- validates the payload
- returns an adjudication decision with explicit reasons

Exit behavior for this first version:

- `build-worker-handoff`: exit `0` on success, nonzero on failure
- `adjudicate-worker-result`: exit `0` for `accept`, `retry`, or `escalate`; exit nonzero for `reject`

## Non-Goals

This contract does not:

- run the worker
- call model providers
- create autonomous loops
- infer execution policy automatically
- execute suggested or verification commands
- replace human or orchestrator review

## Reference Examples

- `docs/examples/worker-handoff-example.json`
- `docs/examples/worker-result-example.json`
- `docs/examples/adjudication-result-example.json`