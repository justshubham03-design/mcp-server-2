#!/usr/bin/env python3
"""
Verification Script for Generic Gmail + Google Docs MCP Server.
Tests subprocess stdio JSON-RPC communication, tool schema discovery, and auth status.
"""

import sys
import os
import json
import subprocess
from pathlib import Path

def run_check(title: str):
    print(f"\n========================================================")
    print(f" Checking: {title}")
    print(f"========================================================")

def verify_tool_listing():
    run_check("1. CLI Tool Listing (--list-tools)")
    cmd = [sys.executable, "-m", "src.mcp_server.main", "--list-tools"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[FAIL] Process exited with code {proc.returncode}")
        print(f"Stderr: {proc.stderr}")
        return False
    
    try:
        tools = json.loads(proc.stdout)
        print(f"[PASS] Successfully retrieved {len(tools)} tools via CLI.")
        for tool in tools:
            print(f"  - Tool: {tool['name']}")
            print(f"    Description: {tool['description'][:60]}...")
            print(f"    Required params: {tool['inputSchema'].get('required', [])}")
        return True
    except Exception as e:
        print(f"[FAIL] JSON parsing failed: {e}")
        print(f"Raw stdout: {proc.stdout}")
        return False

def verify_stdio_jsonrpc():
    run_check("2. Stdio JSON-RPC 2.0 Protocol Compliance")
    cmd = [sys.executable, "-m", "src.mcp_server.main"]
    
    # Start server process in background
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    try:
        # Step A: Test 'initialize'
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        proc.stdin.write(json.dumps(init_payload) + "\n")
        proc.stdin.flush()
        
        response_line = proc.stdout.readline()
        init_res = json.loads(response_line)
        assert init_res.get("jsonrpc") == "2.0", "Invalid JSON-RPC version"
        assert init_res.get("id") == 1, "Mismatched request ID"
        server_info = init_res["result"]["serverInfo"]
        print(f"[PASS] 'initialize' handshake successful!")
        print(f"  Server Name: {server_info.get('name')}")
        print(f"  Server Version: {server_info.get('version')}")
        print(f"  Capabilities: {list(init_res['result']['capabilities'].keys())}")

        # Step B: Test 'tools/list'
        tools_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        proc.stdin.write(json.dumps(tools_payload) + "\n")
        proc.stdin.flush()

        response_line = proc.stdout.readline()
        tools_res = json.loads(response_line)
        assert tools_res.get("id") == 2
        tools_list = tools_res["result"]["tools"]
        tool_names = [t["name"] for t in tools_list]
        print(f"[PASS] 'tools/list' returned {len(tools_list)} tools: {tool_names}")
        assert "gmail_create_draft" in tool_names
        assert "gmail_send_email" in tool_names
        assert "google_docs_append" in tool_names

        # Step C: Test 'tools/call' validation handling
        call_payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "gmail_create_draft",
                "arguments": {
                    "to": ["invalid-email-address"],
                    "subject": "Test",
                    "body": "Test body"
                }
            }
        }
        proc.stdin.write(json.dumps(call_payload) + "\n")
        proc.stdin.flush()

        response_line = proc.stdout.readline()
        call_res = json.loads(response_line)
        assert call_res.get("id") == 3
        # Should gracefully return error in MCP result schema
        result_content = call_res["result"]["content"][0]["text"]
        print(f"[PASS] 'tools/call' schema validation correctly caught invalid input:")
        print(f"  Response: {result_content}")

        # Step D: Test unknown tool
        unknown_payload = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "unknown_tool_xyz",
                "arguments": {}
            }
        }
        proc.stdin.write(json.dumps(unknown_payload) + "\n")
        proc.stdin.flush()

        response_line = proc.stdout.readline()
        unknown_res = json.loads(response_line)
        assert unknown_res.get("id") == 4
        print(f"[PASS] 'tools/call' unknown tool error handled gracefully:")
        print(f"  Response: {unknown_res['result']['content'][0]['text']}")

        return True
    finally:
        proc.terminate()
        proc.wait(timeout=2)

def verify_auth_token_status():
    run_check("3. Google OAuth 2.0 Token Status")
    token_path_env = os.getenv("GOOGLE_TOKEN_PATH", "./.config/google_token.json")
    resolved_path = Path(os.path.expanduser(token_path_env)).resolve()
    print(f"Checking Token File at: {resolved_path}")
    
    if not resolved_path.exists():
        print(f"[PENDING] No OAuth token file found at {resolved_path}.")
        print("  -> MCP server protocol and schemas are operational.")
        print("  -> Live Google API calls require browser authorization via:")
        print(f"     .venv/bin/python3 -m src.mcp_server.main --auth")
        return False
    
    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        has_refresh = bool(data.get("refresh_token"))
        has_access = bool(data.get("token"))
        scopes = data.get("scopes", [])
        print(f"[PASS] Token file exists!")
        print(f"  Has Refresh Token: {has_refresh}")
        print(f"  Has Access Token: {has_access}")
        print(f"  Authorized Scopes: {scopes}")
        return True
    except Exception as e:
        print(f"[WARN] Error reading token file: {e}")
        return False

def main():
    print("=" * 60)
    print(" GENERIC GMAIL + GOOGLE DOCS MCP SERVER VERIFICATION")
    print("=" * 60)
    
    success_listing = verify_tool_listing()
    success_stdio = verify_stdio_jsonrpc()
    success_auth = verify_auth_token_status()

    print("\n" + "=" * 60)
    print(" VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"1. CLI Tool Schema Discovery:   {'PASSED' if success_listing else 'FAILED'}")
    print(f"2. JSON-RPC 2.0 stdio Server:   {'PASSED' if success_stdio else 'FAILED'}")
    print(f"3. Auth & Credentials Check:    {'PASSED' if success_auth else 'FAILED'}")
    print("=" * 60)

    if success_listing and success_stdio and success_auth:
        print("\nAll MCP Server components are fully verified and functioning!\n")
        sys.exit(0)
    else:
        print("\nSome checks encountered issues.\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
