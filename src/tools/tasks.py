"""
Task Management Tools

MCP tools for creating, reading, updating, and searching Asana tasks.
"""

from typing import Optional, List
from pydantic import BaseModel, Field

# Tool implementations will be added to the MCP server
# These are the input schemas and handler functions


class ListWorkspacesInput(BaseModel):
    """Input schema for list_workspaces"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    opt_fields: Optional[str] = Field(
        None,
        description="Comma-separated list of fields to return (e.g., 'name,is_organization')"
    )


class SearchTasksInput(BaseModel):
    """Input schema for search_tasks"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    workspace: str = Field(
        description="Workspace GID to search in"
    )
    text: Optional[str] = Field(
        None,
        description="Text search query (searches task names and descriptions)"
    )
    completed: Optional[bool] = Field(
        None,
        description="Filter by completion status (true/false)"
    )
    assignee: Optional[str] = Field(
        None,
        description="Assignee GID to filter by"
    )
    projects: Optional[str] = Field(
        None,
        description="Comma-separated list of project GIDs to filter by"
    )
    tags: Optional[str] = Field(
        None,
        description="Comma-separated list of tag GIDs to filter by"
    )
    due_on_before: Optional[str] = Field(
        None,
        description="Due date before this date (YYYY-MM-DD format)"
    )
    due_on_after: Optional[str] = Field(
        None,
        description="Due date after this date (YYYY-MM-DD format)"
    )
    modified_since: Optional[str] = Field(
        None,
        description="Only tasks modified after this date (ISO 8601 format)"
    )
    opt_fields: Optional[str] = Field(
        "name,completed,due_on,assignee.name,projects.name,tags.name",
        description="Comma-separated fields to return"
    )
    limit: Optional[int] = Field(
        100,
        description="Maximum number of results to return (1-100)"
    )


class GetTaskInput(BaseModel):
    """Input schema for get_task"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    task_gid: str = Field(
        description="Task GID to retrieve"
    )
    opt_fields: Optional[str] = Field(
        "name,completed,due_on,assignee.name,projects.name,notes,tags.name,custom_fields,created_at,modified_at",
        description="Comma-separated fields to return"
    )


class GetMultipleTasksInput(BaseModel):
    """Input schema for get_multiple_tasks"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    task_gids: str = Field(
        description="Comma-separated list of task GIDs (maximum 25)"
    )
    opt_fields: Optional[str] = Field(
        "name,completed,due_on,assignee.name,projects.name",
        description="Comma-separated fields to return"
    )


class CreateTaskInput(BaseModel):
    """Input schema for create_task"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    workspace: Optional[str] = Field(
        None,
        description="Workspace GID (required if not providing projects)"
    )
    name: str = Field(
        description="Task name (required)"
    )
    notes: Optional[str] = Field(
        None,
        description="Task description/notes"
    )
    assignee: Optional[str] = Field(
        None,
        description="Assignee GID"
    )
    projects: Optional[str] = Field(
        None,
        description="Comma-separated list of project GIDs to add task to"
    )
    due_on: Optional[str] = Field(
        None,
        description="Due date (YYYY-MM-DD format)"
    )
    due_at: Optional[str] = Field(
        None,
        description="Due date and time (ISO 8601 format)"
    )
    tags: Optional[str] = Field(
        None,
        description="Comma-separated list of tag GIDs"
    )
    parent: Optional[str] = Field(
        None,
        description="Parent task GID (to create as subtask)"
    )


class UpdateTaskInput(BaseModel):
    """Input schema for update_task"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    task_gid: str = Field(
        description="Task GID to update"
    )
    name: Optional[str] = Field(
        None,
        description="New task name"
    )
    notes: Optional[str] = Field(
        None,
        description="New task notes"
    )
    completed: Optional[bool] = Field(
        None,
        description="Completion status"
    )
    assignee: Optional[str] = Field(
        None,
        description="New assignee GID"
    )
    due_on: Optional[str] = Field(
        None,
        description="New due date (YYYY-MM-DD)"
    )
    due_at: Optional[str] = Field(
        None,
        description="New due date and time (ISO 8601)"
    )


class GetTaskStoriesInput(BaseModel):
    """Input schema for get_task_stories"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    task_gid: str = Field(
        description="Task GID to get stories for"
    )
    opt_fields: Optional[str] = Field(
        "type,text,created_at,created_by.name",
        description="Comma-separated fields to return"
    )


class CreateTaskStoryInput(BaseModel):
    """Input schema for create_task_story"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    task_gid: str = Field(
        description="Task GID to add comment to"
    )
    text: str = Field(
        description="Comment text"
    )


# Tool handler functions

async def list_workspaces_handler(client, params: dict) -> str:
    """List all workspaces the user has access to"""
    from ..utils.formatters import format_workspaces, format_error

    try:
        workspaces = await client.get_workspaces()
        return format_workspaces(workspaces)
    except Exception as e:
        return format_error(e, "listing workspaces")


async def search_tasks_handler(client, params: dict) -> str:
    """
    Search tasks in a workspace with advanced filtering.

    Supports filtering by:
    - Text search (task names and descriptions)
    - Completion status
    - Assignee
    - Projects
    - Tags
    - Due dates
    - Modification date

    Returns up to 100 tasks matching the criteria.
    """
    from ..utils.formatters import format_tasks, format_error

    try:
        workspace_gid = params["workspace"]

        # Build query parameters
        query_params = {}

        # Text search
        if params.get("text"):
            query_params["text"] = params["text"]

        # Completion status
        if params.get("completed") is not None:
            query_params["completed"] = str(params["completed"]).lower()

        # Assignee
        if params.get("assignee"):
            query_params["assignee.any"] = params["assignee"]

        # Projects (comma-separated)
        if params.get("projects"):
            query_params["projects.any"] = params["projects"]

        # Tags (comma-separated)
        if params.get("tags"):
            query_params["tags.any"] = params["tags"]

        # Due date filters
        if params.get("due_on_before"):
            query_params["due_on.before"] = params["due_on_before"]
        if params.get("due_on_after"):
            query_params["due_on.after"] = params["due_on_after"]

        # Modified since
        if params.get("modified_since"):
            query_params["modified_since"] = params["modified_since"]

        # Opt fields
        if params.get("opt_fields"):
            query_params["opt_fields"] = params["opt_fields"]

        # Search tasks
        tasks = await client.search_tasks(workspace_gid, params=query_params)

        # Apply limit if specified
        limit = params.get("limit", 100)
        if limit and len(tasks) > limit:
            tasks = tasks[:limit]

        return format_tasks(tasks, detailed=False)

    except Exception as e:
        return format_error(e, "searching tasks")


async def get_task_handler(client, params: dict) -> str:
    """Get detailed information about a specific task"""
    from ..utils.formatters import format_task, format_error

    try:
        task_gid = params["task_gid"]
        opt_fields = params.get("opt_fields")

        task = await client.get_task(task_gid, opt_fields=opt_fields)
        return format_task(task, detailed=True)

    except Exception as e:
        return format_error(e, f"getting task {params.get('task_gid')}")


async def get_multiple_tasks_handler(client, params: dict) -> str:
    """Get multiple tasks by GID (batch operation, max 25)"""
    from ..utils.formatters import format_tasks, format_error

    try:
        task_gids = params["task_gids"].split(",")
        task_gids = [gid.strip() for gid in task_gids if gid.strip()]

        if len(task_gids) > 25:
            return "⚠️ Maximum 25 tasks can be fetched at once. Please provide fewer GIDs."

        opt_fields = params.get("opt_fields")
        tasks = await client.get_multiple_tasks(task_gids, opt_fields=opt_fields)

        return format_tasks(tasks, detailed=False)

    except Exception as e:
        return format_error(e, "getting multiple tasks")


async def create_task_handler(client, params: dict) -> str:
    """Create a new task"""
    from ..utils.formatters import format_task, format_error

    try:
        # Build task data
        task_data = {"name": params["name"]}

        # Optional fields
        if params.get("notes"):
            task_data["notes"] = params["notes"]
        if params.get("assignee"):
            task_data["assignee"] = params["assignee"]
        if params.get("due_on"):
            task_data["due_on"] = params["due_on"]
        if params.get("due_at"):
            task_data["due_at"] = params["due_at"]
        if params.get("parent"):
            task_data["parent"] = params["parent"]

        # Workspace or projects (at least one required)
        if params.get("workspace"):
            task_data["workspace"] = params["workspace"]
        if params.get("projects"):
            project_gids = [p.strip() for p in params["projects"].split(",")]
            task_data["projects"] = project_gids

        # Tags
        if params.get("tags"):
            tag_gids = [t.strip() for t in params["tags"].split(",")]
            task_data["tags"] = tag_gids

        # Create task
        task = await client.create_task(task_data)

        return f"✅ Task created successfully!\n\n{format_task(task, detailed=True)}"

    except Exception as e:
        return format_error(e, "creating task")


async def update_task_handler(client, params: dict) -> str:
    """Update an existing task"""
    from ..utils.formatters import format_task, format_error

    try:
        task_gid = params["task_gid"]

        # Build update data
        update_data = {}

        if params.get("name") is not None:
            update_data["name"] = params["name"]
        if params.get("notes") is not None:
            update_data["notes"] = params["notes"]
        if params.get("completed") is not None:
            update_data["completed"] = params["completed"]
        if params.get("assignee") is not None:
            update_data["assignee"] = params["assignee"]
        if params.get("due_on") is not None:
            update_data["due_on"] = params["due_on"]
        if params.get("due_at") is not None:
            update_data["due_at"] = params["due_at"]

        if not update_data:
            return "⚠️ No update fields provided. Please specify at least one field to update."

        # Update task
        task = await client.update_task(task_gid, update_data)

        return f"✅ Task updated successfully!\n\n{format_task(task, detailed=True)}"

    except Exception as e:
        return format_error(e, f"updating task {params.get('task_gid')}")


async def get_task_stories_handler(client, params: dict) -> str:
    """Get task stories (comments and activity)"""
    from ..utils.formatters import format_stories, format_error

    try:
        task_gid = params["task_gid"]
        opt_fields = params.get("opt_fields")

        stories = await client.get_task_stories(task_gid, opt_fields=opt_fields)
        return format_stories(stories)

    except Exception as e:
        return format_error(e, f"getting stories for task {params.get('task_gid')}")


async def create_task_story_handler(client, params: dict) -> str:
    """Add a comment to a task"""
    from ..utils.formatters import format_error

    try:
        task_gid = params["task_gid"]
        text = params["text"]

        story = await client.create_task_story(task_gid, text)

        return f"✅ Comment added successfully!\n\n💬 {text}"

    except Exception as e:
        return format_error(e, f"adding comment to task {params.get('task_gid')}")


# Tool definitions for MCP server registration
TASK_TOOLS = [
    {
        "name": "asana_list_workspaces",
        "description": "List all Asana workspaces the user has access to. Returns workspace names and GIDs.",
        "inputSchema": ListWorkspacesInput.model_json_schema(),
        "handler": list_workspaces_handler
    },
    {
        "name": "asana_search_tasks",
        "description": """Search tasks in a workspace with advanced filtering options.

Supports filtering by:
- Text search (searches task names and descriptions)
- Completion status (completed/incomplete)
- Assignee (user GID)
- Projects (comma-separated project GIDs)
- Tags (comma-separated tag GIDs)
- Due dates (before/after specific dates)
- Modification date (tasks modified since a date)

Returns up to 100 tasks matching the criteria. Use opt_fields to control which fields are returned to minimize response size.

Example: Find incomplete tasks assigned to user in a specific project due next week.""",
        "inputSchema": SearchTasksInput.model_json_schema(),
        "handler": search_tasks_handler
    },
    {
        "name": "asana_get_task",
        "description": "Get detailed information about a specific task by GID. Returns all task fields including name, assignee, due dates, notes, custom fields, projects, tags, and activity timestamps.",
        "inputSchema": GetTaskInput.model_json_schema(),
        "handler": get_task_handler
    },
    {
        "name": "asana_get_multiple_tasks_by_gid",
        "description": "Get multiple tasks by their GIDs in a single request (batch operation). Maximum 25 tasks per request. More efficient than calling get_task multiple times. Provide comma-separated list of task GIDs.",
        "inputSchema": GetMultipleTasksInput.model_json_schema(),
        "handler": get_multiple_tasks_handler
    },
    {
        "name": "asana_create_task",
        "description": """Create a new task in Asana.

Required: task name, and either workspace or projects
Optional: notes, assignee, due_on/due_at, tags, parent (for subtasks)

Example: Create a task named "Review PR" in project XYZ, assigned to user ABC, due tomorrow.

Returns the created task with its GID.""",
        "inputSchema": CreateTaskInput.model_json_schema(),
        "handler": create_task_handler
    },
    {
        "name": "asana_update_task",
        "description": """Update an existing task's properties.

Can update: name, notes, completed status, assignee, due_on/due_at

Provide only the fields you want to change. Unspecified fields remain unchanged.

Returns the updated task.""",
        "inputSchema": UpdateTaskInput.model_json_schema(),
        "handler": update_task_handler
    },
    {
        "name": "asana_get_task_stories",
        "description": "Get all stories (comments and activity) for a task. Stories include user comments, system-generated activity (task completed, assignee changed, etc.), and other updates. Useful for understanding task history and collaboration.",
        "inputSchema": GetTaskStoriesInput.model_json_schema(),
        "handler": get_task_stories_handler
    },
    {
        "name": "asana_create_task_story",
        "description": "Add a comment to a task. Comments are visible to all users with access to the task. Use this to provide updates, ask questions, or collaborate with team members.",
        "inputSchema": CreateTaskStoryInput.model_json_schema(),
        "handler": create_task_story_handler
    }
]
