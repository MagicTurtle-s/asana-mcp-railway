"""
Organization Tools

MCP tools for workspaces and tags.
"""

from typing import Optional
from pydantic import BaseModel, Field


class GetTagsInput(BaseModel):
    """Input schema for get_tags"""
    workspace: str = Field(
        description="Workspace GID to get tags from"
    )
    opt_fields: Optional[str] = Field(
        "name,color",
        description="Comma-separated fields to return"
    )


class GetTasksForTagInput(BaseModel):
    """Input schema for get_tasks_for_tag"""
    tag_gid: str = Field(
        description="Tag GID to get tasks for"
    )
    opt_fields: Optional[str] = Field(
        "name,completed,due_on,assignee.name",
        description="Comma-separated fields to return"
    )


# Tool handler functions

async def get_tags_handler(client, params: dict) -> str:
    """Get all tags in a workspace"""
    from ..utils.formatters import format_tags, format_error

    try:
        workspace_gid = params["workspace"]
        opt_fields = params.get("opt_fields")

        tags = await client.get_tags(workspace_gid, opt_fields=opt_fields)
        return format_tags(tags)

    except Exception as e:
        return format_error(e, f"getting tags for workspace {params.get('workspace')}")


async def get_tasks_for_tag_handler(client, params: dict) -> str:
    """Get all tasks with a specific tag"""
    from ..utils.formatters import format_tasks, format_error

    try:
        tag_gid = params["tag_gid"]
        opt_fields = params.get("opt_fields")

        tasks = await client.get_tasks_for_tag(tag_gid, opt_fields=opt_fields)
        return format_tasks(tasks, detailed=False)

    except Exception as e:
        return format_error(e, f"getting tasks for tag {params.get('tag_gid')}")


# Tool definitions for MCP server registration
ORGANIZATION_TOOLS = [
    {
        "name": "asana_get_tags_for_workspace",
        "description": """Get all tags in a workspace.

Tags are labels that can be applied to tasks for categorization and filtering. Common uses:
- Priority (high, medium, low)
- Status (blocked, waiting, ready)
- Categories (bug, feature, documentation)

Returns tag names, GIDs, and colors.""",
        "inputSchema": GetTagsInput.model_json_schema(),
        "handler": get_tags_handler
    },
    {
        "name": "asana_get_tasks_for_tag",
        "description": """Get all tasks with a specific tag.

Useful for finding tasks by category, priority, or other tag-based classification.

Example: Get all tasks tagged as "urgent" or "bug" to see what needs immediate attention.

Returns list of tasks with the specified tag.""",
        "inputSchema": GetTasksForTagInput.model_json_schema(),
        "handler": get_tasks_for_tag_handler
    }
]
