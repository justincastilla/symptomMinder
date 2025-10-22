"""SymptomMinder FastMCP Server for recording and analyzing symptom data."""

import copy
import os
from typing import List, Optional

from elasticsearch import AsyncElasticsearch
from fastmcp import Context, FastMCP

from jury_tools import llm_jury_compare_notes
from symptom_schema import SymptomEntry

# --- Elasticsearch Client ---
ES_ENDPOINT = os.environ.get("ES_ENDPOINT", "http://localhost:9200")
ES_API_KEY = os.environ.get("ES_API_KEY")
ES_INDEX = os.environ.get("ES_INDEX", "symptom_entries")
JURY_COUNTER_INDEX = os.environ.get("JURY_COUNTER_INDEX", "jury_counter")

# Initialize Elasticsearch client
try:
    # Configure client based on whether we're using cloud/serverless or local
    if ES_API_KEY:
        # Cloud/Serverless with API key authentication
        es = AsyncElasticsearch(
            hosts=[ES_ENDPOINT],
            api_key=ES_API_KEY,
            verify_certs=True,
            request_timeout=30
        )
    else:
        # Local instance without authentication
        es = AsyncElasticsearch(
            hosts=[ES_ENDPOINT],
            verify_certs=False,
            request_timeout=30
        )
except Exception as e:
    raise RuntimeError(f"Failed to initialize Elasticsearch client: {e}")

# --- Anthropic API Configuration ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY environment variable not set.")

# --- Jury Configuration ---
JURY_MODE = os.environ.get("JURY_MODE", "every_1")  # 'none', or 'every_X' (e.g., 'every_5')


mcp = FastMCP("SymptomMinder")

# Null value variations to normalize
NULL_VALUES = {"none", "null", "n/a", "na", "nil", ""}


def _is_null_value(value: str) -> bool:
    """Check if a string represents a null value."""
    return isinstance(value, str) and value.strip().lower() in NULL_VALUES


def _clean_entry(entry: dict) -> dict:
    """
    Clean and normalize entry data from client.

    Args:
        entry: Raw entry dictionary

    Returns:
        Cleaned entry dictionary with normalized values
    """
    entry = copy.deepcopy(entry)
    sd = entry.get("symptom_details")
    if sd:
        # Convert null-like strings to None or [] for lists
        for k, v in list(sd.items()):
            if _is_null_value(v):
                # Use [] for known list fields, else None
                if k in ("associated_symptoms",):
                    sd[k] = []
                else:
                    sd[k] = None
        # Convert associated_symptoms to list if needed
        if "associated_symptoms" in sd and not isinstance(sd["associated_symptoms"], list):
            if isinstance(sd["associated_symptoms"], str):
                sd["associated_symptoms"] = [sd["associated_symptoms"]]
            elif sd["associated_symptoms"] is None:
                sd["associated_symptoms"] = []
    entry["symptom_details"] = sd
    return entry


def _ensure_raw_notes(entry: dict) -> dict:
    """
    Ensure raw_notes field is populated from description or similar fields.

    Args:
        entry: Entry dictionary with symptom_details

    Returns:
        Entry with raw_notes populated if possible
    """
    entry = copy.deepcopy(entry)
    sd = entry.get("symptom_details", {})

    # Ensure raw_notes is set to user's description if not already present
    if not sd.get("raw_notes"):
        # Prefer description, then notes, then summary, then context if present
        for field in ["description", "notes", "summary", "context"]:
            if field in sd and isinstance(sd[field], str) and sd[field].strip():
                sd["raw_notes"] = sd[field].strip()
                break

    entry["symptom_details"] = sd
    return entry


def _get_es_response_id(resp) -> Optional[str]:
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


async def _get_jury_counter() -> int:
    """Get the current jury trigger counter from Elasticsearch."""
    try:
        resp = await es.get(index=JURY_COUNTER_INDEX, id="global_counter")
        return resp["_source"].get("count", 0)
    except Exception:
        # Counter doesn't exist yet, initialize it
        return 0


async def _increment_jury_counter() -> int:
    """Increment and return the jury trigger counter."""
    try:
        current = await _get_jury_counter()
        new_count = current + 1
        await es.index(
            index=JURY_COUNTER_INDEX,
            id="global_counter",
            document={"count": new_count}
        )
        return new_count
    except Exception:
        # Fallback to 0 if counter update fails
        return 0


def _generate_review_prompt(entry: SymptomEntry) -> str:
    """
    Generate human-readable review prompt for symptom entry.

    Args:
        entry: Validated SymptomEntry object

    Returns:
        Formatted review prompt string
    """
    details = entry.symptom_details
    env = entry.environmental
    summary = (
        f"Symptom: {details.symptom}\n"
        f"Severity: {details.severity}\n"
        f"Timestamp: {entry.timestamp}\n"
        f"Length (min): {details.length_minutes}\n"
        f"Location: {getattr(env, 'location', '') if env else ''}\n"
        f"Cause: {details.cause}\n"
        f"Mediation Attempt: {details.mediation_attempt}\n"
        f"On Medication: {details.on_medication}\n"
        f"Raw Notes: {details.raw_notes}\n"
        f"Event Complete: {details.event_complete}\n"
        f"Onset Type: {details.onset_type}\n"
        f"Intensity Pattern: {details.intensity_pattern}\n"
        f"Associated Symptoms: {details.associated_symptoms}\n"
        f"Relief Factors: {details.relief_factors}\n"
        f"Environmental Factors: {getattr(env, 'environmental_factors', '') if env else ''}\n"
        f"Activity Context: {getattr(env, 'activity_context', '') if env else ''}\n"
        f"Tags: {entry.tags}\n"
    )
    return (
        f"Please review the following symptom entry for accuracy before saving:\n\n"
        f"{summary}\nIs this information correct?"
    )


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
    ctx: Context = None
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

        entry = _clean_entry(entry)
        parsed = SymptomEntry(**entry)
        prompt = _generate_review_prompt(parsed)
        return {"status": "review", "review_prompt": prompt, "entry": parsed.model_dump()}
    except Exception as e:
        if ctx:
            ctx.error(f"Failed to generate review: {e}")
        return {"status": "error", "error": str(e)}


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
    ctx: Context = None
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

        entry = _clean_entry(entry)
        entry = _ensure_raw_notes(entry)
        parsed = SymptomEntry(**entry)
        resp = await es.index(index=ES_INDEX, document=parsed.model_dump())

        # Jury trigger logic with persistent counter
        jury_trigger_count = await _increment_jury_counter()
        jury_reviewed = False

        if jury_trigger_modulo and (jury_trigger_count % jury_trigger_modulo == 0):
            try:
                # Extract event_id from Elasticsearch response
                event_id = _get_es_response_id(resp)

                if event_id:
                    raw_notes_val = (
                        parsed.symptom_details.raw_notes
                        if hasattr(parsed.symptom_details, "raw_notes")
                        else None
                    )
                    # Use mode='json' to serialize datetime objects to ISO format strings
                    structured_entry = parsed.model_dump(mode='json')
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
            "jury_reviewed": jury_reviewed
        }
    except Exception as e:
        if ctx:
            ctx.error(f"Failed to save entry: {e}")
        return {"status": "error", "error": str(e)}


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
    try:
        resp = await es.search(index=ES_INDEX, size=limit, sort="timestamp:desc")
        hits = resp["hits"]["hits"]
        return [hit["_source"] for hit in hits]
    except Exception as e:
        return [{"status": "error", "error": str(e)}]


# --- MCP Prompt: Follow-up Guidance ---
@mcp.prompt(
    name="symptom_followup_guidance",
    description="Guidance for following up on incomplete symptoms naturally and non-intrusively"
)
async def symptom_followup_guidance() -> str:
    """
    Provide guidance for Claude on when and how to follow up on incomplete symptoms.

    Returns:
        str: Prompt text with follow-up guidance
    """
    return """# Symptom Follow-up Guidance

When interacting with users, you can help track ongoing symptoms by naturally asking about incomplete entries.

## When to Check for Follow-ups

Check for incomplete symptoms in these situations:
1. At the START of a conversation (once per session, not every message)
2. When the user mentions feeling better or different than before
3. When the user brings up a previous symptom
4. If the user asks about their symptom history

## How to Ask (Non-Intrusive)

✅ GOOD (Natural and helpful):
- "Before we start, I noticed you had an ongoing headache from yesterday. How's that feeling now?"
- "I see you mentioned kidney pain earlier that was marked as incomplete. Has that resolved?"
- "You had noted some symptoms were still ongoing. Would you like to update me on how those are doing?"

❌ AVOID (Annoying and pushy):
- Don't ask about incomplete symptoms in EVERY message
- Don't ask during unrelated conversations
- Don't force the user to provide updates if they're focused on something else
- Don't make it feel like homework or a checklist

## Using the Tools

1. **get_incomplete_symptoms()** - Check for incomplete entries
   - Returns incomplete symptoms sorted by **MOST RECENT FIRST**
   - **ALWAYS use `limit=1`** to get only the single most recent symptom
   - DO NOT list all symptoms - overwhelming for user
   - If user updates one and wants more, call again with `limit=1`

2. **update_symptom_entry()** - Update when user provides follow-up
   - Always include `event_id` from the incomplete symptom
   - Set `event_complete=true` if resolved
   - Add `resolution_notes` with what the user shared
   - Update `length_minutes` if they mention total duration
   - Add `relief_factors` if they mention what helped

## Prioritization Strategy: ONLY the Most Recent

**CRITICAL: DO NOT OVERWHELM THE USER**
- Use `get_incomplete_symptoms(limit=1)` - gets ONLY the single most recent
- Ask about ONLY that one symptom
- DO NOT list all incomplete symptoms
- DO NOT mention how many incomplete symptoms there are
- Keep it simple and focused

**Why:** The most recently recorded incomplete symptom is freshest in memory = best data quality. Asking about multiple at once is overwhelming.

**How to ask:**
1. Check `get_incomplete_symptoms(limit=1)` - returns ONLY the most recent one
2. If you get a result, ask about that ONE symptom naturally
3. If user updates it, STOP - do not ask about more
4. If user seems willing to continue, you can call the tool again to get the next one, but ONLY if they explicitly want to continue

**Example:**
Query returns: [Headache from 2025-10-22 14:00]
Ask: "I noticed your most recent incomplete symptom was a headache. How's that feeling now?"
DO NOT SAY: "You have 5 incomplete symptoms. Let me ask about them..."

## Example Flow

User: "Good morning!"
Assistant: [Calls get_incomplete_symptoms(limit=1) - returns just the headache]
Assistant: "Good morning! I noticed your most recent incomplete symptom was a headache. How's that feeling now?"

User: "Oh yeah, that went away yesterday afternoon after I drank more water."
Assistant: [Calls update_symptom_entry with event_complete=true, resolution_notes="Resolved after drinking more water", relief_factors="hydration"]
Assistant: "Great to hear it resolved! Now, what can I help you with today?"

---

**If user wants to continue:**
User: "Are there any other symptoms I should update?"
Assistant: [NOW calls get_incomplete_symptoms(limit=1) again to get the next most recent]
Assistant: "Yes, you also have knee pain from last week. Is that still bothering you?"

## Key Principles

- Be **helpful**, not **nagging**
- Respect the user's **current focus**
- Make it feel like **caring**, not **tracking**
- **Once per session** is enough for proactive checks
- Let the user **opt out** gracefully if they don't want to discuss it
"""


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
    try:
        must_clauses = []
        symptom = query.get("symptom")
        on_medication = query.get("on_medication")
        mediation_attempt = query.get("mediation_attempt")
        start_time = query.get("start_time")
        end_time = query.get("end_time")
        notes_query = query.get("notes_query")
        limit = query.get("limit", 20)

        # Fix: Use correct nested field paths
        if symptom:
            must_clauses.append({"match": {"symptom_details.symptom": symptom}})
        if on_medication is not None:
            must_clauses.append({"term": {"symptom_details.on_medication": on_medication}})
        if mediation_attempt:
            must_clauses.append({"match": {"symptom_details.mediation_attempt": mediation_attempt}})
        if start_time or end_time:
            range_query = {}
            if start_time:
                range_query["gte"] = start_time
            if end_time:
                range_query["lte"] = end_time
            must_clauses.append({"range": {"timestamp": range_query}})
        if notes_query:
            must_clauses.append(
                {"match": {"symptom_details.raw_notes": {"query": notes_query, "fuzziness": "AUTO"}}}
            )

        es_query = {"bool": {"must": must_clauses}} if must_clauses else {"match_all": {}}
        resp = await es.search(
            index=ES_INDEX, size=limit, query=es_query, sort=[{"timestamp": {"order": "desc"}}]
        )
        hits = resp["hits"]["hits"]
        return [hit["_source"] for hit in hits]
    except Exception as e:
        return [{"status": "error", "error": str(e)}]


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
    limit: int = 1,
    days_back: int = None,
    ctx: Context = None
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
    try:
        # Query for incomplete symptoms (false or null)
        # Should match where event_complete is NOT explicitly true
        query = {
            "bool": {
                "should": [
                    {"term": {"symptom_details.event_complete": False}},
                    {"bool": {"must_not": {"exists": {"field": "symptom_details.event_complete"}}}}
                ],
                "minimum_should_match": 1
            }
        }

        # Add time range if specified
        if days_back is not None:
            from datetime import datetime, timedelta, timezone
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_back)
            cutoff_iso = cutoff_time.isoformat()

            query["bool"]["must"] = [
                {"range": {"timestamp": {"gte": cutoff_iso}}}
            ]

        resp = await es.search(
            index=ES_INDEX,
            size=limit,
            query=query,
            sort=[{"timestamp": {"order": "desc"}}]
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
        return [{"status": "error", "error": str(e)}]


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
    ctx: Context = None
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
    try:
        # First, get the existing document
        existing = await es.get(index=ES_INDEX, id=event_id)
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
                doc["symptom_details"]["raw_notes"] = f"{existing_notes}\n\nFollow-up: {resolution_notes}"
            else:
                doc["symptom_details"]["raw_notes"] = f"Follow-up: {resolution_notes}"

        if tags is not None:
            doc["tags"] = tags

        # Update the document in Elasticsearch
        resp = await es.index(index=ES_INDEX, id=event_id, document=doc)

        return {
            "status": "updated",
            "event_id": event_id,
            "updated_fields": {
                "event_complete": event_complete,
                "resolution_notes": resolution_notes is not None,
                "length_minutes": length_minutes,
                "relief_factors": relief_factors,
                "severity": severity,
                "tags": tags
            },
            "entry": resp.body if hasattr(resp, "body") else resp
        }
    except Exception as e:
        if ctx:
            ctx.error(f"Failed to update symptom entry: {e}")
        return {"status": "error", "error": str(e)}


# --- Initialize and Register ---
if __name__ == "__main__":
    mcp.run()
