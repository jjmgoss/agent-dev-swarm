# Task Specs

## Purpose

Task specs are the first-class data representation of one bounded unit of work.

This primitive is limited to locating, parsing, validating, and returning one task spec. It does not execute the task, derive execution policy, create worker orchestration, or decide task acceptance on its own.

## Default Location

Task specs should live under the target project at:

```text
<project>/.swarm/tasks/
```

The default file naming convention is:

```text
<task-id>.yaml
```

The framework CLI accepts either:

- a task id such as `issue-3`, which resolves to `<project>/.swarm/tasks/issue-3.yaml`
- an explicit absolute or project-relative path to a YAML file

## Required Fields

Every task spec must include:

- `task_id`: non-empty string
- `title`: non-empty string
- `goal`: non-empty string
- `scope`: non-empty list of non-empty strings
- `non_goals`: non-empty list of non-empty strings
- `required_outputs`: non-empty list of non-empty strings
- `success_criteria`: non-empty list of non-empty strings

## Optional Fields

The first version also supports these optional fields:

- `notes`: non-empty string when provided
- `allowed_roots`: list of non-empty strings when provided
- `suggested_commands`: list of non-empty strings when provided
- `verification_commands`: list of non-empty strings when provided
- `implementation_record_path`: non-empty string when provided

Optional list fields may be empty, but if entries are present they must be non-empty strings.

## What The Primitive Does

`load-task-spec` performs these checks in order:

1. resolve the task id or path to one file
2. verify that the file exists
3. parse the YAML
4. require a top-level mapping
5. require the known required fields
6. validate required strings and required string lists
7. validate optional fields if they are present
8. return a structured result and a concise terminal summary

## What The Primitive Does Not Do

This primitive does not:

- execute the task
- run suggested or verification commands
- infer execution policy
- create implementation records automatically
- orchestrate workers
- decompose the task into subtasks

## Structured Result Shape

The structured result includes at least:

- `status`
- `project_root`
- `task_path`
- `task_id` when available
- `checks`
- `errors`
- `parsed_task` when validation succeeds

Each check includes:

- `name`
- `status`
- `message`

## Example Task Spec

```yaml
task_id: issue-3
title: Add task-spec loading contract
goal: Load and validate one bounded task spec from .swarm/tasks.

scope:
  - Add a task-spec loader and validator.
  - Expose a CLI command for text and JSON output.

non_goals:
  - Do not execute the task.
  - Do not add worker orchestration.

required_outputs:
  - Structured task load result.
  - CLI text summary.

success_criteria:
  - The task spec loads successfully.
  - Invalid task specs fail with explicit reasons.

verification_commands:
  - python -m unittest discover -s tests -v

implementation_record_path: .swarm/implementation-records/issue-3-load-task-spec.md
```

See `docs/examples/task-spec-example.yaml` for a reference example kept in this repo.