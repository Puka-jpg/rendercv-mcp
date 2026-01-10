# End-to-End Guide: Building a Remote MCP Server

This guide covers the complete lifecycle of creating a **Remote Model Context Protocol (MCP) Server**, from initial setup to deployment and connection. Unlike local servers that communicate via `stdio`, remote servers expose an **SSE (Server-Sent Events)** endpoint over HTTP, allowing connection from distributed clients (like Claude Desktop or custom apps).

## 1. Environment Setup

We'll use **Python** with `uv` for dependency management.

### Prerequisites
- Python 3.10+
- `uv` (recommended) or `pip`

### Initialize Project
```bash
# Create project directory
uv init remote-mcp-server
cd remote-mcp-server

# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies (MCP SDK + Starlette for HTTP/SSE)
uv add "mcp[cli]" starlette uvicorn
```

## 2. Implementing the Server

Create a file named `server.py`. We will use the `mcp.server.fastmcp` or standard `mcp.server` classes. For remote servers, we essentially wrap the MCP logs in a web server compatible with SSE.

### Basic Structure using Starlette (Recommended for Control)

```python
import asyncio
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Resource, Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import Response
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import uvicorn

# 1. Initialize MCP Server
mcp_server = Server("my-remote-server")

# 2. Define Tools (The core logic)
@mcp_server.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_weather",
            description="Get weather for a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            }
        )
    ]

@mcp_server.call_tool()
async def call_tool(name, arguments):
    if name == "get_weather":
        location = arguments.get("location")
        # specific logic here
        return [TextContent(type="text", text=f"Weather in {location} is Sunny")]
    raise ValueError(f"Tool {name} not found")

# 3. Create SSE & Message Handling Endpoints for Starlette

# Note: This requires the 'mcp' SDK and 'starlette'.
# The specific implementation details for SseServerTransport may vary by SDK version.
# Consult https://github.com/modelcontextprotocol/python-sdk/tree/main/examples/servers/sse-server
# for the latest official boilerplate.

sse = SseServerTransport("/messages")

async def handle_sse(request):
    """
    Handle the Server-Sent Events (SSE) connection.
    This endpoint establishes the persistent connection.
    """
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp_server.run(
            streams[0], 
            streams[1], 
            mcp_server.create_initialization_options()
        )
    return Response(status_code=200)

async def handle_messages(request):
    """
    Handle client messages (JSON-RPC) sent via POST.
    """
    await sse.handle_post_message(request.scope, request.receive, request._send)
    return Response(status_code=200)

app = Starlette(debug=True, routes=[
    Route("/sse", endpoint=handle_sse),
    Route("/messages", endpoint=handle_messages, methods=["POST"])
])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

> **Note**: As of early 2025, the standard `mcp` library optimizes for `stdio`. For HTTP/SSE, you often write a small adapter using `starlette` or `fastapi`.

### High-Level "FastMCP" (If available)
If you are using a higher-level framework wrapper (often community provided or future SDK updates), you might just do:
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather-server")

@mcp.tool()
def get_weather(location: str):
    return f"Weather in {location} is Sunny"

# Run as standard HTTP
mcp.run(transport="sse", port=8000)
```

## 3. Exposing Remotely

To make your local server "Remote", you need a public URL.

### Option A: Tunneling (Dev / Testing)
Use `ngrok` or similar to expose your localhost.
```bash
ngrok http 8000
```
This gives you a URL like `https://xyz.ngrok-free.app`.
Your SSE endpoint would be `https://xyz.ngrok-free.app/sse`.

### Option B: Cloud Deployment (Production)
Deploy to Railway, Render, or a VPS.
- **Dockerfile**:
  ```dockerfile
  FROM python:3.10-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install -r requirements.txt
  COPY server.py .
  CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
  ```

## 4. Connecting Claude to the Remote Server

Claude Desktop and other clients need to know about your remote server.

1.  Open **Claude Desktop**.
2.  Go to **Settings** (or Developer Settings if enabled).
3.  Add a **Custom Connector** (or edit `claude_desktop_config.json`).
    *   **Type**: `remote` (or `sse`)
    *   **URL**: `https://your-public-url.com/sse` (the endpoint handling the SSE connection)
    
**(Configuration File Example)**
```json
{
  "mcpServers": {
    "my-remote-weather": {
      "command": "", 
      "url": "https://xyz.ngrok-free.app/sse"
    }
  }
}
```
*Note: For remote servers, you provide `url` instead of `command` in some client configs, or use the UI.*

## 5. Testing & Debugging

-   **MCP Inspector**: Use the official inspector tool.
    ```bash
    npx @modelcontextprotocol/inspector https://localhost:8000/sse
    ```
-   **Logs**: Check your server stdout/stderr (uvicorn logs).
-   **Common Errors**:
    -   *CORS*: Ensure your HTTP server allows requests from the client's origin (or `*`).
    -   *Connection Refused*: Check public URL reachability.
    -   *Auth*: If using OAuth, ensure the callback flow is correctly implemented (Advanced).

## 6. Best Practices regarding "Remote"

-   **Security**: A remote server on the public internet is accessible by ANYONE unless you add authentication.
    -   Implement strict input validation.
    -   Use headers/tokens if the client supports it.
-   **Statelessness**: SSE connections might drop. Ensure your server can handle reconnects gracefully.
-   **Logging**: Use `logging` library, not `print`, as `print` might interfere if you ever switch back to `stdio` or clutter system logs.

---
**Summary Checklist**
- [ ] Server code implements `mcp` interfaces.
- [ ] Starlette/FastAPI wrapper handles SSE endpoints.
- [ ] Public URL is reachable (HTTPS).
- [ ] Client configured with correct SSE URL.
