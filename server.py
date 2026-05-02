"""
MCP Server — Web Search/Fetch · File/Text Utilities · Calculator
Transport: Streamable HTTPS  (FastAPI + SSE fallback)
"""

import asyncio
import json
import math
import operator
import re
import textwrap
import urllib.parse
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    TextContent,
    Tool,
)

# ── MCP Server instance ──────────────────────────────────────────────────────
mcp = Server("multi-tool-mcp")

# ── Tool definitions ─────────────────────────────────────────────────────────
TOOLS: list[Tool] = [
    # ── Web tools ────────────────────────────────────────────────────────────
    Tool(
        name="web_fetch",
        description="Fetch the raw text content of any public URL.",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL to fetch (must start with http/https)"},
                "max_chars": {"type": "integer", "description": "Truncate response to this many characters (default 4000)", "default": 4000},
            },
            "required": ["url"],
        },
    ),
    Tool(
        name="web_search",
        description="Search the web using DuckDuckGo and return top results.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Number of results to return (1-10, default 5)", "default": 5},
            },
            "required": ["query"],
        },
    ),
    # ── Text / file utilities ─────────────────────────────────────────────────
    Tool(
        name="text_word_count",
        description="Count words, characters, sentences, and lines in a piece of text.",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to analyse"},
            },
            "required": ["text"],
        },
    ),
    Tool(
        name="text_transform",
        description="Transform text: uppercase, lowercase, title_case, snake_case, camel_case, reverse, strip, wrap.",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input text"},
                "operation": {
                    "type": "string",
                    "enum": ["uppercase", "lowercase", "title_case", "snake_case", "camel_case", "reverse", "strip", "wrap"],
                    "description": "Transformation to apply",
                },
                "wrap_width": {"type": "integer", "description": "Column width for 'wrap' operation (default 80)", "default": 80},
            },
            "required": ["text", "operation"],
        },
    ),
    Tool(
        name="text_extract_pattern",
        description="Extract all matches of a regex pattern from text.",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input text to search"},
                "pattern": {"type": "string", "description": "Python regex pattern"},
                "flags": {"type": "string", "description": "Regex flags: I=ignore case, M=multiline, S=dotall", "default": ""},
            },
            "required": ["text", "pattern"],
        },
    ),
    Tool(
        name="text_find_replace",
        description="Find and replace text (literal or regex).",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "find": {"type": "string"},
                "replace": {"type": "string"},
                "use_regex": {"type": "boolean", "default": False},
            },
            "required": ["text", "find", "replace"],
        },
    ),
    # ── Calculator ────────────────────────────────────────────────────────────
    Tool(
        name="calculator_evaluate",
        description=(
            "Safely evaluate a mathematical expression. "
            "Supports: +  -  *  /  //  %  **  sqrt()  log()  log2()  log10()  "
            "sin()  cos()  tan()  abs()  round()  floor()  ceil()  pi  e  "
            "and standard parentheses."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression, e.g. 'sqrt(2) * pi'"},
            },
            "required": ["expression"],
        },
    ),
    Tool(
        name="calculator_unit_convert",
        description="Convert between common units (length, mass, temperature, data).",
        inputSchema={
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "from_unit": {"type": "string", "description": "Source unit, e.g. 'km', 'kg', 'F', 'MB'"},
                "to_unit": {"type": "string", "description": "Target unit"},
            },
            "required": ["value", "from_unit", "to_unit"],
        },
    ),
]


# ── Tool handlers ─────────────────────────────────────────────────────────────

async def handle_web_fetch(args: dict) -> str:
    url: str = args["url"]
    max_chars: int = args.get("max_chars", 4000)
    if not url.startswith(("http://", "https://")):
        return "Error: URL must start with http:// or https://"
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        r = await client.get(url, headers={"User-Agent": "MCP-Server/1.0"})
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        if "html" in content_type:
            text = re.sub(r"<[^>]+>", " ", r.text)
            text = re.sub(r"\s+", " ", text).strip()
        else:
            text = r.text
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n…[truncated at {max_chars} chars]"
    return text


async def handle_web_search(args: dict) -> str:
    query: str = args["query"]
    max_results: int = min(args.get("max_results", 5), 10)
    encoded = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    results = re.findall(
        r'class="result__title".*?href="([^"]+)".*?class="result__snippet"[^>]*>(.*?)</a>',
        r.text, re.DOTALL
    )
    out = []
    for i, (href, snippet) in enumerate(results[:max_results], 1):
        snippet_clean = re.sub(r"<[^>]+>", "", snippet).strip()
        snippet_clean = re.sub(r"\s+", " ", snippet_clean)
        out.append(f"{i}. {href}\n   {snippet_clean}")
    return "\n\n".join(out) if out else "No results found."


def handle_text_word_count(args: dict) -> str:
    text: str = args["text"]
    words = len(text.split())
    chars = len(text)
    chars_no_space = len(text.replace(" ", ""))
    sentences = len(re.findall(r"[.!?]+", text)) or 1
    lines = len(text.splitlines())
    return json.dumps({
        "words": words,
        "characters": chars,
        "characters_no_spaces": chars_no_space,
        "sentences": sentences,
        "lines": lines,
    }, indent=2)


def handle_text_transform(args: dict) -> str:
    text: str = args["text"]
    op: str = args["operation"]
    if op == "uppercase":
        return text.upper()
    if op == "lowercase":
        return text.lower()
    if op == "title_case":
        return text.title()
    if op == "snake_case":
        return re.sub(r"[\s\-]+", "_", text).lower()
    if op == "camel_case":
        words = re.split(r"[\s_\-]+", text)
        return words[0].lower() + "".join(w.title() for w in words[1:])
    if op == "reverse":
        return text[::-1]
    if op == "strip":
        return text.strip()
    if op == "wrap":
        width = args.get("wrap_width", 80)
        return textwrap.fill(text, width)
    return f"Unknown operation: {op}"


def handle_text_extract_pattern(args: dict) -> str:
    text: str = args["text"]
    pattern: str = args["pattern"]
    flag_str: str = args.get("flags", "")
    flags = 0
    if "I" in flag_str.upper():
        flags |= re.IGNORECASE
    if "M" in flag_str.upper():
        flags |= re.MULTILINE
    if "S" in flag_str.upper():
        flags |= re.DOTALL
    matches = re.findall(pattern, text, flags)
    return json.dumps({"count": len(matches), "matches": matches}, indent=2)


def handle_text_find_replace(args: dict) -> str:
    text: str = args["text"]
    find: str = args["find"]
    replace: str = args["replace"]
    use_regex: bool = args.get("use_regex", False)
    if use_regex:
        result = re.sub(find, replace, text)
    else:
        result = text.replace(find, replace)
    count = text.count(find) if not use_regex else len(re.findall(find, text))
    return json.dumps({"result": result, "replacements_made": count}, indent=2)


_SAFE_MATH_NAMES = {
    "sqrt": math.sqrt, "log": math.log, "log2": math.log2, "log10": math.log10,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil,
    "pi": math.pi, "e": math.e,
}
_SAFE_OPS = {
    ast_node_type: True for ast_node_type in [
        "Expression", "BinOp", "UnaryOp", "Call", "Constant", "Name",
        "Add", "Sub", "Mult", "Div", "FloorDiv", "Mod", "Pow",
        "USub", "UAdd",
    ]
}

def _safe_eval(expr: str) -> float:
    import ast
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if type(node).__name__ not in _SAFE_OPS:
            raise ValueError(f"Disallowed expression node: {type(node).__name__}")
    return eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}}, _SAFE_MATH_NAMES)


def handle_calculator_evaluate(args: dict) -> str:
    expr: str = args["expression"].strip()
    try:
        result = _safe_eval(expr)
        return json.dumps({"expression": expr, "result": result})
    except Exception as ex:
        return json.dumps({"error": str(ex)})


_UNIT_MAP: dict[str, tuple[str, float]] = {
    # length → metres
    "m": ("length", 1), "km": ("length", 1000), "cm": ("length", 0.01),
    "mm": ("length", 0.001), "mi": ("length", 1609.344), "mile": ("length", 1609.344),
    "miles": ("length", 1609.344), "ft": ("length", 0.3048), "in": ("length", 0.0254),
    "yd": ("length", 0.9144),
    # mass → kg
    "kg": ("mass", 1), "g": ("mass", 0.001), "mg": ("mass", 1e-6),
    "lb": ("mass", 0.453592), "lbs": ("mass", 0.453592), "oz": ("mass", 0.0283495),
    "tonne": ("mass", 1000), "ton": ("mass", 907.185),
    # data → bytes
    "b": ("data", 1), "kb": ("data", 1024), "mb": ("data", 1024**2),
    "gb": ("data", 1024**3), "tb": ("data", 1024**4),
}

def handle_calculator_unit_convert(args: dict) -> str:
    value: float = args["value"]
    from_u = args["from_unit"].lower()
    to_u = args["to_unit"].lower()

    # Temperature special-case
    def _temp(v, f, t):
        to_c = {"c": lambda x: x, "f": lambda x: (x-32)*5/9, "k": lambda x: x-273.15}
        from_c = {"c": lambda x: x, "f": lambda x: x*9/5+32, "k": lambda x: x+273.15}
        if f not in to_c or t not in from_c:
            return None
        return from_c[t](to_c[f](v))

    if from_u in ("c","f","k") or to_u in ("c","f","k"):
        result = _temp(value, from_u, to_u)
        if result is None:
            return json.dumps({"error": "Unknown temperature unit"})
        return json.dumps({"value": value, "from": from_u.upper(), "to": to_u.upper(), "result": round(result, 6)})

    if from_u not in _UNIT_MAP or to_u not in _UNIT_MAP:
        return json.dumps({"error": f"Unknown unit(s): {from_u}, {to_u}"})
    cat_f, factor_f = _UNIT_MAP[from_u]
    cat_t, factor_t = _UNIT_MAP[to_u]
    if cat_f != cat_t:
        return json.dumps({"error": f"Cannot convert {cat_f} to {cat_t}"})
    result = value * factor_f / factor_t
    return json.dumps({"value": value, "from": from_u, "to": to_u, "result": round(result, 9)})


# ── MCP handler registration ──────────────────────────────────────────────────

@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@mcp.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "web_fetch":
            result = await handle_web_fetch(arguments)
        elif name == "web_search":
            result = await handle_web_search(arguments)
        elif name == "text_word_count":
            result = handle_text_word_count(arguments)
        elif name == "text_transform":
            result = handle_text_transform(arguments)
        elif name == "text_extract_pattern":
            result = handle_text_extract_pattern(arguments)
        elif name == "text_find_replace":
            result = handle_text_find_replace(arguments)
        elif name == "calculator_evaluate":
            result = handle_calculator_evaluate(arguments)
        elif name == "calculator_unit_convert":
            result = handle_calculator_unit_convert(arguments)
        else:
            result = f"Unknown tool: {name}"
    except Exception as ex:
        result = f"Error: {ex}"

    return [TextContent(type="text", text=str(result))]


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="Multi-Tool MCP Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sse_transport = SseServerTransport("/messages/")


@app.get("/")
async def root():
    return {
        "name": "Multi-Tool MCP Server",
        "version": "1.0.0",
        "tools": [t.name for t in TOOLS],
        "transport": ["Streamable HTTPS", "SSE"],
        "endpoints": {
            "sse": "/sse",
            "messages": "/messages/",
            "health": "/health",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/sse")
async def sse_endpoint(request: Request):
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp.run(streams[0], streams[1], mcp.create_initialization_options())


@app.post("/messages/")
async def messages_endpoint(request: Request):
    await sse_transport.handle_post_message(request.scope, request.receive, request._send)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
