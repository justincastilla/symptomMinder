import os

from fastmcp import FastMCP, Context
from elasticsearch import AsyncElasticsearch
from typing import  List

from symptom_schema import SymptomEntry
from jury_tools import llm_jury_compare_notes

# --- Elasticsearch Client ---
ES_ENDPOINT = os.environ.get("ES_ENDPOINT", "http://localhost:9200")
ES_API_KEY = os.environ.get("ES_API_KEY")
ES_INDEX = os.environ.get("ES_INDEX", "symptom_entries")
es = AsyncElasticsearch(hosts=[ES_ENDPOINT], api_key=ES_API_KEY)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY environment variable not set.")

# --- Jury Configuration ---
JURY_MODE = os.environ.get("JURY_MODE", "every_1")  # 'none', or 'every_X' (e.g., 'every_5')


mcp = FastMCP("SymptomMinder")


# --- MCP Tool: Record Symptom Entry ---
@mcp.tool(
    name="review_symptom_entry",
    description="Review a symptom entry and return a confirmation prompt before saving."
)
def review_symptom_entry(entry: dict, ctx: Context) -> dict:
    """Return a review prompt for the symptom entry, do not save yet."""
    def _generate_review_prompt(entry: SymptomEntry) -> str:
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
        return f"Please review the following symptom entry for accuracy before saving:\n\n{summary}\nIs this information correct?"

    # Pre-validation: fix common client mistakes
    def _clean_entry(entry: dict) -> dict:
        import copy
        entry = copy.deepcopy(entry)
        # Ensure symptom_details is present and correct
        sd = entry.get("symptom_details")
        if sd:
            # Convert string 'none' to None or [] for lists
            for k, v in list(sd.items()):
                if isinstance(v, str) and v.strip().lower() == "none":
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

    try:
        entry = _clean_entry(entry)
        parsed = SymptomEntry(**entry)
        prompt = _generate_review_prompt(parsed)
        return {"status": "review", "review_prompt": prompt, "entry": parsed.model_dump()}
    except Exception as e:
        ctx.error(f"Failed to generate review: {e}")
        return {"status": "error", "error": str(e)}

# --- Jury trigger counter (in-memory, resets on server restart) ---
JURY_TRIGGER_COUNT = 0
JURY_TRIGGER_MODULO = 1
if JURY_MODE.startswith("every_"):
    try:
        JURY_TRIGGER_MODULO = int(JURY_MODE.split("_")[1])
    except Exception:
        JURY_TRIGGER_MODULO = 1
elif JURY_MODE == "none":
    JURY_TRIGGER_MODULO = 0

@mcp.tool(
    name="confirm_and_save_symptom_entry",
    description="Save a symptom entry to Elasticsearch after user confirmation."
)
async def confirm_and_save_symptom_entry(entry: dict, ctx: Context) -> dict:
    """Save the confirmed symptom entry to Elasticsearch and trigger jury per JURY_MODE."""
    global JURY_TRIGGER_COUNT, JURY_TRIGGER_MODULO
    def _clean_entry(entry: dict) -> dict:
        import copy
        entry = copy.deepcopy(entry)
        sd = entry.get("symptom_details")
        if sd:
            for k, v in list(sd.items()):
                if isinstance(v, str) and v.strip().lower() == "none":
                    if k in ("associated_symptoms",):
                        sd[k] = []
                    else:
                        sd[k] = None
            if "associated_symptoms" in sd and not isinstance(sd["associated_symptoms"], list):
                if isinstance(sd["associated_symptoms"], str):
                    sd["associated_symptoms"] = [sd["associated_symptoms"]]
                elif sd["associated_symptoms"] is None:
                    sd["associated_symptoms"] = []
            # Ensure raw_notes is set to user's description if not already present
            if not sd.get("raw_notes"):
                # Prefer description, then notes, then summary, then context if present
                for field in ["description", "notes", "summary", "context"]:
                    if field in sd and isinstance(sd[field], str) and sd[field].strip():
                        sd["raw_notes"] = sd[field].strip()
                        break
        entry["symptom_details"] = sd
        return entry

    try:
        entry = _clean_entry(entry)
        parsed = SymptomEntry(**entry)
        resp = await es.index(index=ES_INDEX, document=parsed.model_dump())
        # Jury trigger logic
        JURY_TRIGGER_COUNT += 1
        jury_result = None
        if JURY_TRIGGER_MODULO and (JURY_TRIGGER_COUNT % JURY_TRIGGER_MODULO == 0):
            try:
                # Call jury tool with event_id, raw_notes, and full entry as dict
                event_id = resp.body.get("_id") if hasattr(resp, "body") and resp.body else None
                if not event_id:
                    # fallback to Elasticsearch response structure
                    event_id = resp.get("_id") if hasattr(resp, "get") else None
                # Use the same entry as saved
                raw_notes = parsed.symptom_details.raw_notes if hasattr(parsed.symptom_details, "raw_notes") else None
                structured_entry = parsed.model_dump()
                # jury_tools.llm_jury_compare_notes expects es as argument
                jury_result = await llm_jury_compare_notes(event_id, raw_notes, structured_entry, ctx, es)
            except Exception as e:
                ctx.error(f"Failed to trigger jury tool: {e}")
        return {"status": "saved", "entry": resp.body, "jury_result": jury_result}
    except Exception as e:
        ctx.error(f"Failed to save entry: {e}")
        return {"status": "error", "error": str(e)}

# --- MCP Resource: Retrieve Symptom Entries ---
@mcp.resource(
    uri="symptom://entries/{limit}",
    name="list_symptom_entries",
    description="Retrieve symptom entries from Elasticsearch"
)
def list_symptom_entries(limit: int = 20) -> List[dict]:
    """Retrieve the most recent symptom entries."""
    try:
        resp = es.search(index=ES_INDEX, size=limit, sort="timestamp:desc")
        hits = resp["hits"]["hits"]
        return [hit["_source"] for hit in hits]
    except Exception as e:
        return [{"status": "error", "error": str(e)}]

# --- MCP Resource: Flexible Search with Semantic Notes ---
@mcp.tool(
    name="flexible_search",
    description="Flexible search for symptom entries using a query object. Accepts a dict of filters, supporting semantic search and field filters."
)
async def flexible_search(ctx: Context, query: dict) -> List[dict]:
    """
    Flexible search for symptom entries. Accepts a query dict with any of these keys:
        - symptom: str
        - on_medication: bool
        - mediation_attempt: str
        - start_time: str (ISO8601)
        - end_time: str (ISO8601)
        - notes_query: str
        - limit: int (default 20)
    Returns a list of matching symptom entries.
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

        if symptom:
            must_clauses.append({"match": {"symptom": symptom}})
        if on_medication is not None:
            must_clauses.append({"term": {"on_medication": on_medication}})
        if mediation_attempt:
            must_clauses.append({"match": {"mediation_attempt": mediation_attempt}})
        if start_time or end_time:
            range_query = {}
            if start_time:
                range_query["gte"] = start_time
            if end_time:
                range_query["lte"] = end_time
            must_clauses.append({"range": {"timestamp": range_query}})
        if notes_query:
            must_clauses.append({"match": {"raw_notes": {"query": notes_query, "fuzziness": "AUTO"}}})
        es_query = {"bool": {"must": must_clauses}} if must_clauses else {"match_all": {}}
        resp = await es.search(index=ES_INDEX, size=limit, query=es_query, sort=[{"timestamp": {"order": "desc"}}])
        hits = resp["hits"]["hits"]
        return [hit["_source"] for hit in hits]
    except Exception as e:
        return [{"status": "error", "error": str(e)}]

# --- Initialize and Register ---

if __name__ == "__main__":
   mcp.run()