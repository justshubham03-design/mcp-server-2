#!/usr/bin/env python3
"""
Helper script to export environment variables and OAuth token for Railway / Cloud deployment.
"""

import os
import json
import base64
from pathlib import Path

def export_env():
    token_path = Path("./.config/google_token.json")
    print("=" * 65)
    print(" RAILWAY DEPLOYMENT ENVIRONMENT VARIABLES HELPER")
    print("=" * 65)
    print("Copy and paste these variables into your Railway Service Settings:")
    print("Railway Dashboard -> Your Service -> Variables -> Raw Editor\n")
    
    env_vars = {}
    
    # Read existing .env
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()

    # Add token as string and base64
    if token_path.exists():
        token_str = token_path.read_text(encoding="utf-8").strip()
        env_vars["GOOGLE_TOKEN_JSON"] = token_str
        env_vars["GOOGLE_TOKEN_BASE64"] = base64.b64encode(token_str.encode("utf-8")).decode("utf-8")
        print("[FOUND] Local Google OAuth token detected and formatted.\n")
    else:
        print("[WARNING] Local Google OAuth token not found at ./.config/google_token.json")
        print("Run '.venv/bin/python3 -m src.mcp_server.main --auth' first if you want live Google API access.\n")

    print("-" * 65)
    for k, v in env_vars.items():
        if "KEY" in k or "SECRET" in k or "TOKEN" in k:
            masked = v[:6] + "..." + v[-4:] if len(v) > 12 else "***"
            print(f"{k}={v}")
        else:
            print(f"{k}={v}")
    print("-" * 65)

if __name__ == "__main__":
    export_env()
