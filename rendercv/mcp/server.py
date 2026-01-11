import asyncio
import os
import json
import logging
import tempfile
import base64
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Mount
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent, EmbeddedResource, BlobResourceContents

# Import RenderCV functionalities
from rendercv.schema.json_schema_generator import generate_json_schema
from rendercv.schema.models.design.built_in_design import available_themes
from rendercv.schema.rendercv_model_builder import build_rendercv_dictionary_and_model
from rendercv.renderer.typst import generate_typst
from rendercv.renderer.pdf_png import generate_pdf

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rendercv-mcp")

# Initialize MCP Server
mcp_server = Server("rendercv-mcp")
BASE_URL = os.environ.get("BASE_URL", "http://207.180.224.154:8080")

@mcp_server.list_tools()
async def list_tools():
    return [
        Tool(
            name="render_cv",
            description="Render a CV from a YAML string to a PDF. Returns the PDF file as a base64 encoded blob.",
            inputSchema={
                "type": "object",
                "properties": {
                    "yaml_content": {
                        "type": "string",
                        "description": "The full YAML content of the CV."
                    },
                    "output_name": {
                        "type": "string",
                        "description": "Base name for the output file (without extension). Defaults to 'cv'.",
                        "default": "cv"
                    }
                },
                "required": ["yaml_content"]
            }
        ),
        Tool(
            name="validate_cv",
            description="Validate a CV YAML string against the RenderCV schema.",
            inputSchema={
                "type": "object",
                "properties": {
                    "yaml_content": {
                        "type": "string",
                        "description": "The full YAML content of the CV."
                    }
                },
                "required": ["yaml_content"]
            }
        ),
        Tool(
            name="get_templates",
            description="List available RenderCV themes.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        Tool(
            name="get_schema",
            description="Get the JSON schema for the RenderCV YAML input.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        )
    ]

@mcp_server.call_tool()
async def call_tool(name, arguments):
    if name == "get_templates":
        return [TextContent(type="text", text=json.dumps(available_themes, indent=2))]

    elif name == "get_schema":
        schema = generate_json_schema()
        return [TextContent(type="text", text=json.dumps(schema, indent=2))]

    elif name == "validate_cv":
        yaml_content = arguments.get("yaml_content")
        if not yaml_content:
            return [TextContent(type="text", text="Error: yaml_content is required")]
        
        try:
            build_rendercv_dictionary_and_model(yaml_content)
            return [TextContent(type="text", text="Validation Successful: The YAML is valid.")]
        except Exception as e:
            return [TextContent(type="text", text=f"Validation Error: {str(e)}")]

    elif name == "render_cv":
        yaml_content = arguments.get("yaml_content")
        output_name = arguments.get("output_name", "cv")
        
        if not yaml_content:
            return [TextContent(type="text", text="Error: yaml_content is required")]

        try:
            # Use a temporary directory for generation since we only need the bytes
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                yaml_file_path = temp_path / f"{output_name}.yaml"
                yaml_file_path.write_text(yaml_content, encoding="utf-8")
                
                # Switch CWD to temp dir to contain outputs
                cwd = os.getcwd()
                os.chdir(temp_path)
                
                try:
                    # 1. Build Model
                    _, rendercv_model = build_rendercv_dictionary_and_model(yaml_file_path)
                    
                    # 2. Render Typst
                    typst_path = generate_typst(rendercv_model)
                    
                    # 3. Render PDF
                    pdf_path = generate_pdf(rendercv_model, typst_path)
                    
                    if pdf_path and pdf_path.exists():
                         pdf_bytes = pdf_path.read_bytes()
                         pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
                         
                         return [
                             TextContent(type="text", text=f"Successfully rendered CV '{output_name}.pdf'."),
                             EmbeddedResource(
                                 type="resource",
                                 resource=BlobResourceContents(
                                     uri=f"file:///{output_name}.pdf",
                                     mimeType="application/pdf",
                                     blob=pdf_base64
                                 )
                             )
                         ]
                    else:
                        return [TextContent(type="text", text="Error: PDF was not generated found in output directory.")]

                finally:
                    # Restore CWD
                    os.chdir(cwd)

        except Exception as e:
            return [TextContent(type="text", text=f"Rendering Error: {str(e)}")]

    raise ValueError(f"Tool {name} not found")

# SSE & Starlette Setup
sse = SseServerTransport(f"{BASE_URL}/sse/messages")

async def sse_app(scope, receive, send):
    """Raw ASGI app for SSE and Messages."""
    if scope["type"] == "http" and scope["method"] == "POST":
        await sse.handle_post_message(scope, receive, send)
    else:
        async with sse.connect_sse(scope, receive, send) as streams:
            await mcp_server.run(
                streams[0],
                streams[1],
                mcp_server.create_initialization_options()
            )

routes = [
    Mount("/sse", app=sse_app),
]

middleware = [
    Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
]

app = Starlette(debug=True, routes=routes, middleware=middleware)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
