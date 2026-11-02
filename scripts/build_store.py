"""Costruisce il triple store completo: ETL, OWL RL, SWRL e report di validazione."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cinetrope.store import CineTropeStore  # noqa: E402


def main() -> None:
    store = CineTropeStore.rebuild()
    stats = store.stats()
    print("Triple store creato in data/generated/store.trig")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    report = store.build_report()
    print("\nValidazione:")
    for check in report.get("validation", []):
        print(f"  {check['label']}: {check['count']}")


if __name__ == "__main__":
    main()
