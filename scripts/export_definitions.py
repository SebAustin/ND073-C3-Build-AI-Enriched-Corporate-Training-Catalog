"""Export the live index/skillset/indexer definitions into submission/ with secrets scrubbed.

Usage: python scripts/export_definitions.py step2|step3
Writes Step{N}_{Index|Skillset|Indexer}_{Courses|Library}.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import search_client as sc

SUBMISSION = Path(__file__).resolve().parents[1] / "submission"
KINDS = {"Index": ("indexes", "index"), "Skillset": ("skillsets", "skillset"), "Indexer": ("indexers", "indexer")}
DATASETS = {"Courses": sc.COURSES, "Library": sc.LIBRARY}


def export(step: str) -> list[Path]:
    number = {"step2": "2", "step3": "3"}[step]
    SUBMISSION.mkdir(exist_ok=True)
    written = []
    for label, (collection, key) in KINDS.items():
        for dataset, names in DATASETS.items():
            definition = sc.scrub(sc.get(collection, names[key]))
            definition.pop("@odata.etag", None)
            path = SUBMISSION / f"Step{number}_{label}_{dataset}.json"
            path.write_text(json.dumps(definition, indent=2, ensure_ascii=False) + "\n")
            written.append(path)
    return written


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("step2", "step3"):
        raise SystemExit(__doc__)
    for path in export(sys.argv[1]):
        print(f"wrote {path.relative_to(SUBMISSION.parent)}")
