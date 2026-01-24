# 🤖 MCP-Integrated AI Chatbot

A powerful AI chatbot powered by Google Gemini that can discover and use tools from multiple MCP (Model Context Protocol) servers. This allows your chatbot to interact with filesystems, APIs, databases, and custom tools dynamically.

## ✨ Features

- **Multi-Server MCP Support**: Connect to multiple MCP servers simultaneously
- **Automatic Tool Discovery**: Automatically discovers and integrates tools from connected servers
- **Google Gemini Integration**: Uses Gemini's function calling for intelligent tool usage
- **Extensible**: Easy to add new MCP servers and custom tools
- **Interactive Chat**: Clean command-line interface for conversations

## 📋 Prerequisites

- Python 3.10 or higher
- Node.js (for Node-based MCP servers like filesystem)
- Google Gemini API key ([Get one here](https://makersuite.google.com/app/apikey))

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install the filesystem MCP server (optional but recommended)
npm install -g @modelcontextprotocol/server-filesystem
```

### 2. Configure Environment

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:

```env
GEMINI_API_KEY=your_actual_api_key_here
```

### 3. Configure MCP Servers

The `mcp_config.json` file contains MCP server configurations. By default, it includes:

- **Filesystem Server**: Read/write files in the scratch directory
- **Custom Example Server**: Demo server with greet, calculate, and time tools

Edit `mcp_config.json` to:

- Modify the allowed filesystem paths
- Add/remove MCP servers
- Configure server-specific settings

### 4. Run the Chatbot

```bash
cd src
python app.py
```

## 💬 Using the Chatbot

Once started, you can:

- **Chat normally**: Ask questions or request tasks
- **Use tools**: The AI will automatically use MCP tools when needed
- **Type `tools`**: See all available tools
- **Type `quit`/`exit`**: Exit the application

### Example Conversations

```text
You: List the files in the current directory
🤖 Assistant: [Uses filesystem MCP server to list files]

You: Greet me in Spanish
🤖 Assistant: [Uses custom server's greet_user tool]

You: What's 42 multiplied by 17?
🤖 Assistant: [Uses custom server's calculate tool]
```

## 🔧 Adding New MCP Servers

### Using Existing MCP Servers

Add to `mcp_config.json`:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "your_github_token"
      },
      "description": "GitHub repository access"
    }
  }
}
```

### Creating Custom MCP Servers

See `examples/custom_mcp_server.py` for a complete example. Key steps:

1. Import the MCP server SDK
2. Create a `Server` instance
3. Define tools with `@app.list_tools()`
4. Implement tool handlers with `@app.call_tool()`
5. Run with stdio transport

## 📁 Project Structure

```text
mcp-chatbot/
├── src/
│   ├── app.py                  # Main entry point
│   ├── chatbot.py              # Chatbot logic with Gemini
│   └── mcp_client_manager.py   # MCP client management
├── examples/
│   └── custom_mcp_server.py    # Example custom server
├── mcp_config.json             # MCP server configurations
├── requirements.txt            # Python dependencies
├── .env.example               # Environment template
└── README.md                  # This file
```

## 🛠️ Architecture

```text
┌─────────────────┐
│   User Input    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│    MCPChatbot (chatbot.py)  │
│  - Google Gemini Integration │
│  - Function Call Handling   │
└────────┬────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  MCPClientManager (mcp_client_       │
│  manager.py)                         │
│  - Server Connection Management      │
│  - Tool Discovery                    │
│  - Tool Execution Routing            │
└────────┬─────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│         MCP Servers                    │
│  ┌──────────┐  ┌──────────┐           │
│  │Filesystem│  │  Custom  │  ...      │
│  │  Server  │  │  Server  │           │
│  └──────────┘  └──────────┘           │
└────────────────────────────────────────┘
```

## 🔍 How It Works

1. **Initialization**: App loads MCP config and connects to all servers
2. **Tool Discovery**: Each server reports its available tools
3. **Chat Loop**: User sends messages to the chatbot
4. **AI Processing**: Gemini decides if it needs to use tools
5. **Tool Execution**: MCP Client Manager routes tool calls to appropriate servers
6. **Response**: Results are sent back through Gemini to generate final response

## 🐛 Troubleshooting

### "GEMINI_API_KEY not found"

- Make sure you created a `.env` file
- Check that your API key is correctly set in `.env`

### Phase 1: Backend Standard & Debugging

- [x] Add explicit `PUBLIC_BASE_URL` logging in `chatbot.py`
- [x] Refactor `GenerateImage` tool response to include more metadata (width, height, etc.)
- [x] Add "Open Image" backup links to markdown output
- [x] Implement `GET /debug/image-test` in `main.py`
- [x] Standardize server-side download for *all* providers (Gemini/Pollinations)

### Phase 2: Frontend Robustness

- [x] Add debug JSON view in `chat.js`
- [x] Implement explicit `<img>` tag rendering with `onerror` fallback
- [x] Improve image styling (rounded corners, max-width)

### Phase 3: Verification & Deploy

- [x] Create `test_image_deploy.py` verification script
- [x] Mark fixed images in production logs
- [x] Push all changes and verify on Render

### "Configuration file not found"

- Ensure `mcp_config.json` exists in the project root
- Check that you're running the app from the correct directory

### MCP Server Connection Failures

- For Node servers: Ensure Node.js is installed and in PATH
- For custom servers: Check Python path and dependencies
- Review server logs for specific error messages

### No Tools Available

- Check MCP server configurations in `mcp_config.json`
- Verify servers are starting correctly (check logs)
- Ensure server commands and paths are correct

## 📚 Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [Google Gemini API](https://ai.google.dev/docs)
- [Available MCP Servers](https://github.com/modelcontextprotocol/servers)

## 🤝 Contributing

Feel free to extend this chatbot with:

- Additional MCP servers
- Custom tools
- UI improvements
- Better error handling

## 📄 License

MIT License - Feel free to use and modify!

---

## 🚀 Render Deployment

### Important Notes

- **Free Tier Sleep**: Render free services automatically sleep after 15 minutes of inactivity. This can cause "cold start" delays of 30-60 seconds when waking up.
- **Keep Alive**: Use a monitoring service like UptimeRobot to ping your app every 5 minutes to prevent sleep.
- **Server Binding**: The server binds to `0.0.0.0` and uses the `PORT` environment variable (required by Render).

### Health Check Endpoints

The app includes health check endpoints that don't require authentication and don't call any AI models:

| Endpoint | Description |
| :--- | :--- |
| `GET /health` | Returns status, timestamp, version |
| `GET /ping` | Returns simple pong response |
| `GET /api/health` | Same as /health |
| `GET /api/ping` | Same as /ping |

### Environment Variables for Render

Set these in your Render dashboard under Environment:

- `GROQ_API_KEY` - Your Groq API key
- `GEMINI_API_KEY` - Your Gemini API key
- `HF_TOKEN` - Your HuggingFace token
- `REPLICATE_API_TOKEN` - Your Replicate token
- `PUBLIC_BASE_URL` - **CRITICAL**: The public URL of your service (e.g., `https://your-chatbot.onrender.com`)

### Render Deploy Steps

1. **Connect Repository**:
   - Go to [Render Dashboard](https://dashboard.render.com) → New → Web Service
   - Connect your GitHub repo

2. **Configure Settings**:
   - **Name**: `mcp-chatbot` (or your preferred name)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

3. **Set Environment Variables**:
   - Go to Environment tab
   - Add all 4 API keys listed above

4. **Deploy**:
   - Click "Create Web Service"
   - Wait for build to complete

5. **Redeploy** (after code changes):
   - Push to GitHub, Render auto-deploys
   - Or: Dashboard → Manual Deploy → Deploy latest commit

---

## 📊 UptimeRobot Setup

To prevent Render cold starts and monitor uptime:

1. **Create Account**: Sign up at [UptimeRobot](https://uptimerobot.com/)
2. **Add New Monitor**:
   - Monitor Type: **HTTP(s)**
   - Friendly Name: `MCP Chatbot Health`
   - URL: `https://your-app.onrender.com/health`
   - Monitoring Interval: **5 minutes**
   - Expected Response Code: **200**
3. **Alert Contacts**: (Optional) Add email/webhook for downtime alerts

---

---

### Built with ❤️ using MCP and Google Gemini
