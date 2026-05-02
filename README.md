# 🔧 Multi-Tool MCP Server

A Python MCP server with **Web Search/Fetch**, **Text Utilities**, and **Calculator** tools.
Transport: **Streamable HTTPS** + **SSE** fallback — compatible with SARA, LibreChat, Claude Desktop, and any MCP client.

---

## 🛠 Tools Available

### 🌐 Web
| Tool | Description |
|------|-------------|
| `web_fetch` | Fetch & extract text from any public URL |
| `web_search` | Search the web via DuckDuckGo |

### 📝 Text / File Utilities
| Tool | Description |
|------|-------------|
| `text_word_count` | Count words, chars, sentences, lines |
| `text_transform` | uppercase · lowercase · title_case · snake_case · camel_case · reverse · strip · wrap |
| `text_extract_pattern` | Extract all regex matches from text |
| `text_find_replace` | Find & replace (literal or regex) |

### 🔢 Calculator
| Tool | Description |
|------|-------------|
| `calculator_evaluate` | Safely evaluate math expressions (sqrt, sin, log, pi, …) |
| `calculator_unit_convert` | Convert units: length · mass · data · temperature |

---

## 🚀 Deploy in 5 minutes (free)

### Option A — Railway (recommended)
1. Push this folder to a GitHub repo
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
3. Select your repo — Railway auto-detects the Dockerfile
4. Once deployed, copy the public URL (e.g. `https://multi-tool-mcp-production.up.railway.app`)

### Option B — Render
1. Push to GitHub
2. Go to [render.com](https://render.com) → **New Web Service** → connect your repo
3. Render uses `render.yaml` automatically
4. Your URL will be `https://multi-tool-mcp.onrender.com`

### Option C — Run locally + Ngrok (instant testing)
```bash
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000

# In another terminal:
ngrok http 8000
# Copy the https://xxxx.ngrok.io URL
```

---

## 🔌 Connect to SARA / LibreChat

Fill in the **Add MCP Server** form:

| Field | Value |
|-------|-------|
| **Name** | Multi-Tool MCP |
| **MCP Server URL** | `https://YOUR-DEPLOY-URL.railway.app` |
| **Transport** | Streamable HTTPS |
| **Authentication** | No Auth |

Click **Create** ✅

---

## 🔌 Connect to Claude Desktop

Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "multi-tool-mcp": {
      "url": "https://YOUR-DEPLOY-URL.railway.app/sse"
    }
  }
}
```

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Server info & tool list |
| `/health` | GET | Health check |
| `/sse` | GET | SSE transport (Claude Desktop) |
| `/messages/` | POST | SSE message posting |

---

## 🧪 Test Locally

```bash
# Health check
curl http://localhost:8000/health

# List tools
curl http://localhost:8000/

# Test via MCP inspector
npx @modelcontextprotocol/inspector http://localhost:8000/sse
```

---

## 📦 Files

```
mcp_server/
├── server.py          # Main server (all tools)
├── requirements.txt   # Python dependencies
├── Dockerfile         # Container build
├── railway.json       # Railway deployment config
├── render.yaml        # Render deployment config
└── README.md          # This file
```
