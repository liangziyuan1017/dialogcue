<!--
  WORKING FILE — Runtime Impact Tracker
  Purpose: The ONLY writable file inside this module during runtime.
  Tracks what happens OUTSIDE the module when capabilities are invoked.
  All other module files are READ-ONLY during runtime.
-->

# Working File for clowder-dev Module

## purpose
Track external runtime impact when clowder-dev development flow capabilities are invoked.

## external_related_files
- `src/` — Project source code directory.

## src_entrypoints
- N/A — reference-only module. Capabilities describe development processes, not data transformations.

## src_invocation_functions
- N/A — reference-only module. No src/ functions invoke clowder-dev capabilities directly.

## src_output_targets
- N/A — reference-only module. No data output to src/.

## src_affected_files
- None — this module describes processes. It does not read from or write to external files.

## file_policy
- `working_file.md`: **writable** (this file — update to record runtime impact).
- All other module files: **read-only** during execution.

## modification_conditions
- Update this file during runtime execution to track external runtime impact.
- Do NOT modify any other file in the module during runtime.

## progress_notes
(Updated at runtime)

## validation_notes
(Updated at runtime)
