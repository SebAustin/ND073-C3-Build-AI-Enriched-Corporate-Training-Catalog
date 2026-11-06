# Lab session runbook

Everything below runs in **one** Udacity Cloud Lab session. Local prep (scripts, Function, website, Step 1 files) is already done. Secrets stay in shell variables; nothing secret is written to the repo or `submission/`.

## 0. Sign in (you)

1. Start the lab and note the session timer and resource group name.
2. Sign in to https://portal.azure.com in Chrome as the lab user.
3. In a terminal: `az login --use-device-code` with the same lab user.

```bash
RG=<lab resource group>; LOC=$(az group show -n $RG --query location -o tsv); SFX=$RANDOM
SEARCH=tcat-search-$SFX; AI=tcat-ai-$SFX; ST=tcatstorage$SFX; FUNC=tcat-func-$SFX
```

## 1. Resources (≈5 min)

```bash
az search service create -g $RG -n $SEARCH --sku free -l $LOC
az cognitiveservices account create -g $RG -n $AI --kind CognitiveServices --sku S0 -l $LOC --yes
az storage account create -g $RG -n $ST -l $LOC --sku Standard_LRS --kind StorageV2 --allow-blob-public-access false
az functionapp create -g $RG -n $FUNC --storage-account $ST --consumption-plan-location $LOC \
  --runtime dotnet --runtime-version 8 --functions-version 4 --os-type Windows
```

## 2. Data (≈3 min)

```bash
export AZURE_STORAGE_CONNECTION_STRING=$(az storage account show-connection-string -g $RG -n $ST -o tsv)
.venv/bin/python scripts/prepare_courses.py upload starter/Data/courses.csv          # typed entities -> table "courses"
az storage container create -n papers --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
az storage blob upload-batch -d papers -s starter/Data/Library --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
```

## 3. Step 2: create the search objects

> **What actually ran (2026-11-06):** the new portal "Import data" flow only lists *AIServices*-kind accounts
> and forces managed-identity storage access, and it stalled on the account picker. Step 2 was created
> with `scripts/search_step2.py` instead (same definitions, managed identity to storage):
>
> ```bash
> PID=$(az search service update -g $RG -n $SEARCH --identity-type SystemAssigned --query identity.principalId -o tsv)
> az role assignment create --assignee-object-id $PID --assignee-principal-type ServicePrincipal --role "Storage Table Data Reader" --scope $(az storage account show -g $RG -n $ST --query id -o tsv)
> az role assignment create --assignee-object-id $PID --assignee-principal-type ServicePrincipal --role "Storage Blob Data Reader" --scope $(az storage account show -g $RG -n $ST --query id -o tsv)
> STORAGE_RESOURCE_ID=... AI_SERVICES_KEY=... python3 scripts/search_step2.py   # AI account must be --kind AIServices
> python3 scripts/indexer_status.py --wait
> ```
>
> Free tier: on-demand indexer runs are limited to one every 180 s. Springer answers HTTP 404 for "no match".

Original wizard checklist (portal, ≈15 min):

**Courses**: Search service → Import data → Azure Table Storage → table `courses`, data source name `course-data`.
- Attach AI Services: **`$AI`** (not Free). Enrichment: Key phrases on source field **description**, enrichment name `courses-skillset`.
- Index `courses-index`, key `Key`. Flags per [Step1_Requirements](../submission/Step1_Requirements.txt) / design:

| Field | Retrievable | Searchable | Filterable | Facetable | Sortable |
|---|---|---|---|---|---|
| title | ✓ | ✓ | | | ✓ |
| description | ✓ | ✓ | | | |
| source, type, level, role, product | ✓ | | ✓ | ✓ | |
| instructor | ✓ | ✓ | ✓ | ✓ | |
| duration, rating_average, rating_count | ✓ | | ✓ | | ✓ |
| duration_text, url, RowKey | ✓ | | | | |
| keyphrases | ✓ | ✓ | ✓ | ✓ | |

- Indexer `courses-indexer`, schedule **Daily**.

**Library**: Import data → Azure Blob Storage → container `papers`, data source `research-library`.
- Attach AI Services **`$AI`** (avoids the 20-documents/day free cap when Step 3 re-runs). Enable OCR; enrichments: people, organizations, key phrases, language, on `merged_content`; skillset `library-skillset`.
- Index `library-index`: `people`, `organizations` searchable/filterable/facetable; `keyphrases` searchable/facetable; `content`/`merged_content` searchable; `metadata_title`, `metadata_storage_name` retrievable (+ searchable title).
- Indexer `library-indexer`, schedule **Daily**.

Then: screenshot **Data sources** tab → `submission/Step2_Data-Sources.png`, and

```bash
export SEARCH_ENDPOINT=https://$SEARCH.search.windows.net
export SEARCH_ADMIN_KEY=$(az search admin-key show -g $RG --service-name $SEARCH --query primaryKey -o tsv)
python3 scripts/export_definitions.py step2
python3 scripts/run_queries.py step2
```

## 4. Step 3 (≈10 min)

```bash
(cd starter/Function && dotnet publish -c Release -o publish && cd publish && zip -qr ../func.zip .)
az functionapp deployment source config-zip -g $RG -n $FUNC --src starter/Function/func.zip
az functionapp config appsettings set -g $RG -n $FUNC --settings SPRINGER_API_KEY=<paste key>   # from local.settings.json
export FUNCTION_KEY=$(az functionapp keys list -g $RG -n $FUNC --query functionKeys.default -o tsv)

python3 scripts/search_step3.py courses
python3 scripts/search_step3.py library --function-url https://$FUNC.azurewebsites.net/api/SpringerLookup
python3 scripts/search_step3.py run        # wait until both indexers show Success in the portal
python3 scripts/export_definitions.py step3
python3 scripts/run_queries.py step3
```

## 5. Step 4: website (≈10 min + metrics delay)

```bash
az storage blob service-properties update --account-name $ST --static-website --index-document index.html --404-document 404.html
WEB=$(az storage account show -g $RG -n $ST --query primaryEndpoints.web -o tsv)
QUERY_KEY=$(az search query-key list -g $RG --service-name $SEARCH --query [0].key -o tsv)
python3 scripts/search_step3.py cors --origin ${WEB%/}
```

Put `$SEARCH` and `$QUERY_KEY` into `starter/Website/index.html`, upload it and `404.html` to `$web`, then run 15–20 searches using facets, the slider and the pre-built filters.

Screenshots (`submission/`): `Step4_Usage.png` (Search service → Usage: storage, documents, indexes, indexers, data sources), `Step4_Monitoring.png` (Monitoring → Search latency / queries per second; allow ~5 min for metrics), plus the working site.

## 6. Close out

Commit `starter/Function` and `starter/Website/index.html`, push to the fork, zip `submission/`, and delete the lab resources.
