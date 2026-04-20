Artifact Spec
Purpose

This document defines the expected output shape for framework actions.

The framework should produce artifacts that are easy to inspect, easy to diff, and easy to reason about.

Artifacts should make it possible to answer:

what was requested
what was checked
what happened
what evidence supports the result
what remains unresolved
Principles
1. Artifacts should be filesystem-friendly

Artifacts should be regular files written to disk.

They should not depend on hidden in-memory state.

2. Artifacts should separate machine-readable and human-readable output

A framework action should ideally produce both:

a machine-readable result artifact
a short human-readable summary
3. Artifacts should be scoped to a single action

One command or bounded step should produce one coherent result set.

The system should avoid mixing unrelated work into a single artifact.

Initial Artifact Types

The initial framework can remain minimal, but it should be designed around these logical artifact types.

Input Artifact

Describes what the command or step was asked to do.

Example contents:

command name
target project path
relevant input file paths
timestamp
framework version if available
Result Artifact

Describes the pass/fail outcome in structured form.

Suggested fields:

status
checks_run
checks_passed
checks_failed
missing_items
errors
output_paths
Summary Artifact

A short human-readable explanation of the outcome.

This should be concise and easy to read in a terminal or commit review.

Evidence Artifact

Contains supporting evidence such as:

parsed config values
file existence checks
command outputs
captured stderr
validation notes

In the earliest versions, evidence can be embedded directly in the result artifact rather than split out.

Initial Output Expectations for validate-project

The first command should be able to produce, at minimum:

exit code
stdout summary
a structured result object or file

Even if the earliest implementation prints only to stdout, it should be written so that structured output can be added without changing the command’s conceptual contract.

Suggested Minimal Structured Schema

A minimal result schema might look like this:

status: success | failure
project_root: <path>
config_path: <path>
checks:

name: project_config_exists
status: pass
name: project_config_parses
status: pass
name: framework_checkout_exists
status: fail
missing_items: []
errors: []

The implementation does not need to support all fields immediately, but this is the target shape.

Status Semantics
success

All required checks passed.

failure

One or more expected checks failed.

escalate

The framework could not safely determine success or failure because the situation requires a higher-level decision.

This status may not be needed in the first implementation, but the artifact model should leave room for it.

Naming and Location

Project-specific generated artifacts should live under the target project’s local swarm directory, for example:

<project>/.swarm/runs/
<project>/.swarm/evidence/

The framework repo itself should not accumulate project run artifacts by default.

Early Implementation Guidance

The first implementation should keep artifacts simple.

Prefer:

plain YAML or JSON
short text summaries
explicit field names
stable, unsurprising output

Avoid:

overly abstract schemas
multiple nested formats too early
opaque binary output
large amounts of prose without structured facts