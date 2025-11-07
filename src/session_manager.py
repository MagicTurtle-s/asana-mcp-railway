"""
Session Manager for Multi-User Authentication

Manages Desktop-scoped sessions with token storage, state machine,
concurrent request protection, and loop prevention mechanisms.
"""

import asyncio
import time
import secrets
from typing import Dict, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SessionState(str, Enum):
    """Session state machine"""
    PENDING = "pending"      # OAuth initiated, waiting for callback
    ACTIVE = "active"        # Authenticated and ready
    EXPIRED = "expired"      # Token expired, needs refresh
    REVOKED = "revoked"      # Explicitly revoked by user
    PURGED = "purged"        # Auto-cleaned after 30 days


@dataclass
class ReAuthAttempt:
    """Track re-authentication attempts for circuit breaker"""
    timestamp: float
    count: int = 1

    def increment(self):
        self.count += 1
        self.timestamp = time.time()

    def should_allow(self, max_attempts: int = 3, window_seconds: int = 600) -> bool:
        """Check if re-auth should be allowed based on circuit breaker"""
        age = time.time() - self.timestamp
        if age > window_seconds:
            # Reset counter if outside window
            self.count = 0
            return True
        return self.count < max_attempts


@dataclass
class Session:
    """Session data structure"""
    session_id: str
    desktop_instance_id: str
    state: SessionState
    created_at: float
    last_used_at: float

    # Token data
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[float] = None

    # User info
    user_gid: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    # Concurrent request protection
    refresh_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    is_refreshing: bool = False

    # Loop prevention
    re_auth_attempts: Optional[ReAuthAttempt] = None
    retry_count: int = 0

    def update_tokens(self, access_token: str, refresh_token: str, expires_in: int):
        """Update session tokens"""
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expires_at = time.time() + expires_in
        self.state = SessionState.ACTIVE
        self.last_used_at = time.time()

    def update_user_info(self, user_gid: str, user_name: str, user_email: str):
        """Update user information"""
        self.user_gid = user_gid
        self.user_name = user_name
        self.user_email = user_email

    def is_token_expired(self) -> bool:
        """Check if token is expired (with 5-minute buffer)"""
        if not self.token_expires_at:
            return True
        return time.time() >= (self.token_expires_at - 300)  # 5-minute buffer

    def needs_refresh(self) -> bool:
        """Check if token needs refresh"""
        return self.is_token_expired() and self.refresh_token is not None

    def should_allow_reauth(self) -> bool:
        """Check if re-authentication should be allowed (circuit breaker)"""
        if not self.re_auth_attempts:
            self.re_auth_attempts = ReAuthAttempt(timestamp=time.time(), count=0)
            return True
        return self.re_auth_attempts.should_allow()

    def record_reauth_attempt(self):
        """Record a re-authentication attempt"""
        if not self.re_auth_attempts:
            self.re_auth_attempts = ReAuthAttempt(timestamp=time.time())
        else:
            self.re_auth_attempts.increment()

    def reset_retry_count(self):
        """Reset retry count after successful authentication"""
        self.retry_count = 0

    def increment_retry_count(self) -> bool:
        """
        Increment retry count and check if max retries exceeded.

        Returns:
            True if retry allowed, False if max retries exceeded
        """
        self.retry_count += 1
        return self.retry_count <= 1  # Only allow 1 retry


class SessionManager:
    """
    Manages Desktop-scoped sessions for multi-user authentication.

    Features:
    - Session lifecycle management
    - Concurrent request protection
    - Circuit breakers for re-auth
    - State machine for session status
    - Automatic cleanup of old sessions
    """

    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._desktop_sessions: Dict[str, str] = {}  # desktop_id -> session_id
        self._lock = asyncio.Lock()

    def generate_session_id(self) -> str:
        """Generate a unique session ID"""
        return secrets.token_urlsafe(32)

    async def create_session(self, desktop_instance_id: str) -> str:
        """
        Create a new session for a Desktop instance.

        Args:
            desktop_instance_id: Unique identifier for Desktop instance

        Returns:
            session_id: Unique session identifier
        """
        async with self._lock:
            # Check if Desktop already has a session
            if desktop_instance_id in self._desktop_sessions:
                old_session_id = self._desktop_sessions[desktop_instance_id]
                # Revoke old session
                if old_session_id in self._sessions:
                    self._sessions[old_session_id].state = SessionState.REVOKED
                    logger.info(f"Revoked old session {old_session_id} for Desktop {desktop_instance_id}")

            # Create new session
            session_id = self.generate_session_id()
            session = Session(
                session_id=session_id,
                desktop_instance_id=desktop_instance_id,
                state=SessionState.PENDING,
                created_at=time.time(),
                last_used_at=time.time()
            )

            self._sessions[session_id] = session
            self._desktop_sessions[desktop_instance_id] = session_id

            logger.info(f"Created session {session_id} for Desktop {desktop_instance_id}")
            return session_id

    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session object or None if not found
        """
        session = self._sessions.get(session_id)
        if session:
            session.last_used_at = time.time()
        return session

    async def store_session(
        self,
        session_id: str,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        user_gid: str,
        user_name: str,
        user_email: str
    ) -> bool:
        """
        Store authentication data in session.

        Args:
            session_id: Session identifier
            access_token: Asana access token
            refresh_token: Asana refresh token
            expires_in: Token expiry in seconds
            user_gid: User global ID
            user_name: User display name
            user_email: User email

        Returns:
            True if successful, False if session not found
        """
        session = await self.get_session(session_id)
        if not session:
            logger.error(f"Session {session_id} not found")
            return False

        session.update_tokens(access_token, refresh_token, expires_in)
        session.update_user_info(user_gid, user_name, user_email)
        session.reset_retry_count()

        logger.info(f"Stored tokens for session {session_id} (user: {user_name})")
        return True

    async def update_session(
        self,
        session_id: str,
        access_token: str,
        refresh_token: str,
        expires_in: int
    ) -> bool:
        """
        Update session tokens after refresh.

        Args:
            session_id: Session identifier
            access_token: New access token
            refresh_token: New refresh token
            expires_in: Token expiry in seconds

        Returns:
            True if successful, False if session not found
        """
        session = await self.get_session(session_id)
        if not session:
            logger.error(f"Session {session_id} not found")
            return False

        session.update_tokens(access_token, refresh_token, expires_in)
        logger.info(f"Updated tokens for session {session_id}")
        return True

    async def validate_session(self, session_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that a session is active and ready for API calls.

        Args:
            session_id: Session identifier

        Returns:
            (is_valid, error_message) tuple
        """
        session = await self.get_session(session_id)

        if not session:
            return False, "Session not found"

        if session.state == SessionState.REVOKED:
            return False, "Session has been revoked"

        if session.state == SessionState.PURGED:
            return False, "Session has been purged"

        if session.state == SessionState.PENDING:
            return False, "Session pending authentication"

        if not session.access_token:
            return False, "Session not authenticated"

        # Check if token needs refresh
        if session.needs_refresh():
            session.state = SessionState.EXPIRED
            return False, "Session token expired, refresh required"

        return True, None

    async def revoke_session(self, session_id: str) -> bool:
        """
        Revoke a session explicitly.

        Args:
            session_id: Session identifier

        Returns:
            True if successful, False if session not found
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        session.state = SessionState.REVOKED
        session.access_token = None
        session.refresh_token = None

        # Remove from desktop mapping
        if session.desktop_instance_id in self._desktop_sessions:
            del self._desktop_sessions[session.desktop_instance_id]

        logger.info(f"Revoked session {session_id}")
        return True

    async def get_or_create_session(self, desktop_instance_id: str) -> str:
        """
        Get existing session for Desktop or create a new one.

        Args:
            desktop_instance_id: Unique identifier for Desktop instance

        Returns:
            session_id: Session identifier
        """
        # Check if Desktop has an active session
        if desktop_instance_id in self._desktop_sessions:
            session_id = self._desktop_sessions[desktop_instance_id]
            session = await self.get_session(session_id)

            # If session is active or expired (can be refreshed), return it
            if session and session.state in [SessionState.ACTIVE, SessionState.EXPIRED]:
                return session_id

        # Create new session
        return await self.create_session(desktop_instance_id)

    async def cleanup_old_sessions(self, max_age_days: int = 30):
        """
        Clean up sessions older than max_age_days.

        Args:
            max_age_days: Maximum age in days before purging
        """
        async with self._lock:
            cutoff_time = time.time() - (max_age_days * 86400)
            purged_count = 0

            for session_id, session in list(self._sessions.items()):
                if session.last_used_at < cutoff_time:
                    session.state = SessionState.PURGED
                    session.access_token = None
                    session.refresh_token = None

                    # Remove from desktop mapping
                    if session.desktop_instance_id in self._desktop_sessions:
                        if self._desktop_sessions[session.desktop_instance_id] == session_id:
                            del self._desktop_sessions[session.desktop_instance_id]

                    # Remove from sessions
                    del self._sessions[session_id]
                    purged_count += 1

            if purged_count > 0:
                logger.info(f"Purged {purged_count} old sessions")

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session information for debugging/monitoring.

        Args:
            session_id: Session identifier

        Returns:
            Session info dictionary or None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "desktop_instance_id": session.desktop_instance_id,
            "state": session.state.value,
            "created_at": datetime.fromtimestamp(session.created_at).isoformat(),
            "last_used_at": datetime.fromtimestamp(session.last_used_at).isoformat(),
            "user": {
                "gid": session.user_gid,
                "name": session.user_name,
                "email": session.user_email
            } if session.user_gid else None,
            "token_expired": session.is_token_expired(),
            "needs_refresh": session.needs_refresh(),
            "retry_count": session.retry_count,
            "re_auth_attempts": session.re_auth_attempts.count if session.re_auth_attempts else 0
        }

    def get_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get info for all sessions (for monitoring)"""
        return {
            session_id: self.get_session_info(session_id)
            for session_id in self._sessions.keys()
        }


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def initialize_session_manager() -> SessionManager:
    """Initialize the global session manager"""
    global _session_manager
    _session_manager = SessionManager()
    logger.info("Session manager initialized")
    return _session_manager


def get_session_manager() -> SessionManager:
    """Get the global session manager instance"""
    if _session_manager is None:
        raise RuntimeError("Session manager not initialized. Call initialize_session_manager() first.")
    return _session_manager
