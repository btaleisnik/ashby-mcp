# /// script
# dependencies = [
#   "mcp",
#   "requests",
#   "python-dotenv"
# ]
# ///
import asyncio
import base64
import copy
import json
import os
import re
from typing import Any, Optional

from dotenv import load_dotenv
import requests

import mcp.types as types
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio


class AshbyClient:
    """Handles Ashby API communication."""

    def __init__(self):
        self.api_key: Optional[str] = None
        self.base_url = "https://api.ashbyhq.com"
        self.headers = {}

    def connect(self) -> bool:
        try:
            self.api_key = os.getenv("ASHBY_API_KEY")
            if not self.api_key:
                raise ValueError("ASHBY_API_KEY environment variable not set")
            encoded_key = base64.b64encode(f"{self.api_key}:".encode()).decode()
            self.headers = {
                "Authorization": f"Basic {encoded_key}",
                "Content-Type": "application/json",
            }
            return True
        except Exception as e:
            print(f"Ashby connection failed: {str(e)}")
            return False

    def request(self, endpoint: str, data: Optional[dict] = None) -> dict:
        if not self.api_key:
            raise ValueError("Ashby connection not established")
        url = f"{self.base_url}{endpoint}"
        response = requests.post(url, headers=self.headers, json=data or {})
        response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# OpenAPI spec parsing – generate MCP tools from the bundled openapi.json
# ---------------------------------------------------------------------------

def _resolve_ref(spec: dict, ref: str) -> Any:
    """Resolve a JSON Pointer $ref within the spec."""
    parts = ref.lstrip("#").lstrip("/").split("/")
    node = spec
    for part in parts:
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list):
            node = node[int(part)]
        else:
            node = node[part]
    return copy.deepcopy(node)


def _resolve_refs(spec: dict, schema: Any, depth: int = 0) -> Any:
    """Recursively resolve all $ref pointers in a schema (depth-limited)."""
    if depth > 15:
        return schema
    if isinstance(schema, dict):
        if "$ref" in schema:
            try:
                resolved = _resolve_ref(spec, schema["$ref"])
                return _resolve_refs(spec, resolved, depth + 1)
            except (KeyError, TypeError):
                return {"type": "object"}
        return {k: _resolve_refs(spec, v, depth + 1) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_resolve_refs(spec, item, depth + 1) for item in schema]
    return schema


def _merge_allof(schema: Any) -> Any:
    """Flatten allOf arrays into a single merged schema."""
    if not isinstance(schema, dict):
        return schema

    if "allOf" in schema:
        merged: dict[str, Any] = {}
        merged_props: dict[str, Any] = {}
        merged_required: list[str] = []
        for sub in schema["allOf"]:
            sub = _merge_allof(sub)
            if not isinstance(sub, dict):
                continue
            merged_props.update(sub.get("properties", {}))
            merged_required.extend(sub.get("required", []))
            for k, v in sub.items():
                if k not in ("properties", "required", "allOf"):
                    merged[k] = v
        if merged_props:
            merged["properties"] = {k: _merge_allof(v) for k, v in merged_props.items()}
        if merged_required:
            merged["required"] = sorted(set(merged_required))
        for k, v in schema.items():
            if k != "allOf" and k not in merged:
                merged[k] = v
        if "type" not in merged and merged_props:
            merged["type"] = "object"
        return merged

    # Recurse into sub-schemas
    result: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "properties" and isinstance(value, dict):
            result[key] = {k: _merge_allof(v) for k, v in value.items()}
        elif isinstance(value, dict):
            result[key] = _merge_allof(value)
        elif isinstance(value, list):
            result[key] = [_merge_allof(i) if isinstance(i, dict) else i for i in value]
        else:
            result[key] = value
    return result


def _simplify_oneof(schema: Any) -> Any:
    """For top-level oneOf, merge all option properties into one object schema."""
    if not isinstance(schema, dict):
        return schema
    if "oneOf" not in schema:
        return schema

    merged_props: dict[str, Any] = {}
    for option in schema["oneOf"]:
        if isinstance(option, dict) and "properties" in option:
            for name, prop_schema in option["properties"].items():
                if name not in merged_props:
                    merged_props[name] = prop_schema
    if merged_props:
        return {"type": "object", "properties": merged_props}
    return schema


def _clean_schema(schema: Any) -> Any:
    """Strip non-essential fields to keep inputSchemas compact."""
    if not isinstance(schema, dict):
        return schema
    result: dict[str, Any] = {}
    for key, value in schema.items():
        # Drop examples, extension fields, and titles (noisy for MCP)
        if key in ("example", "examples") or key.startswith("x-"):
            continue
        if key == "properties" and isinstance(value, dict):
            result[key] = {k: _clean_schema(v) for k, v in value.items()}
        elif isinstance(value, dict):
            result[key] = _clean_schema(value)
        elif isinstance(value, list):
            result[key] = [_clean_schema(i) if isinstance(i, dict) else i for i in value]
        else:
            result[key] = value
    return result


_DESC_PERM_RE = re.compile(r"\*\*Requires the \[.*?\]\(.*?\) permission\.\*\*\s*", re.DOTALL)


def _path_to_tool_name(path: str) -> str:
    """Convert API path to MCP tool name.  /candidate.create -> candidate_create"""
    return path.lstrip("/").replace(".", "_")


def _build_tools(spec: dict) -> tuple[list[types.Tool], dict[str, str]]:
    """Build MCP tools and an endpoint map from an OpenAPI spec."""
    tools: list[types.Tool] = []
    endpoint_map: dict[str, str] = {}

    for path, methods in spec.get("paths", {}).items():
        post_op = methods.get("post")
        if not post_op:
            continue

        tool_name = _path_to_tool_name(path)

        # Description — strip markdown permission annotations
        desc = post_op.get("description", post_op.get("summary", tool_name))
        desc = _DESC_PERM_RE.sub("", desc).strip()
        if len(desc) > 1024:
            desc = desc[:1021] + "..."

        # Extract input schema from requestBody
        input_schema: dict[str, Any] = {"type": "object", "properties": {}}
        rb = post_op.get("requestBody", {})
        content = rb.get("content", {})
        json_content = content.get("application/json", {})
        if json_content:
            raw_schema = json_content.get("schema", {})
            resolved = _resolve_refs(spec, raw_schema)
            merged = _merge_allof(resolved)
            simplified = _simplify_oneof(merged)
            input_schema = _clean_schema(simplified)
            if "type" not in input_schema:
                input_schema["type"] = "object"

        tools.append(
            types.Tool(
                name=tool_name,
                description=desc,
                inputSchema=input_schema,
            )
        )
        endpoint_map[tool_name] = path

    return tools, endpoint_map


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

SPEC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "openapi.json")

server = Server("ashby-mcp")
load_dotenv()

ashby_client = AshbyClient()
if not ashby_client.connect():
    print("Failed to initialize Ashby connection")

# Load OpenAPI spec and build tools at import time
with open(SPEC_PATH) as f:
    _spec = json.load(f)
_tools, _endpoint_map = _build_tools(_spec)


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return _tools


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    try:
        endpoint = _endpoint_map.get(name)
        if not endpoint:
            raise ValueError(f"Unknown tool: {name}")
        response = ashby_client.request(endpoint, data=arguments)
        return [types.TextContent(type="text", text=json.dumps(response, indent=2))]
    except requests.HTTPError as e:
        body = ""
        if e.response is not None:
            try:
                body = e.response.json()
            except Exception:
                body = e.response.text
        return [types.TextContent(type="text", text=f"HTTP error calling {name}: {e}\n{json.dumps(body, indent=2) if isinstance(body, dict) else body}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error executing {name}: {str(e)}")]


async def run():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ashby",
                server_version="0.2.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
