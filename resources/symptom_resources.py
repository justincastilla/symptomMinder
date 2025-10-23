"""Resources implementations for SymptomMinder MCP server."""

from typing import List
from elasticsearch import AsyncElasticsearch


async def list_symptom_entries_impl(
    es: AsyncElasticsearch, es_index: str, limit: int = 20
) -> List[dict]:
    """
    Implementation for retrieving the most recent symptom entries.

    Args:
        es: Elasticsearch client
        es_index: Index name to search
        limit: Maximum number of entries to retrieve

    Returns:
        List of symptom entry dictionaries sorted by timestamp descending

    Raises:
        Exception: If Elasticsearch query fails
    """
    resp = await es.search(index=es_index, size=limit, sort="timestamp:desc")
    hits = resp["hits"]["hits"]
    return [hit["_source"] for hit in hits]
