"""Costruisce il dataset esplicito (named graph) senza inferenza."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cinetrope.etl import build_catalog, dataset_stats  # noqa: E402


def main() -> None:
    dataset = build_catalog(write=True)
    stats = dataset_stats(dataset)
    print("Dataset esplicito creato in data/generated/catalog.trig")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
