Bootstrap Plan
Purpose

This document defines the initial sequence for turning agent-dev-swarm from a scaffold into a minimally real framework.

The plan is intentionally narrow.

Current Starting Point

The current system has:

a standalone agent-dev-swarm repo
a CLI placeholder
a separate application repo, hn-trend-tracker
a nested framework checkout under hn-trend-tracker/swarm
a project-local config area under hn-trend-tracker/.swarm

This is enough scaffolding to begin implementing real behavior.

Phase 1: Validate Project Attachment
Goal

Implement a command that validates whether a target project is correctly attached to the framework.

Target Command

swarm validate-project --project <path>

Required Behaviors

The command should:

find <path>/.swarm/project.yaml
parse the YAML
confirm that framework_checkout exists relative to the target project
confirm that referenced framework docs exist
print a short summary
return exit code 0 on success and nonzero on failure
Non-Goals

This phase should not:

edit application code
execute tasks
invoke worker models
create autonomous loops
make architecture choices for the target app
Phase 2: Load a Bounded Task Spec
Goal

Teach the framework to read a single bounded task spec from project-local config.

Target Shape

The framework should eventually support something like:

<project>/.swarm/tasks/<task>.yaml

This phase comes after project validation is real.

Phase 3: Run One Verified Bounded Step
Goal

Execute one tiny bounded action against the project and capture evidence.

Examples:

check file presence
run one test command
summarize one log
validate one config contract

This phase still should not involve broad code editing.

Phase 4: Introduce Worker Role Execution
Goal

Allow the orchestrator to delegate one bounded action to a worker role.

This should only happen after the framework can already validate the project and capture structured results.

Acceptance Philosophy

Each phase must be real before the next one begins.

“Real” means:

implemented
runnable
inspectable
verified against an actual target repo
Immediate Next Step

The immediate next step is Phase 1.

Nothing broader should be handed to a development agent until the Phase 1 behavior is clearly specified.

END FILE

FILE: specs/001-validate-project.yaml

feature_id: 001-validate-project
name: validate-project
goal: Validate that a target project is correctly attached to agent-dev-swarm.
command_shape: "swarm validate-project --project <path>"

inputs:
required:
- project_root_path

project_expectations:
required_project_file:
- .swarm/project.yaml

required_project_yaml_fields:

project_name
framework_checkout

optional_project_yaml_fields:

project_type
language
primary_goal
task_dir
runs_dir
evidence_dir
rules_doc
artifact_spec_doc
framework_architecture_doc
bootstrap_plan_doc

required_checks:

name: project_config_exists
description: ".swarm/project.yaml exists under the target project root."
name: project_config_parses
description: "The project YAML parses successfully."
name: required_yaml_fields_present
description: "Required YAML fields are present."
name: framework_checkout_exists
description: "The configured framework checkout path exists relative to the target project root."

conditional_checks:

name: referenced_doc_exists
description: "If a referenced doc path is provided in the YAML, that file exists."

success_definition:

All required checks pass.

failure_definition:

Missing project config.
Invalid YAML.
Missing required YAML fields.
Missing framework checkout.
Missing referenced docs when those doc fields are provided.

required_outputs:

terminal_summary
process_exit_code

desired_outputs:

structured_result_object

exit_code_contract:
success: 0
failure: nonzero

non_goals:

Do not edit project files.
Do not execute project tasks.
Do not invoke worker models.
Do not create run artifacts yet unless needed by implementation design.

implementation_notes:

Keep the command synchronous and local.
Prefer explicit checks over inference.
Make failure messages concrete and actionable.

END FILE