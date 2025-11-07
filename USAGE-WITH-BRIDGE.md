# Using Asana MCP with Claude Code Bridge

This guide explains how to use the Asana MCP Railway server via Claude Code Bridge for seamless integration with Claude Desktop.

## Architecture

```
Claude Desktop
    ↓ (STDIO/MCP)
Claude Code Bridge
    ↓ (HTTP/Session-based)
Asana MCP Railway Server
    ↓ (OAuth 2.0)
Asana API
```

## Setup

### 1. Prerequisites

- ✅ Claude Desktop installed and configured
- ✅ Claude Code Bridge installed and running
- ✅ Asana MCP deployed to Railway (https://asana-mcp-railway-production.up.railway.app)

### 2. Create a Session

When using the Asana MCP for the first time, create a session:

```bash
curl -X POST https://asana-mcp-railway-production.up.railway.app/session/create \
  -H "Content-Type: application/json" \
  -d '{"desktop_instance_id": "claude-desktop-main"}'
```

Response:
```json
{
  "status": "success",
  "session_id": "abc123...",
  "oauth_url": "/oauth/start?session=abc123..."
}
```

### 3. Authenticate

Open the OAuth URL in your browser:
```
https://asana-mcp-railway-production.up.railway.app/oauth/start?session=abc123...
```

This will:
1. Redirect you to Asana authorization page
2. After approval, redirect back and store tokens
3. Show success message with your user info

### 4. Save Your Session ID

Store the session ID for future use. You'll need it for all API calls.

**Recommended**: Add to your Bridge environment variables:
```json
{
  "ASANA_SESSION_ID": "abc123..."
}
```

## Usage Examples

### Via Claude Desktop (through Bridge)

Ask Claude Desktop to delegate Asana tasks to Claude Code:

**Example 1: List Tasks**
```
Can you search for my open tasks in Asana?
```

The Bridge will:
1. Create a Claude Code session
2. Execute the task with Asana MCP tools
3. Include `session_id` in all Asana tool calls
4. Return results to Desktop

**Example 2: Create Task**
```
Create a new task in Asana called "Review PR #123"
in the Engineering project, due tomorrow
```

### Direct API Usage (Testing)

You can also test the API directly:

**Check Session Status:**
```bash
curl "https://asana-mcp-railway-production.up.railway.app/session/info?session=abc123..."
```

**List Workspaces:**
```bash
curl -X POST https://asana-mcp-railway-production.up.railway.app/tools/asana_list_workspaces \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc123..."}'
```

## Session Management

### Check if Token Needs Refresh

Sessions automatically refresh tokens when they expire (1-hour lifetime with 5-minute buffer).

```bash
curl "https://asana-mcp-railway-production.up.railway.app/session/info?session=abc123..."
```

Look for:
- `token_expired`: false (token is valid)
- `needs_refresh`: false (no refresh needed)
- `state`: "active" (session ready)

### Re-authenticate if Needed

If your session expires or tokens are revoked:

1. Check session status (will show `state: "expired"`)
2. Re-authenticate via OAuth URL:
   ```
   https://asana-mcp-railway-production.up.railway.app/oauth/start?session=abc123...
   ```
3. Circuit breaker limits: Max 3 re-auth attempts per 10 minutes

### Revoke Session

When done or to log out:

```bash
curl -X POST https://asana-mcp-railway-production.up.railway.app/session/revoke \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc123..."}'
```

## Available Tools

The Asana MCP provides **42 tools** with **full parity** to the official Asana MCP:

### Task Management (15 tools)
- `asana_list_workspaces` - List all accessible workspaces
- `asana_search_tasks` - Search tasks with advanced filters
- `asana_get_task` - Get detailed task information
- `asana_get_multiple_tasks_by_gid` - Batch fetch multiple tasks
- `asana_create_task` - Create a new task
- `asana_update_task` - Update existing task
- `asana_delete_task` - Delete a task permanently
- `asana_duplicate_task` - Duplicate task with properties
- `asana_get_task_stories` - Get task comments/activity
- `asana_create_task_story` - Add comment to task
- `asana_get_subtasks` - Get all subtasks of a task
- `asana_get_tasks_from_project` - Get all tasks in a project
- `asana_get_tasks_from_section` - Get all tasks in a section
- `asana_add_followers_to_task` - Add task followers
- `asana_remove_followers_from_task` - Remove task followers

### Project Management (10 tools)
- `asana_search_projects` - Search projects in workspace
- `asana_get_project` - Get project details
- `asana_create_project` - Create new project
- `asana_update_project` - Update project properties
- `asana_delete_project` - Delete a project
- `asana_duplicate_project` - Duplicate project with tasks
- `asana_get_project_task_counts` - Get task count statistics
- `asana_get_project_sections` - List project sections
- `asana_get_project_statuses` - Get project status updates
- `asana_create_project_status` - Create status update

### Section Management (5 tools)
- `asana_create_section` - Create section in project
- `asana_get_section` - Get section details
- `asana_update_section` - Update section name
- `asana_delete_section` - Delete a section
- `asana_add_task_to_section` - Move task to section

### Task Relationships (8 tools)
- `asana_add_task_dependencies` - Add blocking tasks
- `asana_add_task_dependents` - Add blocked tasks
- `asana_get_task_dependencies` - Get tasks this depends on
- `asana_get_task_dependents` - Get tasks depending on this
- `asana_remove_task_dependencies` - Remove dependencies
- `asana_remove_task_dependents` - Remove dependents
- `asana_create_subtask` - Create child task
- `asana_set_parent_for_task` - Convert to subtask

### Task Organization (4 tools)
- `asana_add_project_to_task` - Add task to project
- `asana_remove_project_from_task` - Remove from project
- `asana_add_tag_to_task` - Add tag to task
- `asana_remove_tag_from_task` - Remove tag from task

### Workspace & Tags (2 tools)
- `asana_get_tags_for_workspace` - List workspace tags
- `asana_get_tasks_for_tag` - Get tasks with specific tag

## Troubleshooting

### "Session not found" Error

**Cause**: Session ID invalid or expired
**Fix**: Create a new session (see Setup step 2)

### "Authentication required" Error

**Cause**: Session not authenticated or tokens expired
**Fix**: Visit OAuth URL to authenticate (see Setup step 3)

### "Too many authentication attempts" Error

**Cause**: Circuit breaker triggered (3+ attempts in 10 minutes)
**Fix**: Wait 10 minutes, then try again

### Token Already Expired on Creation

**Cause**: Clock skew or immediate validation
**Fix**: Check if tokens are actually expired via `/session/info`

## Rate Limiting

- **Free tier**: 150 requests/minute
- **Premium**: 1,500 requests/minute
- Rate limiter tracks requests per session
- Automatic backoff if limits exceeded

## Security Notes

- Sessions are Desktop-scoped (one per Desktop instance)
- Tokens stored in-memory on server (not persisted)
- OAuth 2.0 with PKCE for secure authentication
- All requests over HTTPS
- Session IDs are cryptographically secure (32-byte random tokens)

## Bridge Integration Details

When Claude Code Bridge delegates Asana tasks:

1. **Session Injection**: Bridge adds `session_id` to all tool arguments
2. **Error Handling**: Bridge detects auth failures and can trigger re-auth
3. **Retry Logic**: One retry per tool call after re-authentication
4. **Session Caching**: Bridge can cache session ID for efficiency

## Production Deployment Info

- **Endpoint**: https://asana-mcp-railway-production.up.railway.app
- **Health Check**: `/health` endpoint for monitoring
- **Session Info**: `/session/info` for debugging
- **OAuth Callback**: `/oauth/callback` (configured in Asana OAuth app)

## Support

For issues or questions:
- Check Railway logs for server-side errors
- Use `/session/info` endpoint for session debugging
- Review SESSION-AUTH.md for architecture details
- Check .claude/context.md for implementation notes
