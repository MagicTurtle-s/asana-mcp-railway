"""
Project Management Tools

MCP tools for working with Asana projects.
"""

from typing import Optional
from pydantic import BaseModel, Field


class SearchProjectsInput(BaseModel):
    """Input schema for search_projects"""
    workspace: str = Field(
        description="Workspace GID to search in"
    )
    archived: Optional[bool] = Field(
        None,
        description="Filter by archived status (true/false)"
    )
    team: Optional[str] = Field(
        None,
        description="Team GID to filter by"
    )
    opt_fields: Optional[str] = Field(
        "name,owner.name,archived,due_on,team.name",
        description="Comma-separated fields to return"
    )


class GetProjectInput(BaseModel):
    """Input schema for get_project"""
    project_gid: str = Field(
        description="Project GID to retrieve"
    )
    opt_fields: Optional[str] = Field(
        "name,owner.name,notes,archived,due_on,start_on,team.name,num_tasks,num_incomplete_tasks,created_at,modified_at",
        description="Comma-separated fields to return"
    )


class GetProjectSectionsInput(BaseModel):
    """Input schema for get_project_sections"""
    project_gid: str = Field(
        description="Project GID to get sections for"
    )
    opt_fields: Optional[str] = Field(
        "name,created_at",
        description="Comma-separated fields to return"
    )


class GetProjectStatusesInput(BaseModel):
    """Input schema for get_project_statuses"""
    project_gid: str = Field(
        description="Project GID to get status updates for"
    )
    opt_fields: Optional[str] = Field(
        "title,text,color,created_at,created_by.name",
        description="Comma-separated fields to return"
    )


class CreateProjectStatusInput(BaseModel):
    """Input schema for create_project_status"""
    project_gid: str = Field(
        description="Project GID to create status update for"
    )
    title: str = Field(
        description="Status update title"
    )
    text: Optional[str] = Field(
        None,
        description="Status update text/description"
    )
    color: Optional[str] = Field(
        "blue",
        description="Status color: green (on track), yellow (at risk), red (off track), blue (complete)"
    )


# Tool handler functions

async def search_projects_handler(client, params: dict) -> str:
    """Search projects in a workspace"""
    from ..utils.formatters import format_projects, format_error

    try:
        workspace_gid = params["workspace"]

        # Build query parameters
        query_params = {}

        if params.get("archived") is not None:
            query_params["archived"] = str(params["archived"]).lower()
        if params.get("team"):
            query_params["team"] = params["team"]
        if params.get("opt_fields"):
            query_params["opt_fields"] = params["opt_fields"]

        # Search projects
        projects = await client.search_projects(workspace_gid, params=query_params)

        return format_projects(projects, detailed=False)

    except Exception as e:
        return format_error(e, "searching projects")


async def get_project_handler(client, params: dict) -> str:
    """Get detailed information about a specific project"""
    from ..utils.formatters import format_project, format_error

    try:
        project_gid = params["project_gid"]
        opt_fields = params.get("opt_fields")

        project = await client.get_project(project_gid, opt_fields=opt_fields)
        return format_project(project, detailed=True)

    except Exception as e:
        return format_error(e, f"getting project {params.get('project_gid')}")


async def get_project_sections_handler(client, params: dict) -> str:
    """Get sections in a project"""
    from ..utils.formatters import format_sections, format_error

    try:
        project_gid = params["project_gid"]
        opt_fields = params.get("opt_fields")

        sections = await client.get_project_sections(project_gid, opt_fields=opt_fields)
        return format_sections(sections)

    except Exception as e:
        return format_error(e, f"getting sections for project {params.get('project_gid')}")


async def get_project_statuses_handler(client, params: dict) -> str:
    """Get project status updates"""
    from ..utils.formatters import format_error

    try:
        project_gid = params["project_gid"]
        opt_fields = params.get("opt_fields")

        statuses = await client.get_project_statuses(project_gid, opt_fields=opt_fields)

        if not statuses:
            return "No project status updates found."

        lines = [f"Found {len(statuses)} status update(s):\n"]

        for status in statuses:
            title = status.get("title", "Untitled")
            text = status.get("text", "")
            color = status.get("color", "blue")
            created_at = status.get("created_at", "")
            created_by = status.get("created_by", {}).get("name", "Unknown")

            # Color emoji
            color_map = {
                "green": "🟢",
                "yellow": "🟡",
                "red": "🔴",
                "blue": "🔵"
            }
            color_emoji = color_map.get(color, "⚪")

            lines.append(f"{color_emoji} **{title}**")
            lines.append(f"   By: {created_by} on {created_at}")
            if text:
                lines.append(f"   {text[:200]}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return format_error(e, f"getting statuses for project {params.get('project_gid')}")


async def create_project_status_handler(client, params: dict) -> str:
    """Create a project status update"""
    from ..utils.formatters import format_error

    try:
        project_gid = params["project_gid"]

        # Build status data
        status_data = {
            "title": params["title"],
            "color": params.get("color", "blue")
        }

        if params.get("text"):
            status_data["text"] = params["text"]

        # Create status
        status = await client.create_project_status(project_gid, status_data)

        title = status.get("title", "")
        color = status.get("color", "blue")

        color_map = {
            "green": "🟢",
            "yellow": "🟡",
            "red": "🔴",
            "blue": "🔵"
        }
        color_emoji = color_map.get(color, "⚪")

        return f"✅ Project status created successfully!\n\n{color_emoji} **{title}**"

    except Exception as e:
        return format_error(e, f"creating status for project {params.get('project_gid')}")


# Tool definitions for MCP server registration
PROJECT_TOOLS = [
    {
        "name": "asana_search_projects",
        "description": """Search projects in a workspace.

Supports filtering by:
- Archived status (active or archived projects)
- Team (team GID)

Returns list of projects with name, owner, status, and other metadata.

Example: Find all active projects in workspace XYZ for team ABC.""",
        "inputSchema": SearchProjectsInput.model_json_schema(),
        "handler": search_projects_handler
    },
    {
        "name": "asana_get_project",
        "description": "Get detailed information about a specific project by GID. Returns project name, owner, notes, dates, team, task counts, and other metadata.",
        "inputSchema": GetProjectInput.model_json_schema(),
        "handler": get_project_handler
    },
    {
        "name": "asana_get_project_sections",
        "description": "Get all sections in a project. Sections are used to organize tasks within a project (e.g., 'To Do', 'In Progress', 'Done'). Returns section names and GIDs.",
        "inputSchema": GetProjectSectionsInput.model_json_schema(),
        "handler": get_project_sections_handler
    },
    {
        "name": "asana_get_project_statuses",
        "description": "Get all status updates for a project. Status updates are progress reports posted by project owners/members. Each status has a color (green=on track, yellow=at risk, red=off track, blue=complete), title, and description. Useful for tracking project health over time.",
        "inputSchema": GetProjectStatusesInput.model_json_schema(),
        "handler": get_project_statuses_handler
    },
    {
        "name": "asana_create_project_status",
        "description": """Create a new status update for a project.

Status updates communicate project progress to stakeholders.

Colors:
- green: On track
- yellow: At risk
- red: Off track
- blue: Complete

Example: Post a status update that the project is on track with title "Week 10 Update" and description of accomplishments.""",
        "inputSchema": CreateProjectStatusInput.model_json_schema(),
        "handler": create_project_status_handler
    }
]
