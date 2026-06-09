<!--
  RULES FILE — Module-Specific Constraints
  Purpose: Define the constraints and invariants that govern ALL execution within this module.
  Rules are read during runtime to enforce boundaries.
  This is a reference-only module — scripts/ and tests/ are empty.
-->

# clowder-dev Rules

## input_constraints
<!--
  SECTION PURPOSE: What kind of data this module accepts.
-->
- N/A — reference-only module, no data inputs.

## execution_constraints
<!--
  SECTION PURPOSE: Rules that govern HOW execution happens.
-->
- This is a reference-only module. Scripts/ and tests/ are empty.
- Workflows describe development processes, not executable commands.
- No external APIs, no filesystem writes outside the module.
- No network access required.

## output_constraints
<!--
  SECTION PURPOSE: Rules that define the shape and format of outputs.
-->
- N/A — reference-only module.
- Workflows return process descriptions, not structured data.

## immutability_rule
<!--
  SECTION PURPOSE: Enforces the write-boundary contract.
-->
- During runtime, the ONLY writable file in this module is `working_file.md`.
- All other files (router.md, rules.md, workflows/, scripts/, tests/) are READ-ONLY.
