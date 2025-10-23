"""SymptomMinder FastMCP Server for recording and analyzing symptom data."""

import copy
import os
from typing import List, Optional

from fastmcp import Context, FastMCP

from jury_tools import llm_jury_compare_notes
from symptom_schema import SymptomEntry
from utils.data_utils import clean_entry, ensure_raw_notes
from utils.es_utils import (
    create_es_client,
    get_es_response_id,
    get_jury_counter,
    increment_jury_counter,
)
from utils.prompt_utils import generate_review_prompt
from tools.symptom_tools import (
    review_symptom_entry_impl,
    confirm_and_save_symptom_entry_impl,
)
from tools.search_tools import (
    flexible_search_impl,
    get_incomplete_symptoms_impl,
    update_symptom_entry_impl,
)
from resources.symptom_resources import list_symptom_entries_impl
from prompts.followup_prompts import symptom_followup_guidance_impl

# --- Elasticsearch Client ---
ES_INDEX = os.environ.get("ES_INDEX", "symptom_entries")

# Initialize Elasticsearch client using shared utility
try:
    es = create_es_client()
except Exception as e:
    raise RuntimeError(f"Failed to initialize Elasticsearch client: {e}")

# --- Anthropic API Configuration ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY environment variable not set.")

# --- Jury Configuration ---
JURY_MODE = os.environ.get(
    "JURY_MODE", "every_1"
)  # 'none', or 'every_X' (e.g., 'every_5')


mcp = FastMCP("SymptomMinder")


# --- MCP Tool: Review Symptom Entry ---
@mcp.tool(
    name="review_symptom_entry",
    description=(
        "Review a symptom entry before saving. Provide symptom details including: "
        "symptom (required), severity 1-10 (required), timestamp (required), "
        "optional: length_minutes, cause, mediation_attempt, on_medication, raw_notes. "
        "Returns a human-readable summary for user confirmation."
    ),
)
def review_symptom_entry(
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
) -> dict:
    """
    Return a review prompt for the symptom entry, do not save yet.

    Args:
        symptom: Description of the symptom (required)
        severity: Severity from 1 (light) to 10 (severe) (required)
        timestamp: ISO8601 timestamp of symptom occurrence (required)
        length_minutes: Duration of symptom in minutes
        cause: Suspected cause of symptom
        mediation_attempt: What was done to mediate symptom
        on_medication: Whether user was on medication at the time
        raw_notes: Raw notes from user
        event_complete: Whether the recorded event is considered complete
        onset_type: Onset type (sudden, gradual, recurring, etc.)
        intensity_pattern: Pattern of symptom intensity over time
        associated_symptoms: Other symptoms present at the same time
        relief_factors: Factors that relieved or worsened the symptom
        location: Location where symptom occurred
        environmental_factors: Environmental data at the time
        activity_context: User activity when symptom began
        tags: User or system tags for this entry
        user_id: Unique identifier for the user
        ctx: FastMCP context for logging

    Returns:
        dict: Review status with prompt or error message
    """
    return review_symptom_entry_impl(
        symptom=symptom,
        severity=severity,
        timestamp=timestamp,
        length_minutes=length_minutes,
        cause=cause,
        mediation_attempt=mediation_attempt,
        on_medication=on_medication,
        raw_notes=raw_notes,
        event_complete=event_complete,
        onset_type=onset_type,
        intensity_pattern=intensity_pattern,
        associated_symptoms=associated_symptoms,
        relief_factors=relief_factors,
        location=location,
        environmental_factors=environmental_factors,
        activity_context=activity_context,
        tags=tags,
        user_id=user_id,
        ctx=ctx,
    )


# --- Jury Configuration Parsing ---
jury_trigger_modulo = 1

if JURY_MODE.startswith("every_"):
    try:
        jury_trigger_modulo = int(JURY_MODE.split("_")[1])
    except (ValueError, IndexError):
        jury_trigger_modulo = 1
elif JURY_MODE == "none":
    jury_trigger_modulo = 0


@mcp.tool(
    name="confirm_and_save_symptom_entry",
    description=(
        "Save a confirmed symptom entry to Elasticsearch. Use the same parameters "
        "from review_symptom_entry after user confirms the entry is correct."
    ),
)
async def confirm_and_save_symptom_entry(
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
) -> dict:
    """
    Save the confirmed symptom entry to Elasticsearch and trigger jury per JURY_MODE.

    Args:
        symptom: Description of the symptom (required)
        severity: Severity from 1 (light) to 10 (severe) (required)
        timestamp: ISO8601 timestamp of symptom occurrence (required)
        length_minutes: Duration of symptom in minutes
        cause: Suspected cause of symptom
        mediation_attempt: What was done to mediate symptom
        on_medication: Whether user was on medication at the time
        raw_notes: Raw notes from user
        event_complete: Whether the recorded event is considered complete
        onset_type: Onset type (sudden, gradual, recurring, etc.)
        intensity_pattern: Pattern of symptom intensity over time
        associated_symptoms: Other symptoms present at the same time
        relief_factors: Factors that relieved or worsened the symptom
        location: Location where symptom occurred
        environmental_factors: Environmental data at the time
        activity_context: User activity when symptom began
        tags: User or system tags for this entry
        user_id: Unique identifier for the user
        ctx: FastMCP context for logging

    Returns:
        dict: Save status with entry details and optional jury results
    """
    return await confirm_and_save_symptom_entry_impl(
        es=es,
        es_index=ES_INDEX,
        jury_trigger_modulo=jury_trigger_modulo,
        symptom=symptom,
        severity=severity,
        timestamp=timestamp,
        length_minutes=length_minutes,
        cause=cause,
        mediation_attempt=mediation_attempt,
        on_medication=on_medication,
        raw_notes=raw_notes,
        event_complete=event_complete,
        onset_type=onset_type,
        intensity_pattern=intensity_pattern,
        associated_symptoms=associated_symptoms,
        relief_factors=relief_factors,
        location=location,
        environmental_factors=environmental_factors,
        activity_context=activity_context,
        tags=tags,
        user_id=user_id,
        ctx=ctx,
    )


# --- MCP Resource: Retrieve Symptom Entries ---
@mcp.resource(
    uri="symptom://entries/{limit}",
    name="list_symptom_entries",
    description="Retrieve symptom entries from Elasticsearch",
)
async def list_symptom_entries(limit: int = 20) -> List[dict]:
    """
    Retrieve the most recent symptom entries.

    Args:
        limit: Maximum number of entries to retrieve

    Returns:
        List of symptom entry dictionaries
    """
    return await list_symptom_entries_impl(es=es, es_index=ES_INDEX, limit=limit)


# --- MCP Prompt: Follow-up Guidance ---
@mcp.prompt(
    name="symptom_followup_guidance",
    description="Guidance for following up on incomplete symptoms naturally and non-intrusively",
)
async def symptom_followup_guidance() -> str:
    """
    Provide guidance for Claude on when and how to follow up on incomplete symptoms.

    Returns:
        str: Prompt text with follow-up guidance
    """
    return await symptom_followup_guidance_impl()


# --- MCP Tool: Flexible Search with Semantic Notes ---
@mcp.tool(
    name="flexible_search",
    description=(
        "Flexible search for symptom entries using a query object. "
        "Accepts a dict of filters, supporting semantic search and field filters."
    ),
)
async def flexible_search(query: dict) -> List[dict]:
    """
    Flexible search for symptom entries.

    Accepts a query dict with any of these keys:
        - symptom: str
        - on_medication: bool
        - mediation_attempt: str
        - start_time: str (ISO8601)
        - end_time: str (ISO8601)
        - notes_query: str
        - limit: int (default 20)

    Args:
        query: Dictionary containing search filters

    Returns:
        List of matching symptom entries
    """
    return await flexible_search_impl(es=es, es_index=ES_INDEX, query=query)


# --- MCP Tool: Get Incomplete Symptoms ---
@mcp.tool(
    name="get_incomplete_symptoms",
    description=(
        "Retrieve incomplete symptom entries for follow-up. "
        "IMPORTANT: Always use limit=1 to get only the most recent incomplete symptom. "
        "Do NOT list all incomplete symptoms - overwhelming for users. "
        "Returns entries sorted by most recent first."
    ),
)
async def get_incomplete_symptoms(
    limit: int = 1, days_back: int = None, ctx: Context = None
) -> List[dict]:
    """
    Find symptoms marked as incomplete for follow-up.

    Args:
        limit: Maximum number of incomplete entries to return (default: 1 - ONLY the most recent)
        days_back: How many days back to search (default: None = all time)
        ctx: FastMCP context for logging

    Returns:
        List of incomplete symptom entries with event IDs (sorted most recent first)
    """
    return await get_incomplete_symptoms_impl(
        es=es, es_index=ES_INDEX, limit=limit, days_back=days_back, ctx=ctx
    )


# --- MCP Tool: Update Symptom Entry ---
@mcp.tool(
    name="update_symptom_entry",
    description=(
        "Update an existing symptom entry with follow-up information. "
        "Use this when the user provides updates about a previous symptom. "
        "Can mark symptoms as complete, add resolution notes, or update any field."
    ),
)
async def update_symptom_entry(
    event_id: str,
    event_complete: bool = None,
    resolution_notes: str = None,
    length_minutes: int = None,
    relief_factors: str = None,
    severity: int = None,
    tags: list[str] = None,
    ctx: Context = None,
) -> dict:
    """
    Update an existing symptom entry with new information.

    Args:
        event_id: The Elasticsearch document ID of the entry to update
        event_complete: Mark the event as complete (true) or ongoing (false)
        resolution_notes: Notes about how the symptom resolved or progressed
        length_minutes: Updated total duration in minutes
        relief_factors: What helped relieve the symptom
        severity: Updated severity (1-10) if it changed
        tags: Add or update tags
        ctx: FastMCP context for logging

    Returns:
        dict: Update status with updated entry
    """
    return await update_symptom_entry_impl(
        es=es,
        es_index=ES_INDEX,
        event_id=event_id,
        event_complete=event_complete,
        resolution_notes=resolution_notes,
        length_minutes=length_minutes,
        relief_factors=relief_factors,
        severity=severity,
        tags=tags,
        ctx=ctx,
    )


# --- Initialize and Register ---
if __name__ == "__main__":
    mcp.run()
