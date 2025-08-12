# ⚠️ Developer NOTE ⚠️ :
 > This project is currently in development and is not at all ready for production. The purpose is to document possibly sensitive medical information and provide a platform for analysis and visualization. There should be absolutely NO assumption of data privacy or security in this demonstration. Advice or instructions given by the server or the llm should be taken with a grain of salt. This application demo and proof of concept is not intended for medical use and should not be used as a substitute for professional medical advice.

# SymptomMinder FastMCP Server

This project is an MCP server built with FastMCP for recording symptoms and related environmental/body information, storing it in Elasticsearch, and supporting integration with Claude Desktop for user review and visualization.

## Motivation
Now more than ever, people are empowering themselves with tools to better understand their health and well-being. With the rise of AI and machine learning, we can use these tools to better understand our individual health through data collection and analysis. Sickness and wellness are complex, and we can't always know what the big picture is. By recording and analyzing our symptoms and related information, we can better understand our health and make informed decisions about our care. 

By recording symptoms and surrounding information, we can possibly identify patterns and correlations that we might not otherwise notice. This can help us better understand our health and make informed decisions about our care. We all know at least three people who have a "silent" condition that may not have an outward appearance, but may be causing them significant discomfort, pain, or disability. By creating and maintaining a record of their physical experience, we hope to provide documentation and support for their care. 

## Server Tools and Data Flow

### Tools and Resources in `server.py`

- **review_symptom_entry**: An MCP tool that reviews a symptom entry before saving. It generates a human-readable summary for confirmation, ensuring the user can validate the entry's accuracy.
- **confirm_and_save_symptom_entry**: Handles the saving of a confirmed symptom entry to Elasticsearch. It also triggers the jury tool for additional review based on the `JURY_MODE` configuration.
- **list_symptom_entries**: An MCP resource that retrieves the most recent symptom entries from Elasticsearch, supporting quick access to historical data.
- **flexible_search**: An MCP tool that enables flexible and semantic searching of symptom entries. It accepts various filters (symptom, medication, mediation attempt, time range, notes, etc.) for advanced querying.

### The `jury_tools` Function

- **llm_jury_compare_notes**: This function, imported from `jury_tools`, is invoked after a symptom entry is saved (depending on the `JURY_MODE` setting). It uses a large language model (LLM) to analyze and compare the raw notes and structured entry for validation, quality assurance, or further review. This helps maintain the integrity and usefulness of the recorded data.

### Role of the Symptom Schema

- **SymptomEntry**: Defined in `symptom_schema.py`, this Pydantic schema enforces the structure and validation of all symptom entries processed by the server. It ensures data consistency, type safety, and completeness for all operations (review, save, search), and is fundamental to the application's reliability.

---

## 1. Setup

1. Copy the example environment file and fill in your actual API keys:

   ```sh
   cp .env.example .env
   # Then open .env and add your Elasticsearch and Anthropic API keys
   ```

2. Virtual Environment

It is recommended to use `uv` for fast, reliable Python environments.

```bash
# Install uv if you don't have it
pip install uv

# Create a virtual environment in the project directory
uv venv

# Activate the virtual environment (macOS/Linux)
source .venv/bin/activate

# (Windows)
# .venv\Scripts\activate
```

---

## 2. Install Dependencies

With the virtual environment activated:

```bash
uv pip install -r requirements.txt
```

---

## 3. Set Environment Variables for Elasticsearch

- `ANTHROPIC_API_KEY` - The API key for your Anthropic instance.
 
- `ES_ENDPOINT` - The endpoint URL of your Elasticsearch instance. 

- `ES_API_KEY` - The API key for your Elasticsearch instance.

- `ES_INDEX` - the name of the index where you want to store the symptom entries. (default: `symptom_entries`)

- `JURY_SUMMARY_INDEX` - the name of the index where you want to store the llm jury summaries. (default: `event_summaries`)


Example:

```bash
export ANTHROPIC_API_KEY="<your-anthropic-api-key>"
export ES_ENDPOINT="<your-elasticsearch-endpoint>"
export ES_API_KEY="<your-elasticsearch-api-key>"
export ES_INDEX="<your-elasticsearch-index>"
export JURY_SUMMARY_INDEX="<your-jury-summary-index>"
```

Add these lines to your shell profile (e.g., `.zshrc` or `.bashrc`) for persistence, or set them before running the server.

---

## 4. Testing the Server Locally

With the virtual environment activated and environment variables set:

```bash
fastmcp dev server.py
```

The server will start on `http://localhost:6274` by default. The terminal will provdie a link with an auth parameter to access the FastMCP inspector.

---

## 5. Using with Claude Desktop

1. Ensure Claude Desktop is installed on your system.
2. Run the install script for the FastMCP server:
    ```bash
    $ fastmcp install claude-desktop --server-spec fastmcp_server.py --name "Symptom Minder"
    ```
3. Restart Claude Desktop.
4. Use the Claude Desktop interface to submit, review, and confirm symptom entries and view visualizations.

---

## 6. Additional Notes

- Ensure your Elasticsearch instance is running and accessible at the configured URL.
- For production deployments, configure authentication and secure your Elasticsearch instance and MCP server accordingly.
---


### 7. Future Improvements


