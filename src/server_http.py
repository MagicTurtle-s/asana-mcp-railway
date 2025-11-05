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
from .tools.tasks import TASK_TOOLS
from .tools.projects import PROJECT_TOOLS
from .tools.relationships import RELATIONSHIP_TOOLS
from .tools.organization import ORGANIZATION_TOOLS

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

# Tool registry
ALL_TOOLS = TASK_TOOLS + PROJECT_TOOLS + RELATIONSHIP_TOOLS + ORGANIZATION_TOOLS


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

    For now, we'll use a default user. In production, this should
    extract user_id from the request context.
    """
    # TODO: Extract user_id from request context
    # For development, use a default user_id
    user_id = arguments.get("user_id", "default_user")

    try:
        # Find the tool
        tool_def = next((t for t in ALL_TOOLS if t["name"] == name), None)
        if not tool_def:
            return [TextContent(
                type="text",
                text=f"❌ Unknown tool: {name}"
            )]

        # Get authenticated client
        client = await get_asana_client_for_user(user_id)

        # Call the tool handler
        handler = tool_def["handler"]
        result = await handler(client, arguments)

        # Close client
        await client.close()

        return [TextContent(type="text", text=result)]

    except AuthenticationError as e:
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

    Redirects user to Asana authorization page.
    """
    oauth_manager = get_oauth_manager()

    # Generate authorization URL
    auth_url, state = oauth_manager.get_authorization_url()

    # Store state in session (for production, use proper session management)
    # For now, we'll include it in the redirect

    logger.info(f"Starting OAuth flow with state: {state}")

    return RedirectResponse(url=auth_url)


async def oauth_callback(request: Request) -> Response:
    """
    Handle OAuth callback from Asana.

    Exchanges authorization code for tokens and stores them.
    """
    oauth_manager = get_oauth_manager()

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

        # Store tokens for user
        user_id = tokens.user_gid or "default_user"
        oauth_manager.store_tokens(user_id, tokens)

        logger.info(f"OAuth successful for user: {tokens.user_name} ({user_id})")

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

    For development. In production, check specific user.
    """
    oauth_manager = get_oauth_manager()

    # Check default user
    user_id = "default_user"
    is_authenticated = oauth_manager.is_authenticated(user_id)

    if is_authenticated:
        user_info = oauth_manager.get_user_info(user_id)
        return JSONResponse({
            "authenticated": True,
            "user": user_info
        })
    else:
        return JSONResponse({
            "authenticated": False,
            "message": "Not authenticated. Visit /oauth/start to authenticate."
        })


# Create Starlette app
app = Starlette(
    debug=os.getenv("NODE_ENV") != "production",
    routes=[
        Route("/health", health_check, methods=["GET"]),
        Route("/oauth/start", oauth_start, methods=["GET"]),
        Route("/oauth/callback", oauth_callback, methods=["GET"]),
        Route("/oauth/status", oauth_status, methods=["GET"]),
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
