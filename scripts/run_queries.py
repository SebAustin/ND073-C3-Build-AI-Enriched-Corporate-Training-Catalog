"""Run the demonstration queries and write Step2_Queries / Step2_AdvancedQueries / Step3_AdvancedQueries.

Each query is a Search Explorer query string; it is sent to the same GET /docs endpoint
the portal uses, and the file records the string, the index, and the JSON result.

Usage: python scripts/run_queries.py step2|step3 [--author "<name>"] [--organization "<org>"]
  (author / organization pick real values for the library filters; if omitted, the
   first facet value from the index is used)
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from pathlib import Path

import search_client as sc

SUBMISSION = Path(__file__).resolve().parents[1] / "submission"
C, L = sc.COURSES["index"], sc.LIBRARY["index"]

STEP2_BASIC = [
    ("Courses: keyword search returns all Course Offering fields", C,
     "search=kubernetes&$count=true&$top=3&$select=title,description,source,type,level,role,product,"
     "duration,duration_text,rating_average,rating_count,url,keyphrases"),
    ("Library: keyword search returns Paper fields (authors, institutions, key phrases)", L,
     "search=sentiment analysis&$count=true&$top=3&$select=metadata_storage_name,metadata_title,people,organizations,keyphrases"),
]

STEP2_ADVANCED = [
    ("Courses: filter on rating, sorted by rating", C,
     "search=*&$filter=rating_average ge 4.7&$orderby=rating_average desc&$count=true&$top=5"
     "&$select=title,source,rating_average,rating_count"),
    ("Courses: facet by source, level and role", C,
     "search=*&$count=true&$top=0&facet=source&facet=level&facet=role"),
    ("Courses: beginner offerings of at most 1 hour, shortest first", C,
     "search=*&$filter=duration le 1 and level eq 'beginner'&$orderby=duration asc&$count=true&$top=5"
     "&$select=title,level,duration,duration_text"),
    ("Courses: phrase search in descriptions, faceted by Skill", C,
     "search=\"machine learning\"&searchFields=description&$count=true&$top=3&facet=keyphrases,count:10"
     "&$select=title,description,keyphrases"),
    ("Library: facet by institution and author", L,
     "search=*&$count=true&$top=0&facet=organizations,count:10&facet=people,count:10"),
    ("Library: search by author (Lucene field search)", L,
     "queryType=full&search=people:\"{author}\"&$count=true&$select=metadata_title,people,organizations"),
    ("Library: big data Papers from one institution", L,
     "search=big data&$filter=organizations/any(o: o eq '{organization}')&$count=true"
     "&$select=metadata_title,organizations"),
]

STEP3_ADVANCED = [
    ("Courses: Internal offerings return their Instructor Profiles", C,
     "search=*&$filter=type eq 'Internal'&$count=true&$top=5&$select=title,instructor,instructorProfiles"),
    ("Courses: filter by Instructor Profile name", C,
     "search=*&$filter=instructorProfiles/any(p: p/name eq 'Eileen Diaz')&$count=true"
     "&$select=title,instructorProfiles"),
    ("Courses: search inside Instructor Profile descriptions", C,
     "search=skiing&searchFields=instructorProfiles/description&$count=true&$select=title,instructorProfiles"),
    ("Courses: facet by Instructor", C,
     "search=*&$count=true&$top=0&facet=instructorProfiles/name"),
    ("Library: Publication details and DOI returned with each Paper", L,
     "search=*&$count=true&$top=5&$select=metadata_title,publicationName,publisher,publicationDate,doi"),
    ("Library: facet by publisher and Publication", L,
     "search=*&$count=true&$top=0&facet=publisher&facet=publicationName"),
    ("Library: Papers published since 2019, newest first", L,
     "search=*&$filter=publicationDate ge 2019-01-01T00:00:00Z&$orderby=publicationDate desc&$count=true"
     "&$select=metadata_title,publicationName,publicationDate,doi"),
    ("Library: search by Publication name", L,
     "queryType=full&search=publicationName:\"Journal of Big Data\"&$count=true"
     "&$select=metadata_title,publicationName,doi"),
]


def run(index: str, query: str) -> dict:
    params = urllib.parse.parse_qsl(query, keep_blank_values=True)
    return sc.request("GET", f"indexes/{index}/docs?{urllib.parse.urlencode(params)}")


def first_facet(field: str) -> str:
    facets = run(L, f"search=*&$top=0&facet={field},count:1").get("@search.facets", {}).get(field, [])
    return facets[0]["value"] if facets else ""


def write(name: str, queries: list[tuple[str, str, str]], values: dict[str, str]) -> Path:
    blocks = []
    for number, (title, index, template) in enumerate(queries, start=1):
        query = template.format(**values)
        result = run(index, query)
        blocks.append(f"### Query {number}: {title}\nIndex: {index}\nQuery string: {query}\n\nResult:\n"
                      f"{json.dumps(result, indent=2, ensure_ascii=False)}\n")
    path = SUBMISSION / f"{name}.txt"
    path.write_text("\n".join(blocks))
    return path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=("step2", "step3"))
    parser.add_argument("--author")
    parser.add_argument("--organization")
    args = parser.parse_args(argv)
    SUBMISSION.mkdir(exist_ok=True)

    if args.step == "step2":
        values = {"author": args.author or first_facet("people"),
                  "organization": args.organization or first_facet("organizations")}
        paths = [write("Step2_Queries", STEP2_BASIC, values), write("Step2_AdvancedQueries", STEP2_ADVANCED, values)]
    else:
        paths = [write("Step3_AdvancedQueries", STEP3_ADVANCED, {})]
    for path in paths:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
