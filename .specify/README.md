# Spec Kit Setup For StCalibration-Linux

This repository uses Spec Kit as a specification-first layer around the existing
steering calibration application. New work should start from the current project
memory before creating specs, plans, or tasks.

## Current Spec Kit Baseline

As of 2026-07-21, GitHub Spec Kit latest release is `v0.13.0`.

Recommended install command when the machine has network access:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v0.13.0
```

If the CLI is already installed, initialize or refresh agent integration from the
repository root using the agent integration used by the team. For Codex skills
mode, use the Spec Kit Codex skills integration if available in the installed CLI.

## Local Memory Files

- `.specify/memory/constitution.md`: project principles and quality gates.
- `.specify/memory/project-overview.md`: detailed description of existing
  workflows, modules, data ownership, hardware boundaries, and reuse rules.
- `AGENTS.md`: short operational instructions for coding agents working in this
  repository.

## Spec Workflow

1. Read `.specify/memory/project-overview.md` and
   `.specify/memory/constitution.md`.
2. Create or update the feature spec with `/speckit.specify` or the equivalent
   `speckit-specify` skill. Describe the desired manufacturing behavior and
   acceptance criteria; avoid implementation details in the spec.
3. Run clarify/checklist for ambiguous hardware, operator, data, and safety
   behavior before planning.
4. Create the implementation plan with `/speckit.plan`. The plan must explicitly
   reuse existing driver, logic, GUI, report, and product-resolution modules
   unless it explains why reuse is impossible.
5. Generate tasks with `/speckit.tasks`.
6. Implement tasks. Hardware-free tests are required for parsing, state-machine,
   workbook, product-resolution, and safety behavior. Manual hardware validation
   is separate and must be documented in the spec or plan.

## Repository-Specific Rule

Do not create a second CAN layer, MU SDK wrapper, camera angle algorithm, QR
scanner, relay protocol, product folder resolver, status workbook format, or EOL
sequence checker without first extending the existing module that owns that
behavior.
