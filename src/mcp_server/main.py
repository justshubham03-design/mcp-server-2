#!/usr/bin/env python3
"""
Generic Gmail + Google Docs Model Context Protocol (MCP) Server.
Executable standalone server for Cursor, Claude Desktop, Antigravity, and AI Agents.
"""

import os
import sys
import argparse
import asyncio
import json

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from dotenv import load_dotenv
load_dotenv()

from src.mcp_server.server import MCPServer
from src.mcp_server.auth.google_auth import GoogleAuthManager
from src.mcp_server.utils.logger import get_sanitized_logger

logger = get_sanitized_logger("mcp_main")

def main():
    parser = argparse.ArgumentParser(description="Generic Gmail + Google Docs MCP Server")
    parser.add_argument("--auth", action="store_true", help="Launch interactive browser OAuth 2.0 flow to authenticate")
    parser.add_argument("--list-tools", action="store_true", help="Print available MCP tools and JSON schemas")

    args = parser.parse_args()

    if args.auth:
        logger.info("Starting interactive Google OAuth 2.0 authorization flow...")
        auth_manager = GoogleAuthManager()
        try:
            creds = auth_manager.authenticate_interactive()
            print("\n Google OAuth authorization successful!")
            print(f"Credentials stored securely at: {auth_manager.token_path}\n")
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            sys.exit(1)
        return

    if args.list_tools:
        server = MCPServer()
        tools = server.get_tool_definitions()
        print(json.dumps(tools, indent=2))
        return

    # Default: Run stdio JSON-RPC MCP server
    server = MCPServer()
    try:
        asyncio.run(server.run_stdio())
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user.")
    except Exception as e:
        logger.error(f"MCP server terminated with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
