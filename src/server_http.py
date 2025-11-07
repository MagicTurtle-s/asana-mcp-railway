"""
Asana MCP HTTP Server

Main server implementation with HTTP/SSE transport and OAuth routes.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlencode

from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
import uvicorn

# MCP imports - using mcp package
from mcp.server import Server
from mcp.types import Tool, TextContent

# Our modules
from .oauth import initialize_oauth_manager, get_oauth_manager, AuthenticationError
from .asana_client import AsanaClient, RateLimiter
from .session_manager import initialize_session_manager, get_session_manager, SessionState
from .tools import ALL_TOOLS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global MCP server
mcp_server = Server("asana-mcp")

# Global rate limiter
rate_limiter = RateLimiter(max_requests=150)  # Free tier default

# Tool registry imported from src.tools
# ALL_TOOLS now includes all 42 tools (Phase 1 + Phase 2)


# Helper function to get Asana client for a user
async def get_asana_client_for_user(user_id: str) -> AsanaClient:
    """
    Get an authenticated Asana client for a user.

    Args:
        user_id: User identifier

    Returns:
        Authenticated AsanaClient

    Raises:
        AuthenticationError: If user not authenticated
    """
    oauth_manager = get_oauth_manager()
    access_token = await oauth_manager.get_valid_token(user_id)
    return AsanaClient(access_token, rate_limiter=rate_limiter)

# Helper function to get Asana client for a session
async def get_asana_client_for_session(session_id: str) -> AsanaClient:
    """
    Get an authenticated Asana client for a session.

    Args:
        session_id: Session identifier

    Returns:
        Authenticated AsanaClient

    Raises:
        AuthenticationError: If session not authenticated or token refresh fails
    """
    session_manager = get_session_manager()
    oauth_manager = get_oauth_manager()

    # Get session
    session = await session_manager.get_session(session_id)
    if not session:
        raise AuthenticationError(f"Session {session_id} not found")

    # Validate session
    is_valid, error_msg = await session_manager.validate_session(session_id)
    if not is_valid:
        raise AuthenticationError(f"Session invalid: {error_msg}")

    # Get valid token (with automatic refresh if needed)
    access_token = await oauth_manager.get_valid_token_for_session(session)

    return AsanaClient(access_token, rate_limiter=rate_limiter)



# MCP Tool Registration
@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available MCP tools"""
    return [
        Tool(
            name=tool["name"],
            description=tool["description"],
            inputSchema=tool["inputSchema"]
        )
        for tool in ALL_TOOLS
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    """
    Handle tool calls from MCP clients.

    Supports both session-based (with session_id) and legacy (with user_id) authentication.
    """
    # Check for session_id (preferred) or user_id (legacy)
    session_id = arguments.get("session_id")
    user_id = arguments.get("user_id", "default_user")

    try:
        # Find the tool
        tool_def = next((t for t in ALL_TOOLS if t["name"] == name), None)
        if not tool_def:
            return [TextContent(
                type="text",
                text=f"❌ Unknown tool: {name}"
            )]

        # Get authenticated client (session-based or legacy)
        if session_id:
            client = await get_asana_client_for_session(session_id)
        else:
            client = await get_asana_client_for_user(user_id)

        # Call the tool handler
        handler = tool_def["handler"]
        result = await handler(client, arguments)

        # Close client
        await client.close()

        return [TextContent(type="text", text=result)]

    except AuthenticationError as e:
        if session_id:
            return [TextContent(
                type="text",
                text=f"🔒 Authentication required: {str(e)}\n\nSession {session_id[:8]}... needs re-authentication.\nVisit /oauth/start?session={session_id} to re-authenticate."
            )]
        else:
            return [TextContent(
                type="text",
                text=f"🔒 Authentication required: {str(e)}\n\nPlease visit /oauth/start to authenticate."
            )]
    except Exception as e:
        logger.error(f"Error calling tool {name}: {str(e)}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"❌ Error executing {name}: {str(e)}"
        )]


# HTTP Routes

async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint"""
    oauth_manager = get_oauth_manager()

    return JSONResponse({
        "status": "ok",
        "service": "asana-mcp",
        "version": "0.1.0",
        "rate_limiter": {
            "max_requests_per_minute": rate_limiter.max_requests,
            "remaining": rate_limiter.get_remaining()
        }
    })


async def oauth_start(request: Request) -> Response:
    """
    Start OAuth authorization flow.

    Supports both session-based (with ?session=xxx) and legacy flows.
    Redirects user to Asana authorization page.
    """
    oauth_manager = get_oauth_manager()
    session_manager = get_session_manager()

    # Check if session_id is provided (session-based flow)
    session_id = request.query_params.get("session")

    if session_id:
        # Session-based flow
        session = await session_manager.get_session(session_id)
        if not session:
            return JSONResponse({
                "error": "invalid_session",
                "description": "Session not found"
            }, status_code=404)

        # Check circuit breaker
        if not session.should_allow_reauth():
            return JSONResponse({
                "error": "rate_limited",
                "description": "Too many authentication attempts. Please wait before trying again.",
                "retry_after": 600  # 10 minutes
            }, status_code=429)

        # Record re-auth attempt
        session.record_reauth_attempt()

        # Generate authorization URL with session_id as state
        auth_url, state = oauth_manager.get_authorization_url(session_id=session_id)
        logger.info(f"Starting OAuth flow for session {session_id[:8]}... (attempt #{session.re_auth_attempts.count if session.re_auth_attempts else 1})")

    else:
        # Legacy flow (backward compatibility)
        auth_url, state = oauth_manager.get_authorization_url()
        logger.info(f"Starting OAuth flow with state: {state[:8]}... (legacy)")

    return RedirectResponse(url=auth_url)


async def oauth_callback(request: Request) -> Response:
    """
    Handle OAuth callback from Asana.

    Exchanges authorization code for tokens and stores them.
    Supports both session-based and legacy flows.
    """
    oauth_manager = get_oauth_manager()
    session_manager = get_session_manager()

    # Get authorization code and state from query params
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        logger.error(f"OAuth error: {error}")
        return JSONResponse({
            "error": error,
            "description": request.query_params.get("error_description", "Unknown error")
        }, status_code=400)

    if not code or not state:
        return JSONResponse({
            "error": "missing_parameters",
            "description": "Missing code or state parameter"
        }, status_code=400)

    try:
        # Exchange code for tokens
        tokens = await oauth_manager.exchange_code_for_tokens(code, state)

        # Check if state is a session_id (session-based flow)
        session = await session_manager.get_session(state)

        if session:
            # Session-based flow
            success = await session_manager.store_session(
                session_id=state,
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                expires_in=tokens.expires_in,
                user_gid=tokens.user_gid,
                user_name=tokens.user_name,
                user_email=tokens.user_email
            )

            if success:
                logger.info(f"OAuth successful for session {state[:8]}...: {tokens.user_name} ({tokens.user_gid})")
                return JSONResponse({
                    "status": "success",
                    "message": "Authentication successful! You can close this window.",
                    "session_id": state,
                    "user": {
                        "gid": tokens.user_gid,
                        "name": tokens.user_name,
                        "email": tokens.user_email
                    }
                })
            else:
                return JSONResponse({
                    "error": "session_storage_failed",
                    "description": "Failed to store session data"
                }, status_code=500)

        else:
            # Legacy flow (backward compatibility)
            user_id = tokens.user_gid or "default_user"
            oauth_manager.store_tokens(user_id, tokens)

            logger.info(f"OAuth successful for user: {tokens.user_name} ({user_id}) [legacy]")

            return JSONResponse({
                "status": "success",
                "message": "Authentication successful!",
                "user": {
                    "gid": tokens.user_gid,
                    "name": tokens.user_name,
                    "email": tokens.user_email
                }
            })

    except AuthenticationError as e:
        logger.error(f"OAuth callback error: {str(e)}")
        return JSONResponse({
            "error": "authentication_failed",
            "description": str(e)
        }, status_code=401)


async def oauth_status(request: Request) -> JSONResponse:
    """
    Check OAuth authentication status.

    Supports both session-based (with ?session=xxx) and legacy flows.
    """
    session_manager = get_session_manager()
    oauth_manager = get_oauth_manager()

    # Check if session_id is provided
    session_id = request.query_params.get("session")

    if session_id:
        # Session-based flow
        session = await session_manager.get_session(session_id)
        if not session:
            return JSONResponse({
                "authenticated": False,
                "error": "session_not_found",
                "message": "Session not found"
            }, status_code=404)

        # Validate session
        is_valid, error_msg = await session_manager.validate_session(session_id)

        if is_valid:
            return JSONResponse({
                "authenticated": True,
                "session_id": session_id,
                "state": session.state.value,
                "user": {
                    "gid": session.user_gid,
                    "name": session.user_name,
                    "email": session.user_email
                },
                "token_expired": session.is_token_expired(),
                "needs_refresh": session.needs_refresh()
            })
        else:
            return JSONResponse({
                "authenticated": False,
                "session_id": session_id,
                "state": session.state.value,
                "error": error_msg,
                "message": f"Session invalid: {error_msg}. Visit /oauth/start?session={session_id} to re-authenticate."
            })

    else:
        # Legacy flow
        user_id = "default_user"
        is_authenticated = oauth_manager.is_authenticated(user_id)

        if is_authenticated:
            user_info = oauth_manager.get_user_info(user_id)
            return JSONResponse({
                "authenticated": True,
                "user": user_info,
                "legacy": True
            })
        else:
            return JSONResponse({
                "authenticated": False,
                "message": "Not authenticated. Visit /oauth/start to authenticate.",
                "legacy": True
            })


async def session_create(request: Request) -> JSONResponse:
    """
    Create a new session for a Desktop instance.

    POST /session/create
    Body: {"desktop_instance_id": "unique-desktop-id"}
    """
    session_manager = get_session_manager()

    try:
        data = await request.json()
        desktop_instance_id = data.get("desktop_instance_id")

        if not desktop_instance_id:
            return JSONResponse({
                "error": "missing_parameter",
                "description": "desktop_instance_id is required"
            }, status_code=400)

        # Create session
        session_id = await session_manager.create_session(desktop_instance_id)

        logger.info(f"Created session {session_id[:8]}... for Desktop {desktop_instance_id}")

        return JSONResponse({
            "status": "success",
            "session_id": session_id,
            "desktop_instance_id": desktop_instance_id,
            "oauth_url": f"/oauth/start?session={session_id}",
            "message": "Session created. User should visit oauth_url to authenticate."
        })

    except Exception as e:
        logger.error(f"Session creation error: {str(e)}")
        return JSONResponse({
            "error": "session_creation_failed",
            "description": str(e)
        }, status_code=500)


async def session_validate(request: Request) -> JSONResponse:
    """
    Validate that a session is active and ready for API calls.

    POST /session/validate
    Body: {"session_id": "session-id"}
    """
    session_manager = get_session_manager()

    try:
        data = await request.json()
        session_id = data.get("session_id")

        if not session_id:
            return JSONResponse({
                "error": "missing_parameter",
                "description": "session_id is required"
            }, status_code=400)

        # Validate session
        is_valid, error_msg = await session_manager.validate_session(session_id)

        if is_valid:
            session = await session_manager.get_session(session_id)
            return JSONResponse({
                "valid": True,
                "session_id": session_id,
                "user": {
                    "gid": session.user_gid,
                    "name": session.user_name,
                    "email": session.user_email
                }
            })
        else:
            return JSONResponse({
                "valid": False,
                "session_id": session_id,
                "error": error_msg,
                "requires_auth": True,
                "oauth_url": f"/oauth/start?session={session_id}"
            })

    except Exception as e:
        logger.error(f"Session validation error: {str(e)}")
        return JSONResponse({
            "error": "validation_failed",
            "description": str(e)
        }, status_code=500)


async def session_revoke(request: Request) -> JSONResponse:
    """
    Revoke a session explicitly.

    POST /session/revoke
    Body: {"session_id": "session-id"}
    """
    session_manager = get_session_manager()

    try:
        data = await request.json()
        session_id = data.get("session_id")

        if not session_id:
            return JSONResponse({
                "error": "missing_parameter",
                "description": "session_id is required"
            }, status_code=400)

        # Revoke session
        success = await session_manager.revoke_session(session_id)

        if success:
            logger.info(f"Revoked session {session_id[:8]}...")
            return JSONResponse({
                "status": "success",
                "message": "Session revoked successfully"
            })
        else:
            return JSONResponse({
                "error": "session_not_found",
                "description": "Session not found"
            }, status_code=404)

    except Exception as e:
        logger.error(f"Session revocation error: {str(e)}")
        return JSONResponse({
            "error": "revocation_failed",
            "description": str(e)
        }, status_code=500)


async def session_info(request: Request) -> JSONResponse:
    """
    Get detailed session information (for debugging/monitoring).

    GET /session/info?session={id}
    """
    session_manager = get_session_manager()
    session_id = request.query_params.get("session")

    if not session_id:
        # Return all sessions
        all_sessions = session_manager.get_all_sessions()
        return JSONResponse({
            "sessions": all_sessions,
            "count": len(all_sessions)
        })

    # Return specific session
    session_info_data = session_manager.get_session_info(session_id)

    if session_info_data:
        return JSONResponse(session_info_data)
    else:
        return JSONResponse({
            "error": "session_not_found",
            "description": "Session not found"
        }, status_code=404)


# Create Starlette app
app = Starlette(
    debug=os.getenv("NODE_ENV") != "production",
    routes=[
        Route("/health", health_check, methods=["GET"]),
        Route("/oauth/start", oauth_start, methods=["GET"]),
        Route("/oauth/callback", oauth_callback, methods=["GET"]),
        Route("/oauth/status", oauth_status, methods=["GET"]),
        Route("/session/create", session_create, methods=["POST"]),
        Route("/session/validate", session_validate, methods=["POST"]),
        Route("/session/revoke", session_revoke, methods=["POST"]),
        Route("/session/info", session_info, methods=["GET"]),
        # MCP endpoint will be added via SSE transport
    ],
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],  # In production, restrict this
            allow_methods=["*"],
            allow_headers=["*"],
            allow_credentials=True
        )
    ]
)


# Main entry point
def main():
    """Start the HTTP server"""
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Get configuration
    client_id = os.getenv("ASANA_CLIENT_ID")
    client_secret = os.getenv("ASANA_CLIENT_SECRET")
    redirect_uri = os.getenv("ASANA_REDIRECT_URI")
    port = int(os.getenv("PORT", "3000"))
    host = os.getenv("HOST", "0.0.0.0")

    # Validate configuration
    if not all([client_id, client_secret, redirect_uri]):
        logger.error("Missing required environment variables:")
        if not client_id:
            logger.error("  - ASANA_CLIENT_ID")
        if not client_secret:
            logger.error("  - ASANA_CLIENT_SECRET")
        if not redirect_uri:
            logger.error("  - ASANA_REDIRECT_URI")
        logger.error("\nPlease set these variables in your .env file")
        return

    # Initialize OAuth manager
    initialize_oauth_manager(client_id, client_secret, redirect_uri)
    logger.info("OAuth manager initialized")

    # Initialize session manager
    initialize_session_manager()
    logger.info("Session manager initialized")

    # Log startup info
    logger.info(f"Starting Asana MCP Server")
    logger.info(f"  OAuth Redirect URI: {redirect_uri}")
    logger.info(f"  Server: http://{host}:{port}")
    logger.info(f"  Health check: http://{host}:{port}/health")
    logger.info(f"  OAuth start: http://{host}:{port}/oauth/start")
    logger.info(f"  MCP endpoint: http://{host}:{port}/mcp")
    logger.info(f"  Total tools: {len(ALL_TOOLS)}")

    # Note about MCP transport
    logger.info("\nNote: Full MCP SSE transport implementation requires additional setup.")
    logger.info("For now, the server provides OAuth and tool implementations.")
    logger.info("MCP transport will be added in the next update.")

    # Start server
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
