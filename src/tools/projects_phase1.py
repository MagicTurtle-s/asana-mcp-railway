"""
Phase 1 Additional Project Tools

New project management tools for parity with official Asana MCP.
"""

from typing import Optional
from pydantic import BaseModel, Field


# Create Project

class CreateProjectInput(BaseModel):
    """Input schema for create_project"""
    workspace: Optional[str] = Field(
        None,
        description="Workspace GID (required if not providing team)"
    )
    team: Optional[str] = Field(
        None,
        description="Team GID (required if not providing workspace)"
    )
    name: str = Field(
        description="Project name (required)"
    )
    notes: Optional[str] = Field(
        None,
        description="Project description/notes"
    )
    color: Optional[str] = Field(
        None,
        description="Project color (e.g., 'light-green', 'dark-blue')"
    )
    archived: Optional[bool] = Field(
        False,
        description="Whether project should be archived"
    )
    public: Optional[bool] = Field(
        True,
        description="Whether project is public to the workspace"
    )
    due_on: Optional[str] = Field(
        None,
        description="Project due date (YYYY-MM-DD)"
    )
    start_on: Optional[str] = Field(
        None,
        description="Project start date (YYYY-MM-DD)"
    )


async def create_project_handler(client, params: dict) -> str:
    """Create a new project"""
    from ..utils.formatters import format_project, format_error

    try:
        # Build project data
        project_data = {"name": params["name"]}

        # Required: workspace or team
        if params.get("workspace"):
            project_data["workspace"] = params["workspace"]
        elif params.get("team"):
            project_data["team"] = params["team"]
        else:
            return "Error: Either workspace or team must be provided."

        # Optional fields
        if params.get("notes"):
            project_data["notes"] = params["notes"]
        if params.get("color"):
            project_data["color"] = params["color"]
        if params.get("archived") is not None:
            project_data["archived"] = params["archived"]
        if params.get("public") is not None:
            project_data["public"] = params["public"]
        if params.get("due_on"):
            project_data["due_on"] = params["due_on"]
        if params.get("start_on"):
            project_data["start_on"] = params["start_on"]

        # Create project
        project = await client.create_project(project_data)

        return f"Project created successfully!\n\n{format_project(project, detailed=True)}"

    except Exception as e:
        return format_error(e, "creating project")


# Update Project

class UpdateProjectInput(BaseModel):
    """Input schema for update_project"""
    project_gid: str = Field(
        description="Project GID to update"
    )
    name: Optional[str] = Field(
        None,
        description="New project name"
    )
    notes: Optional[str] = Field(
        None,
        description="New project notes"
    )
    color: Optional[str] = Field(
        None,
        description="New project color"
    )
    archived: Optional[bool] = Field(
        None,
        description="Archive status"
    )
    public: Optional[bool] = Field(
        None,
        description="Public visibility"
    )
    due_on: Optional[str] = Field(
        None,
        description="New due date (YYYY-MM-DD)"
    )
    start_on: Optional[str] = Field(
        None,
        description="New start date (YYYY-MM-DD)"
    )


async def update_project_handler(client, params: dict) -> str:
    """Update an existing project"""
    from ..utils.formatters import format_project, format_error

    try:
        project_gid = params["project_gid"]

        # Build update data
        update_data = {}

        if params.get("name") is not None:
            update_data["name"] = params["name"]
        if params.get("notes") is not None:
            update_data["notes"] = params["notes"]
        if params.get("color") is not None:
            update_data["color"] = params["color"]
        if params.get("archived") is not None:
            update_data["archived"] = params["archived"]
        if params.get("public") is not None:
            update_data["public"] = params["public"]
        if params.get("due_on") is not None:
            update_data["due_on"] = params["due_on"]
        if params.get("start_on") is not None:
            update_data["start_on"] = params["start_on"]

        if not update_data:
            return "No update fields provided. Please specify at least one field to update."

        # Update project
        project = await client.update_project(project_gid, update_data)

        return f"Project updated successfully!\n\n{format_project(project, detailed=True)}"

    except Exception as e:
        return format_error(e, f"updating project {params.get('project_gid')}")


# Delete Project

class DeleteProjectInput(BaseModel):
    """Input schema for delete_project"""
    project_gid: str = Field(
        description="Project GID to delete"
    )


async def delete_project_handler(client, params: dict) -> str:
    """Delete a project"""
    from ..utils.formatters import format_error

    try:
        project_gid = params["project_gid"]
        await client.delete_project(project_gid)
        return f"Project {project_gid} deleted successfully."

    except Exception as e:
        return format_error(e, f"deleting project {params.get('project_gid')}")


# Get Project Task Counts

class GetProjectTaskCountsInput(BaseModel):
    """Input schema for get_project_task_counts"""
    project_gid: str = Field(
        description="Project GID to get task counts for"
    )


async def get_project_task_counts_handler(client, params: dict) -> str:
    """Get task count statistics for a project"""
    from ..utils.formatters import format_error

    try:
        project_gid = params["project_gid"]
        counts = await client.get_project_task_counts(project_gid)

        num_tasks = counts.get("num_tasks", 0)
        num_incomplete = counts.get("num_incomplete_tasks", 0)
        num_completed = counts.get("num_completed_tasks", 0)
        num_milestones = counts.get("num_milestones", 0)

        lines = [
            f"Task Statistics for Project {project_gid}:",
            f"",
            f"Total Tasks: {num_tasks}",
            f"Incomplete: {num_incomplete}",
            f"Completed: {num_completed}",
            f"Milestones: {num_milestones}"
        ]

        if num_tasks > 0:
            completion_pct = (num_completed / num_tasks) * 100
            lines.append(f"Completion: {completion_pct:.1f}%")

        return "\n".join(lines)

    except Exception as e:
        return format_error(e, f"getting task counts for project {params.get('project_gid')}")


# Duplicate Project

class DuplicateProjectInput(BaseModel):
    """Input schema for duplicate_project"""
    project_gid: str = Field(
        description="Project GID to duplicate"
    )
    name: str = Field(
        description="Name for the duplicated project (required)"
    )
    include: Optional[str] = Field(
        "notes,members,task_notes",
        description="Comma-separated fields to include (forms,notes,members,task_notes,task_assignee,task_subtasks,task_attachments,task_dates,task_dependencies,task_followers,task_tags,task_projects)"
    )
    schedule_dates_due_on: Optional[str] = Field(
        None,
        description="Due date for the duplicated project (YYYY-MM-DD)"
    )
    schedule_dates_start_on: Optional[str] = Field(
        None,
        description="Start date for the duplicated project (YYYY-MM-DD)"
    )


async def duplicate_project_handler(client, params: dict) -> str:
    """Duplicate a project"""
    from ..utils.formatters import format_project, format_error

    try:
        project_gid = params["project_gid"]
        name = params["name"]
        include = params.get("include")

        schedule_dates = None
        if params.get("schedule_dates_due_on") or params.get("schedule_dates_start_on"):
            schedule_dates = {}
            if params.get("schedule_dates_due_on"):
                schedule_dates["due_on"] = params["schedule_dates_due_on"]
            if params.get("schedule_dates_start_on"):
                schedule_dates["start_on"] = params["schedule_dates_start_on"]

        project = await client.duplicate_project(
            project_gid,
            name,
            include=include,
            schedule_dates=schedule_dates
        )

        return f"Project duplicated successfully!\n\n{format_project(project, detailed=True)}"

    except Exception as e:
        return format_error(e, f"duplicating project {params.get('project_gid')}")


# Tool definitions for Phase 1 project tools

PHASE1_PROJECT_TOOLS = [
    {
        "name": "asana_create_project",
        "description": """Create a new project in a workspace or team.

Projects are containers for tasks and can be visualized as lists or boards.

Required: name, and either workspace or team
Optional: notes, color, dates, visibility settings

Example: Create a project called "Q4 Marketing Campaign" in the Marketing team with a due date.""",
        "inputSchema": CreateProjectInput.model_json_schema(),
        "handler": create_project_handler
    },
    {
        "name": "asana_update_project",
        "description": """Update an existing project's properties.

Can update: name, notes, color, archived status, visibility, dates

Provide only the fields you want to change. Unspecified fields remain unchanged.

Example: Archive a completed project or update the due date.""",
        "inputSchema": UpdateProjectInput.model_json_schema(),
        "handler": update_project_handler
    },
    {
        "name": "asana_delete_project",
        "description": """Delete a project permanently.

This action cannot be undone. The project and all its sections will be deleted.
Tasks in the project will remain but will be removed from this project.

Use with caution. Consider archiving instead for projects you might need later.""",
        "inputSchema": DeleteProjectInput.model_json_schema(),
        "handler": delete_project_handler
    },
    {
        "name": "asana_get_project_task_counts",
        "description": """Get task count statistics for a project.

Returns:
- Total number of tasks
- Number of incomplete tasks
- Number of completed tasks
- Number of milestones
- Completion percentage

Useful for project progress tracking and reporting.""",
        "inputSchema": GetProjectTaskCountsInput.model_json_schema(),
        "handler": get_project_task_counts_handler
    },
    {
        "name": "asana_duplicate_project",
        "description": """Duplicate a project with its structure and optionally its tasks.

Creates a copy of a project including sections, and optionally task properties like notes, assignees, subtasks, dates, dependencies, etc.

Use schedule_dates to shift task dates for the new project.

Perfect for recurring projects or using a project as a template.

Example: Duplicate "Monthly Newsletter" project for next month with new due dates.""",
        "inputSchema": DuplicateProjectInput.model_json_schema(),
        "handler": duplicate_project_handler
    }
]
