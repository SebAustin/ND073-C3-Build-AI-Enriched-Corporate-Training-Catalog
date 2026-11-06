"""Create the Step 2 data sources, skillsets, indexes and indexers over REST.

Equivalent to what the portal Import data wizard generates, with the field attributes from the
design (docs/lab-runbook.md). Used because the new portal wizard would not list the AI Services
account. Storage is reached with the search service's managed identity (no keys stored).

Environment: SEARCH_ENDPOINT, SEARCH_ADMIN_KEY (see search_client.py), plus
  STORAGE_RESOURCE_ID  /subscriptions/.../storageAccounts/<name>
  AI_SERVICES_KEY      key of the AI Services account (same region as search)

Usage: python scripts/search_step2.py
"""

from __future__ import annotations

import os
import sys

import search_client as sc

DAILY = {"interval": "P1D", "startTime": "2026-11-06T06:00:00Z"}
EN = "en.microsoft"


def f(name: str, kind: str = "Edm.String", analyzer: str | None = None, **flags: bool) -> dict:
    field = {"name": name, "type": kind, "retrievable": True, "searchable": False, "filterable": False,
             "facetable": False, "sortable": False, **flags}
    if analyzer and field["searchable"]:
        field["analyzer"] = analyzer
    return field


def cognitive_services(key: str) -> dict:
    return {"@odata.type": "#Microsoft.Azure.Search.CognitiveServicesByKey",
            "description": "AI Services (S0) for enrichment billing", "key": key}


def courses(storage_id: str, ai_key: str) -> None:
    n = sc.COURSES
    sc.put("datasources", n["datasource"], {
        "name": n["datasource"], "type": "azuretable",
        "description": "Course Data: MS Learn, Udacity and Company Moodle Course Offerings",
        "credentials": {"connectionString": f"ResourceId={storage_id};"},
        "container": {"name": "courses"},
    })
    sc.put("skillsets", n["skillset"], {
        "name": n["skillset"], "description": "Course Data enrichment",
        "cognitiveServices": cognitive_services(ai_key),
        "skills": [{
            "@odata.type": "#Microsoft.Skills.Text.KeyPhraseExtractionSkill",
            "name": "description-skills", "description": "Skills = key phrases of the description",
            "context": "/document", "defaultLanguageCode": "en",
            "inputs": [{"name": "text", "source": "/document/description"}],
            "outputs": [{"name": "keyPhrases", "targetName": "keyphrases"}],
        }],
    })
    sc.put("indexes", n["index"], {"name": n["index"], "fields": [
        f("Key", key=True, filterable=True),
        f("PartitionKey", filterable=True), f("RowKey", filterable=True),
        f("title", searchable=True, sortable=True, analyzer=EN),
        f("description", searchable=True, analyzer=EN),
        f("source", filterable=True, facetable=True),
        f("type", filterable=True, facetable=True),
        f("level", filterable=True, facetable=True),
        f("role", filterable=True, facetable=True),
        f("product", filterable=True, facetable=True),
        f("instructor", searchable=True, filterable=True, facetable=True),
        f("duration", "Edm.Double", filterable=True, sortable=True),
        f("duration_text"),
        f("rating_average", "Edm.Double", filterable=True, sortable=True),
        f("rating_count", "Edm.Int32", filterable=True, sortable=True),
        f("url"),
        f("keyphrases", "Collection(Edm.String)", searchable=True, filterable=True, facetable=True, analyzer=EN),
    ]})
    sc.put("indexers", n["indexer"], {
        "name": n["indexer"], "dataSourceName": n["datasource"], "skillsetName": n["skillset"],
        "targetIndexName": n["index"], "schedule": DAILY,
        "parameters": {"maxFailedItems": 0, "maxFailedItemsPerBatch": 0},
        "outputFieldMappings": [{"sourceFieldName": "/document/keyphrases", "targetFieldName": "keyphrases"}],
    })
    print("courses: data source, skillset, index, indexer created")


def library(storage_id: str, ai_key: str) -> None:
    n = sc.LIBRARY
    pages = "/document/pages/*"
    sc.put("datasources", n["datasource"], {
        "name": n["datasource"], "type": "azureblob",
        "description": "Research: Curated Library of open-access journal Papers (PDF)",
        "credentials": {"connectionString": f"ResourceId={storage_id};"},
        "container": {"name": "papers"},
    })
    sc.put("skillsets", n["skillset"], {
        "name": n["skillset"], "description": "Curated Library enrichment",
        "cognitiveServices": cognitive_services(ai_key),
        "skills": [
            {"@odata.type": "#Microsoft.Skills.Vision.OcrSkill", "name": "ocr", "context": "/document/normalized_images/*",
             "defaultLanguageCode": "en", "detectOrientation": True,
             "inputs": [{"name": "image", "source": "/document/normalized_images/*"}],
             "outputs": [{"name": "text", "targetName": "text"}]},
            {"@odata.type": "#Microsoft.Skills.Text.MergeSkill", "name": "merge-text", "context": "/document",
             "insertPreTag": " ", "insertPostTag": " ",
             "inputs": [{"name": "text", "source": "/document/content"},
                        {"name": "itemsToInsert", "source": "/document/normalized_images/*/text"},
                        {"name": "offsets", "source": "/document/normalized_images/*/contentOffset"}],
             "outputs": [{"name": "mergedText", "targetName": "merged_content"}]},
            {"@odata.type": "#Microsoft.Skills.Text.LanguageDetectionSkill", "name": "language", "context": "/document",
             "inputs": [{"name": "text", "source": "/document/merged_content"}],
             "outputs": [{"name": "languageCode", "targetName": "language"}]},
            # Authors and institutions sit on the first pages; analysing only the opening pages avoids
            # picking up every cited author from the reference list and keeps enrichment cost low.
            {"@odata.type": "#Microsoft.Skills.Text.SplitSkill", "name": "opening-pages", "context": "/document",
             "textSplitMode": "pages", "maximumPageLength": 5000, "maximumPagesToTake": 2, "defaultLanguageCode": "en",
             "inputs": [{"name": "text", "source": "/document/merged_content"}],
             "outputs": [{"name": "textItems", "targetName": "pages"}]},
            {"@odata.type": "#Microsoft.Skills.Text.V3.EntityRecognitionSkill", "name": "authors-institutions",
             "context": pages, "categories": ["Person", "Organization"], "defaultLanguageCode": "en",
             "inputs": [{"name": "text", "source": pages}],
             "outputs": [{"name": "persons", "targetName": "people"},
                         {"name": "organizations", "targetName": "organizations"}]},
            {"@odata.type": "#Microsoft.Skills.Text.KeyPhraseExtractionSkill", "name": "key-phrases",
             "context": pages, "defaultLanguageCode": "en",
             "inputs": [{"name": "text", "source": pages}],
             "outputs": [{"name": "keyPhrases", "targetName": "keyphrases"}]},
        ],
    })
    sc.put("indexes", n["index"], {"name": n["index"], "fields": [
        f("metadata_storage_path", key=True),
        f("metadata_storage_name", searchable=True, filterable=True, sortable=True),
        f("metadata_title", searchable=True, sortable=True, analyzer=EN),
        f("metadata_storage_size", "Edm.Int64", filterable=True, sortable=True),
        f("merged_content", searchable=True, analyzer=EN),
        f("language", filterable=True, facetable=True),
        f("people", "Collection(Edm.String)", searchable=True, filterable=True, facetable=True),
        f("organizations", "Collection(Edm.String)", searchable=True, filterable=True, facetable=True),
        f("keyphrases", "Collection(Edm.String)", searchable=True, filterable=True, facetable=True, analyzer=EN),
    ]})
    sc.put("indexers", n["indexer"], {
        "name": n["indexer"], "dataSourceName": n["datasource"], "skillsetName": n["skillset"],
        "targetIndexName": n["index"], "schedule": DAILY,
        "parameters": {"maxFailedItems": -1, "maxFailedItemsPerBatch": -1, "configuration": {
            "dataToExtract": "contentAndMetadata", "parsingMode": "default",
            "imageAction": "generateNormalizedImages"}},
        "fieldMappings": [{"sourceFieldName": "metadata_storage_path", "targetFieldName": "metadata_storage_path",
                           "mappingFunction": {"name": "base64Encode"}}],
        "outputFieldMappings": [
            {"sourceFieldName": "/document/merged_content", "targetFieldName": "merged_content"},
            {"sourceFieldName": "/document/language", "targetFieldName": "language"},
            {"sourceFieldName": f"{pages}/people/*", "targetFieldName": "people"},
            {"sourceFieldName": f"{pages}/organizations/*", "targetFieldName": "organizations"},
            {"sourceFieldName": f"{pages}/keyphrases/*", "targetFieldName": "keyphrases"},
        ],
    })
    print("library: data source, skillset, index, indexer created")


def main() -> int:
    storage_id = os.environ.get("STORAGE_RESOURCE_ID")
    ai_key = os.environ.get("AI_SERVICES_KEY")
    if not storage_id or not ai_key:
        raise SystemExit("Set STORAGE_RESOURCE_ID and AI_SERVICES_KEY.")
    courses(storage_id, ai_key)
    library(storage_id, ai_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
