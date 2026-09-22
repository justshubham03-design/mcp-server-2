# Generic Gmail + Google Docs MCP Server

A generic, secure **Model Context Protocol (MCP)** server enabling AI agents (Cursor, Claude Desktop, Antigravity, LangChain/LangGraph) to interact safely with **Gmail** and **Google Docs** over standard JSON-RPC 2.0 `stdio`.

---

## 1. Available MCP Tools

### `gmail_create_draft`
Creates an email draft in Gmail without sending it.
```json
{
  "to": ["recipient@example.com"],
  "cc": ["optional_cc@example.com"],
  "bcc": ["optional_bcc@example.com"],
  "subject": "Review Pulse Notes",
  "body": "Here is the summary..."
}
```
**Response**:
```json
{
  "success": true,
  "draftId": "r-849201948201",
  "messageId": "18f910a8bc02e4d1"
}
```

### `gmail_send_email`
Sends an email immediately using the authenticated Gmail account.
```json
{
  "to": ["recipient@example.com"],
  "subject": "Urgent Pulse Update",
  "body": "Sent email content..."
}
```
**Response**:
```json
{
  "success": true,
  "messageId": "18f910a8bc02e4d1",
  "recipientCount": 1
}
```

### `google_docs_append`
Safely appends text to the end of an existing Google Doc using Docs API structural indexing.
```json
{
  "documentId": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
  "content": "## New Section\nAppended weekly pulse content...",
  "addNewline": true
}
```
**Response**:
```json
{
  "success": true,
  "documentId": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
  "appendedCharacters": 48,
  "insertLocationIndex": 842
}
```

---

## 2. Setup & Authentication

### Step 1: Configure `.env`
```env
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
GOOGLE_REDIRECT_URI=http://localhost:3000/oauth2callback
GOOGLE_TOKEN_PATH=~/.config/google-mcp/token.json
```

### Step 2: Authenticate with Google
Run the one-time interactive OAuth setup:
```bash
python -m src.mcp_server.main --auth
```
This opens your browser to authorize access to Gmail and Google Docs, saving the refresh token securely with `0600` permissions.

---

## 3. Connecting to MCP Clients

### Cursor Configuration (`~/.cursor/mcp.json` or Project Config)
```json
{
  "mcpServers": {
    "google-workspace": {
      "command": "/Users/shubham73/Documents/groww review ai/.venv/bin/python3",
      "args": ["-m", "src.mcp_server.main"],
      "env": {
        "GOOGLE_CLIENT_ID": "your_client_id",
        "GOOGLE_CLIENT_SECRET": "your_client_secret",
        "GOOGLE_TOKEN_PATH": "~/.config/google-mcp/token.json"
      }
    }
  }
}
```

### Claude Desktop Configuration (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "google-workspace": {
      "command": "/Users/shubham73/Documents/groww review ai/.venv/bin/python3",
      "args": ["-m", "src.mcp_server.main"],
      "env": {
        "GOOGLE_TOKEN_PATH": "~/.config/google-mcp/token.json"
      }
    }
  }
}
```

---

## 4. Testing

Run the test suite:
```bash
pytest tests/test_mcp_server.py -v
```
