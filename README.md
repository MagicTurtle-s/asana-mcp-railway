# Asana MCP Server for Railway

Production-ready Model Context Protocol (MCP) server for Asana with **full parity** to the official Asana MCP. Features OAuth 2.0 authentication and 42 comprehensive tools for complete task and project management.

## Features

- ✅ **OAuth 2.0 Authentication** with PKCE for enhanced security
- ✅ **42 MCP Tools** - Full parity with official Asana MCP
- ✅ **HTTP/SSE Transport** for remote access from Claude Code
- ✅ **Rate Limiting** (150-1,500 requests/minute)
- ✅ **Automatic Token Refresh** (1-hour access token lifecycle)
- ✅ **Multi-User Support** with per-user token management
- ✅ **Railway Deployment** ready with Docker configuration

## Available Tools (42 Total)

**Full parity with official Asana MCP** - All essential Asana operations supported.

### Task Management (15 tools)
Complete task lifecycle management including CRUD operations, search, batch operations, and subtask hierarchy.

### Project Management (10 tools)
Full project CRUD, duplication, statistics, sections, and status updates.

### Section Management (5 tools)
Complete section CRUD and task assignment operations.

### Task Relationships (8 tools)
Dependencies, dependents, and subtask relationships with full add/remove/view capabilities.

### Task Organization (4 tools)
Manage task projects and tags (add/remove operations).

### Workspace & Tags (2 tools)
Workspace listing and tag-based task queries.

**See [TOOL-LIST-v1.1.0.md](TOOL-LIST-v1.1.0.md) for complete tool documentation.**

## 📚 Included Skills

This repository includes a Claude Code skill for optimal Asana MCP usage:

**asana-mcp-field-guide** - Execution-ready reference that automatically activates when performing Asana operations. Provides:
- ✅ **Query optimization patterns** - 30-50x token reduction through field filtering
- ✅ **Date range best practices** - Prevents unbounded historical data fetches
- ✅ **Custom field handling** - Systematic filtering to avoid response bloat
- ✅ **Anti-patterns guide** - Common mistakes and fixes
- ✅ **Ready-to-use templates** - Workload checks, priority lists, overdue analysis

The skill auto-discovers when you use this MCP server and provides context-aware guidance for efficient API usage.

**Location**: `.claude/skills/asana-mcp-field-guide/SKILL.md`

## Quick Start

### 1. Register Asana OAuth App

1. Go to [Asana Developer Console](https://app.asana.com/0/developer-console)
2. Create new app
3. Set redirect URI:
   - Development: `http://localhost:3000/oauth/callback`
   - Production: `https://your-app.railway.app/oauth/callback`
4. Configure scopes: `default` (or specific scopes)
5. Save `CLIENT_ID` and `CLIENT_SECRET`

### 2. Local Development

```bash
# Clone repository
git clone https://github.com/MagicTurtle-s/asana-mcp-railway.git
cd asana-mcp-railway

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your Asana OAuth credentials

# Start server
python -m src.server_http
```

Server will start at `http://localhost:3000`

### 3. Authenticate

1. Visit `http://localhost:3000/oauth/start`
2. Complete Asana authorization
3. You'll be redirected to callback with success message

### 4. Configure in Claude Code

```bash
# Add MCP server
claude mcp add --transport http --scope user asana http://localhost:3000/mcp

# Verify connection
claude mcp list
```

### 5. Test Tools

Ask Claude Code to:
- "List my Asana workspaces"
- "Search for incomplete tasks in workspace [GID]"
- "Create a task named 'Test MCP' in project [GID]"

## Railway Deployment

### Prerequisites

- GitHub repository with your code
- Railway account ([railway.app](https://railway.app))
- Asana OAuth app configured with production redirect URI

### Deploy Steps

1. **Connect Repository**
   ```bash
   # Push to GitHub
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Create Railway Project**
   - Go to [railway.app](https://railway.app)
   - New Project → Deploy from GitHub
   - Select your repository

3. **Configure Environment Variables**

   In Railway dashboard, add:
   ```
   ASANA_CLIENT_ID=your_client_id
   ASANA_CLIENT_SECRET=your_client_secret
   ASANA_REDIRECT_URI=https://your-app.railway.app/oauth/callback
   PORT=3000
   NODE_ENV=production
   ```

4. **Deploy**
   - Railway will auto-deploy using the Dockerfile
   - Wait for deployment to complete
   - Note your app URL: `https://your-app.railway.app`

5. **Update Asana OAuth App**
   - Add production redirect URI in Asana Developer Console
   - `https://your-app.railway.app/oauth/callback`

6. **Test Deployment**
   ```bash
   # Health check
   curl https://your-app.railway.app/health

   # Start OAuth flow
   # Visit: https://your-app.railway.app/oauth/start
   ```

7. **Configure in Claude Code**
   ```bash
   claude mcp add --transport http --scope user asana https://your-app.railway.app/mcp
   ```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ASANA_CLIENT_ID` | Yes | OAuth app client ID |
| `ASANA_CLIENT_SECRET` | Yes | OAuth app client secret |
| `ASANA_REDIRECT_URI` | Yes | OAuth callback URL |
| `PORT` | No | Server port (default: 3000) |
| `HOST` | No | Server host (default: 0.0.0.0) |
| `NODE_ENV` | No | Environment (development/production) |
| `LOG_LEVEL` | No | Logging level (default: info) |

### Rate Limits

- **Free Plan**: 150 requests/minute
- **Premium Plan**: 1,500 requests/minute

To use premium rate limit, modify `src/server_http.py`:
```python
rate_limiter = RateLimiter(max_requests=1500)  # Premium tier
```

## API Endpoints

### Health Check
```
GET /health
```

Returns server status and rate limiter info.

### OAuth Flow
```
GET /oauth/start
```
Initiates OAuth authorization. Redirects to Asana.

```
GET /oauth/callback?code=...&state=...
```
Handles OAuth callback. Exchanges code for tokens.

```
GET /oauth/status
```
Check authentication status.

### MCP Endpoint
```
POST /mcp
```
MCP communication endpoint (SSE transport).

## Development

### Project Structure
```
asana-mcp-railway/
├── src/
│   ├── __init__.py
│   ├── __main__.py
│   ├── oauth.py              # OAuth 2.0 manager
│   ├── asana_client.py       # Asana API client
│   ├── server_http.py        # HTTP server + MCP
│   ├── tools/
│   │   ├── tasks.py          # Task tools
│   │   ├── projects.py       # Project tools
│   │   ├── relationships.py  # Dependency tools
│   │   └── organization.py   # Tag/workspace tools
│   └── utils/
│       └── formatters.py     # Response formatting
├── .claude/
│   └── context.md            # Architecture docs
├── PROJECT.md                # Quick reference
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container config
├── railway.toml              # Railway config
└── .env.example              # Env template
```

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/
```

### Code Quality

```bash
# Format code
pip install black
black src/

# Type checking
pip install mypy
mypy src/
```

## Troubleshooting

### OAuth Issues

**Problem**: "Invalid state parameter"
- **Solution**: Clear browser cookies and try again. State parameter expires after 10 minutes.

**Problem**: "Redirect URI mismatch"
- **Solution**: Ensure the redirect URI in `.env` exactly matches the one registered in Asana Developer Console.

### Rate Limiting

**Problem**: "Rate limit exceeded"
- **Solution**: Wait 60 seconds. The rate limiter automatically retries. Consider upgrading to Asana Premium for 10x higher limits.

### Token Expiration

**Problem**: "Authentication expired"
- **Solution**: Tokens auto-refresh. If refresh fails, re-authenticate via `/oauth/start`.

### Railway Deployment

**Problem**: Health check failing
- **Solution**: Check Railway logs for errors. Ensure environment variables are set correctly.

**Problem**: OAuth redirect fails
- **Solution**: Verify production redirect URI is registered in Asana OAuth app settings.

## Security Considerations

### Token Storage

- **Development**: In-memory cache (lost on restart)
- **Production**: Recommended to use Redis
  - Add Redis to Railway project
  - Set `REDIS_URL` environment variable
  - Update `oauth.py` to use Redis backend

### HTTPS Requirement

- Production OAuth requires HTTPS
- Railway provides HTTPS by default
- Development can use HTTP localhost

### CORS

- Currently allows all origins (`allow_origins=["*"]`)
- For production, restrict to specific domains:
  ```python
  allow_origins=["https://your-domain.com"]
  ```

## Performance Optimization

### Connection Pooling

- HTTP client uses connection pooling (100 connections max)
- Keepalive connections to Asana API
- Configurable in `asana_client.py`

### Caching

Consider caching:
- Workspace lists (rarely change)
- Project lists (hourly refresh)
- User lists (daily refresh)

### Batch Operations

- Use `asana_get_multiple_tasks_by_gid` for batch fetches (up to 25)
- More efficient than individual get_task calls

## Cost Estimate

- **Railway Hosting**: ~$5/month (Hobby plan)
- **Asana API**: Free (150 req/min)
- **Total**: ~$5/month

## Support

- **Issues**: [GitHub Issues](https://github.com/MagicTurtle-s/asana-mcp-railway/issues)
- **Documentation**: See `.claude/context.md` and `PROJECT.md`
- **Asana API**: [Asana Developer Docs](https://developers.asana.com/docs)

## Related Projects

- **Claude Code MCP Bridge** - Delegate tasks from Claude Desktop to Claude Code
- **SharePoint MCP Railway** - Similar OAuth + Railway pattern
- **HubSpot MCP Railway** - HTTP transport reference

## License

MIT

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Changelog

### v0.1.0 (2025-11-05)
- Initial release
- OAuth 2.0 with PKCE
- 22 MCP tools
- HTTP/SSE transport
- Railway deployment ready

---

**Built with** ❤️ **by MagicTurtle-s**
