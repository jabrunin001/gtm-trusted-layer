"""Fail if any registry metric lacks a description or freshness source."""
import sys
from pathlib import Path

# Ensure the repo root is on sys.path when the script is run directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from gtm.registry import load_registry


def main() -> int:
    reg = load_registry()
    problems = []
    for m in reg.metrics:
        if not m.description.strip():
            problems.append(f"{m.name}: missing description")
        if not m.freshness_sources:
            problems.append(f"{m.name}: no freshness sources")
    if problems:
        print("\n".join(problems))
        return 1
    print(f"Doc coverage OK for {len(reg.metrics)} metrics.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
