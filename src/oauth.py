"""
Asana OAuth 2.0 Manager

Handles the OAuth authorization code grant flow with PKCE for secure authentication.
Manages access and refresh tokens with automatic renewal.
"""

import os
import time
import secrets
import hashlib
import base64
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode
import httpx
from pydantic import BaseModel


class TokenData(BaseModel):
    """OAuth token data"""
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    user_gid: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None


class AuthenticationError(Exception):
    """Raised when authentication fails"""
    pass


class AsanaOAuthManager:
    """
    Manages OAuth 2.0 flow for Asana API authentication.

    Implements Authorization Code Grant with PKCE for enhanced security.
    Handles token storage, refresh, and validation.
    """

    # Asana OAuth endpoints
    AUTH_URL = "https://app.asana.com/-/oauth_authorize"
    TOKEN_URL = "https://app.asana.com/-/oauth_token"
    REVOKE_URL = "https://app.asana.com/-/oauth_revoke"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str
    ):
        """
        Initialize OAuth manager.

        Args:
            client_id: Asana OAuth app client ID
            client_secret: Asana OAuth app client secret
            redirect_uri: OAuth callback URL (must match app registration)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

        # Token cache: user_id -> token data
        self._token_cache: Dict[str, Dict] = {}

        # PKCE verifier cache: state -> verifier
        self._verifier_cache: Dict[str, str] = {}

        # HTTP client for token requests
        self._http_client = httpx.AsyncClient(timeout=30.0)

    def generate_pkce_pair(self) -> Tuple[str, str]:
        """
        Generate PKCE code verifier and challenge.

        Returns:
            Tuple of (verifier, challenge)
        """
        # Generate verifier (43-128 characters)
        verifier = secrets.token_urlsafe(32)

        # Generate challenge (SHA256 hash of verifier)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).decode().rstrip('=')

        return verifier, challenge

    def get_authorization_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        """
        Generate OAuth authorization URL with PKCE.

        Args:
            state: CSRF protection token (generated if not provided)

        Returns:
            Tuple of (authorization_url, state)
        """
        if not state:
            state = secrets.token_urlsafe(32)

        # Generate PKCE pair
        verifier, challenge = self.generate_pkce_pair()

        # Store verifier for later use in token exchange
        self._verifier_cache[state] = verifier

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256"
        }

        auth_url = f"{self.AUTH_URL}?{urlencode(params)}"
        return auth_url, state

    async def exchange_code_for_tokens(
        self,
        code: str,
        state: str
    ) -> TokenData:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from callback
            state: State parameter for PKCE verifier lookup

        Returns:
            TokenData with access token, refresh token, and user info

        Raises:
            AuthenticationError: If token exchange fails
        """
        # Retrieve PKCE verifier
        verifier = self._verifier_cache.pop(state, None)
        if not verifier:
            raise AuthenticationError("Invalid state parameter or PKCE verifier not found")

        # Prepare token request
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
            "code_verifier": verifier
        }

        try:
            response = await self._http_client.post(
                self.TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()

            token_response = response.json()

            # Extract user info from response
            user_data = token_response.get("data", {})

            return TokenData(
                access_token=token_response["access_token"],
                refresh_token=token_response["refresh_token"],
                expires_in=token_response["expires_in"],
                token_type=token_response.get("token_type", "bearer"),
                user_gid=user_data.get("gid"),
                user_name=user_data.get("name"),
                user_email=user_data.get("email")
            )

        except httpx.HTTPStatusError as e:
            error_data = e.response.json() if e.response.content else {}
            error_msg = error_data.get("error_description", str(e))
            raise AuthenticationError(f"Token exchange failed: {error_msg}")
        except Exception as e:
            raise AuthenticationError(f"Token exchange failed: {str(e)}")

    async def refresh_access_token(self, refresh_token: str) -> TokenData:
        """
        Refresh an expired access token.

        Args:
            refresh_token: Current refresh token

        Returns:
            TokenData with new access token and refresh token

        Raises:
            AuthenticationError: If token refresh fails
        """
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token
        }

        try:
            response = await self._http_client.post(
                self.TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()

            token_response = response.json()

            # Extract user info if present
            user_data = token_response.get("data", {})

            return TokenData(
                access_token=token_response["access_token"],
                refresh_token=token_response.get("refresh_token", refresh_token),
                expires_in=token_response["expires_in"],
                token_type=token_response.get("token_type", "bearer"),
                user_gid=user_data.get("gid"),
                user_name=user_data.get("name"),
                user_email=user_data.get("email")
            )

        except httpx.HTTPStatusError as e:
            error_data = e.response.json() if e.response.content else {}
            error_msg = error_data.get("error_description", str(e))
            raise AuthenticationError(f"Token refresh failed: {error_msg}")
        except Exception as e:
            raise AuthenticationError(f"Token refresh failed: {str(e)}")

    async def revoke_token(self, token: str):
        """
        Revoke an access or refresh token.

        Args:
            token: Token to revoke
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "token": token
        }

        try:
            await self._http_client.post(
                self.REVOKE_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
        except Exception:
            # Revocation failure is not critical
            pass

    def store_tokens(self, user_id: str, tokens: TokenData):
        """
        Store tokens for a user.

        Args:
            user_id: User identifier (typically user_gid)
            tokens: Token data to store
        """
        self._token_cache[user_id] = {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_at": time.time() + tokens.expires_in,
            "user_gid": tokens.user_gid,
            "user_name": tokens.user_name,
            "user_email": tokens.user_email
        }

    async def get_valid_token(self, user_id: str) -> str:
        """
        Get a valid access token for a user, refreshing if necessary.

        Args:
            user_id: User identifier

        Returns:
            Valid access token

        Raises:
            AuthenticationError: If user not authenticated or refresh fails
        """
        cached = self._token_cache.get(user_id)
        if not cached:
            raise AuthenticationError("User not authenticated")

        # Check if token is expired (with 5-minute buffer)
        now = time.time()
        if now >= cached["expires_at"] - 300:
            # Token expired or expiring soon, refresh it
            new_tokens = await self.refresh_access_token(cached["refresh_token"])
            self.store_tokens(user_id, new_tokens)
            return new_tokens.access_token

        return cached["access_token"]

    def get_user_info(self, user_id: str) -> Optional[Dict[str, str]]:
        """
        Get stored user information.

        Args:
            user_id: User identifier

        Returns:
            Dict with user_gid, user_name, user_email or None
        """
        cached = self._token_cache.get(user_id)
        if not cached:
            return None

        return {
            "user_gid": cached.get("user_gid"),
            "user_name": cached.get("user_name"),
            "user_email": cached.get("user_email")
        }

    def is_authenticated(self, user_id: str) -> bool:
        """
        Check if user is authenticated.

        Args:
            user_id: User identifier

        Returns:
            True if user has valid tokens
        """
        return user_id in self._token_cache

    async def logout(self, user_id: str):
        """
        Log out a user and revoke their tokens.

        Args:
            user_id: User identifier
        """
        cached = self._token_cache.get(user_id)
        if cached:
            # Revoke tokens
            await self.revoke_token(cached["access_token"])
            await self.revoke_token(cached["refresh_token"])

            # Remove from cache
            del self._token_cache[user_id]

    async def cleanup_expired_verifiers(self):
        """
        Clean up expired PKCE verifiers (older than 10 minutes).
        Should be called periodically.
        """
        # For production, implement proper TTL with timestamps
        # This is a simple implementation for development
        pass

    async def close(self):
        """Close HTTP client"""
        await self._http_client.aclose()


# Global OAuth manager instance (initialized in server)
_oauth_manager: Optional[AsanaOAuthManager] = None


def get_oauth_manager() -> AsanaOAuthManager:
    """Get the global OAuth manager instance"""
    if _oauth_manager is None:
        raise RuntimeError("OAuth manager not initialized")
    return _oauth_manager


def initialize_oauth_manager(
    client_id: str,
    client_secret: str,
    redirect_uri: str
) -> AsanaOAuthManager:
    """
    Initialize the global OAuth manager.

    Args:
        client_id: Asana OAuth app client ID
        client_secret: Asana OAuth app client secret
        redirect_uri: OAuth callback URL

    Returns:
        Initialized OAuth manager
    """
    global _oauth_manager
    _oauth_manager = AsanaOAuthManager(client_id, client_secret, redirect_uri)
    return _oauth_manager
