"""
Bulk Elasticsearch Insertion Script for Generated Symptom Data

Loads generated symptom data and inserts it into Elasticsearch using the
same configuration as the SymptomMinder server.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

# Add parent directory to path so we can import from utils
parent_dir = Path(__file__).parent.parent
sys.path.append(str(parent_dir))

# Load environment variables from .env file (override shell env vars)
load_dotenv(parent_dir / ".env", override=True)

from utils.es_utils import create_es_client


async def load_and_insert_symptoms(
    filename: str = "data/gluten_intolerance_symptoms.json",
):
    """Load symptom data from JSON file and bulk insert into Elasticsearch."""

    # Use same ES configuration as server
    ES_ENDPOINT = os.environ.get("ES_ENDPOINT", "http://localhost:9200")
    ES_INDEX = os.environ.get("ES_INDEX", "symptom_entries")

    print(f"Connecting to Elasticsearch at: {ES_ENDPOINT}")
    print(f"Target index: {ES_INDEX}")

    # Initialize Elasticsearch client using shared utility
    try:
        es = create_es_client()
    except Exception as e:
        print(f"Failed to initialize Elasticsearch client: {e}")
        return False

    try:
        # Test connection
        info = await es.info()
        print(f"✅ Connected to Elasticsearch: {info['version']['number']}")

        # Load symptom data
        if not os.path.exists(filename):
            print(f"❌ File not found: {filename}")
            print("Please run generate_gluten_symptoms.py first!")
            return False

        with open(filename, "r") as f:
            symptoms = json.load(f)

        print(f"📄 Loaded {len(symptoms)} symptom entries from {filename}")

        if not symptoms:
            print("❌ No symptom entries found in file")
            return False

        # Prepare documents for bulk insertion
        def doc_generator():
            for symptom in symptoms:
                yield {"_index": ES_INDEX, "_source": symptom}

        # Perform bulk insertion
        print("🔄 Starting bulk insertion...")

        # Use es.options() to set request_timeout (avoids deprecation warning)
        es_with_timeout = es.options(request_timeout=60)
        success_count, errors = await async_bulk(
            es_with_timeout,
            doc_generator(),
            chunk_size=100,  # Process in batches of 100
        )

        if errors:
            print(f"⚠️  Insertion completed with {len(errors)} errors:")
            for error in errors[:5]:  # Show first 5 errors
                print(f"   - {error}")
            if len(errors) > 5:
                print(f"   ... and {len(errors) - 5} more errors")
        else:
            print(f"✅ Successfully inserted {success_count} symptom entries!")

        # Verify insertion with a quick search
        await asyncio.sleep(1)  # Allow time for indexing

        search_result = await es.search(
            index=ES_INDEX,
            query={"match": {"user_id": "demo_user_gluten_story"}},
            size=0,  # Just get count
        )

        total_inserted = search_result["hits"]["total"]["value"]
        print(f"📊 Verification: {total_inserted} entries found in index")

        # Show date range of inserted data
        date_agg_result = await es.search(
            index=ES_INDEX,
            query={"match": {"user_id": "demo_user_gluten_story"}},
            aggs={"date_range": {"stats": {"field": "timestamp"}}},
            size=0,
        )

        if "aggregations" in date_agg_result:
            date_stats = date_agg_result["aggregations"]["date_range"]
            min_date = datetime.fromisoformat(
                date_stats["min_as_string"].replace("Z", "+00:00")
            )
            max_date = datetime.fromisoformat(
                date_stats["max_as_string"].replace("Z", "+00:00")
            )
            print(f"📅 Date range: {min_date.date()} to {max_date.date()}")

        return True

    except Exception as e:
        print(f"❌ Error during insertion: {e}")
        return False
    finally:
        await es.close()


async def verify_pattern():
    """Verify the gluten intolerance pattern in inserted data."""

    ES_INDEX = os.environ.get("ES_INDEX", "symptom_entries")

    try:
        es = create_es_client()

        print("\n🔍 Analyzing symptom patterns...")

        # Get severity by day of week
        day_agg_result = await es.search(
            index=ES_INDEX,
            query={"match": {"user_id": "demo_user_gluten_story"}},
            aggs={
                "by_day_of_week": {
                    "terms": {
                        "script": {
                            "source": "doc['timestamp'].value.getDayOfWeek()"
                        }
                    },
                    "aggs": {
                        "avg_severity": {
                            "avg": {"field": "symptom_details.severity"}
                        }
                    },
                }
            },
            size=0,
        )

        if "aggregations" in day_agg_result:
            day_buckets = day_agg_result["aggregations"]["by_day_of_week"]["buckets"]
            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

            print("📊 Average severity by day of week:")
            for bucket in sorted(day_buckets, key=lambda x: x["key"]):
                day_num = int(bucket["key"])
                day_name = days[day_num - 1]  # ES uses 1-7, we use 0-6
                avg_severity = bucket["avg_severity"]["value"]
                print(f"   {day_name}: {avg_severity:.1f}")

        await es.close()

    except Exception as e:
        print(f"❌ Error during pattern verification: {e}")


def check_environment():
    """Check if required environment variables are set."""
    required_vars = ["ES_ENDPOINT"]

    print("🔧 Checking environment configuration...")

    for var in required_vars:
        value = os.environ.get(var)
        if value:
            print(f"   ✅ {var}: {value}")
        else:
            print(f"   ⚠️  {var}: Not set (will use default)")

    es_api_key = os.environ.get("ES_API_KEY")
    if es_api_key:
        print(f"   ✅ ES_API_KEY: {'*' * 20} (hidden)")
    else:
        print("   ℹ️  ES_API_KEY: Not set (local ES assumed)")

    print()


async def main():
    """Main execution function."""

    print("🚀 SymptomMinder Gluten Intolerance Data Insertion")
    print("=" * 55)

    check_environment()

    # Generate data if it doesn't exist
    data_file = "data/gluten_intolerance_symptoms.json"
    if not os.path.exists(data_file):
        print(f"📋 Symptom data file not found. Generating now...")

        # Import and run the generator
        sys.path.append(".")
        from data.generate_gluten_symptoms import main as generate_main

        generate_main()
        print()

    # Insert the data
    success = await load_and_insert_symptoms(data_file)

    if success:
        # Verify the pattern
        await verify_pattern()

        print("\n✅ Data insertion completed successfully!")
        print("\n🎯 Next steps:")
        print("   1. Start SymptomMinder server: python server.py")
        print("   2. Use flexible_search to query symptoms")
        print("   3. Look for patterns in Sunday → Monday → Tuesday symptoms")
        print("   4. Notice the gluten discovery progression in raw_notes")

    else:
        print("\n❌ Data insertion failed. Please check the errors above.")
        return 1

    return 0


if __name__ == "__main__":
    # Run the async main function
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
