Public source: https://raw.githubusercontent.com/OpenHands/OpenHands-CLI/main/README.md
Read at: 2026-10-13T02:53:02Z
HTTP status: 200
Capture: selected readable source text; embedded scripts/styles omitted.

> ⚠️ **This project is no longer actively maintained.**
- `mcp.json`: MCP server configuration
### [MCP Servers](https://docs.openhands.dev/openhands/usage/cli/mcp-servers)
Extend OpenHands capabilities with [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) servers:
openhands mcp list
openhands mcp add tavily --transport stdio \
npx -- -y mcp-remote "https://mcp.tavily.com/mcp/?tavilyApiKey=<your-api-key>"
openhands mcp enable <server-name>
openhands mcp disable <server-name>
openhands --headless --json -t "Create a Flask app"
