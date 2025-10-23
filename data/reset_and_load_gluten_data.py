#!/usr/bin/env python3
"""
Reset Elasticsearch and load gluten intolerance symptom data.
This script will:
1. Delete all existing symptom entries
2. Reset the jury counter
3. Load the generated gluten intolerance symptoms
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path so we can import from utils
parent_dir = Path(__file__).parent.parent
sys.path.append(str(parent_dir))

# Load environment variables from .env file in parent directory
# IMPORTANT: override=True forces .env file values to take precedence over shell env vars
env_file = parent_dir / ".env"
env_loaded = load_dotenv(env_file, override=True)
if not env_loaded:
    print(f"⚠️  Warning: .env file not found at {env_file}")
    print(f"   Looking for: {env_file.absolute()}")
    print(f"   File exists: {env_file.exists()}")

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
from utils.es_utils import create_es_client


async def clear_existing_data(es):
    """Clear all existing symptom data and reset counters."""
    ES_INDEX = os.environ.get("ES_INDEX", "symptom_entries")
    JURY_COUNTER_INDEX = os.environ.get("JURY_COUNTER_INDEX", "jury_counter")
    JURY_SUMMARY_INDEX = os.environ.get("JURY_SUMMARY_INDEX", "event_summaries")

    print("🗑️  Clearing existing data...")

    # Delete all symptom entries
    try:
        response = await es.delete_by_query(
            index=ES_INDEX,
            query={"match_all": {}},
        )
        print(f"   Deleted {response.get('deleted', 0)} symptom entries")
    except Exception as e:
        if "index_not_found_exception" in str(e):
            print(f"   Index {ES_INDEX} doesn't exist yet (that's fine)")
        else:
            print(f"   Error deleting symptom entries: {e}")

    # Reset jury counter
    try:
        await es.index(
            index=JURY_COUNTER_INDEX,
            id="global_counter",
            document={"count": 0},
        )
        print("   Reset jury counter to 0")
    except Exception as e:
        print(f"   Error resetting jury counter: {e}")

    # Clear jury summaries (optional)
    try:
        response = await es.delete_by_query(
            index=JURY_SUMMARY_INDEX,
            query={"match_all": {}},
        )
        print(f"   Deleted {response.get('deleted', 0)} jury summaries")
    except Exception as e:
        if "index_not_found_exception" in str(e):
            print(f"   Index {JURY_SUMMARY_INDEX} doesn't exist yet (that's fine)")
        else:
            print(f"   Error deleting jury summaries: {e}")


async def load_gluten_symptoms(es):
    """Load the generated gluten intolerance symptoms."""
    ES_INDEX = os.environ.get("ES_INDEX", "symptom_entries")

    # Load the generated symptoms
    symptoms_file = Path(__file__).parent / "gluten_intolerance_symptoms.json"

    if not symptoms_file.exists():
        print(f"❌ Symptoms file not found: {symptoms_file}")
        print("   Run generate_gluten_symptoms.py first!")
        return False

    print(f"📥 Loading symptoms from {symptoms_file}")

    with open(symptoms_file, "r") as f:
        symptoms = json.load(f)

    print(f"   Found {len(symptoms)} symptoms to upload")

    # Prepare bulk actions
    def doc_generator():
        for symptom in symptoms:
            yield {"_index": ES_INDEX, "_source": symptom}

    # Bulk upload
    try:
        # Use es.options() to set request_timeout (avoids deprecation warning)
        es_with_timeout = es.options(request_timeout=60)
        success_count, failed_items = await async_bulk(
            es_with_timeout,
            doc_generator(),
            chunk_size=100,
        )
        print(f"✅ Successfully uploaded {success_count} symptoms")

        if failed_items:
            print(f"⚠️  {len(failed_items)} items failed to upload")
            for item in failed_items[:5]:  # Show first 5 failures
                print(f"   Failed: {item}")

        return True

    except Exception as e:
        print(f"❌ Error during bulk upload: {e}")
        return False


async def verify_upload(es):
    """Verify the upload was successful."""
    ES_INDEX = os.environ.get("ES_INDEX", "symptom_entries")

    try:
        # Get total count
        response = await es.count(index=ES_INDEX)
        total_count = response["count"]
        print(f"📊 Total symptoms in Elasticsearch: {total_count}")

        # Get date range
        response = await es.search(
            index=ES_INDEX,
            size=0,
            aggs={"date_range": {"stats": {"field": "timestamp"}}},
        )

        date_stats = response["aggregations"]["date_range"]
        print(
            f"📅 Date range: {date_stats['min_as_string']} to {date_stats['max_as_string']}"
        )

        # Get sample entry
        response = await es.search(
            index=ES_INDEX,
            size=1,
            sort=[{"timestamp": {"order": "asc"}}],
        )

        if response["hits"]["hits"]:
            sample = response["hits"]["hits"][0]["_source"]
            print(
                f"📝 Sample symptom: {sample['symptom_details']['symptom']} (severity: {sample['symptom_details']['severity']})"
            )

        return True

    except Exception as e:
        print(f"❌ Error verifying upload: {e}")
        return False


async def main():
    """Main function to reset and load data."""
    print("🚀 SymptomMinder Data Reset & Load")
    print("=" * 40)

    # Check environment variables
    print("\n📋 Environment Configuration:")
    ES_ENDPOINT = os.environ.get("ES_ENDPOINT")
    ES_API_KEY = os.environ.get("ES_API_KEY")

    print(f"  ES_ENDPOINT: {ES_ENDPOINT or 'Not set (will use default)'}")
    print(f"  ES_API_KEY: {'Set (' + str(len(ES_API_KEY)) + ' chars)' if ES_API_KEY else 'Not set (will use no auth)'}")
    print(f"  ES_INDEX: {os.environ.get('ES_INDEX', 'symptom_entries (default)')}")

    if not ES_ENDPOINT and not ES_API_KEY:
        print("\n⚠️  No credentials configured - attempting local connection without auth")

    es = None
    try:
        # Connect to Elasticsearch
        print("\n🔌 Connecting to Elasticsearch...")
        es = create_es_client(debug=True)

        # Test connection
        info = await es.info()
        print(f"   Connected to Elasticsearch {info['version']['number']}")

        # Clear existing data
        await clear_existing_data(es)

        # Load new data
        if await load_gluten_symptoms(es):
            # Verify upload
            print("\n🔍 Verifying upload...")
            await verify_upload(es)

            print("\n✅ Data reset and load completed successfully!")
            print("🎯 Ready to test gluten intolerance symptom tracking!")
            return 0
        else:
            print("\n❌ Data load failed!")
            return 1

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Close the Elasticsearch client
        if es:
            await es.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
