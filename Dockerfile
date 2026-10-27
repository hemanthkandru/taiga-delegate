FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# HTTP mode by default in a container; usage log on a volume so it survives rebuilds.
ENV MCP_TRANSPORT=http \
    MCP_USAGE_LOG=/data/usage.jsonl
VOLUME /data
EXPOSE 8765

CMD ["taiga-delegate"]
