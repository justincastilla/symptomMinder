"""Elasticsearch utilities for SymptomMinder."""

import os
from typing import Optional, Any
from elasticsearch import AsyncElasticsearch

# Get configuration from environment
JURY_COUNTER_INDEX = os.environ.get("JURY_COUNTER_INDEX", "jury_counter")


def create_es_client(
    endpoint: Optional[str] = None, api_key: Optional[str] = None, debug: bool = False
) -> AsyncElasticsearch:
    """
    Create and configure AsyncElasticsearch client.

    Args:
        endpoint: Elasticsearch endpoint URL (defaults to ES_ENDPOINT env var)
        api_key: API key for authentication (defaults to ES_API_KEY env var)
        debug: If True, print connection details (default: False)

    Returns:
        Configured AsyncElasticsearch client

    Examples:
        # Use environment variables
        es = create_es_client()

        # Override with specific values
        es = create_es_client(endpoint="http://localhost:9200")

        # Debug connection issues
        es = create_es_client(debug=True)
    """
    ES_ENDPOINT = endpoint or os.environ.get("ES_ENDPOINT", "http://localhost:9200")
    ES_API_KEY = api_key or os.environ.get("ES_API_KEY")

    # Clean up endpoint and API key (remove whitespace)
    if ES_ENDPOINT:
        ES_ENDPOINT = ES_ENDPOINT.strip()
    if ES_API_KEY:
        ES_API_KEY = ES_API_KEY.strip()

    if debug:
        print(f"[ES Client Debug]")
        print(f"  Endpoint: {ES_ENDPOINT}")
        print(f"  API Key: {'*' * 20 if ES_API_KEY else 'None (using no auth)'}")
        print(f"  API Key type: {type(ES_API_KEY)}")
        if ES_API_KEY:
            print(f"  API Key length: {len(ES_API_KEY)}")
            # Check for common issues
            if '\n' in ES_API_KEY:
                print(f"  ⚠️  WARNING: API key contains newline characters!")
            if ' ' in ES_API_KEY:
                print(f"  ⚠️  WARNING: API key contains spaces!")
            # Check if it looks like a placeholder
            if '<' in ES_API_KEY or '>' in ES_API_KEY:
                print(f"  ⚠️  WARNING: API key looks like a placeholder (contains < or >)")

    # Configure client based on whether we're using cloud/serverless or local
    if ES_API_KEY:
        # Cloud/Serverless with API key authentication
        return AsyncElasticsearch(
            hosts=[ES_ENDPOINT],
            api_key=ES_API_KEY,
            verify_certs=True,
            request_timeout=30,
        )
    else:
        # Local instance without authentication
        return AsyncElasticsearch(
            hosts=[ES_ENDPOINT], verify_certs=False, request_timeout=30
        )


def get_es_response_id(resp: Any) -> Optional[str]:
    """
    Standardize extraction of document ID from Elasticsearch response.

    Args:
        resp: Elasticsearch response object

    Returns:
        Document ID or None if not found
    """
    if hasattr(resp, "get"):
        return resp.get("_id")
    if hasattr(resp, "body") and resp.body:
        return resp.body.get("_id")
    return None


async def get_jury_counter(es: AsyncElasticsearch) -> int:
    """
    Get the current jury trigger counter from Elasticsearch.

    Args:
        es: Elasticsearch client

    Returns:
        Current counter value (0 if counter doesn't exist)
    """
    try:
        resp = await es.get(index=JURY_COUNTER_INDEX, id="global_counter")
        return resp["_source"].get("count", 0)
    except Exception:
        # Counter doesn't exist yet, initialize it
        return 0


async def increment_jury_counter(es: AsyncElasticsearch) -> int:
    """
    Increment and return the jury trigger counter.

    Args:
        es: Elasticsearch client

    Returns:
        New counter value after increment (0 if update fails)
    """
    try:
        current = await get_jury_counter(es)
        new_count = current + 1
        await es.index(
            index=JURY_COUNTER_INDEX, id="global_counter", document={"count": new_count}
        )
        return new_count
    except Exception:
        # Fallback to 0 if counter update fails
        return 0
