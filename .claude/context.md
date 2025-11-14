# Asana MCP Railway - Claude Context

Architecture, patterns, and implementation details for the Asana MCP server.

## MCP Configuration

This project uses a project-specific MCP configuration to load the Asana MCP server when working in this directory.

**Setup:**
- `.claude/settings.json` (local, gitignored) contains the actual MCP server configuration
- `.claude/settings.json.example` (committed) serves as a template
- The Asana MCP (~35.7k tokens) is only loaded when working in this project

**When working on this project:**
- The Asana MCP tools are automatically available for testing
- You can use tools like `mcp__asana__asana_create_task` directly
- This configuration doesn't affect other projects

## Architecture Overview

### System Design

```
┌─────────────────┐
│  Claude Code    │
│      CLI        │
└────────┬────────┘
         │ HTTP/SSE
         │
    ┌────▼─────────────────────┐
    │  Asana MCP Server        │
    │  (Railway)               │
    │                          │
    │  ┌──────────────────┐   │
    │  │ HTTP/SSE Server  │   │
    │  │  (Starlette)     │   │
    │  └────────┬─────────┘   │
    │           │              │
    │  ┌────────▼─────────┐   │
    │  │  OAuth Manager   │   │
    │  │  Token Storage   │   │
    │  └────────┬─────────┘   │
    │           │              │
    │  ┌────────▼─────────┐   │
    │  │  Asana Client    │   │
    │  │  Rate Limiter    │   │
    │  └────────┬─────────┘   │
    │           │              │
    │  ┌────────▼─────────┐   │
    │  │   MCP Tools      │   │
    │  │  (22 tools)      │   │
    │  └──────────────────┘   │
    └───────────┬──────────────┘
                │ HTTPS
                │
      ┌─────────▼──────────┐
      │   Asana API        │
      │   (REST)           │
      └────────────────────┘
```

### Component Responsibilities

**HTTP/SSE Server** (`server_http.py`):
- Handles MCP communication via Server-Sent Events
- Provides OAuth flow endpoints (/oauth/start, /oauth/callback)
- Health check endpoint (/health)
- CORS configuration for web access

**OAuth Manager** (`oauth.py`):
- Authorization URL generation with PKCE
- Authorization code exchange for tokens
- Automatic token refresh (1-hour expiry)
- Per-user token storage (in-memory cache)
- Session management

**Asana Client** (`asana_client.py`):
- Wraps Asana REST API (https://app.asana.com/api/1.0/)
- HTTP client using httpx (async)
- Rate limit tracking and enforcement
- Pagination handling (offset-based)
- Error handling and retries

**MCP Tools** (`tools/*.py`):
- 22 tool implementations grouped by category
- Pydantic models for input validation
- Consistent response formatting (JSON/Markdown)
- Comprehensive docstrings for LLM understanding

## Key Patterns

### 1. OAuth 2.0 Flow

**Authorization Code Grant with PKCE**:

```python
# 1. Generate PKCE challenge
verifier = secrets.token_urlsafe(32)
challenge = base64.urlsafe_b64encode(
    hashlib.sha256(verifier.encode()).digest()
).decode().rstrip('=')

# 2. Build authorization URL
auth_url = f"https://app.asana.com/-/oauth_authorize?{params}"
# - client_id
# - redirect_uri
# - response_type=code
# - state (CSRF token)
# - code_challenge
# - code_challenge_method=S256

# 3. User authorizes → callback with code

# 4. Exchange code for tokens
POST https://app.asana.com/-/oauth_token
{
  "grant_type": "authorization_code",
  "client_id": CLIENT_ID,
  "client_secret": CLIENT_SECRET,
  "redirect_uri": REDIRECT_URI,
  "code": auth_code,
  "code_verifier": verifier
}

# 5. Store tokens per user
tokens = {
  "access_token": "...",    # 1-hour expiry
  "refresh_token": "...",   # long-lived
  "expires_in": 3600,
  "user_id": "..."
}

# 6. Auto-refresh before expiry
if time.time() >= expires_at - 300:  # 5-min buffer
    new_tokens = refresh_access_token(refresh_token)
```

### 2. Token Management

**In-Memory Cache (Development)**:
```python
class TokenCache:
    """Per-user token storage"""
    _cache: Dict[str, TokenData] = {}

    def store(self, user_id: str, tokens: TokenData):
        self._cache[user_id] = {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_at": time.time() + tokens.expires_in
        }

    def get_valid_token(self, user_id: str) -> str:
        """Returns valid access token, refreshing if needed"""
        tokens = self._cache.get(user_id)
        if not tokens:
            raise AuthenticationError("User not authenticated")

        # Check expiration with 5-min buffer
        if time.time() >= tokens["expires_at"] - 300:
            new_tokens = self._refresh(tokens["refresh_token"])
            self.store(user_id, new_tokens)
            return new_tokens.access_token

        return tokens["access_token"]
```

**Production Enhancement (Redis)**:
```python
# For production, replace in-memory cache with Redis
import redis

class RedisTokenCache:
    def __init__(self):
        self.redis = redis.from_url(os.getenv("REDIS_URL"))

    def store(self, user_id: str, tokens: TokenData):
        key = f"asana:tokens:{user_id}"
        self.redis.setex(
            key,
            tokens.expires_in,
            json.dumps(tokens.dict())
        )
```

### 3. Rate Limiting

**Asana API Limits**:
- Free: 150 requests/minute
- Premium: 1,500 requests/minute
- Evaluated continuously (not just at minute boundaries)

**Implementation**:
```python
class RateLimiter:
    def __init__(self, max_requests: int = 150):
        self.max_requests = max_requests
        self.requests: List[float] = []
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Wait if rate limit would be exceeded"""
        async with self.lock:
            now = time.time()
            # Remove requests older than 1 minute
            self.requests = [
                t for t in self.requests
                if now - t < 60
            ]

            if len(self.requests) >= self.max_requests:
                # Wait until oldest request ages out
                wait_time = 60 - (now - self.requests[0])
                await asyncio.sleep(wait_time)
                self.requests.pop(0)

            self.requests.append(now)
```

**Asana Response Headers**:
```
X-RateLimit-Limit: 150
X-RateLimit-Remaining: 145
X-RateLimit-Reset: 1699999999
```

### 4. Pagination Pattern

**Asana uses offset-based pagination**:

```python
async def get_all_tasks(workspace_gid: str) -> List[Task]:
    """Fetch all tasks with automatic pagination"""
    tasks = []
    offset = None

    while True:
        response = await client.get(
            f"/workspaces/{workspace_gid}/tasks",
            params={
                "limit": 100,  # max per page
                "offset": offset,
                "opt_fields": "name,completed,due_on"
            }
        )

        tasks.extend(response["data"])

        # Check for next page
        if "next_page" in response and response["next_page"]:
            offset = response["next_page"]["offset"]
        else:
            break

    return tasks
```

### 5. Tool Implementation Pattern

**Standard tool structure**:

```python
from pydantic import BaseModel, Field
from typing import Optional, List

class SearchTasksInput(BaseModel):
    """Input schema for search_tasks tool"""
    workspace: str = Field(
        description="Workspace GID to search in"
    )
    text: Optional[str] = Field(
        None,
        description="Text search query"
    )
    completed: Optional[bool] = Field(
        None,
        description="Filter by completion status"
    )
    assignee: Optional[str] = Field(
        None,
        description="Assignee GID"
    )
    projects: Optional[List[str]] = Field(
        None,
        description="List of project GIDs"
    )
    opt_fields: Optional[str] = Field(
        "name,completed,due_on,assignee",
        description="Comma-separated fields to return"
    )

@mcp.tool()
async def asana_search_tasks(
    workspace: str,
    text: Optional[str] = None,
    completed: Optional[bool] = None,
    assignee: Optional[str] = None,
    projects: Optional[List[str]] = None,
    opt_fields: str = "name,completed,due_on,assignee"
) -> str:
    """
    Search tasks in a workspace with advanced filtering.

    Supports filtering by:
    - Text search
    - Completion status
    - Assignee
    - Projects
    - Custom fields
    - Tags
    - Attachments
    - Dependencies

    Returns up to 100 tasks per request.
    Use pagination for larger result sets.
    """
    try:
        # Get authenticated client for user
        client = await get_asana_client(user_id)

        # Build query parameters
        params = {"opt_fields": opt_fields}
        if text:
            params["text"] = text
        if completed is not None:
            params["completed"] = str(completed).lower()
        if assignee:
            params["assignee.any"] = assignee
        if projects:
            params["projects.any"] = ",".join(projects)

        # Make API request
        response = await client.get(
            f"/workspaces/{workspace}/tasks/search",
            params=params
        )

        # Format response
        tasks = response["data"]
        return format_tasks(tasks)

    except RateLimitError as e:
        return f"Rate limit exceeded. Retry after {e.retry_after}s"
    except AuthenticationError:
        return "Authentication expired. Please re-authenticate."
    except Exception as e:
        return f"Error searching tasks: {str(e)}"
```

### 6. Error Handling

**Asana API Error Codes**:
```python
ERROR_HANDLERS = {
    400: "Bad Request - Invalid parameters",
    401: "Unauthorized - Token expired, re-authenticate",
    402: "Payment Required - Premium feature",
    403: "Forbidden - Insufficient permissions",
    404: "Not Found - Resource doesn't exist",
    424: "Failed Dependency - Related operation failed",
    429: "Rate Limit Exceeded - Wait and retry",
    500: "Server Error - Asana service issue",
    503: "Service Unavailable - Asana maintenance"
}

async def handle_api_error(response: httpx.Response) -> str:
    """Convert Asana errors to user-friendly messages"""
    status = response.status_code

    if status == 429:
        retry_after = response.headers.get("Retry-After", "60")
        return f"Rate limited. Please wait {retry_after} seconds."

    if status == 401:
        return "Your session expired. Please re-authenticate with Asana."

    if status in ERROR_HANDLERS:
        error_data = response.json()
        message = error_data.get("errors", [{}])[0].get("message", "")
        return f"{ERROR_HANDLERS[status]}: {message}"

    return f"API error ({status}): {response.text}"
```

### 7. Response Formatting

**Consistent output formats**:

```python
def format_tasks(tasks: List[dict]) -> str:
    """Format tasks for LLM consumption"""
    if not tasks:
        return "No tasks found."

    output = [f"Found {len(tasks)} tasks:\n"]

    for task in tasks:
        output.append(f"**{task['name']}** (GID: {task['gid']})")

        if task.get("completed"):
            output.append("  ✓ Completed")

        if task.get("due_on"):
            output.append(f"  📅 Due: {task['due_on']}")

        if task.get("assignee"):
            output.append(f"  👤 Assignee: {task['assignee']['name']}")

        output.append("")  # blank line

    return "\n".join(output)
```

## Common Gotchas

### 1. GID vs ID
- Asana uses "GID" (Global ID) as the primary identifier
- Always use GID in API requests, not numeric ID
- Format: String like "1234567890123456"

### 2. Opt Fields
- By default, API returns minimal fields
- Use `opt_fields` parameter to request specific fields
- Format: Comma-separated string: "name,completed,due_on,assignee.name"
- Nested fields: Use dot notation "assignee.name"
- **Important**: Requesting fields requires corresponding OAuth scopes

### 3. Array Parameters
- Asana API expects comma-separated strings for arrays
- Example: `projects.any=123,456,789`
- Don't send as JSON array in GET requests

### 4. Boolean Values
- Must be lowercase strings: "true" or "false"
- Not: True, False, 1, 0

### 5. Rate Limit Strategy
- Don't batch requests too aggressively
- Implement exponential backoff on 429 errors
- Cache workspace/project lists (change infrequently)
- Use opt_fields to minimize response size

### 6. Token Storage Security
- Never log access tokens or refresh tokens
- Use environment variables, not hardcoded values
- Encrypt tokens at rest (production)
- Implement token revocation on logout

### 7. CORS for HTTP Transport
- Railway deployment needs CORS enabled
- Allow origins: Claude Code CLI, web interfaces
- Include credentials: True (for OAuth)

### 8. Webhook Support (Future)
- Asana supports webhooks for real-time updates
- Consider adding webhook endpoints for:
  - Task completion notifications
  - Project status changes
  - Comment additions

## Testing Patterns

### Local Testing with stdio
```bash
# Run server in stdio mode
python -m src.server_stdio

# In another terminal, use MCP inspector
npx @modelcontextprotocol/inspector python -m src.server_stdio
```

### Testing OAuth Flow
```python
# 1. Start server locally
python -m src.server_http

# 2. Visit authorization URL
http://localhost:3000/oauth/start

# 3. Complete Asana authorization

# 4. Check token storage
# Should see tokens in logs

# 5. Test tool call
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "asana_list_workspaces"
    },
    "id": 1
  }'
```

### Unit Testing
```python
import pytest
from src.oauth import AsanaOAuthManager

@pytest.mark.asyncio
async def test_token_refresh():
    manager = AsanaOAuthManager(
        client_id="test_id",
        client_secret="test_secret",
        redirect_uri="http://localhost:3000/callback"
    )

    # Mock HTTP response
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MockResponse(
            status_code=200,
            json_data={
                "access_token": "new_token",
                "refresh_token": "new_refresh",
                "expires_in": 3600
            }
        )

        tokens = await manager.refresh_access_token("old_refresh")
        assert tokens["access_token"] == "new_token"
```

## Deployment Checklist

### Pre-Deployment
- [ ] All environment variables configured in Railway
- [ ] Asana OAuth app redirect URI updated to production URL
- [ ] Health check endpoint responds correctly
- [ ] CORS configured for production domains
- [ ] Error handling tested
- [ ] Rate limiting tested with high load

### Post-Deployment
- [ ] Health check passes: `curl https://[app].railway.app/health`
- [ ] OAuth flow works end-to-end
- [ ] All 22 tools functional
- [ ] Rate limit handling verified
- [ ] Token refresh tested
- [ ] MCP server accessible from Claude Code
- [ ] Documentation updated with production URLs

### Monitoring
- Watch Railway logs for errors
- Monitor rate limit warnings
- Track OAuth token refresh success rate
- Check health check uptime

## Performance Considerations

### Token Cache
- In-memory cache OK for development
- Production: Use Redis (Railway add-on)
- Cache TTL: Match token expiry (1 hour)
- Implement cache warming on startup

### API Response Caching
- Cache workspace lists (rarely change)
- Cache project lists per workspace (refresh hourly)
- Cache user lists per workspace (refresh daily)
- Don't cache task data (frequently changes)

### Request Batching
- Use `get_multiple_tasks_by_gid` for batch fetches (up to 25)
- Combine related API calls where possible
- Implement request deduplication

### Connection Pooling
- httpx client with connection pooling
- Keep-alive connections to Asana API
- Timeout configurations:
  - Connect: 10s
  - Read: 30s
  - Pool: 100 connections

## Security Best Practices

1. **OAuth State Parameter**: Always include and validate
2. **PKCE**: Implement for enhanced security
3. **HTTPS Only**: Production must use HTTPS
4. **Token Encryption**: Encrypt tokens at rest (production)
5. **Scope Minimization**: Request only needed scopes
6. **Session Security**: Use secure, httpOnly cookies
7. **CORS**: Restrict to known origins
8. **Rate Limiting**: Implement per-user limits
9. **Audit Logging**: Log authentication events
10. **Error Messages**: Don't leak sensitive info

## Future Enhancements

1. **Redis Token Storage**: Replace in-memory cache
2. **Webhook Support**: Real-time task updates
3. **Custom Fields**: Full CRUD operations
4. **Attachments**: Upload/download support
5. **Portfolios**: Portfolio management tools
6. **Goals**: Goal tracking tools
7. **Teams**: Team management
8. **Batch Operations**: Bulk task updates
9. **Search Improvements**: Advanced filtering
10. **Caching Layer**: Reduce API calls

## Related Documentation

- **MCP Best Practices**: See `mcp-builder` skill reference files
- **Asana API Docs**: https://developers.asana.com/docs
- **OAuth 2.0 Spec**: https://oauth.net/2/
- **FastMCP Guide**: https://github.com/jlowin/fastmcp

---

**Last Updated**: 2025-11-05
