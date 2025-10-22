FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir aiohttp>=3.12.15 anthropic>=0.61.0 elasticsearch>=9.1.0 fastmcp>=2.11.1

# Copy application files
COPY server.py .
COPY symptom_schema.py .
COPY jury_tools.py .

# Set environment variable for unbuffered output
ENV PYTHONUNBUFFERED=1

# Run the MCP server
CMD ["python", "server.py"]
