# Sandbox

## Purpose

The sandbox is the first in-repo self-exercise surface for `agent-dev-swarm`.

It exists so the framework can be exercised inside its own repository without granting broad write access to the whole repo or pretending that an ordinary folder is a safe test boundary.

This first slice defines a disposable scenario system, not a full runtime.

The sandbox is designed to be:

- disposable
- reproducible
- scenario-driven
- observable
- low-side-effect
- compatible with later containerized execution

## Why The Sandbox Lives Here

The framework maturity path is intentionally staged:

- `agent-dev-swarm` is the bounded self-exercise environment
- `hn-trends-tracker` is the later staging environment for more realistic constrained trials
- broader repos come later

That means `agent-dev-swarm` needs an internal place where future workers can operate on small, disposable objects instead of the whole framework repo.

## Core Separation

The sandbox separates reusable scenario definitions from ephemeral run outputs.

Stable fixture definitions live under:

```text
sandbox/fixtures/<fixture-name>/
```

Disposable run outputs live under:

```text
sandbox/runs/<run-id>/
```

This keeps hand-authored fixture content clean while making run-specific outputs easy to wipe and recreate.

## Initial Directory Layout

The first slice uses this shape:

```text
sandbox/
  fixtures/
    tiny-calculator/
      fixture.yaml
      project/
        README.md
        src/
        tests/
        .swarm/
  runs/
    <run-id>/
      run-info.json
      workspace/
      artifacts/
        task-input/
        policy-input/
        handoff/
        commands/
        worker-result/
        adjudication/
        implementation-record/
        summary/
```

The `workspace/` directory is the materialized copy of the reusable fixture.

The `artifacts/` directory is reserved for per-run outputs. The first slice only scaffolds those directories so later issues have a stable place to store structured results.

## Fixture Manifest

Each fixture has a small YAML manifest at:

```text
sandbox/fixtures/<fixture-name>/fixture.yaml
```

The first version requires these fields:

- `fixture_id`
- `description`
- `layout_version`
- `source_root`
- `materialized_paths`
- `editable_paths`
- `read_only_paths`
- `generated_paths`
- `intended_outcome`

It also supports these optional fields:

- `default_task_spec`
- `default_policy`

The manifest is intentionally small. It does not try to describe a complete orchestration runtime.

## Mutability Zones

The first slice records mutability metadata explicitly in the manifest.

- `editable_paths` mark workspace paths intended for agent edits.
- `read_only_paths` mark reference material that should stay unchanged during a bounded run.
- `generated_paths` mark directories intended for generated in-workspace outputs.

The current implementation validates and records these zones but does not yet enforce file permissions or container boundaries from them.

## Materialization And Reset

The first sandbox command is:

```text
swarm materialize-sandbox-run --fixture <name> --run-id <id>
```

This command:

- locates the fixture
- validates the fixture manifest
- creates a run directory under `sandbox/runs/<run-id>/`
- copies only the declared fixture content into `workspace/`
- creates a standard artifact scaffold under `artifacts/`
- writes `run-info.json` so the run records which fixture and manifest were used

If the run directory already exists, the command refuses by default.

To recreate a run deterministically, use:

```text
swarm materialize-sandbox-run --fixture <name> --run-id <id> --force-reset
```

That wipes the existing run directory and materializes it again from the fixture manifest.

## Supervised Run Scaffold

After a sandbox run exists, the next narrow setup step is:

```text
swarm scaffold-supervised-run --run-id <id> --worker-role <role>
```

This command does not execute the task.

It only prepares the next stable artifact set for one bounded supervised attempt by:

- reading `run-info.json`
- resolving the default or explicit task spec
- resolving the default or explicit policy reference when available
- building the worker handoff payload
- creating a starter worker-result payload
- writing a run-plan artifact that records what the run is about

The current artifact outputs are:

- `artifacts/task-input/task-spec.json`
- `artifacts/policy-input/policy-reference.json`
- `artifacts/handoff/worker-handoff.json`
- `artifacts/worker-result/worker-result-starter.json`
- `artifacts/summary/run-plan.json`

The starter worker-result payload is intentionally incomplete but structurally valid.

It prefills:

- `task_id`
- `worker_role`
- `required_outputs_status` item names
- `success_criteria_status` item names

It leaves evidence-bearing fields empty and uses placeholder summary text instead of inventing work that did not happen.

If those artifact files already exist, the scaffold refuses by default. Use `--force-overwrite` to regenerate them explicitly.

## Replayability

This first slice supports replayability in a narrow, explicit way:

- fixture identity is recorded
- run identity is explicit
- manifest path is recorded
- default task and policy references are preserved when present
- artifact directories are created in stable locations

That is enough to rerun the same fixture with the same run id after a reset and compare the resulting workspace and later artifacts.

## Example Fixture

The example fixture is `tiny-calculator`.

It is intentionally small:

- one tiny Python module
- one tiny test file
- one task spec
- one execution policy
- explicit mutability metadata

It is meant to prove the shape of the sandbox system, not to simulate a realistic full project yet.

## Isolation Scope In This Issue

This issue does not fully solve runtime isolation.

It only establishes the shape needed for later isolation work:

- fixtures are separate from run outputs
- runs are disposable
- materialization is deterministic
- mutability metadata exists
- the layout is easy to mount into a future disposable container

## Deferred Work

This first slice does not yet:

- run sandbox tasks automatically
- enforce read-only versus editable zones at the filesystem level
- capture every artifact automatically
- start containers
- add network controls
- scrub environment variables
- manage background processes
- implement a full workflow engine

The supervised run scaffold also does not yet:

- execute commands automatically
- fill worker-result evidence automatically
- adjudicate automatically
- write implementation records automatically

Those are later steps. The goal here is to establish a clean disposable scenario system that later work can build on.