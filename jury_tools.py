"""LLM-based jury tool for comparing raw notes with structured symptom entries."""

import asyncio
import json
import os

import anthropic
from elasticsearch import AsyncElasticsearch
from fastmcp import Context

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
JURY_SUMMARY_INDEX = os.environ.get("JURY_SUMMARY_INDEX", "event_summaries")

# Jury prompt templates
JURY_COMPARISON_PROMPT_TEMPLATE = (
    "Compare the following raw user notes with the finalized structured symptom entry.\n"
    "- Identify any information in the notes that is missing or misrepresented in the entry.\n"
    "- Rate the faithfulness of the structured entry to the user's notes on a scale of 1-10.\n"
    "- Provide a brief summary of any discrepancies.\n\n"
    "Raw Notes:\n{raw_notes}\n\n"
    "Structured Entry (JSON):\n{structured_entry}"
)

JURY_AGGREGATION_PROMPT_TEMPLATE = (
    "You are an expert reviewer. Three different Claude models have acted as a 'jury' to "
    "compare raw user notes and a structured symptom entry. Below are their findings. "
    "Please compile a markdown table summarizing each model's findings side by side, "
    "including missing/misrepresented info, faithfulness rating, and summary of discrepancies.\n\n"
    "---\n\n{jury_reports}\n\n"
    "Table columns: Model, Missing/Misrepresented Info, Faithfulness Rating, Summary of Discrepancies."
)

# Jury models configuration
JURY_MODELS = [
    ("claude-3-5-sonnet-latest", "Claude 3.5 Sonnet (latest)"),
    ("claude-3-7-sonnet-latest", "Claude 3.7 Sonnet (latest)"),
    ("claude-sonnet-4-20250514", "Claude 4 Sonnet (20250514)"),
]
AGGREGATION_MODEL = "claude-sonnet-4-20250514"


# Jury tool function (to be referenced in server)
async def llm_jury_compare_notes(
    event_id: str, raw_notes: str, structured_entry: dict, ctx: Context, es: AsyncElasticsearch
) -> dict:
    """
    Compares raw_notes to structured entry using LLM, saves report in Elasticsearch.

    Args:
        event_id: Unique identifier for the event
        raw_notes: User's original notes/description
        structured_entry: Parsed and structured symptom entry
        ctx: FastMCP context for logging
        es: Elasticsearch client for storing results

    Returns:
        dict: Jury comparison results including analysis from multiple models
    """
    prompt = JURY_COMPARISON_PROMPT_TEMPLATE.format(
        raw_notes=raw_notes,
        structured_entry=json.dumps(structured_entry, indent=2)
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

        # Parallel execution helper for jury models
        async def call_jury_model(model_id: str, model_label: str) -> dict:
            """Call a single jury model and track success/failure."""
            try:
                response = await client.messages.create(
                    model=model_id,
                    max_tokens=512,
                    messages=[{"role": "user", "content": prompt}]
                )
                jury_text = (
                    response.content[0].text
                    if hasattr(response, "content") and response.content
                    else str(response)
                )
                return {
                    "model_id": model_id,
                    "model_label": model_label,
                    "jury_report": jury_text,
                    "success": True,
                    "error": None
                }
            except Exception as e:
                error_msg = str(e)
                ctx.error(f"Jury model {model_label} failed: {error_msg}")
                return {
                    "model_id": model_id,
                    "model_label": model_label,
                    "jury_report": f"Error: {error_msg}",
                    "success": False,
                    "error": error_msg
                }

        # Execute all jury models in parallel
        jury_outputs = await asyncio.gather(
            *[call_jury_model(model_id, model_label) for model_id, model_label in JURY_MODELS]
        )

        # Count successful and failed models
        successful_models = [o for o in jury_outputs if o["success"]]
        failed_models = [o for o in jury_outputs if not o["success"]]

        # Compose aggregation prompt
        jury_reports = "\n\n".join([
            f"### {o['model_label']}\n\n{o['jury_report']}"
            for o in jury_outputs
        ])
        table_prompt = JURY_AGGREGATION_PROMPT_TEMPLATE.format(jury_reports=jury_reports)

        # Use aggregation model to compile results
        agg_response = await client.messages.create(
            model=AGGREGATION_MODEL,
            max_tokens=700,
            messages=[{"role": "user", "content": table_prompt}],
        )
        agg_text = (
            agg_response.content[0].text
            if hasattr(agg_response, "content") and agg_response.content
            else str(agg_response)
        )

        # Save all outputs and aggregation
        report = {
            "event_id": event_id,
            "jury_prompt": prompt,
            "jury_models": [m[0] for m in JURY_MODELS],
            "jury_outputs": jury_outputs,
            "successful_models_count": len(successful_models),
            "failed_models_count": len(failed_models),
            "jury_aggregation_model": AGGREGATION_MODEL,
            "jury_aggregation": agg_text,
        }
        await es.index(index=JURY_SUMMARY_INDEX, document=report)

        return {
            "status": "jury_completed",
            "event_id": event_id,
            "jury_outputs": jury_outputs,
            "successful_models_count": len(successful_models),
            "failed_models_count": len(failed_models),
            "jury_aggregation": agg_text,
        }
    except Exception as e:
        ctx.error(f"Jury comparison failed: {e}")
        return {"status": "error", "error": str(e)}
