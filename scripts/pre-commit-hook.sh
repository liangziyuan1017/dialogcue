#!/bin/sh
#
# Pre-commit hook: enforce memory hook compliance.
# If a feature doc exists with status in-progress or review,
# verify that at least one ADR exists for that feature.
#

ROOT="$(git rev-parse --show-toplevel)"
FEATURES_DIR="$ROOT/docs/features"
DECISIONS_DIR="$ROOT/docs/decisions"

if [ ! -d "$FEATURES_DIR" ]; then
  exit 0
fi

for feat_file in "$FEATURES_DIR"/F*.md; do
  [ -f "$feat_file" ] || continue

  status=$(grep -oP '(?<=\*\*Status\*\*: )\S+' "$feat_file" 2>/dev/null | head -1)

  if [ "$status" = "in-progress" ] || [ "$status" = "review" ] || [ "$status" = "complete" ]; then
    feat_id=$(basename "$feat_file" | grep -oP 'F\d+' | head -1)
    [ -z "$feat_id" ] && continue

    if [ -d "$DECISIONS_DIR" ]; then
      has_adr=$(grep -rl "feature_ids.*$feat_id" "$DECISIONS_DIR" 2>/dev/null | head -1)
    else
      has_adr=""
    fi

    if [ -z "$has_adr" ]; then
      echo "BLOCK: Feature $feat_id is $status but has no ADR in docs/decisions/"
      echo "  Run decision-record hook before committing."
      echo "  Feature doc: $feat_file"
      exit 1
    fi
  fi
done

exit 0
