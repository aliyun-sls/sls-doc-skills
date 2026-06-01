#!/usr/bin/env bash
# Pack a skill directory into <name>.tar.gz for OSS upload.
# Usage: ./pack.sh <subsite> <skill-name>
# Example: ./pack.sh starops rds-inspection
# Output: dist/<skill-name>.tar.gz (tar root is <skill-name>/, matching OSS legacy layout)

set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <subsite> <skill-name>" >&2
  exit 1
fi

SUBSITE=$1
NAME=$2
ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/$SUBSITE/$NAME"
DIST="$ROOT/dist"

if [ ! -d "$SRC" ]; then
  echo "Skill not found: $SRC" >&2
  exit 1
fi

if [ ! -f "$SRC/SKILL.md" ]; then
  echo "Missing SKILL.md in $SRC" >&2
  exit 1
fi

mkdir -p "$DIST"
OUT="$DIST/$NAME.tar.gz"

tar -czf "$OUT" -C "$ROOT/$SUBSITE" "$NAME"

echo "Packed: $OUT"
echo "Contents:"
tar -tzf "$OUT" | head -20
