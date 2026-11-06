"""Apply the Step 3 enrichments on top of the definitions the Step 2 import wizard created.

Reads each live definition, adds only what Step 3 needs, and PUTs it back, so it does
not depend on the exact names the wizard generated for the Step 2 fields. Safe to re-run.

  courses: Custom Entity Lookup on `instructor` -> instructorProfiles [{name, description}]
  library: Springer Function (custom Web API skill) -> publicationName, publisher, doi, publicationDate

Usage (SEARCH_ENDPOINT / SEARCH_ADMIN_KEY set, see search_client.py):
  python scripts/search_step3.py courses
  python scripts/search_step3.py library --function-url https://<app>.azurewebsites.net/api/SpringerLookup
      (reads FUNCTION_KEY from the environment)
  python scripts/search_step3.py cors --origin https://<account>.z13.web.core.windows.net
  python scripts/search_step3.py run   # reset + run both indexers
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import search_client as sc

ROOT = Path(__file__).resolve().parents[1]
PROFILES_FILE = ROOT / "starter" / "Data" / "MoodleInstructorProfiles.json"


def _with_skill(skillset: dict, skill: dict) -> dict:
    others = [s for s in skillset.get("skills", []) if s.get("name") != skill["name"]]
    return {**skillset, "skills": [*others, skill]}


def _with_fields(index: dict, fields: list[dict]) -> dict:
    existing = {f["name"] for f in index["fields"]}
    return {**index, "fields": [*index["fields"], *[f for f in fields if f["name"] not in existing]]}


def _with_mappings(indexer: dict, mappings: list[dict]) -> dict:
    targets = {m["targetFieldName"] for m in mappings}
    kept = [m for m in indexer.get("outputFieldMappings") or [] if m["targetFieldName"] not in targets]
    return {**indexer, "outputFieldMappings": [*kept, *mappings]}


def _field(name: str, kind: str = "Edm.String", **flags: bool) -> dict:
    return {"name": name, "type": kind, "retrievable": True, "searchable": False, "filterable": False,
            "facetable": False, "sortable": False, **flags}


def courses_step3() -> None:
    names = sc.COURSES
    profiles = json.loads(PROFILES_FILE.read_text())["inlineEntitiesDefinition"]

    lookup = {
        "@odata.type": "#Microsoft.Skills.Text.CustomEntityLookupSkill",
        "name": "instructor-profile-lookup",
        "description": "Matches Instructors against the company's Instructor Profiles",
        "context": "/document",
        "defaultLanguageCode": "en",
        "inlineEntitiesDefinition": profiles,
        "inputs": [{"name": "text", "source": "/document/instructor"}],
        "outputs": [{"name": "entities", "targetName": "instructorEntities"}],
    }
    shaper = {
        "@odata.type": "#Microsoft.Skills.Util.ShaperSkill",
        "name": "instructor-profile-shaper",
        "description": "Keeps only name and description of each matched Instructor Profile",
        "context": "/document/instructorEntities/*",
        "inputs": [{"name": "name", "source": "/document/instructorEntities/*/name"},
                   {"name": "description", "source": "/document/instructorEntities/*/description"}],
        "outputs": [{"name": "output", "targetName": "profile"}],
    }
    skillset = _with_skill(_with_skill(sc.get("skillsets", names["skillset"]), lookup), shaper)
    sc.put("skillsets", names["skillset"], skillset)

    profile_field = {"name": "instructorProfiles", "type": "Collection(Edm.ComplexType)", "fields": [
        _field("name", searchable=True, filterable=True, facetable=True),
        _field("description", searchable=True),
    ]}
    sc.put("indexes", names["index"], _with_fields(sc.get("indexes", names["index"]), [profile_field]))

    indexer = _with_mappings(sc.get("indexers", names["indexer"]), [
        {"sourceFieldName": "/document/instructorEntities/*/profile", "targetFieldName": "instructorProfiles"},
    ])
    sc.put("indexers", names["indexer"], indexer)
    print("courses: instructor profile enrichment applied")


def library_step3(function_url: str) -> None:
    names = sc.LIBRARY
    function_key = os.environ.get("FUNCTION_KEY")
    if not function_key:
        raise SystemExit("Set FUNCTION_KEY (Function App > App keys > default).")

    springer = {
        "@odata.type": "#Microsoft.Skills.Custom.WebApiSkill",
        "name": "springer-publication-lookup",
        "description": "Azure Function that looks up Publication details for a Paper in Springer Nature",
        "uri": f"{function_url}?code={function_key}",
        "httpMethod": "POST",
        "timeout": "PT90S",
        "batchSize": 4,
        "degreeOfParallelism": 1,
        "context": "/document",
        "inputs": [{"name": "ArticleName", "source": "/document/metadata_title"},
                   {"name": "FileName", "source": "/document/metadata_storage_name"}],
        "outputs": [{"name": "PublicationName", "targetName": "publicationName"},
                    {"name": "Publisher", "targetName": "publisher"},
                    {"name": "DOI", "targetName": "doi"},
                    {"name": "PublicationDate", "targetName": "publicationDate"}],
    }
    sc.put("skillsets", names["skillset"], _with_skill(sc.get("skillsets", names["skillset"]), springer))

    fields = [
        _field("publicationName", searchable=True, filterable=True, facetable=True, sortable=True),
        _field("publisher", searchable=True, filterable=True, facetable=True),
        _field("doi", filterable=True),
        _field("publicationDate", "Edm.DateTimeOffset", filterable=True, sortable=True, facetable=True),
    ]
    sc.put("indexes", names["index"], _with_fields(sc.get("indexes", names["index"]), fields))

    mappings = [{"sourceFieldName": f"/document/{name}", "targetFieldName": name}
                for name in ("publicationName", "publisher", "doi", "publicationDate")]
    sc.put("indexers", names["indexer"], _with_mappings(sc.get("indexers", names["indexer"]), mappings))
    print("library: Springer publication enrichment applied")


def set_cors(origin: str) -> None:
    for names in (sc.COURSES, sc.LIBRARY):
        index = sc.get("indexes", names["index"])
        sc.put("indexes", names["index"], {**index, "corsOptions": {"allowedOrigins": [origin], "maxAgeInSeconds": 300}})
    print(f"CORS limited to {origin}")


def reset_and_run() -> None:
    for names in (sc.COURSES, sc.LIBRARY):
        sc.request("POST", f"indexers/{names['indexer']}/reset")
        sc.request("POST", f"indexers/{names['indexer']}/run")
        print(f"{names['indexer']}: reset and started")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("courses")
    library = sub.add_parser("library")
    library.add_argument("--function-url", required=True)
    cors = sub.add_parser("cors")
    cors.add_argument("--origin", required=True)
    sub.add_parser("run")
    args = parser.parse_args(argv)

    actions = {
        "courses": courses_step3,
        "library": lambda: library_step3(args.function_url),
        "cors": lambda: set_cors(args.origin),
        "run": reset_and_run,
    }
    actions[args.command]()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
