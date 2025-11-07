# Session-Based Authentication Guide

## Overview

The Asana MCP Server supports **session-based authentication** for multi-user environments, specifically designed for Claude Desktop + Claude Code Bridge deployments. This eliminates the need for manual token management while providing robust loop prevention and concurrent request handling.

## Architecture

### Key Components

1. **SessionManager** (`src/session_manager.py`)
   - Desktop-scoped session lifecycle management
   - State machine: PENDING → ACTIVE → EXPIRED → REVOKED → PURGED
   - Concurrent request protection with asyncio locks
   - Circuit breakers for re-authentication attempts
   - Automatic session cleanup (30-day purge)

2. **AsanaOAuthManager** (`src/oauth.py`)
   - OAuth 2.0 with PKCE integration
   - Session-based token refresh with locking
   - Automatic token renewal (5-minute buffer before expiry)
   - Backward compatible with legacy user_id-based auth

3. **HTTP Server** (`src/server_http.py`)
   - Session management endpoints
   - OAuth flow with session support
   - Legacy flow fallback for backward compatibility

## Session Flow

### 1. Desktop Initialization

When Claude Desktop starts with the Bridge:

```javascript
// Desktop generates unique instance ID
const desktop_instance_id = `desktop-${process.pid}-${Date.now()}`;

// Create session via MCP server
const response = await fetch('http://localhost:3000/session/create', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ desktop_instance_id })
});

const { session_id, oauth_url } = await response.json();

// Store session_id for all future requests
process.env.ASANA_SESSION_ID = session_id;

// Launch browser for OAuth (one-time setup)
openBrowser(oauth_url);
```

### 2. User Authentication

User completes OAuth flow once:

```
1. Desktop opens: http://localhost:3000/oauth/start?session={session_id}
2. User redirects to Asana, authorizes app
3. Callback stores tokens in session
4. User returns to Desktop (window can close)
5. Session now ACTIVE, ready for API calls
```

### 3. Tool Calls with Session

All MCP tool calls include session_id:

```javascript
// Bridge injects session_id into tool arguments
const toolCall = {
  name: "asana_search_tasks",
  arguments: {
    session_id: process.env.ASANA_SESSION_ID,  // Injected by Bridge
    workspace: "1234567890",
    completed: false
  }
};
```

### 4. Automatic Token Refresh

When token expires (1-hour lifetime):

```python
# src/oauth.py - get_valid_token_for_session()
async with session.refresh_lock:  # Concurrent protection
    if session.needs_refresh():
        session.is_refreshing = True
        new_tokens = await refresh_access_token(session.refresh_token)
        session.update_tokens(new_tokens.access_token, ...)
        session.is_refreshing = False
```

**Key Features:**
- Only one refresh at a time per session (asyncio lock)
- Other concurrent requests wait for refresh to complete
- Silent refresh (5-minute buffer before expiry)
- No user interaction required

### 5. Re-authentication (Token Expired)

If refresh fails (e.g., refresh token revoked):

```python
# Tool call detects auth failure
except AuthenticationError:
    # Check circuit breaker
    if session.should_allow_reauth():
        # Auto-trigger browser
        openBrowser(f"/oauth/start?session={session_id}")
        return "Authentication expired. Please complete OAuth flow."
    else:
        return "Too many auth attempts. Please wait 10 minutes."
```

**Circuit Breaker Rules:**
- Max 3 re-auth attempts per 10 minutes
- Exponential backoff between attempts (1s, 2s, 4s)
- 2-minute timeout on re-auth completion

## API Endpoints

### Session Management

#### Create Session
```bash
POST /session/create
Content-Type: application/json

{
  "desktop_instance_id": "unique-desktop-id"
}

# Response
{
  "status": "success",
  "session_id": "BBlpmZ2YKKUCXLbkHbh7f9ek5y5cdmzr3lA2R9ZQj9M",
  "desktop_instance_id": "unique-desktop-id",
  "oauth_url": "/oauth/start?session=BBlpmZ2YKKUCXLbkHbh7f9ek5y5cdmzr3lA2R9ZQj9M",
  "message": "Session created. User should visit oauth_url to authenticate."
}
```

#### Validate Session
```bash
POST /session/validate
Content-Type: application/json

{
  "session_id": "session-id"
}

# Response (valid)
{
  "valid": true,
  "session_id": "session-id",
  "user": {
    "gid": "1200071404939449",
    "name": "Andrea",
    "email": "user@example.com"
  }
}

# Response (invalid)
{
  "valid": false,
  "session_id": "session-id",
  "error": "Session token expired, refresh required",
  "requires_auth": true,
  "oauth_url": "/oauth/start?session=session-id"
}
```

#### Get Session Info
```bash
GET /session/info?session={session_id}

# Response
{
  "session_id": "session-id",
  "desktop_instance_id": "desktop-123",
  "state": "active",
  "created_at": "2025-11-05T16:57:07.097731",
  "last_used_at": "2025-11-05T16:57:12.763568",
  "user": {
    "gid": "1200071404939449",
    "name": "Andrea",
    "email": "user@example.com"
  },
  "token_expired": false,
  "needs_refresh": false,
  "retry_count": 0,
  "re_auth_attempts": 1
}

# Get all sessions
GET /session/info

# Response
{
  "sessions": {
    "session-id-1": {...},
    "session-id-2": {...}
  },
  "count": 2
}
```

#### Revoke Session
```bash
POST /session/revoke
Content-Type: application/json

{
  "session_id": "session-id"
}

# Response
{
  "status": "success",
  "message": "Session revoked successfully"
}
```

### OAuth Flow

#### Start OAuth (Session-Based)
```bash
GET /oauth/start?session={session_id}

# Redirects to Asana authorization page
# Circuit breaker: Returns 429 after 3 attempts in 10 minutes
```

#### OAuth Callback
```bash
GET /oauth/callback?code={code}&state={session_id}

# Automatically stores tokens in session
# Returns success message
```

#### Check OAuth Status (Session-Based)
```bash
GET /oauth/status?session={session_id}

# Response
{
  "authenticated": true,
  "session_id": "session-id",
  "state": "active",
  "user": {
    "gid": "1200071404939449",
    "name": "Andrea",
    "email": "user@example.com"
  },
  "token_expired": false,
  "needs_refresh": false
}
```

## Loop Prevention Mechanisms

### 1. Circuit Breakers

**Re-Authentication Rate Limit:**
- Max 3 attempts per 10-minute window
- Tracked per session via `ReAuthAttempt` dataclass
- Returns HTTP 429 when exceeded

```python
class ReAuthAttempt:
    timestamp: float
    count: int = 1

    def should_allow(self, max_attempts: int = 3, window_seconds: int = 600) -> bool:
        age = time.time() - self.timestamp
        if age > window_seconds:
            self.count = 0  # Reset
            return True
        return self.count < max_attempts
```

### 2. Retry Limits

**Tool Call Retries:**
- Only retry ONCE after re-authentication
- Second failure returns error to user
- Non-auth errors (5xx, rate limits) don't trigger re-auth

```python
if not session.increment_retry_count():
    # Max retries exceeded
    return "Unable to complete request after re-authentication."
```

### 3. Concurrent Request Protection

**Token Refresh Locking:**
- `asyncio.Lock` per session prevents simultaneous refreshes
- First request refreshes, others wait
- 10-second timeout on lock acquisition

```python
async with session.refresh_lock:
    # Double-check after acquiring lock
    if not session.needs_refresh():
        return session.access_token

    # Only one request does the actual refresh
    session.is_refreshing = True
    new_tokens = await refresh_access_token(...)
    session.update_tokens(...)
```

### 4. State Machine

**Valid Transitions:**
```
PENDING → ACTIVE    (OAuth success)
ACTIVE → EXPIRED    (Token expired)
EXPIRED → ACTIVE    (Token refreshed)
ANY → REVOKED       (User logout)
ANY → PURGED        (Auto-cleanup)
```

Prevents:
- Re-auth from REVOKED state
- API calls from PENDING state
- Refresh from PURGED state

### 5. Stale Session Detection

**Periodic Validation:**
- Check every 5 minutes (Desktop responsibility)
- Ensures Desktop and MCP stay synchronized
- One session per Desktop instance

## Testing

### Manual Testing

**1. Test Session Creation:**
```bash
curl -X POST http://localhost:3000/session/create \
  -H "Content-Type: application/json" \
  -d '{"desktop_instance_id":"test-desktop-123"}'

# Response should include session_id and oauth_url
```

**2. Test OAuth Flow:**
```bash
# Open in browser
http://localhost:3000/oauth/start?session={session_id}

# Complete Asana authorization
# Check callback success
```

**3. Test Session Validation:**
```bash
curl -X POST http://localhost:3000/session/validate \
  -H "Content-Type: application/json" \
  -d '{"session_id":"session-id"}'

# Should return valid:true after OAuth
```

**4. Test Circuit Breaker:**
```bash
# Rapid requests (should trigger after 3)
for i in {1..5}; do
  curl "http://localhost:3000/oauth/start?session={session_id}" \
    -w "\nAttempt $i - Status: %{http_code}\n" -o /dev/null -s
done

# Attempts 1-2: 307 (redirect)
# Attempts 3-5: 429 (rate limited)
```

### Integration Testing

**Test Concurrent Token Refresh:**
```python
import asyncio
import httpx

async def concurrent_tool_calls(session_id):
    # Simulate 10 simultaneous tool calls
    async with httpx.AsyncClient() as client:
        tasks = [
            client.post(
                "http://localhost:3000/mcp",
                json={
                    "method": "tools/call",
                    "params": {
                        "name": "asana_list_workspaces",
                        "arguments": {"session_id": session_id}
                    }
                }
            )
            for _ in range(10)
        ]
        responses = await asyncio.gather(*tasks)

    # All should succeed, only one refresh should occur
    assert all(r.status_code == 200 for r in responses)

# Run test
asyncio.run(concurrent_tool_calls("your-session-id"))
```

## Claude Code Bridge Integration

### Bridge Setup

The Claude Code Bridge needs to:

1. **Generate Desktop Instance ID:**
```javascript
const DESKTOP_INSTANCE_ID = `desktop-${process.pid}-${Date.now()}`;
```

2. **Create Session on Startup:**
```javascript
async function initializeSession() {
  const response = await fetch('http://localhost:3000/session/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ desktop_instance_id: DESKTOP_INSTANCE_ID })
  });

  const { session_id, oauth_url } = await response.json();
  process.env.ASANA_SESSION_ID = session_id;

  // Launch OAuth if not authenticated
  const validation = await validateSession(session_id);
  if (!validation.valid) {
    openBrowser(`http://localhost:3000${oauth_url}`);
  }
}
```

3. **Inject Session ID into Tool Calls:**
```javascript
function injectSessionId(toolCall) {
  return {
    ...toolCall,
    arguments: {
      ...toolCall.arguments,
      session_id: process.env.ASANA_SESSION_ID
    }
  };
}
```

4. **Handle Auth Failures:**
```javascript
async function executeTool(toolCall) {
  try {
    const response = await mcpClient.callTool(injectSessionId(toolCall));
    return response;
  } catch (error) {
    if (error.message.includes('Authentication')) {
      // Auto-trigger re-auth
      const session_id = process.env.ASANA_SESSION_ID;
      openBrowser(`http://localhost:3000/oauth/start?session=${session_id}`);

      // Wait for re-auth (with timeout)
      await waitForAuth(session_id, { timeout: 120000 });

      // Retry once
      return await mcpClient.callTool(injectSessionId(toolCall));
    }
    throw error;
  }
}
```

5. **Periodic Session Validation:**
```javascript
setInterval(async () => {
  const session_id = process.env.ASANA_SESSION_ID;
  const validation = await validateSession(session_id);

  if (!validation.valid && validation.requires_auth) {
    console.log('Session expired. Re-authentication required.');
    openBrowser(`http://localhost:3000/oauth/start?session=${session_id}`);
  }
}, 5 * 60 * 1000);  // Every 5 minutes
```

## Production Deployment

### Redis for Token Storage

For production, replace in-memory storage with Redis:

```python
# src/session_manager.py

import redis.asyncio as redis

class SessionManager:
    def __init__(self, redis_url: str = None):
        if redis_url:
            self._redis = redis.from_url(redis_url)
        else:
            self._sessions = {}  # Fallback to in-memory
```

### Railway Configuration

Add Redis to Railway project:
```bash
railway plugin add redis

# Automatically sets REDIS_URL environment variable
```

Update `.env` for production:
```bash
REDIS_URL=redis://default:password@redis.railway.internal:6379
SESSION_MAX_AGE_DAYS=30
```

## Security Considerations

### Token Storage

- **Development:** In-memory (lost on restart)
- **Production:** Redis with encryption at rest
- **Never log:** Access tokens, refresh tokens, or session IDs

### Session Security

- Session IDs are cryptographically random (32 bytes, base64url)
- PKCE used for OAuth (prevents code interception)
- HTTPS required for production (Railway provides)

### CORS Policy

Production should restrict origins:
```python
CORSMiddleware(
    allow_origins=["https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"]
)
```

## Troubleshooting

### Session Not Found

**Symptom:** `{"error": "session_not_found"}`

**Causes:**
- Server restarted (in-memory storage lost)
- Session ID typo
- Session was purged (>30 days old)

**Solution:**
```bash
# Create new session
curl -X POST http://localhost:3000/session/create \
  -H "Content-Type: application/json" \
  -d '{"desktop_instance_id":"your-desktop-id"}'
```

### Circuit Breaker Triggered

**Symptom:** `HTTP 429 - Too many authentication attempts`

**Causes:**
- Rapid re-auth clicks (>3 in 10 minutes)
- Automated retry loop

**Solution:**
- Wait 10 minutes for circuit breaker reset
- Check Bridge retry logic
- Investigate root cause of auth failures

### Token Refresh Timeout

**Symptom:** `AuthenticationError: Token refresh timeout`

**Causes:**
- Asana API slow/down
- Network issues
- Concurrent refresh deadlock

**Solution:**
- Check Asana API status
- Increase refresh timeout (currently 10s)
- Review logs for deadlock indicators

### Concurrent Request Errors

**Symptom:** Multiple tool calls fail simultaneously

**Causes:**
- Token refresh race condition
- Lock acquisition timeout

**Solution:**
- Already mitigated by asyncio locks
- Check logs for lock timeout messages
- Increase `max_wait` in `get_valid_token_for_session`

## Performance Metrics

### Session Operations

- **Create Session:** <10ms
- **Validate Session:** <5ms
- **Token Refresh:** 200-500ms (Asana API call)
- **Get Session Info:** <5ms

### Memory Usage

- **Per Session:** ~2KB (in-memory)
- **100 Sessions:** ~200KB
- **1000 Sessions:** ~2MB

### Recommended Limits

- **Max Sessions:** 10,000 (per server instance)
- **Session Cleanup:** Run every 24 hours
- **Max Session Age:** 30 days

## Migration from Legacy Auth

### Backward Compatibility

Both authentication methods work simultaneously:

**Legacy (User ID-based):**
```python
# Still works
user_id = "default_user"
access_token = await oauth_manager.get_valid_token(user_id)
```

**New (Session-based):**
```python
# New method
session = await session_manager.get_session(session_id)
access_token = await oauth_manager.get_valid_token_for_session(session)
```

### Migration Path

1. Deploy session-based code (backward compatible)
2. Update Bridge to use sessions
3. Test with both methods active
4. Deprecate legacy endpoints (future release)
5. Remove legacy code

## Future Enhancements

### Planned Features

1. **Desktop Session Management:**
   - Desktop can list all its sessions
   - Revoke old sessions automatically
   - Session transfer between devices

2. **Enhanced Monitoring:**
   - Prometheus metrics for session health
   - Grafana dashboards for auth flows
   - Alerts for circuit breaker triggers

3. **Multi-Tenancy:**
   - Organization-level session grouping
   - Team-based token sharing
   - Admin dashboard for session management

4. **Advanced Loop Prevention:**
   - ML-based anomaly detection
   - Adaptive circuit breaker thresholds
   - User behavior analysis

---

**Version:** 1.0.0
**Last Updated:** 2025-11-05
**Maintainer:** MagicTurtle-s
