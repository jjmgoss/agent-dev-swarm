# Execution Policy

## Purpose

The execution policy defines the approved command envelope for one bounded task.

The goal is to move approval from individual shell commands to a task-scoped policy.

In the first implementation, the framework does not execute commands. It only loads a policy and determines whether a proposed command would be allowed or refused.

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

## First-Pass Enforcement

The first implementation enforces only these checks:

1. policy file exists
2. policy YAML parses
3. required policy fields are valid
4. proposed working directory is inside an allowed root
5. proposed command matches an allowed command prefix
6. proposed command does not contain a blocked command pattern

The following fields are currently parsed and returned but are not yet enforced:

- `timeout_seconds`
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

## Non-Goals For This Step

This step does not:

- execute shell commands
- retry commands
- capture live command output
- orchestrate workers
- grant unconstrained shell access