FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install essential system libraries for font rendering and graphics
# These are required by RenderCV's PDF engines
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libpango-1.0-0 \
    libnss3 \
    libatk1.0-0 \
    libx11-6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy everything from the current directory into the container
COPY . .

# Install dependencies directly to system
# We include specific sub-dependencies that RenderCV needs for PDF generation
RUN uv pip install --system .
RUN uv pip install --system "mcp[cli]" "uvicorn" "starlette" "rendercv-fonts" "typst" "pydantic-extra-types" "pydantic-settings"

# Set environment variables
ENV PORT=8080
# This ensures Python looks in /app/src for the rendercv package logic
ENV PYTHONPATH="/app/src:/app"

EXPOSE 8080

# Run the server using the relative path to your server file
CMD ["python", "rendercv/mcp/server.py"]