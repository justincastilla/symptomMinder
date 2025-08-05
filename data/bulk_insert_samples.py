import os
import asyncio
import json
from elasticsearch import AsyncElasticsearch

ES_URL = os.environ.get("ES_ENDPOINT", "http://localhost:9200")
ES_INDEX = os.environ.get("ES_INDEX", "symptom_entries")
ES_API_KEY = os.environ.get("ES_API_KEY")
SAMPLE_FILE = os.path.join(os.path.dirname(__file__), "sample_symptom_entries.json")

async def main():
    headers = {"Authorization": f"ApiKey {ES_API_KEY}"} if ES_API_KEY else None
    es = AsyncElasticsearch(ES_URL, headers=headers) if headers else AsyncElasticsearch(ES_URL)
    # Complete index mapping for all fields
    mapping = {
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "user_id": {"type": "keyword"},
                "tags": {"type": "keyword"},
                "symptom_details": {
                    "type": "object",
                    "properties": {
                        "symptom": {"type": "keyword"},
                        "severity": {"type": "integer"},
                        "length_minutes": {"type": "integer"},
                        "cause": {"type": "keyword"},
                        "mediation_attempt": {"type": "keyword"},
                        "on_medication": {"type": "boolean"},
                        "raw_notes": {"type": "semantic_text"},
                        "event_complete": {"type": "boolean"},
                        "onset_type": {"type": "keyword"},
                        "intensity_pattern": {"type": "keyword"},
                        "associated_symptoms": {"type": "keyword"},
                        "relief_factors": {"type": "keyword"}
                    }
                },
                "environmental": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "keyword"},
                        "environmental_factors": {
                            "type": "object",
                            "properties": {
                                "temperature": {"type": "integer"},
                                "humidity": {"type": "integer"}
                            }
                        },
                        "activity_context": {"type": "keyword"}
                    }
                }
            }
        }
    }
    # Delete index if exists (for idempotency in testing)
    if await es.indices.exists(index=ES_INDEX):
        await es.indices.delete(index=ES_INDEX)
    await es.indices.create(index=ES_INDEX, body=mapping)
    with open(SAMPLE_FILE, "r") as f:
        entries = json.load(f)
    actions = []
    for entry in entries:
        actions.append({"index": {"_index": ES_INDEX}})
        actions.append(entry)
    # Bulk insert with longer timeout
    es_with_timeout = es.options(request_timeout=120)
    resp = await es_with_timeout.bulk(operations=actions)
    if not resp.get('errors', True):
        print("Bulk insert successful: All sample entries were loaded into Elasticsearch.")
    else:
        print(f"Bulk insert completed with errors: {resp}")
    await es.close()

if __name__ == "__main__":
    asyncio.run(main())
