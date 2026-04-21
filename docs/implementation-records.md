# Implementation Records

## Purpose

Implementation records are the lightweight audit trail for one bounded piece of agent work.

They complement structured command evidence such as `validate-project`, `check-command-policy`, and `run-checked-command` results. They do not replace those artifacts. The record is the human-readable summary that explains what the task intended to do, what changed, what was verified, and whether the result should be accepted, retried, or escalated.

## Default Location

For a repo using `agent-dev-swarm`, implementation records should live under:

```text
<project>/.swarm/implementation-records/
```

Recommended file naming:

```text
YYYYMMDD-<task-id>-<short-title>.md
```

This keeps records local to the repo and adjacent to other `.swarm` artifacts.

The template and example in this framework repo live under `docs/` only as reference material. They are not the recommended runtime location for project records.

## When To Create A Record

Create one record for each bounded task that does at least one of the following:

- changes tracked files
- runs verification intended to support accept or reject decisions
- produces structured framework evidence that an orchestrator or reviewer should inspect later
- ends with unresolved issues or escalation notes that need a durable handoff

Do not create a record for trivial read-only exploration with no durable outcome.

## Required Fields

Every implementation record must include these fields or sections:

- `Record ID`
- `Task/Issue ID`
- `Title`
- `Created At (UTC)`
- `Updated At (UTC)`
- `Goal`
- `Scope`
- `Non-Goals`
- `Files Changed`
- `Structured Evidence`
- `Commands Run`
- `Observed Results`
- `Verification Status`
- `Unresolved Issues`
- `Escalation Notes`
- `Final Status`

## Optional Fields

These fields are useful but not required for the first convention:

- implementer or reviewer name
- commit hash or branch name
- diff summary
- follow-up tasks
- links to external issue trackers
- embedded JSON excerpts when a separate evidence file would be too heavy

## Status Semantics

`Verification Status` should use one of:

- `not_run`
- `passed`
- `failed`
- `mixed`

`Final Status` should use one of:

- `in_progress`: the record is still being filled out
- `accept`: the bounded task appears complete and evidence supports acceptance
- `retry`: the bounded task is incomplete or failed and should be repeated or revised
- `escalate`: the worker cannot safely complete the task without higher-level direction

## Structured Evidence

Implementation records should reference or embed structured evidence from framework commands instead of duplicating long terminal logs.

Preferred pattern:

1. Run the framework command with structured output when available.
2. Store the JSON result as a normal file when the output is substantial or likely to be reviewed later.
3. Reference that file from the `Structured Evidence` section.
4. In `Commands Run`, summarize the purpose and outcome of the command.

Examples of acceptable evidence references:

- path to a saved JSON file under `.swarm/evidence/`
- short embedded JSON excerpt for a small result
- a direct reference to a framework-generated result object captured in a test fixture

The implementation record should summarize why the evidence matters. It should not paste full command logs unless the logs are short and materially important.

## Unresolved Issues And Escalation

`Unresolved Issues` should list concrete remaining problems, ambiguities, or follow-up items.

Each unresolved issue should be specific enough that a reviewer can decide whether the task should be accepted, retried, or escalated.

`Escalation Notes` should only capture the decision or clarification that is needed from an orchestrator, maintainer, or reviewer. If no escalation is needed, write `None.` rather than leaving the section blank.

## Recommended Shape

Use the template at `docs/templates/implementation-record.md` as the base shape.

The sections should stay short and factual:

- goal and boundary first
- evidence and commands in the middle
- unresolved and escalation handling at the end

## Scaffolding Helper

The framework provides a narrow helper that writes a starter record file and nothing more:

```text
swarm init-implementation-record \
  --issue 2 \
  --title "Define implementation record convention" \
  --goal "Add a lightweight implementation record convention and starter scaffolding" \
  --output .swarm/implementation-records/20260420-issue-2-implementation-record-convention.md
```

The helper does not inspect git state, infer evidence, or decide the task outcome. It only creates a correctly shaped Markdown starter file from explicit inputs.

## Reference Files

- Template: `docs/templates/implementation-record.md`
- Example: `docs/examples/implementation-record-feature-003-run-checked-command.md`