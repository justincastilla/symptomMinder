# ⚠️ Developer NOTE ⚠️
> This project is currently in development and is not ready for production. The purpose is to document possibly sensitive medical information and provide a platform for analysis. There should be absolutely **NO assumption of data privacy or security** in this demonstration. Advice or instructions given by the server or the LLM should be taken with a grain of salt. This application demo and proof of concept is **not intended for medical use** and should not be used as a substitute for professional medical advice.

# SymptomMinder FastMCP Server

A FastMCP server for recording symptoms and related environmental/body information, storing it in Elasticsearch, and integrating with Claude Desktop for intelligent data entry and retrieval.

## Motivation

Now more than ever, people are empowering themselves with tools to better understand their health and well-being. With the rise of AI and machine learning, we can use these tools to better understand our individual health through data collection and analysis.

Sickness and wellness are complex, and we can't always know what the big picture is. By recording and analyzing our symptoms and related information, we can better understand our health and make informed decisions about our care. We all know at least three people who have a "silent" condition that may not have an outward appearance, but may be causing them significant discomfort, pain, or disability. By creating and maintaining a record of their physical experience, we hope to provide documentation and support for their care.

## Features

- **Review-Confirm-Save Pattern**: Validate entries before saving
- **Multi-Model LLM Jury**: Quality assurance using multiple Claude models
- **Flexible Search**: Date ranges, symptoms, medications, semantic notes search
- **Follow-up Tracking**: Track incomplete symptoms and gather updates
- **Elasticsearch Storage**: Powerful querying and data persistence
- **Claude Desktop Integration**: Natural language symptom entry

---

## Quick Start with Docker (Recommended)

### Prerequisites

- Docker and Docker Compose installed
- Anthropic API key
- Elasticsearch instance (or use included local setup)

### 1. Environment Configuration

Copy the example environment file and configure your credentials:

```bash
cp .env.example .env
```

Edit `.env` and set your credentials (no spaces around `=`):

```bash
# Required
ANTHROPIC_API_KEY=your-anthropic-api-key-here
ES_ENDPOINT=https://your-elasticsearch-endpoint:443
ES_API_KEY=your-elasticsearch-api-key-here

# Optional (defaults provided)
ES_INDEX=symptom_entries
JURY_SUMMARY_INDEX=event_summaries
JURY_COUNTER_INDEX=jury_counter
JURY_MODE=every_1
```

**For local Elasticsearch (no cloud):**
```bash
ANTHROPIC_API_KEY=your-anthropic-api-key-here
ES_ENDPOINT=http://elasticsearch:9200
# Leave ES_API_KEY empty for local setup
ES_INDEX=symptom_entries
```

### 2. Start Services with Docker Compose

```bash
# Start Elasticsearch and SymptomMinder
docker-compose up -d

# View logs
docker-compose logs -f symptom-minder

# Stop services
docker-compose down

# Reset all data (removes Elasticsearch volumes)
docker-compose down -v
```

**Access Points:**
- Elasticsearch: `http://localhost:9200`
- Health check: `curl http://localhost:9200/_cluster/health`

### 3. Configure Claude Desktop

Add the following to your Claude Desktop MCP settings file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

**Configuration:**

```json
{
  "mcpServers": {
    "symptom-minder": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--env-file",
        "/absolute/path/to/SymptomMinder/.env",
        "symptom-minder"
      ]
    }
  }
}
```

**Important:** Replace `/absolute/path/to/SymptomMinder/` with the actual path to your SymptomMinder directory.

**Find your absolute path:**
```bash
# macOS/Linux
cd /path/to/SymptomMinder
pwd

# Windows (PowerShell)
cd C:\path\to\SymptomMinder
(Get-Location).Path
```

### 4. Restart Claude Desktop

After adding the configuration:
1. Quit Claude Desktop completely
2. Restart Claude Desktop
3. Look for the 🔨 hammer icon indicating MCP servers are connected
4. Start using SymptomMinder by describing your symptoms naturally!

---

## Testing the Server Locally

### Development Mode with Inspector

```bash
# Build the Docker image first
docker build -t symptom-minder .

# Run in interactive mode for testing
docker run -i --rm --env-file .env symptom-minder
```

### Using FastMCP Inspector (without Docker)

If you want to test without Docker:

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server with inspector
fastmcp dev server.py
```

The inspector will start on `http://localhost:6274` with an auth link in the terminal output.

---

## MCP Tools and Resources

### Entry Tools

- **`review_symptom_entry`**: Reviews a symptom entry before saving, generates human-readable summary
- **`confirm_and_save_symptom_entry`**: Saves confirmed entry to Elasticsearch, triggers jury review

### Search Tools

- **`flexible_search`**: Flexible search with filters (date range, symptom, medications, notes)
  - Use simple key-value pairs: `{"start_time": "2025-08-01", "end_time": "2025-08-31"}`
  - **NOT** raw Elasticsearch queries
- **`get_incomplete_symptoms`**: Find symptoms marked as incomplete for follow-up
- **`update_symptom_entry`**: Update existing entries with resolution notes

### Resources

- **`list_symptom_entries`**: Retrieves recent symptom entries (default: 20)

### Prompts

- **`symptom_followup_guidance`**: Guides Claude on natural follow-up behavior

---

## Data Management

### Generate Demo Data

```bash
# Generate gluten intolerance symptom dataset
python data/generate_gluten_symptoms.py

# Load demo data into Elasticsearch
python data/reset_and_load_gluten_data.py
```

This creates a realistic 3-month dataset showing gradual discovery of gluten intolerance through weekly symptom patterns.

### Reset Database

```bash
# Clear all data and reset counters
python data/reset_and_load_gluten_data.py

# Or with Docker Compose
docker-compose down -v  # Removes all Elasticsearch data
docker-compose up -d
```

---

## Architecture Overview

### Data Flow

1. **User Input** → Claude Desktop natural language
2. **Review Phase** → `review_symptom_entry` generates summary
3. **User Confirmation** → Validates entry accuracy
4. **Save Phase** → `confirm_and_save_symptom_entry` saves to Elasticsearch
5. **Jury Review** (conditional) → Multi-model LLM validation
6. **Query/Retrieval** → `flexible_search` or resource access
7. **Follow-up** (optional) → Track incomplete symptoms over time

### Key Components

- **`server.py`**: FastMCP server with tool/resource definitions
- **`symptom_schema.py`**: Pydantic models for data validation
- **`jury_tools.py`**: Multi-model LLM quality assurance system
- **`tools/`**: Tool implementations (search, update, entry)
- **`resources/`**: Resource implementations (list entries)
- **`utils/`**: Shared utilities (ES client, data cleaning)

### Jury System

The LLM jury validates structured entries against raw notes using 3 Claude models in parallel:
- `claude-3-5-sonnet-latest`
- `claude-3-7-sonnet-latest`
- `claude-sonnet-4-20250514`

Trigger frequency configured via `JURY_MODE` (e.g., `every_5` = runs on entries 5, 10, 15...).

---

## Example Usage with Claude Desktop

**Record a symptom:**
> "I have a severe headache that started 2 hours ago. I took Advil but it hasn't helped yet."

**Search symptoms:**
> "Show me all my headaches from last month"

**Update a symptom:**
> "That headache from earlier resolved after I drank more water"

**Find patterns:**
> "Are there any patterns in my symptoms related to what I eat?"

---

## Troubleshooting

### Docker Issues

**Container won't start:**
```bash
# Check logs
docker-compose logs symptom-minder

# Verify .env file is loaded
docker run -i --rm --env-file .env symptom-minder python -c "import os; print('ES_ENDPOINT:', os.environ.get('ES_ENDPOINT'))"
```

**Elasticsearch connection fails:**
- Verify `ES_ENDPOINT` and `ES_API_KEY` in `.env`
- Check Elasticsearch is running: `curl $ES_ENDPOINT`
- For local ES, ensure no `ES_API_KEY` is set

### Claude Desktop Issues

**MCP server not appearing:**
- Verify JSON syntax in `claude_desktop_config.json`
- Use absolute paths (not relative like `./`)
- Restart Claude Desktop completely
- Check Docker image exists: `docker images | grep symptom-minder`

**Authentication errors:**
- Ensure `.env` file has correct credentials
- Check `--env-file` path is absolute in config
- Verify API keys are valid (no `< >` placeholders)

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Your Anthropic API key |
| `ES_ENDPOINT` | Yes | `http://localhost:9200` | Elasticsearch endpoint URL |
| `ES_API_KEY` | No | - | Elasticsearch API key (omit for local) |
| `ES_INDEX` | No | `symptom_entries` | Main symptom entries index |
| `JURY_SUMMARY_INDEX` | No | `event_summaries` | Jury review summaries index |
| `JURY_COUNTER_INDEX` | No | `jury_counter` | Jury trigger counter index |
| `JURY_MODE` | No | `every_1` | Jury trigger: `none`, `every_1`, `every_5`, etc. |

---

## Security Notice

**This is a demonstration project with NO security guarantees.**

- Data privacy is not enforced
- Do not store real protected health information (PHI)
- Not HIPAA compliant
- Not intended for medical diagnosis or treatment
- Always consult healthcare professionals for medical advice

---

## Development

For detailed development information, see [CLAUDE.md](CLAUDE.md).

### Requirements

- Python 3.12+
- Docker & Docker Compose
- Elasticsearch 8.x+
- Anthropic API access

### Key Dependencies

- `fastmcp>=2.0.0` - FastMCP framework
- `elasticsearch>=9.1.0` - Async Elasticsearch client
- `anthropic>=0.61.0` - Anthropic API
- `pydantic` - Data validation

---

## License

This is a demonstration project. Use at your own risk.

## Contributing

This is a personal demonstration project. Feel free to fork and adapt for your own use.
