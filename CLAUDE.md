# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SymptomMinder is a FastMCP server for recording symptoms and related environmental/body information, storing data in Elasticsearch, and integrating with Claude Desktop for data entry and retrieval. **This is a development/demonstration project and should NOT be considered production-ready or medically reliable.**

## Development Commands

### Docker Setup (Recommended for Claude Desktop)

**1. Environment Configuration:**
```bash
cp .env.example .env
# Edit .env with your credentials (no spaces around =)
```

Required variables:
- `ANTHROPIC_API_KEY` - Your Anthropic API key
- `ES_ENDPOINT` - Elasticsearch endpoint (default: `http://localhost:9200`)
- `ES_API_KEY` - Elasticsearch API key (optional for local instances)
- `ES_INDEX` - Symptom entries index (default: `symptom_entries`)
- `JURY_SUMMARY_INDEX` - Jury summaries index (default: `event_summaries`)
- `JURY_COUNTER_INDEX` - Jury counter index (default: `jury_counter`)
- `JURY_MODE` - Jury trigger mode: `none`, `every_1`, `every_5`, etc. (default: `every_1`)

**2. Build and Run:**
```bash
# Build the Docker image
docker build -t symptom-minder .

# Start all services (Elasticsearch + MCP server)
docker-compose up -d

# View server logs
docker-compose logs -f symptom-minder

# Stop services
docker-compose down

# Clear all data (removes Elasticsearch volumes)
docker-compose down -v
```

**Access Points:**
- Elasticsearch: `http://localhost:9200`
- Elasticsearch healthcheck: `curl http://localhost:9200/_cluster/health`

### Local Python Setup (Alternative)

```bash
# Create and activate virtual environment with uv
uv venv
source .venv/bin/activate  # macOS/Linux

# Install dependencies (two methods)
# Option 1: Using uv (faster)
uv pip install -r requirements.txt

# Option 2: Using pip
pip install -r requirements.txt

# Run development server with inspector
fastmcp dev server.py

# Install to Claude Desktop
fastmcp install claude-desktop --server-spec server.py --name "Symptom Minder"
# Then restart Claude Desktop
```

## Architecture

### System Overview

SymptomMinder uses a **review-confirm-save** pattern for data entry. The system validates entries against user's raw notes using a multi-model LLM jury system for quality assurance.

### Data Flow

1. **User Input** → Claude Desktop
2. **Review Phase** → `review_symptom_entry` generates human-readable summary
3. **User Confirmation** → User validates entry accuracy
4. **Save Phase** → `confirm_and_save_symptom_entry` saves to Elasticsearch
5. **Jury Review** (conditional) → Multi-model LLM jury validates structured entry against raw notes
6. **Query/Retrieval** → `flexible_search` or `list_symptom_entries` resource
7. **Follow-up** (optional) → `get_incomplete_symptoms` and `update_symptom_entry` for ongoing tracking

### Key Components

**server.py** - Main FastMCP server entry point
- Initializes Elasticsearch client with environment-based configuration
- Registers all MCP tools, resources, and prompts using FastMCP decorators
- Delegates implementation to modular components in `tools/`, `resources/`, and `prompts/`
- Implements jury trigger logic with persistent counter (server.py:146-156)
- **Pattern:** Thin wrapper functions delegate to `*_impl()` functions for testability and separation of concerns

**symptom_schema.py** - Pydantic data models enforcing structure
- `SymptomEntry` - Top-level entry (timestamp, user_id, symptom_details, environmental, tags)
- `SymptomDetails` - Core symptom data (symptom, severity, duration, cause, mediation, raw_notes, etc.)
- `EnvironmentalFactors` - Location, environmental data, activity context

**jury_tools.py** - Multi-model LLM validation system
- `llm_jury_compare_notes()` - Validates structured entry against raw notes
- Runs 3 Claude models in parallel: claude-3-5-sonnet-latest, claude-3-7-sonnet-latest, claude-sonnet-4-20250514
- Aggregation model (claude-sonnet-4-20250514) compiles findings into markdown table
- Results saved to `JURY_SUMMARY_INDEX` for quality tracking
- Uses `asyncio.gather()` for parallel model execution (jury_tools.py:100-102)

**Modular Implementation Structure:**
```
tools/
  symptom_tools.py    - Entry review and save implementations
  search_tools.py     - Search, query, and update implementations
resources/
  symptom_resources.py - List entries resource implementation
prompts/
  followup_prompts.py  - Follow-up guidance prompt implementation
utils/
  data_utils.py       - Null value normalization, raw notes preservation
  es_utils.py         - Elasticsearch ID extraction, jury counter management
  prompt_utils.py     - Review prompt generation
```

All tool implementations follow the pattern: `server.py` contains MCP decorator → delegates to `*_impl()` function in appropriate module. This enables unit testing and separates FastMCP framework concerns from business logic.

### Data Schema

Entries use nested Pydantic models stored in Elasticsearch:
```
SymptomEntry
├── timestamp (datetime) *required
├── user_id (str, optional)
├── symptom_details (SymptomDetails) *required
│   ├── symptom (str) *required
│   ├── severity (int 1-10) *required
│   ├── length_minutes (int, optional)
│   ├── cause (str, optional)
│   ├── mediation_attempt (str, optional)
│   ├── on_medication (bool, optional)
│   ├── raw_notes (str, optional) - original user input
│   ├── event_complete (bool, optional)
│   ├── onset_type (str, optional)
│   ├── intensity_pattern (str, optional)
│   ├── associated_symptoms (list[str], optional)
│   └── relief_factors (str, optional)
├── environmental (EnvironmentalFactors, optional)
│   ├── location (str, optional)
│   ├── environmental_factors (dict, optional)
│   └── activity_context (str, optional)
└── tags (list[str], optional)
```

### Jury System Mechanics

**Trigger Logic:**
- Persistent counter in Elasticsearch (`JURY_COUNTER_INDEX`, doc: `global_counter`)
- Increments on each save, triggers based on `JURY_MODE` modulo
- Example: `JURY_MODE=every_5` → jury runs on entries 5, 10, 15...

**Execution:**
1. Extract `event_id` from ES response after save
2. Run `llm_jury_compare_notes()` with event_id, raw_notes, structured_entry
3. Three models evaluate in parallel via `asyncio.gather()` (jury_tools.py:100)
4. Aggregation model (claude-sonnet-4-20250514) compiles markdown table
5. Full report saved to `JURY_SUMMARY_INDEX`
6. Returns `jury_reviewed: true/false` to caller (full results in ES only)

### Follow-up System

**Purpose:**
Track incomplete/ongoing symptoms and gather follow-up data naturally without annoying the user.

**Key Field:**
- `event_complete` (boolean) - Marks whether symptom has resolved

**Tools:**

1. **get_incomplete_symptoms()**
   - Queries for entries where `event_complete` is `false` OR `null`
   - **Defaults to `limit=1`** - returns only the most recent incomplete symptom
   - Searches ALL time (`days_back=None`) to catch everything
   - Returns entries with `_id` for updates (sorted by timestamp desc)
   - Claude should check at conversation start (once per session)

2. **update_symptom_entry()**
   - Updates existing entries by `event_id`
   - Can mark `event_complete=true` when resolved
   - Adds `resolution_notes` appended to `raw_notes`
   - Updates duration, severity, relief factors, etc.

3. **symptom_followup_guidance (prompt)**
   - Guides Claude on when/how to ask follow-ups
   - Emphasizes being helpful, not pushy
   - "Once per session" rule to avoid nagging
   - Provides example conversation flows

**Prioritization Strategy:**
- **Use `limit=1`** - get ONLY the single most recent incomplete symptom
- Ask about that ONE symptom only
- DO NOT list all incomplete symptoms or mention how many exist
- If user updates it and wants to continue, call the tool again for the next one

**Best Practices:**
- Check incomplete symptoms at conversation start, NOT every message
- Always use `limit=1` to avoid overwhelming the user
- Ask about one symptom at a time
- Respect user's current focus - don't interrupt unrelated tasks
- Make it conversational: "I noticed your most recent incomplete symptom was a headache. How's that feeling now?"
- Let user opt out gracefully - if they update one, STOP unless they ask for more

## Critical Implementation Details

### Data Cleaning Pipeline

**Null Value Normalization (utils/data_utils.py:clean_entry)**
- Recognizes null-like strings: `"none"`, `"null"`, `"n/a"`, `"na"`, `"nil"`, `""` (case-insensitive)
- Converts to `None` for scalar fields, `[]` for list fields
- `associated_symptoms` always normalized to list type
- Applied before validation and save

**Raw Notes Preservation (utils/data_utils.py:ensure_raw_notes)**
- `raw_notes` field populated from user input before save
- Fallback chain: `description` → `notes` → `summary` → `context`
- Essential for accurate jury validation
- Called in `confirm_and_save_symptom_entry_impl` (tools/symptom_tools.py:142)

### Elasticsearch Considerations

**Field Paths:**
Always use nested paths in queries: `symptom_details.symptom`, `symptom_details.on_medication`, NOT top-level field names.

**Response Extraction:**
Use `get_es_response_id()` helper (utils/es_utils.py:11-25) to safely extract document IDs from responses (handles both dict and object types).

**Jury Counter:**
Persistent counter stored in Elasticsearch (`JURY_COUNTER_INDEX`, doc ID: `global_counter`). Managed by `get_jury_counter()` and `increment_jury_counter()` in utils/es_utils.py:28-49.

### Async Patterns

- All Elasticsearch operations are async (use `await`)
- Jury models execute in parallel via `asyncio.gather()` for speed
- All Anthropic API calls are async

### FastMCP Context

All MCP tools receive `ctx: Context` parameter for logging. Use `ctx.error()` for error logging visible in FastMCP inspector.

## Requirements

- **Python:** 3.12+ (Dockerfile specifies python:3.12-slim)
- **Key Dependencies:**
  - `fastmcp>=2.0.0` - FastMCP framework for MCP server
  - `elasticsearch>=9.1.0` - Async Elasticsearch client
  - `anthropic>=0.61.0` - Anthropic API for LLM jury
  - `aiohttp>=3.12.15` - Async HTTP client
  - `pydantic` - Data validation (via fastmcp)
  - `python-dotenv` - Environment variable management
  - `uv>=0.1.0` - Fast Python package installer
  - `fastapi>=0.100.0`, `uvicorn>=0.24.0` - FastMCP dependencies

## Security Notice

**This is a demonstration project with NO security guarantees.** Data privacy is not enforced. This application is not intended for medical use and should not be used as a substitute for professional medical advice.
