"""
Phase 2 Additional Tools

Final tools to reach full parity (42 tools) with official Asana MCP.
"""

from typing import Optional
from pydantic import BaseModel, Field


# Remove Task Dependencies

class RemoveDependenciesInput(BaseModel):
    """Input schema for remove_dependencies"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    task_gid: str = Field(
        description="Task GID"
    )
    dependencies: str = Field(
        description="Comma-separated list of dependency task GIDs to remove"
    )


async def remove_dependencies_handler(client, params: dict) -> str:
    """Remove dependencies from a task"""
    from ..utils.formatters import format_error

    try:
        task_gid = params["task_gid"]
        dependencies = params["dependencies"].split(",")
        dependencies = [d.strip() for d in dependencies if d.strip()]

        if not dependencies:
            return "No dependencies provided to remove."

        await client.remove_dependencies(task_gid, dependencies)

        return f"Removed {len(dependencies)} dependenc{'y' if len(dependencies) == 1 else 'ies'} from task {task_gid}."

    except Exception as e:
        return format_error(e, f"removing dependencies from task {params.get('task_gid')}")


# Remove Task Dependents

class RemoveDependentsInput(BaseModel):
    """Input schema for remove_dependents"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    task_gid: str = Field(
        description="Task GID"
    )
    dependents: str = Field(
        description="Comma-separated list of dependent task GIDs to remove"
    )


async def remove_dependents_handler(client, params: dict) -> str:
    """Remove dependents from a task"""
    from ..utils.formatters import format_error

    try:
        task_gid = params["task_gid"]
        dependents = params["dependents"].split(",")
        dependents = [d.strip() for d in dependents if d.strip()]

        if not dependents:
            return "No dependents provided to remove."

        await client.remove_dependents(task_gid, dependents)

        return f"Removed {len(dependents)} dependent{'s' if len(dependents) != 1 else ''} from task {task_gid}."

    except Exception as e:
        return format_error(e, f"removing dependents from task {params.get('task_gid')}")


# Get Section

class GetSectionInput(BaseModel):
    """Input schema for get_section"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    section_gid: str = Field(
        description="Section GID"
    )
    opt_fields: Optional[str] = Field(
        "name,project.name,created_at",
        description="Comma-separated fields to return"
    )


async def get_section_handler(client, params: dict) -> str:
    """Get section details"""
    from ..utils.formatters import format_error

    try:
        section_gid = params["section_gid"]
        opt_fields = params.get("opt_fields")

        section = await client.get_section(section_gid, opt_fields=opt_fields)

        name = section.get("name", "")
        gid = section.get("gid", section_gid)
        project = section.get("project", {})
        project_name = project.get("name", project.get("gid", "Unknown")) if project else "Unknown"
        created_at = section.get("created_at", "")

        lines = [
            f"Section: {name}",
            f"GID: {gid}",
            f"Project: {project_name}",
        ]

        if created_at:
            lines.append(f"Created: {created_at}")

        return "\n".join(lines)

    except Exception as e:
        return format_error(e, f"getting section {params.get('section_gid')}")


# Update Section

class UpdateSectionInput(BaseModel):
    """Input schema for update_section"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    section_gid: str = Field(
        description="Section GID"
    )
    name: str = Field(
        description="New section name"
    )


async def update_section_handler(client, params: dict) -> str:
    """Update a section name"""
    from ..utils.formatters import format_error

    try:
        section_gid = params["section_gid"]
        name = params["name"]

        section = await client.update_section(section_gid, name)

        return f"Section {section_gid} renamed to '{name}'."

    except Exception as e:
        return format_error(e, f"updating section {params.get('section_gid')}")


# Delete Section

class DeleteSectionInput(BaseModel):
    """Input schema for delete_section"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    section_gid: str = Field(
        description="Section GID to delete"
    )


async def delete_section_handler(client, params: dict) -> str:
    """Delete a section"""
    from ..utils.formatters import format_error

    try:
        section_gid = params["section_gid"]
        await client.delete_section(section_gid)

        return f"Section {section_gid} deleted successfully."

    except Exception as e:
        return format_error(e, f"deleting section {params.get('section_gid')}")


# Tool definitions for Phase 2 tools

PHASE2_TOOLS = [
    {
        "name": "asana_remove_task_dependencies",
        "description": """Remove dependencies from a task (unlink tasks that this task depends on).

Use this to remove blocking relationships when dependencies are no longer needed.

Example: Task A no longer depends on Task B after B is complete - remove the dependency to clean up the relationship.""",
        "inputSchema": RemoveDependenciesInput.model_json_schema(),
        "handler": remove_dependencies_handler
    },
    {
        "name": "asana_remove_task_dependents",
        "description": """Remove dependents from a task (unlink tasks that depend on this task).

Use this to remove blocking relationships when dependents are no longer needed.

Example: Task B no longer needs to wait for Task A - remove the dependent relationship.""",
        "inputSchema": RemoveDependentsInput.model_json_schema(),
        "handler": remove_dependents_handler
    },
    {
        "name": "asana_get_section",
        "description": """Get detailed information about a section.

Returns section name, project, and creation details.

Useful for verifying section exists and getting its properties before operations.""",
        "inputSchema": GetSectionInput.model_json_schema(),
        "handler": get_section_handler
    },
    {
        "name": "asana_update_section",
        "description": """Update a section's name.

Use this to rename sections as project workflows evolve.

Example: Rename "To Do" to "Backlog" or "In Progress" to "Active Development".""",
        "inputSchema": UpdateSectionInput.model_json_schema(),
        "handler": update_section_handler
    },
    {
        "name": "asana_delete_section",
        "description": """Delete a section from a project.

This removes the section but does not delete the tasks in it.
Tasks in the deleted section will remain in the project but become unsectioned.

Use with caution. Consider moving tasks to another section first.""",
        "inputSchema": DeleteSectionInput.model_json_schema(),
        "handler": delete_section_handler
    }
]
