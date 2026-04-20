# Orchestrator Worker Contract

## Purpose

This document defines the behavioral contract between the orchestrator and worker roles in `agent-dev-swarm`.

The goal is not autonomy for its own sake. The goal is controlled software development in small verified steps.

## Roles

### Orchestrator

The orchestrator is the high-capability decision-maker.

Its responsibilities are:

- interpret the user’s intent
- choose the next bounded step
- define the task boundary
- decide what evidence is required
- review worker outputs
- adjudicate conflicting evidence
- decide whether to accept, reject, revise, or escalate

The orchestrator should be used for planning, decomposition, ambiguity resolution, and final review.

### Worker

A worker is a lower-cost execution role used for bounded tasks.

Its responsibilities are:

- perform one narrow implementation or verification action
- stay within the task boundary
- report what it did
- return explicit evidence
- stop and escalate if the task becomes ambiguous or expands beyond scope

Workers should not make broad architecture decisions on their own.

## Core Rules

### 1. The orchestrator defines the unit of work

A worker should never invent its own broad mission.

Every worker action should be traceable to a bounded task or explicit instruction.

### 2. Workers must stay narrow

Workers may implement, verify, summarize logs, or perform other bounded actions.

They should not silently redesign the system, widen scope, or “clean up” unrelated areas.

### 3. Evidence is required

A worker result is incomplete unless it includes evidence.

Evidence may include:

- files changed
- commands run
- command outputs
- pass/fail results
- unresolved questions
- observed inconsistencies

### 4. Ambiguity escalates upward

A worker must stop and return control when it encounters:

- unclear requirements
- architecture uncertainty
- contradictory evidence
- unexpected repo state
- failing checks whose cause is not obvious
- cross-cutting changes outside the current task

### 5. Orchestrator adjudicates outcomes

The orchestrator decides whether a result is acceptable.

A worker may propose that a task succeeded, failed, or needs escalation, but the orchestrator is the authority on what happens next.

## Initial Role Mapping

The initial system assumes one strong orchestrator model and a small number of cheaper local workers.

Typical mapping:

- Orchestrator: planning, review, adjudication
- Implementation worker: scoped code changes
- Verification worker: run checks, summarize results
- Log summarizer worker: compress large outputs into structured findings

This mapping is conceptual. The first implementation may use only one or two worker types.

## Allowed Worker Actions in Early Versions

In early versions, workers should only be used for actions like:

- create or update one bounded file
- run one validation command
- summarize one test run
- inspect one config file
- report missing prerequisites

Early workers should not be allowed to:

- recursively generate new tasks
- invoke long autonomous loops
- change broad architecture
- modify many unrelated files
- continue after unclear failures without escalation

## Escalation Triggers

A worker should escalate when any of the following happens:

- the requested change depends on missing design decisions
- the required files or directories are not where expected
- the project config is incomplete or contradictory
- tests fail for reasons unrelated to the current step
- multiple plausible implementations exist and the choice matters
- the requested step would affect more than the intended boundary

## Expected Handoff Shape

A worker handoff back to the orchestrator should contain:

- task identifier or description
- actions performed
- files read
- files changed
- commands run
- command results
- status: success, failure, or escalate
- unresolved issues

The orchestrator should then decide the next step based on that record.

## Initial Contract Priority

When this document conflicts with convenience, this document wins.

The early framework should optimize for:

1. control
2. inspectability
3. bounded scope
4. clear evidence

It should not optimize first for speed, independence, or automation theater.