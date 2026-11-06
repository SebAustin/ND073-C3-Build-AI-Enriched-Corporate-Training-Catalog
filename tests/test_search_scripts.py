import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import search_client as sc  # noqa: E402
import search_step3 as s3  # noqa: E402


def test_scrub_replaces_function_key_and_secret_fields():
    definition = {
        "skills": [{"uri": "https://f.azurewebsites.net/api/SpringerLookup?code=abc123==&x=1"}],
        "cognitiveServices": {"key": "real-key"},
        "credentials": {"connectionString": "DefaultEndpointsProtocol=https;AccountKey=zzz;"},
    }
    scrubbed = sc.scrub(definition)

    assert scrubbed["skills"][0]["uri"].endswith("?code=<function-key>&x=1")
    assert scrubbed["cognitiveServices"]["key"] == "<key>"
    assert scrubbed["credentials"]["connectionString"] == "<connectionString>"
    assert definition["cognitiveServices"]["key"] == "real-key"  # input untouched


def test_with_skill_replaces_same_name_and_keeps_others():
    skillset = {"skills": [{"name": "keyphrases"}, {"name": "lookup", "v": 1}]}
    result = s3._with_skill(skillset, {"name": "lookup", "v": 2})

    assert [s["name"] for s in result["skills"]] == ["keyphrases", "lookup"]
    assert result["skills"][1]["v"] == 2
    assert skillset["skills"][1]["v"] == 1


def test_with_fields_is_idempotent():
    index = {"fields": [{"name": "title"}]}
    once = s3._with_fields(index, [{"name": "doi"}])
    twice = s3._with_fields(once, [{"name": "doi"}])
    assert [f["name"] for f in twice["fields"]] == ["title", "doi"]


def test_with_mappings_replaces_existing_target():
    indexer = {"outputFieldMappings": [{"sourceFieldName": "/a", "targetFieldName": "doi"},
                                       {"sourceFieldName": "/k", "targetFieldName": "keyphrases"}]}
    result = s3._with_mappings(indexer, [{"sourceFieldName": "/document/doi", "targetFieldName": "doi"}])
    assert {m["targetFieldName"]: m["sourceFieldName"] for m in result["outputFieldMappings"]} == {
        "keyphrases": "/k", "doi": "/document/doi"}


def test_instructor_profiles_file_has_names_and_descriptions():
    import json
    profiles = json.loads(s3.PROFILES_FILE.read_text())["inlineEntitiesDefinition"]
    assert len(profiles) == 5 and all(p["name"] and p["description"] for p in profiles)
