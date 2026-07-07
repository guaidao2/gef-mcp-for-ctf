#!/usr/bin/env python3
"""
GEF MCP Server — GDB Enhanced Features Model Context Protocol Server

玄幕安全团队 - guaidao2 开发

Usage:
    python server.py                          # SSE 模式 (默认 :8000)
    python server.py --transport stdio        # stdio 模式 (用于 Claude Desktop)
    python server.py --host 127.0.0.1 --port 8080
"""

import argparse
import asyncio
import json
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent
from mcp.server.sse import SseServerTransport

from manager import session_manager
from tools import TOOLS, dispatch_tool
from utils import log as logger


# ── MCP 服务器 ──────────────────────────────────────────────────

mcp_server = Server("gef-mcp")


@mcp_server.list_tools()
async def list_tools():
    return TOOLS


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    logger.info("call_tool: %s", name)
    try:
        result = dispatch_tool(name, arguments or {})
        return [
            TextContent(
                type="text",
                text=json.dumps(result, indent=2, ensure_ascii=False),
            )
        ]
    except Exception as e:
        logger.exception("Tool error: %s", name)
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"success": False, "error": str(e)}, indent=2
                ),
            )
        ]


# ── SSE 服务器 ──────────────────────────────────────────────────

def build_sse_app(host: str, port: int):
    """构建 Starlette ASGI 应用用于 SSE 传输"""
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import PlainTextResponse
    from starlette.routing import Mount, Route
    import uvicorn

    sse_transport = SseServerTransport("/messages/")

    async def handle_sse(request: Request):
        try:
            async with sse_transport.connect_sse(
                request.scope,
                request.receive,
                request._send,
            ) as streams:
                if streams is None:
                    return PlainTextResponse(
                        "Failed to establish SSE connection", status_code=500
                    )
                read_stream, write_stream = streams
                await mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp_server.create_initialization_options(),
                )
        except Exception as e:
            return PlainTextResponse(f"Error: {e}", status_code=500)

    starlette_app = Starlette(
        debug=False,
        routes=[
            Route(
                "/",
                endpoint=lambda r: PlainTextResponse(
                    "GEF MCP Server — GDB Enhanced Features"
                ),
            ),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", routes=[]),
        ],
    )

    async def asgi_app(scope, receive, send):
        path = scope.get("path", "/")

        if path.startswith("/messages/"):
            await sse_transport.handle_post_message(scope, receive, send)
        else:
            await starlette_app(scope, receive, send)

    return asgi_app, uvicorn


# ── 主入口 ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="GEF MCP Server — GDB Enhanced Features"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="sse",
        help="Transport type (default: sse)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="SSE bind host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="SSE bind port (default: 8000)",
    )
    args = parser.parse_args()

    try:
        if args.transport == "sse":
            _run_sse(args.host, args.port)
        else:
            _run_stdio()
    except KeyboardInterrupt:
        _shutdown()
    except Exception as e:
        logger.error("Fatal: %s", e)
        _shutdown()
        sys.exit(1)


def _run_sse(host: str, port: int):
    """以 SSE 模式启动"""
    import uvicorn

    asgi_app, uvicorn = build_sse_app(host, port)

    banner = f"""
╔═══════════════════════════════════════════════════════════════╗
║   GEF MCP Server v2.0 — GDB Enhanced Features               ║
║   Model Context Protocol                                     ║
╠═══════════════════════════════════════════════════════════════╣
║  SSE Endpoint:  http://{host}:{port}/sse                      ║
║  Messages:      http://{host}:{port}/messages/                 ║
╚═══════════════════════════════════════════════════════════════╝
"""
    print(banner)
    logger.info("SSE server starting on %s:%s", host, port)
    uvicorn.run(asgi_app, host=host, port=port, log_level="warning")


def _run_stdio():
    """以 stdio 模式启动 (用于 Claude Desktop)"""
    logger.info("Starting stdio server...")

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    asyncio.run(run())


def _shutdown():
    """优雅关闭"""
    print("\nShutting down GEF MCP Server...")
    session_manager.close_all()
    session_manager.stop_reaper()
    logger.info("Server shutdown complete")


if __name__ == "__main__":
    main()
