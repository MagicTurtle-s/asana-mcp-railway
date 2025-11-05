# Asana MCP Railway

Production-ready MCP server for Asana integration with Claude Code CLI, featuring OAuth 2.0 authentication and comprehensive task management tools.

## Quick Reference

**Status**: 🔄 IN DEVELOPMENT
**Local Path**: `/c/Users/jonat/asana-mcp-railway`
**GitHub**: https://github.com/MagicTurtle-s/asana-mcp-railway
**Deployed Endpoint**: TBD (Railway)
**Stack**: Python 3.10+, FastMCP, Railway, Asana API, OAuth 2.0

## What This Provides

Access to Asana's Work Graph from Claude Code, including:
- 22 comprehensive MCP tools for task and project management
- OAuth 2.0 authentication with automatic token refresh
- Multi-user support with per-user token management
- Rate limit handling (150-1,500 requests/minute)
- HTTP/SSE transport for remote access

## Key Files

### Core Implementation
- `src/oauth.py` - OAuth 2.0 manager with PKCE support
- `src/asana_client.py` - Asana API wrapper with rate limiting
- `src/server_http.py` - HTTP/SSE MCP server with Starlette
- `src/tools/tasks.py` - Task management tools
- `src/tools/projects.py` - Project management tools
- `src/tools/relationships.py` - Task dependency tools
- `src/tools/organization.py` - Workspace and tag tools

### Configuration
- `.env` - Environment variables (OAuth credentials, PORT)
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration
- `railway.toml` - Railway deployment settings

### Documentation
- `PROJECT.md` - This file
- `.claude/context.md` - Architecture and implementation patterns
- `README.md` - Setup and usage instructions

## Available Tools

### Task Management (7 tools)
- `asana_list_workspaces` - List all available workspaces
- `asana_search_tasks` - Search tasks with filters (assignee, project, completion, dates)
- `asana_get_task` - Get detailed task information
- `asana_create_task` - Create new tasks with metadata
- `asana_update_task` - Update existing tasks
- `asana_get_task_stories` - Get task comments and activity
- `asana_create_task_story` - Add comments to tasks

### Project Management (5 tools)
- `asana_search_projects` - Find projects by name
- `asana_get_project` - Get project details
- `asana_get_project_sections` - List project sections
- `asana_get_project_statuses` - Get project status updates
- `asana_create_project_status` - Post new status updates

### Task Relationships (4 tools)
- `asana_add_task_dependencies` - Add blocking tasks
- `asana_add_task_dependents` - Add dependent tasks
- `asana_create_subtask` - Create child tasks
- `asana_set_parent_for_task` - Set task parent with positioning

### Organization (3 tools)
- `asana_get_tags_for_workspace` - List workspace tags
- `asana_get_tasks_for_tag` - Find tasks with specific tags
- `asana_get_multiple_tasks_by_gid` - Batch fetch up to 25 tasks

## External Services

### Asana OAuth App
**Setup Location**: https://app.asana.com/0/developer-console
**Required Scopes**: `default` (or specific: `tasks:read`, `tasks:write`, `projects:read`, `projects:write`)

**Credentials stored in**:
- Development: `.env` file (local only, gitignored)
- Production: Railway environment variables

**OAuth Endpoints**:
- Authorization: `https://app.asana.com/-/oauth_authorize`
- Token: `https://app.asana.com/-/oauth_token`
- Revoke: `https://app.asana.com/-/oauth_revoke`

### Railway Deployment
**Cost**: ~$5/month (hobby plan)
**Region**: US-West (recommended)
**Health Check**: `/health`
**MCP Endpoint**: `/mcp` (SSE transport)
**OAuth Callback**: `/oauth/callback`

## Setup Instructions

### 1. Register Asana OAuth App
```bash
# Go to: https://app.asana.com/0/developer-console
# Create new app
# Set redirect URI: http://localhost:3000/oauth/callback (dev)
# Configure scopes: default
# Save CLIENT_ID and CLIENT_SECRET
```

### 2. Local Development
```bash
# Clone repository
git clone https://github.com/MagicTurtle-s/asana-mcp-railway.git
cd asana-mcp-railway

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Asana OAuth credentials

# Run server
python -m src.server_http
```

### 3. Railway Deployment
```bash
# Build and push
git add .
git commit -m "Initial deployment"
git push

# Railway will auto-deploy
# Configure environment variables in Railway dashboard
# Update Asana OAuth app with production redirect URI
```

### 4. Configure in Claude Code
```bash
# Add MCP server
claude mcp add --transport http --scope user asana https://[your-app].railway.app/mcp

# Verify connection
claude mcp list
```

### 5. Authenticate
```bash
# Visit OAuth start URL to authenticate
# https://[your-app].railway.app/oauth/start
# Complete Asana authorization flow
```

## Common Tasks

### Test OAuth Flow
```bash
# Start local server
python -m src.server_http

# Visit in browser
http://localhost:3000/oauth/start

# Complete authorization
# Check token storage in logs
```

### Test MCP Tools Locally
```bash
# Use stdio transport for testing
python -m src.server_stdio

# Connect with Claude Code CLI in another terminal
```

### Check Authentication Status
```bash
curl https://[your-app].railway.app/oauth/status
```

### Monitor Rate Limits
```python
# Check logs for rate limit warnings
# Asana returns X-RateLimit headers
# Free: 150/min, Premium: 1500/min
```

### Refresh Tokens Manually
```python
# Tokens auto-refresh before expiry (1-hour lifetime)
# Manual refresh (if needed):
from src.oauth import AsanaOAuthManager
manager = AsanaOAuthManager(...)
new_token = await manager.refresh_access_token(refresh_token)
```

## Related Projects

### Similar Pattern
- **SharePoint MCP Railway** (`C:/Users/jonat/sharepoint-mcp-railway`)
  - Uses OAuth 2.0 with MSAL
  - HTTP/SSE transport
  - Railway deployment
  - Per-user authentication

### Integration
- **Claude Code MCP Bridge** (`C:/Users/jonat/claude-code-mcp-bridge`)
  - Enables Claude Desktop to delegate tasks to Claude Code
  - Claude Desktop can leverage Asana tools via delegation

## Troubleshooting

### OAuth Issues
- Verify CLIENT_ID and CLIENT_SECRET are correct
- Check redirect URI matches OAuth app registration
- Ensure callback URL is accessible (HTTPS for production)
- Check browser console for authorization errors

### Rate Limiting
- Monitor X-RateLimit-* response headers
- Free plan: 150 requests/minute
- Premium plan: 1,500 requests/minute
- Implement request queuing if hitting limits

### Token Expiration
- Access tokens expire after 1 hour
- Refresh tokens are long-lived
- Auto-refresh happens 5 minutes before expiry
- If refresh fails, user must re-authenticate

### Deployment Issues
- Check Railway logs for errors
- Verify environment variables are set
- Ensure health check endpoint responds
- Test OAuth callback URL is reachable

## Architecture Notes

- Token storage: In-memory cache (production should use Redis)
- Rate limiting: Per-user request tracking
- Error handling: Asana-specific error translation
- Pagination: Offset-based (max 100 results per page)
- PKCE: Implemented for enhanced OAuth security

## Cost Breakdown

- **Railway Hosting**: ~$5/month (hobby plan)
- **Asana API**: Free (150 req/min on free plan)
- **Total**: ~$5/month

## Version History

- **v0.1.0** (Current) - Initial development
  - Project structure setup
  - OAuth implementation in progress
  - Tool development pending

---

**Last Updated**: 2025-11-05
**Maintainer**: MagicTurtle-s
**License**: MIT
