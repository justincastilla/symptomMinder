"""Search and retrieval tools for SymptomMinder MCP server."""

from typing import Dict, Any, List
from fastmcp import Context
from elasticsearch import AsyncElasticsearch


async def flexible_search_impl(
    es: AsyncElasticsearch, es_index: str, query: dict
) -> List[dict]:
    """
    Implementation for flexible search of symptom entries.

    Accepts a query dict with search filters and returns matching entries.

    Raises:
        Exception: If Elasticsearch query fails
    """
    must_clauses = []
    symptom = query.get("symptom")
    on_medication = query.get("on_medication")
    mediation_attempt = query.get("mediation_attempt")
    start_time = query.get("start_time")
    end_time = query.get("end_time")
    notes_query = query.get("notes_query")
    limit = query.get("limit", 20)

    # Use correct nested field paths
    if symptom:
        must_clauses.append({"match": {"symptom_details.symptom": symptom}})
    if on_medication is not None:
        must_clauses.append(
            {"term": {"symptom_details.on_medication": on_medication}}
        )
    if mediation_attempt:
        must_clauses.append(
            {"match": {"symptom_details.mediation_attempt": mediation_attempt}}
        )
    if start_time or end_time:
        range_query = {}
        if start_time:
            range_query["gte"] = start_time
        if end_time:
            range_query["lte"] = end_time
        must_clauses.append({"range": {"timestamp": range_query}})
    if notes_query:
        must_clauses.append(
            {
                "match": {
                    "symptom_details.raw_notes": {
                        "query": notes_query,
                        "fuzziness": "AUTO",
                    }
                }
            }
        )

    es_query = (
        {"bool": {"must": must_clauses}} if must_clauses else {"match_all": {}}
    )
    resp = await es.search(
        index=es_index,
        size=limit,
        query=es_query,
        sort=[{"timestamp": {"order": "desc"}}],
    )
    hits = resp["hits"]["hits"]
    return [hit["_source"] for hit in hits]


async def get_incomplete_symptoms_impl(
    es: AsyncElasticsearch,
    es_index: str,
    limit: int = 1,
    days_back: int = None,
    ctx: Context = None,
) -> List[dict]:
    """
    Implementation for finding symptoms marked as incomplete for follow-up.

    Args:
        es: Elasticsearch client
        es_index: Index name to search
        limit: Maximum number of results to return
        days_back: Optional filter for entries within N days
        ctx: FastMCP context for logging

    Returns:
        List of incomplete symptom entries with _id field included

    Raises:
        Exception: If Elasticsearch query fails
    """
    # Query for incomplete symptoms (false or null)
    # Should match where event_complete is NOT explicitly true
    query = {
        "bool": {
            "should": [
                {"term": {"symptom_details.event_complete": False}},
                {
                    "bool": {
                        "must_not": {
                            "exists": {"field": "symptom_details.event_complete"}
                        }
                    }
                },
            ],
            "minimum_should_match": 1,
        }
    }

    # Add time range if specified
    if days_back is not None:
        from datetime import datetime, timedelta, timezone

        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_back)
        cutoff_iso = cutoff_time.isoformat()

        query["bool"]["must"] = [{"range": {"timestamp": {"gte": cutoff_iso}}}]

    try:
        resp = await es.search(
            index=es_index,
            size=limit,
            query=query,
            sort=[{"timestamp": {"order": "desc"}}],
        )

        hits = resp["hits"]["hits"]
        results = []
        for hit in hits:
            entry = hit["_source"]
            entry["_id"] = hit["_id"]  # Include ES document ID for updates
            results.append(entry)

        return results
    except Exception as e:
        if ctx:
            ctx.error(f"Failed to get incomplete symptoms: {e}")
        raise


async def update_symptom_entry_impl(
    es: AsyncElasticsearch,
    es_index: str,
    event_id: str,
    event_complete: bool = None,
    resolution_notes: str = None,
    length_minutes: int = None,
    relief_factors: str = None,
    severity: int = None,
    tags: list[str] = None,
    ctx: Context = None,
) -> Dict[str, Any]:
    """
    Implementation for updating an existing symptom entry with new information.

    Args:
        es: Elasticsearch client
        es_index: Index name
        event_id: Document ID to update
        event_complete: Mark event as complete/incomplete
        resolution_notes: Notes about resolution (appended to raw_notes)
        length_minutes: Updated duration
        relief_factors: What helped relieve the symptom
        severity: Updated severity
        tags: Updated tags
        ctx: FastMCP context for logging

    Returns:
        Dict with status, event_id, updated_fields, and updated entry

    Raises:
        Exception: If Elasticsearch update fails
    """
    try:
        # First, get the existing document
        existing = await es.get(index=es_index, id=event_id)
        doc = existing["_source"]

        # Update fields that were provided
        if event_complete is not None:
            doc["symptom_details"]["event_complete"] = event_complete

        if severity is not None:
            doc["symptom_details"]["severity"] = severity

        if length_minutes is not None:
            doc["symptom_details"]["length_minutes"] = length_minutes

        if relief_factors is not None:
            doc["symptom_details"]["relief_factors"] = relief_factors

        # Append resolution notes to raw_notes
        if resolution_notes:
            existing_notes = doc["symptom_details"].get("raw_notes", "")
            if existing_notes:
                doc["symptom_details"][
                    "raw_notes"
                ] = f"{existing_notes}\n\nFollow-up: {resolution_notes}"
            else:
                doc["symptom_details"]["raw_notes"] = f"Follow-up: {resolution_notes}"

        if tags is not None:
            doc["tags"] = tags

        # Update the document in Elasticsearch
        resp = await es.index(index=es_index, id=event_id, document=doc)

        return {
            "status": "updated",
            "event_id": event_id,
            "updated_fields": {
                "event_complete": event_complete,
                "resolution_notes": resolution_notes is not None,
                "length_minutes": length_minutes,
                "relief_factors": relief_factors,
                "severity": severity,
                "tags": tags,
            },
            "entry": resp.body if hasattr(resp, "body") else resp,
        }
    except Exception as e:
        if ctx:
            ctx.error(f"Failed to update symptom entry: {e}")
        raise
