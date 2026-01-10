import asyncio
import sys
from mcp.client.sse import sse_client
from mcp.types import ClientRequest

async def verify_mcp():
    url = "http://localhost:8000/sse"
    print(f"Connecting to {url}...")
    
    try:
        async with sse_client(url) as streams:
            read_stream, write_stream = streams
            
            # Create a simple initialization request interaction if the client helpers don't do it automatically
            # However, `sse_client` typically returns streams to be used with `ClientSession`
            
            from mcp.client.session import ClientSession
            
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                print("Connected and Initialized!")
                
                # 1. List Tools
                print("\n--- Listing Tools ---")
                tools_result = await session.list_tools()
                for tool in tools_result.tools:
                    print(f"- {tool.name}: {tool.description}")
                
                # 2. Get Templates
                print("\n--- Getting Templates ---")
                templates = await session.call_tool("get_templates")
                print(templates.content[0].text)
                
                # 3. Validate CV
                print("\n--- Validating CV ---")
                valid_yaml = """
cv:
  name: John Doe
  location: Your Location
  email: john@doe.com
  sections:
    test:
      - This is a test.
"""
                validation = await session.call_tool("validate_cv", arguments={"yaml_content": valid_yaml})
                print(validation.content[0].text)
                
                # 4. Render CV
                print("\n--- Rendering CV ---")
                render_result = await session.call_tool("render_cv", arguments={"yaml_content": valid_yaml, "output_name": "test_cv"})
                
                for content in render_result.content:
                    if content.type == "text":
                        print(content.text)
                    elif content.type == "resource":
                        import base64
                        from pathlib import Path
                        output_path = Path("test_cv.pdf")
                        pdf_bytes = base64.b64decode(content.resource.blob)
                        output_path.write_bytes(pdf_bytes)
                        print(f"Saved PDF to: {output_path.absolute()}")

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(verify_mcp())
