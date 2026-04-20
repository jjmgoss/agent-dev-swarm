# Execution Policy

## Purpose

The execution policy defines the approved command envelope for one bounded task.

The goal is to move approval from individual shell commands to a task-scoped policy.

The framework now supports two narrow primitives:

- `check-command-policy`, which evaluates a proposed command without running it
- `run-checked-command`, which executes one command only after it has been allowed by policy

## Intended Role

The orchestrator approves a bounded execution lane.

Implementor and worker agents may eventually operate freely inside that lane.

The framework must refuse requests outside the lane and return explicit reasons.

## Suggested Location

The eventual default location is expected to be under the target project, for example:

```text
<project>/.swarm/execution-policy.yaml
```

The first CLI accepts an explicit policy file path.

## Policy Shape

The current policy shape is YAML and uses explicit fields.

Required fields:

- `allowed_roots`
- `allowed_command_prefixes`

Optional fields:

- `blocked_command_patterns`
- `timeout_seconds`
- `max_output_bytes`
- `allow_network`
- `allow_package_install`
- `allow_git_write`

Example:

```yaml
allowed_roots:
  - .
  - tests/fixtures
  - .tmp

allowed_command_prefixes:
  - python -m unittest
  - python -m pytest
  - uv run
  - git status
  - git diff

blocked_command_patterns:
  - git reset --hard
  - git clean -fd
  - rm -rf /

timeout_seconds: 120
max_output_bytes: 200000
allow_network: false
allow_package_install: false
allow_git_write: false
```

## Resolution Rules

- `allowed_roots` are resolved relative to the target project root unless they are absolute paths.
- The candidate `cwd` is resolved relative to the target project root unless it is absolute.
- The policy file path is resolved relative to the target project root unless it is absolute.
- Commands are evaluated as normalized command strings produced from the provided argv tokens.

## Current Enforcement

The current implementation enforces these checks:

1. policy file exists
2. policy YAML parses
3. required policy fields are valid
4. proposed working directory is inside an allowed root
5. proposed command matches an allowed command prefix
6. proposed command does not contain a blocked command pattern
7. `timeout_seconds` is enforced for `run-checked-command` when provided

The following fields are currently parsed and returned but are not yet fully enforced:

- `max_output_bytes`
- `allow_network`
- `allow_package_install`
- `allow_git_write`

## Matching Semantics

- `allowed_command_prefixes` use straightforward normalized string prefix matching.
- `blocked_command_patterns` use straightforward normalized substring matching.

This is intentionally simple and inspectable. The framework may later evolve to richer matching, but the first version should remain easy to audit.

## Result Shape

Policy evaluation should return structured data that includes at least:

- status: `allowed` or `refused`
- project root
- policy path
- proposed cwd
- proposed command
- checks
- explicit refusal reasons

This result is intended to be consumed by an orchestrator without relying on vague terminal prose.

Checked command execution should return structured data that includes at least:

- status: `success`, `failure`, `refused`, or `timeout`
- project root
- policy path
- requested cwd
- resolved cwd
- command argv
- normalized command text
- checks
- errors
- execution performed
- stdout
- stderr
- exit code

If the command is refused, execution must not happen.

If the command is allowed, the framework should execute it synchronously and capture explicit evidence.

If a timeout occurs, the framework should report that explicitly instead of pretending the command exited normally.

## Non-Goals For This Step

This step does not:

- retry commands
- orchestrate workers
- grant unconstrained shell access

This step still does not:

- add multi-step workflows
- add background execution
- add autonomous retries
- add worker orchestration