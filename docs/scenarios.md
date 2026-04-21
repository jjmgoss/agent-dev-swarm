# Scenarios

## Purpose

Scenarios are the first convenience layer above the sandbox and supervised-run primitives.

They let the repo define one bounded self-exercise flow once and then trigger it with one command such as:

```text
swarm run-scenario scenario-1
```

The first version is intentionally narrow:

- one scenario registry in the repo
- one local-only provider path
- one provider adapter: Ollama
- one bounded run attempt per invocation
- stable artifacts for review

## Registry Location

Tracked scenario manifests live under:

```text
scenarios/
```

The first example scenario is:

```text
scenarios/scenario-1.yaml
```

## Scenario Manifest

The first version requires these fields:

- `scenario_id`
- `description`
- `scenario_version`
- `fixture`
- `worker_role`
- `provider`
- `model`
- `allow_remote_models`
- `reset_before_run`
- `expected_outcome`

Optional fields:

- `task`
- `policy`
- `run_id_prefix`
- `notes`
- `context_files`
- `timeout_seconds`

The scenario manifest is repo configuration. It is not derived from the VS Code model picker or any editor UI state.

## Local-Only Boundary

The first runner only supports:

- `provider: ollama`
- `allow_remote_models: false`

If a scenario requests a different provider, or allows remote models, the runner fails clearly.

It does not:

- silently switch providers
- route to cloud
- use whatever model happened to be selected in the editor UI

That local-only boundary is explicit in the scenario manifest and enforced by runner code.

## Runner Flow

`run-scenario` performs these steps in order:

1. load and validate the scenario manifest
2. enforce local-only provider configuration
3. materialize or reset the configured sandbox fixture
4. scaffold the supervised run
5. read the generated worker handoff and starter worker-result artifacts
6. build a bounded prompt for the local worker model
7. invoke the local Ollama model once, synchronously
8. capture the raw model output into the run artifacts
9. attempt to extract a worker-result JSON candidate when possible
10. stop in a reviewable state

## Produced Artifacts

In addition to the sandbox and supervised-run artifacts, the scenario runner writes:

- `artifacts/commands/worker-prompt.txt`
- `artifacts/commands/worker-invocation.json`
- `artifacts/worker-result/raw-model-output.txt`
- `artifacts/worker-result/worker-result.json` when a valid candidate can be extracted
- `artifacts/summary/scenario-run-summary.json`

If the local model output does not parse into a valid worker-result payload, the raw output is still captured and the original starter artifact remains available for review.

## What The First Version Does Not Automate

This runner does not yet:

- apply file edits automatically
- execute verification commands automatically
- adjudicate automatically
- write implementation records automatically
- support remote providers
- support multi-worker orchestration

The goal is to make the first local-only sandbox self-exercise easy to start, not to build the full future swarm runtime.