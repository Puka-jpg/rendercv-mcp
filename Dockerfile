FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY src/ ./src/
COPY rendercv/ ./rendercv/

# Install dependencies
RUN uv pip install --system .
RUN uv pip install --system "mcp[cli]" "uvicorn" "starlette"

# Expose port
ENV PORT=8080
EXPOSE 8080

# Run the server
CMD ["python", "rendercv/mcp/server.py"]
