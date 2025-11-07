"""
Asana API Client

Wrapper around Asana REST API with rate limiting, pagination, and error handling.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
import httpx
from pydantic import BaseModel


class RateLimitError(Exception):
    """Raised when rate limit is exceeded"""
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class AsanaAPIError(Exception):
    """Raised when Asana API returns an error"""
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


class RateLimiter:
    """
    Rate limiter for Asana API requests.

    Asana limits:
    - Free: 150 requests/minute
    - Premium: 1,500 requests/minute
    """

    def __init__(self, max_requests: int = 150):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests per minute
        """
        self.max_requests = max_requests
        self.requests: List[float] = []
        self.lock = asyncio.Lock()

    async def acquire(self):
        """
        Wait if rate limit would be exceeded.
        Blocks until a request slot is available.
        """
        async with self.lock:
            now = time.time()

            # Remove requests older than 1 minute
            self.requests = [
                timestamp for timestamp in self.requests
                if now - timestamp < 60
            ]

            # Check if at limit
            if len(self.requests) >= self.max_requests:
                # Calculate wait time until oldest request ages out
                oldest = self.requests[0]
                wait_time = 60 - (now - oldest) + 0.1  # Small buffer

                if wait_time > 0:
                    await asyncio.sleep(wait_time)

                # Remove oldest request
                self.requests.pop(0)

            # Record this request
            self.requests.append(now)

    def get_remaining(self) -> int:
        """Get remaining requests in current minute"""
        now = time.time()
        recent = [t for t in self.requests if now - t < 60]
        return max(0, self.max_requests - len(recent))


class AsanaClient:
    """
    Async HTTP client for Asana API.

    Handles:
    - Authentication headers
    - Rate limiting
    - Pagination
    - Error handling
    - Retries
    """

    BASE_URL = "https://app.asana.com/api/1.0"

    def __init__(
        self,
        access_token: str,
        rate_limiter: Optional[RateLimiter] = None
    ):
        """
        Initialize Asana client.

        Args:
            access_token: OAuth access token
            rate_limiter: Optional rate limiter (default: 150 req/min)
        """
        self.access_token = access_token
        self.rate_limiter = rate_limiter or RateLimiter()

        # HTTP client with connection pooling
        self.http_client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            },
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100
            )
        )

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        retry_on_rate_limit: bool = True
    ) -> Dict[str, Any]:
        """
        Make an API request with rate limiting and error handling.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/workspaces")
            params: Query parameters
            data: Request body (for POST/PUT)
            retry_on_rate_limit: Retry automatically on 429

        Returns:
            API response data

        Raises:
            RateLimitError: If rate limited and retry disabled
            AsanaAPIError: If API returns an error
        """
        # Acquire rate limit slot
        await self.rate_limiter.acquire()

        try:
            response = await self.http_client.request(
                method,
                endpoint,
                params=params,
                json=data
            )

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))

                if retry_on_rate_limit:
                    # Wait and retry
                    await asyncio.sleep(retry_after)
                    return await self._make_request(
                        method, endpoint, params, data, retry_on_rate_limit=False
                    )
                else:
                    raise RateLimitError(
                        f"Rate limit exceeded. Retry after {retry_after}s",
                        retry_after=retry_after
                    )

            # Handle errors
            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                errors = error_data.get("errors", [])
                error_message = errors[0].get("message", response.text) if errors else response.text

                raise AsanaAPIError(
                    status_code=response.status_code,
                    message=error_message
                )

            # Parse response
            response_data = response.json()
            return response_data

        except httpx.TimeoutException as e:
            raise AsanaAPIError(status_code=408, message=f"Request timeout: {str(e)}")
        except httpx.NetworkError as e:
            raise AsanaAPIError(status_code=503, message=f"Network error: {str(e)}")

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make a GET request.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            API response data
        """
        return await self._make_request("GET", endpoint, params=params)

    async def post(
        self,
        endpoint: str,
        data: Dict,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make a POST request.

        Args:
            endpoint: API endpoint
            data: Request body
            params: Query parameters

        Returns:
            API response data
        """
        return await self._make_request("POST", endpoint, params=params, data=data)

    async def put(
        self,
        endpoint: str,
        data: Dict,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make a PUT request.

        Args:
            endpoint: API endpoint
            data: Request body
            params: Query parameters

        Returns:
            API response data
        """
        return await self._make_request("PUT", endpoint, params=params, data=data)

    async def delete(
        self,
        endpoint: str,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make a DELETE request.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            API response data
        """
        return await self._make_request("DELETE", endpoint, params=params)

    async def get_paginated(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        limit: int = 100,
        max_results: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch all pages of a paginated endpoint.

        Args:
            endpoint: API endpoint
            params: Query parameters
            limit: Results per page (max 100)
            max_results: Maximum total results to fetch

        Returns:
            List of all results across pages
        """
        params = params or {}
        params["limit"] = min(limit, 100)

        results = []
        offset = None

        while True:
            if offset:
                params["offset"] = offset

            response = await self.get(endpoint, params=params)
            data = response.get("data", [])
            results.extend(data)

            # Check limits
            if max_results and len(results) >= max_results:
                return results[:max_results]

            # Check for next page
            next_page = response.get("next_page")
            if not next_page:
                break

            offset = next_page.get("offset")
            if not offset:
                break

        return results

    # Convenience methods for common endpoints

    async def get_workspaces(self) -> List[Dict]:
        """List all workspaces"""
        response = await self.get("/workspaces")
        return response.get("data", [])

    async def get_workspace(self, workspace_gid: str, opt_fields: Optional[str] = None) -> Dict:
        """Get workspace by GID"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        response = await self.get(f"/workspaces/{workspace_gid}", params=params)
        return response.get("data", {})

    async def search_tasks(
        self,
        workspace_gid: str,
        params: Optional[Dict] = None
    ) -> List[Dict]:
        """Search tasks in a workspace"""
        endpoint = f"/workspaces/{workspace_gid}/tasks/search"
        return await self.get_paginated(endpoint, params=params)

    async def get_task(self, task_gid: str, opt_fields: Optional[str] = None) -> Dict:
        """Get task by GID"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        response = await self.get(f"/tasks/{task_gid}", params=params)
        return response.get("data", {})

    async def get_multiple_tasks(self, task_gids: List[str], opt_fields: Optional[str] = None) -> List[Dict]:
        """Get multiple tasks by GID (max 25)"""
        if len(task_gids) > 25:
            task_gids = task_gids[:25]

        params = {
            "task": ",".join(task_gids)
        }
        if opt_fields:
            params["opt_fields"] = opt_fields

        response = await self.get("/tasks", params=params)
        return response.get("data", [])

    async def create_task(self, data: Dict) -> Dict:
        """Create a new task"""
        response = await self.post("/tasks", data={"data": data})
        return response.get("data", {})

    async def update_task(self, task_gid: str, data: Dict) -> Dict:
        """Update a task"""
        response = await self.put(f"/tasks/{task_gid}", data={"data": data})
        return response.get("data", {})

    async def get_task_stories(
        self,
        task_gid: str,
        opt_fields: Optional[str] = None
    ) -> List[Dict]:
        """Get task stories (comments/activity)"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        return await self.get_paginated(f"/tasks/{task_gid}/stories", params=params)

    async def create_task_story(self, task_gid: str, text: str) -> Dict:
        """Add a comment to a task"""
        response = await self.post(
            f"/tasks/{task_gid}/stories",
            data={"data": {"text": text}}
        )
        return response.get("data", {})

    async def search_projects(
        self,
        workspace_gid: str,
        params: Optional[Dict] = None
    ) -> List[Dict]:
        """Search projects in a workspace"""
        endpoint = f"/workspaces/{workspace_gid}/projects"
        return await self.get_paginated(endpoint, params=params)

    async def get_project(self, project_gid: str, opt_fields: Optional[str] = None) -> Dict:
        """Get project by GID"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        response = await self.get(f"/projects/{project_gid}", params=params)
        return response.get("data", {})

    async def get_project_sections(
        self,
        project_gid: str,
        opt_fields: Optional[str] = None
    ) -> List[Dict]:
        """Get sections in a project"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        return await self.get_paginated(f"/projects/{project_gid}/sections", params=params)

    async def get_project_statuses(
        self,
        project_gid: str,
        opt_fields: Optional[str] = None
    ) -> List[Dict]:
        """Get project status updates"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        return await self.get_paginated(f"/projects/{project_gid}/project_statuses", params=params)

    async def create_project_status(self, project_gid: str, data: Dict) -> Dict:
        """Create a project status update"""
        response = await self.post(
            f"/projects/{project_gid}/project_statuses",
            data={"data": data}
        )
        return response.get("data", {})

    async def get_tags(self, workspace_gid: str, opt_fields: Optional[str] = None) -> List[Dict]:
        """Get tags in a workspace"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        return await self.get_paginated(f"/workspaces/{workspace_gid}/tags", params=params)

    async def get_tasks_for_tag(
        self,
        tag_gid: str,
        opt_fields: Optional[str] = None
    ) -> List[Dict]:
        """Get tasks with a specific tag"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        return await self.get_paginated(f"/tags/{tag_gid}/tasks", params=params)

    async def add_dependencies(self, task_gid: str, dependency_gids: List[str]) -> Dict:
        """Add dependencies to a task"""
        response = await self.post(
            f"/tasks/{task_gid}/addDependencies",
            data={"data": {"dependencies": dependency_gids}}
        )
        return response.get("data", {})

    async def add_dependents(self, task_gid: str, dependent_gids: List[str]) -> Dict:
        """Add dependents to a task"""
        response = await self.post(
            f"/tasks/{task_gid}/addDependents",
            data={"data": {"dependents": dependent_gids}}
        )
        return response.get("data", {})

    async def create_subtask(self, parent_gid: str, data: Dict) -> Dict:
        """Create a subtask"""
        response = await self.post(
            f"/tasks/{parent_gid}/subtasks",
            data={"data": data}
        )
        return response.get("data", {})

    async def set_parent(
        self,
        task_gid: str,
        parent_gid: str,
        insert_after: Optional[str] = None,
        insert_before: Optional[str] = None
    ) -> Dict:
        """Set parent for a task"""
        data = {"parent": parent_gid}
        if insert_after:
            data["insert_after"] = insert_after
        if insert_before:
            data["insert_before"] = insert_before

        response = await self.post(
            f"/tasks/{task_gid}/setParent",
            data={"data": data}
        )
        return response.get("data", {})

    # Phase 1: Additional Task Operations

    async def delete_task(self, task_gid: str) -> Dict:
        """Delete a task"""
        response = await self.delete(f"/tasks/{task_gid}")
        return response.get("data", {})

    async def duplicate_task(
        self,
        task_gid: str,
        include: Optional[str] = None,
        name: Optional[str] = None
    ) -> Dict:
        """
        Duplicate a task.

        Args:
            task_gid: Task to duplicate
            include: Comma-separated fields to include (notes, assignee, subtasks, attachments, tags, followers, projects, dates)
            name: Name for the duplicated task (default: "Copy of [original name]")
        """
        data = {}
        if include:
            data["include"] = include
        if name:
            data["name"] = name

        response = await self.post(
            f"/tasks/{task_gid}/duplicate",
            data={"data": data}
        )
        return response.get("data", {})

    async def get_subtasks(
        self,
        task_gid: str,
        opt_fields: Optional[str] = None
    ) -> List[Dict]:
        """Get subtasks of a task"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        return await self.get_paginated(f"/tasks/{task_gid}/subtasks", params=params)

    async def get_tasks_from_project(
        self,
        project_gid: str,
        params: Optional[Dict] = None
    ) -> List[Dict]:
        """Get all tasks in a project"""
        return await self.get_paginated(f"/projects/{project_gid}/tasks", params=params)

    async def get_tasks_from_section(
        self,
        section_gid: str,
        opt_fields: Optional[str] = None
    ) -> List[Dict]:
        """Get all tasks in a section"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        return await self.get_paginated(f"/sections/{section_gid}/tasks", params=params)

    async def get_task_dependencies(
        self,
        task_gid: str,
        opt_fields: Optional[str] = None
    ) -> List[Dict]:
        """Get dependencies of a task (tasks this task depends on)"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        return await self.get_paginated(f"/tasks/{task_gid}/dependencies", params=params)

    async def get_task_dependents(
        self,
        task_gid: str,
        opt_fields: Optional[str] = None
    ) -> List[Dict]:
        """Get dependents of a task (tasks that depend on this task)"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        return await self.get_paginated(f"/tasks/{task_gid}/dependents", params=params)

    async def add_project_to_task(
        self,
        task_gid: str,
        project_gid: str,
        insert_after: Optional[str] = None,
        insert_before: Optional[str] = None,
        section: Optional[str] = None
    ) -> Dict:
        """Add a task to a project"""
        data = {"project": project_gid}
        if insert_after:
            data["insert_after"] = insert_after
        if insert_before:
            data["insert_before"] = insert_before
        if section:
            data["section"] = section

        response = await self.post(
            f"/tasks/{task_gid}/addProject",
            data={"data": data}
        )
        return response.get("data", {})

    async def remove_project_from_task(self, task_gid: str, project_gid: str) -> Dict:
        """Remove a task from a project"""
        response = await self.post(
            f"/tasks/{task_gid}/removeProject",
            data={"data": {"project": project_gid}}
        )
        return response.get("data", {})

    async def add_tag_to_task(self, task_gid: str, tag_gid: str) -> Dict:
        """Add a tag to a task"""
        response = await self.post(
            f"/tasks/{task_gid}/addTag",
            data={"data": {"tag": tag_gid}}
        )
        return response.get("data", {})

    async def remove_tag_from_task(self, task_gid: str, tag_gid: str) -> Dict:
        """Remove a tag from a task"""
        response = await self.post(
            f"/tasks/{task_gid}/removeTag",
            data={"data": {"tag": tag_gid}}
        )
        return response.get("data", {})

    # Phase 1: Project Operations

    async def create_project(self, data: Dict) -> Dict:
        """Create a new project"""
        response = await self.post("/projects", data={"data": data})
        return response.get("data", {})

    async def update_project(self, project_gid: str, data: Dict) -> Dict:
        """Update a project"""
        response = await self.put(f"/projects/{project_gid}", data={"data": data})
        return response.get("data", {})

    async def delete_project(self, project_gid: str) -> Dict:
        """Delete a project"""
        response = await self.delete(f"/projects/{project_gid}")
        return response.get("data", {})

    async def get_project_task_counts(self, project_gid: str) -> Dict:
        """Get task count of a project"""
        params = {"opt_fields": "num_tasks,num_incomplete_tasks,num_completed_tasks,num_milestones"}
        response = await self.get(f"/projects/{project_gid}/task_counts", params=params)
        return response.get("data", {})

    async def duplicate_project(
        self,
        project_gid: str,
        name: str,
        include: Optional[str] = None,
        schedule_dates: Optional[Dict] = None
    ) -> Dict:
        """
        Duplicate a project.

        Args:
            project_gid: Project to duplicate
            name: Name for the duplicated project
            include: Comma-separated fields to include
            schedule_dates: Optional dict with due_on or start_on
        """
        data = {"name": name}
        if include:
            data["include"] = include
        if schedule_dates:
            data["schedule_dates"] = schedule_dates

        response = await self.post(
            f"/projects/{project_gid}/duplicate",
            data={"data": data}
        )
        return response.get("data", {})

    # Phase 1: Section Operations

    async def create_section(self, project_gid: str, name: str) -> Dict:
        """Create a section in a project"""
        response = await self.post(
            f"/projects/{project_gid}/sections",
            data={"data": {"name": name}}
        )
        return response.get("data", {})

    async def add_task_to_section(
        self,
        section_gid: str,
        task_gid: str,
        insert_after: Optional[str] = None,
        insert_before: Optional[str] = None
    ) -> Dict:
        """Add a task to a section"""
        data = {"task": task_gid}
        if insert_after:
            data["insert_after"] = insert_after
        if insert_before:
            data["insert_before"] = insert_before

        response = await self.post(
            f"/sections/{section_gid}/addTask",
            data={"data": data}
        )
        return response.get("data", {})

        # Phase 1: Additional Task Operations

    async def delete_task(self, task_gid: str) -> Dict:
        """Delete a task"""
        response = await self.delete(f"/tasks/{task_gid}")
        return response.get("data", {})

    async def duplicate_task(
        self,
        task_gid: str,
        include: Optional[str] = None,
        name: Optional[str] = None
    ) -> Dict:
        """
        Duplicate a task.

        Args:
            task_gid: Task to duplicate
            include: Comma-separated fields to include (notes, assignee, subtasks, attachments, tags, followers, projects, dates)
            name: Name for the duplicated task (default: "Copy of [original name]")
        """
        data = {}
        if include:
            data["include"] = include
        if name:
            data["name"] = name

        response = await self.post(
            f"/tasks/{task_gid}/duplicate",
            data={"data": data}
        )
        return response.get("data", {})

    async def get_subtasks(
        self,
        task_gid: str,
        opt_fields: Optional[str] = None
    ) -> List[Dict]:
        """Get subtasks of a task"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        return await self.get_paginated(f"/tasks/{task_gid}/subtasks", params=params)

    async def get_tasks_from_project(
        self,
        project_gid: str,
        params: Optional[Dict] = None
    ) -> List[Dict]:
        """Get all tasks in a project"""
        return await self.get_paginated(f"/projects/{project_gid}/tasks", params=params)

    async def get_tasks_from_section(
        self,
        section_gid: str,
        opt_fields: Optional[str] = None
    ) -> List[Dict]:
        """Get all tasks in a section"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        return await self.get_paginated(f"/sections/{section_gid}/tasks", params=params)

    async def get_task_dependencies(
        self,
        task_gid: str,
        opt_fields: Optional[str] = None
    ) -> List[Dict]:
        """Get dependencies of a task (tasks this task depends on)"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        return await self.get_paginated(f"/tasks/{task_gid}/dependencies", params=params)

    async def get_task_dependents(
        self,
        task_gid: str,
        opt_fields: Optional[str] = None
    ) -> List[Dict]:
        """Get dependents of a task (tasks that depend on this task)"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        return await self.get_paginated(f"/tasks/{task_gid}/dependents", params=params)

    async def add_project_to_task(
        self,
        task_gid: str,
        project_gid: str,
        insert_after: Optional[str] = None,
        insert_before: Optional[str] = None,
        section: Optional[str] = None
    ) -> Dict:
        """Add a task to a project"""
        data = {"project": project_gid}
        if insert_after:
            data["insert_after"] = insert_after
        if insert_before:
            data["insert_before"] = insert_before
        if section:
            data["section"] = section

        response = await self.post(
            f"/tasks/{task_gid}/addProject",
            data={"data": data}
        )
        return response.get("data", {})

    async def remove_project_from_task(self, task_gid: str, project_gid: str) -> Dict:
        """Remove a task from a project"""
        response = await self.post(
            f"/tasks/{task_gid}/removeProject",
            data={"data": {"project": project_gid}}
        )
        return response.get("data", {})

    async def add_tag_to_task(self, task_gid: str, tag_gid: str) -> Dict:
        """Add a tag to a task"""
        response = await self.post(
            f"/tasks/{task_gid}/addTag",
            data={"data": {"tag": tag_gid}}
        )
        return response.get("data", {})

    async def remove_tag_from_task(self, task_gid: str, tag_gid: str) -> Dict:
        """Remove a tag from a task"""
        response = await self.post(
            f"/tasks/{task_gid}/removeTag",
            data={"data": {"tag": tag_gid}}
        )
        return response.get("data", {})

    # Phase 1: Project Operations

    async def create_project(self, data: Dict) -> Dict:
        """Create a new project"""
        response = await self.post("/projects", data={"data": data})
        return response.get("data", {})

    async def update_project(self, project_gid: str, data: Dict) -> Dict:
        """Update a project"""
        response = await self.put(f"/projects/{project_gid}", data={"data": data})
        return response.get("data", {})

    async def delete_project(self, project_gid: str) -> Dict:
        """Delete a project"""
        response = await self.delete(f"/projects/{project_gid}")
        return response.get("data", {})

    async def get_project_task_counts(self, project_gid: str) -> Dict:
        """Get task count of a project"""
        params = {"opt_fields": "num_tasks,num_incomplete_tasks,num_completed_tasks,num_milestones"}
        response = await self.get(f"/projects/{project_gid}/task_counts", params=params)
        return response.get("data", {})

    async def duplicate_project(
        self,
        project_gid: str,
        name: str,
        include: Optional[str] = None,
        schedule_dates: Optional[Dict] = None
    ) -> Dict:
        """
        Duplicate a project.

        Args:
            project_gid: Project to duplicate
            name: Name for the duplicated project
            include: Comma-separated fields to include
            schedule_dates: Optional dict with due_on or start_on
        """
        data = {"name": name}
        if include:
            data["include"] = include
        if schedule_dates:
            data["schedule_dates"] = schedule_dates

        response = await self.post(
            f"/projects/{project_gid}/duplicate",
            data={"data": data}
        )
        return response.get("data", {})

    # Phase 1: Section Operations

    async def create_section(self, project_gid: str, name: str) -> Dict:
        """Create a section in a project"""
        response = await self.post(
            f"/projects/{project_gid}/sections",
            data={"data": {"name": name}}
        )
        return response.get("data", {})

    async def add_task_to_section(
        self,
        section_gid: str,
        task_gid: str,
        insert_after: Optional[str] = None,
        insert_before: Optional[str] = None
    ) -> Dict:
        """Add a task to a section"""
        data = {"task": task_gid}
        if insert_after:
            data["insert_after"] = insert_after
        if insert_before:
            data["insert_before"] = insert_before

        response = await self.post(
            f"/sections/{section_gid}/addTask",
            data={"data": data}
        )
        return response.get("data", {})

        # Phase 2: Additional Operations

    async def remove_dependencies(self, task_gid: str, dependency_gids: list) -> dict:
        """Remove dependencies from a task"""
        response = await self.post(
            f"/tasks/{task_gid}/removeDependencies",
            data={"data": {"dependencies": dependency_gids}}
        )
        return response.get("data", {})

    async def remove_dependents(self, task_gid: str, dependent_gids: list) -> dict:
        """Remove dependents from a task"""
        response = await self.post(
            f"/tasks/{task_gid}/removeDependents",
            data={"data": {"dependents": dependent_gids}}
        )
        return response.get("data", {})

    async def add_followers_to_task(self, task_gid: str, follower_gids: list) -> dict:
        """Add followers to a task"""
        response = await self.post(
            f"/tasks/{task_gid}/addFollowers",
            data={"data": {"followers": follower_gids}}
        )
        return response.get("data", {})

    async def remove_followers_from_task(self, task_gid: str, follower_gids: list) -> dict:
        """Remove followers from a task"""
        response = await self.post(
            f"/tasks/{task_gid}/removeFollowers",
            data={"data": {"followers": follower_gids}}
        )
        return response.get("data", {})

    async def get_section(self, section_gid: str, opt_fields: Optional[str] = None) -> dict:
        """Get section details"""
        params = {}
        if opt_fields:
            params["opt_fields"] = opt_fields
        response = await self.get(f"/sections/{section_gid}", params=params)
        return response.get("data", {})

    async def update_section(self, section_gid: str, name: str) -> dict:
        """Update a section"""
        response = await self.put(
            f"/sections/{section_gid}",
            data={"data": {"name": name}}
        )
        return response.get("data", {})

    async def delete_section(self, section_gid: str) -> dict:
        """Delete a section"""
        response = await self.delete(f"/sections/{section_gid}")
        return response.get("data", {})

    async def add_members_to_project(self, project_gid: str, member_gids: list) -> dict:
        """Add members to a project"""
        response = await self.post(
            f"/projects/{project_gid}/addMembers",
            data={"data": {"members": ",".join(member_gids)}}
        )
        return response.get("data", {})

    async def remove_members_from_project(self, project_gid: str, member_gids: list) -> dict:
        """Remove members from a project"""
        response = await self.post(
            f"/projects/{project_gid}/removeMembers",
            data={"data": {"members": ",".join(member_gids)}}
        )
        return response.get("data", {})

    async def add_followers_to_project(self, project_gid: str, follower_gids: list) -> dict:
        """Add followers to a project"""
        response = await self.post(
            f"/projects/{project_gid}/addFollowers",
            data={"data": {"followers": ",".join(follower_gids)}}
        )
        return response.get("data", {})

    async def remove_followers_from_project(self, project_gid: str, follower_gids: list) -> dict:
        """Remove followers from a project"""
        response = await self.post(
            f"/projects/{project_gid}/removeFollowers",
            data={"data": {"followers": ",".join(follower_gids)}}
        )
        return response.get("data", {})

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()
