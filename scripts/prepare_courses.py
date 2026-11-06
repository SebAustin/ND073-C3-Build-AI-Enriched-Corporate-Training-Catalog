"""Clean the course data and load it into Azure Table Storage with real column types.

Why not Storage Explorer's CSV import: it stores every column as a string, so the
search index would get Edm.String for duration/rating fields and lose numeric
filtering and sorting.

Cleaning (see GLOSSARY.md for terms, docs/adr/0002 for the duration rule):
  * trims every text value; normalises `level` to lower case
  * adds `type` (Course Type) derived from the Source partition
  * swaps rating_count / rating_average on Udacity rows (they are transposed in the source)
  * converts `duration` to hours (Double) and keeps the original wording in `duration_text`
  * stores rating_count as Int32 and rating_average as Double
  * omits empty values (e.g. `instructor` on non-internal Course Offerings, unrated courses)

Usage:
  python scripts/prepare_courses.py clean  <in.csv> <out.csv>
  python scripts/prepare_courses.py upload <in.csv> [--table courses]
      (reads AZURE_STORAGE_CONNECTION_STRING from the environment)
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from typing import Iterable

COURSE_TYPE_BY_PARTITION = {
    "ms-learn": "Module",
    "ud-learn": "Nanodegree",
    "company-moodle": "Internal",
}
HOURS_PER_MONTH = 40.0  # Udacity quotes ~10 h/week; see docs/adr/0002
MINUTES_PER_HOUR = 60.0
SWAPPED_RATING_PARTITIONS = frozenset({"ud-learn"})
MONTHS_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*months?$", re.IGNORECASE)
OUTPUT_COLUMNS = (
    "PartitionKey", "RowKey", "source", "type", "title", "description", "instructor",
    "level", "role", "product", "duration", "duration_text", "rating_count",
    "rating_average", "url",
)
BATCH_SIZE = 100  # Table Storage transaction limit per partition


class CourseDataError(ValueError):
    """Raised when a row cannot be turned into a valid Course Offering."""


def clean_row(row: dict[str, str]) -> dict[str, object]:
    """Return a new, typed Course Offering entity; the input row is not modified."""
    text = {key: (value or "").strip() for key, value in row.items() if key}
    partition = text.get("PartitionKey", "")
    if partition not in COURSE_TYPE_BY_PARTITION:
        raise CourseDataError(f"Unknown source partition {partition!r} (RowKey {text.get('RowKey')!r})")
    if not text.get("RowKey"):
        raise CourseDataError("Row without RowKey")

    row_key = text["RowKey"]
    count_raw, average_raw = text.get("rating_count", ""), text.get("rating_average", "")
    if partition in SWAPPED_RATING_PARTITIONS:
        count_raw, average_raw = average_raw, count_raw

    entity: dict[str, object] = {
        **{key: value for key, value in text.items() if value},
        "level": text.get("level", "").lower(),
        "type": COURSE_TYPE_BY_PARTITION[partition],
        "duration_text": text.get("duration", ""),
        "duration": to_hours(partition, text.get("duration", ""), row_key),
        "rating_count": _parse("rating_count", count_raw, int, row_key) if count_raw else "",
        "rating_average": _parse("rating_average", average_raw, float, row_key) if average_raw else "",
    }
    if entity["rating_count"] == 0:
        entity["rating_average"] = ""  # a 0.0 average with no ratings means "unrated", not "rated zero"
    return {key: value for key, value in entity.items() if value not in ("", None)}


def to_hours(partition: str, raw: str, row_key: str) -> float | None:
    """Convert a source-specific duration to hours (MS Learn: minutes, Udacity: months, Moodle: hours)."""
    if not raw:
        return None
    if partition == "ud-learn":
        match = MONTHS_PATTERN.match(raw)
        if not match:
            raise CourseDataError(f"duration={raw!r} is not '<n> months' (RowKey {row_key})")
        return float(match.group(1)) * HOURS_PER_MONTH
    value = _parse("duration", raw, float, row_key)
    return round(value / MINUTES_PER_HOUR, 2) if partition == "ms-learn" else value


def _parse(field: str, raw: str, kind: type, row_key: str):
    try:
        return kind(raw)
    except ValueError as exc:
        raise CourseDataError(f"{field}={raw!r} is not {kind.__name__} (RowKey {row_key})") from exc


def read_courses(path: str) -> list[dict[str, object]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return [clean_row(row) for row in csv.DictReader(handle)]


def write_csv(entities: Iterable[dict[str, object]], path: str) -> int:
    rows = list(entities)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def upload(entities: list[dict[str, object]], table_name: str) -> int:
    from azure.data.tables import TableServiceClient  # imported lazily: only needed for upload

    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise SystemExit("AZURE_STORAGE_CONNECTION_STRING is not set.")
    table = TableServiceClient.from_connection_string(connection_string).create_table_if_not_exists(table_name)

    by_partition: dict[str, list[dict[str, object]]] = {}
    for entity in entities:
        by_partition.setdefault(str(entity["PartitionKey"]), []).append(entity)

    written = 0
    for partition_entities in by_partition.values():
        for start in range(0, len(partition_entities), BATCH_SIZE):
            chunk = partition_entities[start:start + BATCH_SIZE]
            table.submit_transaction([("upsert", entity) for entity in chunk])
            written += len(chunk)
    return written


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    clean_cmd = sub.add_parser("clean")
    clean_cmd.add_argument("source")
    clean_cmd.add_argument("target")
    upload_cmd = sub.add_parser("upload")
    upload_cmd.add_argument("source")
    upload_cmd.add_argument("--table", default="courses")
    args = parser.parse_args(argv)

    entities = read_courses(args.source)
    if args.command == "clean":
        print(f"Wrote {write_csv(entities, args.target)} Course Offerings to {args.target}")
    else:
        print(f"Upserted {upload(entities, args.table)} Course Offerings into table '{args.table}'")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
