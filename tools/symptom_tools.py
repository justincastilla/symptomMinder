"""Symptom entry tools for SymptomMinder MCP server."""

from typing import Dict, Any, List
from fastmcp import Context
from elasticsearch import AsyncElasticsearch

from symptom_schema import SymptomEntry
from utils.data_utils import clean_entry, ensure_raw_notes
from utils.es_utils import get_es_response_id, increment_jury_counter
from utils.prompt_utils import generate_review_prompt
from jury_tools import llm_jury_compare_notes


def review_symptom_entry_impl(
    symptom: str,
    severity: int,
    timestamp: str,
    length_minutes: int = None,
    cause: str = None,
    mediation_attempt: str = None,
    on_medication: bool = None,
    raw_notes: str = None,
    event_complete: bool = None,
    onset_type: str = None,
    intensity_pattern: str = None,
    associated_symptoms: list[str] = None,
    relief_factors: str = None,
    location: str = None,
    environmental_factors: dict = None,
    activity_context: str = None,
    tags: list[str] = None,
    user_id: str = None,
    ctx: Context = None,
) -> Dict[str, Any]:
    """
    Implementation for reviewing a symptom entry before saving.

    Returns a review prompt for the symptom entry, do not save yet.
    """
    try:
        # Build entry dict from parameters
        entry = {
            "timestamp": timestamp,
            "user_id": user_id,
            "symptom_details": {
                "symptom": symptom,
                "severity": severity,
                "length_minutes": length_minutes,
                "cause": cause,
                "mediation_attempt": mediation_attempt,
                "on_medication": on_medication,
                "raw_notes": raw_notes,
                "event_complete": event_complete,
                "onset_type": onset_type,
                "intensity_pattern": intensity_pattern,
                "associated_symptoms": associated_symptoms,
                "relief_factors": relief_factors,
            },
            "tags": tags,
        }

        # Add environmental if any environmental fields provided
        if location or environmental_factors or activity_context:
            entry["environmental"] = {
                "location": location,
                "environmental_factors": environmental_factors,
                "activity_context": activity_context,
            }

        entry = clean_entry(entry)
        parsed = SymptomEntry(**entry)
        prompt = generate_review_prompt(parsed)
        return {
            "status": "review",
            "review_prompt": prompt,
            "entry": parsed.model_dump(),
        }
    except Exception as e:
        if ctx:
            ctx.error(f"Failed to generate review: {e}")
        return {"status": "error", "error": str(e)}


async def confirm_and_save_symptom_entry_impl(
    es: AsyncElasticsearch,
    es_index: str,
    jury_trigger_modulo: int,
    symptom: str,
    severity: int,
    timestamp: str,
    length_minutes: int = None,
    cause: str = None,
    mediation_attempt: str = None,
    on_medication: bool = None,
    raw_notes: str = None,
    event_complete: bool = None,
    onset_type: str = None,
    intensity_pattern: str = None,
    associated_symptoms: list[str] = None,
    relief_factors: str = None,
    location: str = None,
    environmental_factors: dict = None,
    activity_context: str = None,
    tags: list[str] = None,
    user_id: str = None,
    ctx: Context = None,
) -> Dict[str, Any]:
    """
    Implementation for saving a confirmed symptom entry to Elasticsearch.
    """
    try:
        # Build entry dict from parameters
        entry = {
            "timestamp": timestamp,
            "user_id": user_id,
            "symptom_details": {
                "symptom": symptom,
                "severity": severity,
                "length_minutes": length_minutes,
                "cause": cause,
                "mediation_attempt": mediation_attempt,
                "on_medication": on_medication,
                "raw_notes": raw_notes,
                "event_complete": event_complete,
                "onset_type": onset_type,
                "intensity_pattern": intensity_pattern,
                "associated_symptoms": associated_symptoms,
                "relief_factors": relief_factors,
            },
            "tags": tags,
        }

        # Add environmental if any environmental fields provided
        if location or environmental_factors or activity_context:
            entry["environmental"] = {
                "location": location,
                "environmental_factors": environmental_factors,
                "activity_context": activity_context,
            }

        entry = clean_entry(entry)
        entry = ensure_raw_notes(entry)
        parsed = SymptomEntry(**entry)
        resp = await es.index(index=es_index, document=parsed.model_dump())

        # Jury trigger logic with persistent counter
        jury_trigger_count = await increment_jury_counter(es)
        jury_reviewed = False

        if jury_trigger_modulo and (jury_trigger_count % jury_trigger_modulo == 0):
            try:
                # Extract event_id from Elasticsearch response
                event_id = get_es_response_id(resp)

                if event_id:
                    raw_notes_val = (
                        parsed.symptom_details.raw_notes
                        if hasattr(parsed.symptom_details, "raw_notes")
                        else None
                    )
                    # Use mode='json' to serialize datetime objects to ISO format strings
                    structured_entry = parsed.model_dump(mode="json")
                    # Run jury review in background - results saved to ES
                    await llm_jury_compare_notes(
                        event_id, raw_notes_val, structured_entry, ctx, es
                    )
                    jury_reviewed = True
            except Exception as e:
                jury_error = f"Failed to trigger jury tool: {str(e)}"
                if ctx:
                    ctx.error(jury_error)
                # Don't fail the save if jury fails
                jury_reviewed = False

        return {
            "status": "saved",
            "entry": resp.body if hasattr(resp, "body") else resp,
            "jury_reviewed": jury_reviewed,
        }
    except Exception as e:
        if ctx:
            ctx.error(f"Failed to save entry: {e}")
        return {"status": "error", "error": str(e)}
