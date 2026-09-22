#!/usr/bin/env python3
"""
Test Live MCP Tool Call: gmail_create_draft via stdio JSON-RPC.
"""

import sys
import json
import subprocess

def test_live_mcp_draft():
    cmd = [sys.executable, "-m", "src.mcp_server.main"]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    try:
        # 1. Initialize
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test-live-client", "version": "1.0.0"}
            }
        }
        proc.stdin.write(json.dumps(init_req) + "\n")
        proc.stdin.flush()
        init_res = json.loads(proc.stdout.readline())
        print("Initialize response:", init_res.get("result", {}).get("serverInfo"))

        # 2. Call gmail_create_draft
        call_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "gmail_create_draft",
                "arguments": {
                    "to": ["leadership@groww.in"],
                    "subject": "Groww Weekly Review Pulse - Live MCP Draft Verification",
                    "body": "This is a live test draft created via the Generic Google Workspace MCP Server over stdio JSON-RPC.\n\nAll systems are fully verified and operational."
                }
            }
        }
        proc.stdin.write(json.dumps(call_req) + "\n")
        proc.stdin.flush()
        call_res = json.loads(proc.stdout.readline())
        print("Tool call response:", json.dumps(call_res, indent=2))

        result_content = call_res.get("result", {}).get("content", [{}])[0].get("text", "")
        data = json.loads(result_content)
        if data.get("success"):
            print(f"\n SUCCESS! Live Gmail Draft Created!")
            print(f"Draft ID:   {data.get('draftId')}")
            print(f"Message ID: {data.get('messageId')}")
            return True
        else:
            print(f"\n FAILED: {data}")
            return False

    finally:
        proc.terminate()
        proc.wait(timeout=2)

if __name__ == "__main__":
    success = test_live_mcp_draft()
    sys.exit(0 if success else 1)
