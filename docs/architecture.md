# Architecture

## Purpose

`agent-dev-swarm` is a small framework for evidence-driven software development using a strict orchestrator-and-worker model.

It is meant to help a software project make progress in small verified steps.

The first proof-of-concept target is `hn-trend-tracker`, but the framework is intended to remain a separate project and a reusable tool.

## Core Model

The framework assumes two layers.

The first layer is the **project repo** being developed, such as `hn-trend-tracker`.

The second layer is the **framework repo**, `agent-dev-swarm`, which provides the development control logic, contracts, and command-line entrypoints.

A project uses the framework through:

- a checked-out framework repo, typically available locally as `swarm/`
- a project-local configuration directory, typically `.swarm/`
- explicit commands run by a human or an orchestrator

## Design Principles

### 1. Small-step development

The framework is designed around tiny, bounded, reviewable steps.

A step should do one thing, verify one thing, and leave clear evidence behind.

### 2. Explicit evidence

Every meaningful action should produce evidence.

Evidence can include command output, structured result files, validation summaries, diffs, and failure reports.

The framework should prefer inspectable artifacts over hidden internal state.

### 3. Escalation over guessing

When there is ambiguity, conflicting evidence, missing requirements, or architectural uncertainty, the system should escalate rather than improvise.

Workers should not silently make broad product decisions.

### 4. Separation of concerns

The framework should remain separate from the application being developed.

Framework logic belongs in `agent-dev-swarm`.

Project-specific attachment and configuration belong in the target project’s `.swarm/` directory.

### 5. Minimal viable machinery

The framework should begin with simple local mechanisms.

The first versions should prefer:

- Python
- a CLI entrypoint
- filesystem-based artifacts
- local model execution where applicable
- explicit invocation by a user or orchestrator

It should avoid premature complexity such as distributed coordination, background services, autonomous loops, or large persistent control planes.

## Non-Goals

At this stage, the framework is **not** trying to be:

- a fully autonomous swarm
- a generalized multi-agent platform
- a background daemon
- a hosted orchestration service
- a replacement for human review
- a system that edits code without bounded task definitions

## Initial Supported Scope

The initial framework scope is intentionally narrow.

The first supported behaviors should focus on:

1. validating that a target project is correctly attached to the framework
2. reading project-local configuration
3. verifying expected files and references
4. producing structured pass/fail output
5. supporting later expansion into bounded task execution

## Repository Relationship

Expected local layout:

```text
coding_projects/
  agent-dev-swarm/
  hn-trend-tracker/
    swarm/      <- local checkout of agent-dev-swarm, ignored by parent git
    .swarm/     <- project-specific swarm configuration