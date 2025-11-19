"""
Phase 1 Additional Section Tools

New section management tools for parity with official Asana MCP.
"""

from typing import Optional
from pydantic import BaseModel, Field


# Create Section

class CreateSectionInput(BaseModel):
    """Input schema for create_section"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    project_gid: str = Field(
        description="Project GID to create section in"
    )
    name: str = Field(
        description="Section name (required)"
    )
    insert_after: Optional[str] = Field(
        None,
        description="Section GID to insert after (for positioning)"
    )
    insert_before: Optional[str] = Field(
        None,
        description="Section GID to insert before (for positioning)"
    )


async def create_section_handler(client, params: dict) -> str:
    """Create a section in a project"""
    from ..utils.formatters import format_error

    try:
        project_gid = params["project_gid"]
        name = params["name"]

        section = await client.create_section(project_gid, name)

        section_gid = section.get("gid", "")
        section_name = section.get("name", name)

        return f"Section created successfully!\n\nGID: {section_gid}\nName: {section_name}\nProject: {project_gid}"

    except Exception as e:
        return format_error(e, f"creating section in project {params.get('project_gid')}")


# Add Task to Section

class AddTaskToSectionInput(BaseModel):
    """Input schema for add_task_to_section"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    section_gid: str = Field(
        description="Section GID"
    )
    task_gid: str = Field(
        description="Task GID to add to section"
    )
    insert_after: Optional[str] = Field(
        None,
        description="Task GID to insert after (for positioning)"
    )
    insert_before: Optional[str] = Field(
        None,
        description="Task GID to insert before (for positioning)"
    )


async def add_task_to_section_handler(client, params: dict) -> str:
    """Add a task to a section"""
    from ..utils.formatters import format_error

    try:
        section_gid = params["section_gid"]
        task_gid = params["task_gid"]
        insert_after = params.get("insert_after")
        insert_before = params.get("insert_before")

        await client.add_task_to_section(
            section_gid,
            task_gid,
            insert_after=insert_after,
            insert_before=insert_before
        )

        msg = f"Task {task_gid} added to section {section_gid}"
        if insert_after:
            msg += f" after task {insert_after}"
        elif insert_before:
            msg += f" before task {insert_before}"
        msg += "."

        return msg

    except Exception as e:
        return format_error(e, f"adding task to section {params.get('section_gid')}")


# Tool definitions for Phase 1 section tools

PHASE1_SECTION_TOOLS = [
    {
        "name": "asana_create_section",
        "description": """Create a new section in a project.

Sections organize tasks within a project. They appear as:
- Headers in list view (e.g., "To Do", "In Progress", "Done")
- Columns in board view

Use insert_after or insert_before to position the section relative to existing sections.

Example: Create "Backlog" section at the beginning of a project.""",
        "inputSchema": CreateSectionInput.model_json_schema(),
        "handler": create_section_handler
    },
    {
        "name": "asana_add_task_to_section",
        "description": """Move or add a task to a specific section within a project.

This changes which section contains the task, effectively moving it between workflow stages.

Use insert_after or insert_before to position the task relative to other tasks in the section.

Essential for kanban/board workflows where tasks move between columns.

Example: Move task from "To Do" to "In Progress" section.""",
        "inputSchema": AddTaskToSectionInput.model_json_schema(),
        "handler": add_task_to_section_handler
    }
]
