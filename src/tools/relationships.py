"""
Task Relationship Tools

MCP tools for managing task dependencies, dependents, and subtasks.
"""

from typing import Optional
from pydantic import BaseModel, Field


class AddDependenciesInput(BaseModel):
    """Input schema for add_dependencies"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    task_gid: str = Field(
        description="Task GID to add dependencies to"
    )
    dependencies: str = Field(
        description="Comma-separated list of task GIDs that this task depends on (blocking tasks)"
    )


class AddDependentsInput(BaseModel):
    """Input schema for add_dependents"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    task_gid: str = Field(
        description="Task GID to add dependents to"
    )
    dependents: str = Field(
        description="Comma-separated list of task GIDs that depend on this task (blocked tasks)"
    )


class CreateSubtaskInput(BaseModel):
    """Input schema for create_subtask"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    parent_gid: str = Field(
        description="Parent task GID"
    )
    name: str = Field(
        description="Subtask name (required)"
    )
    notes: Optional[str] = Field(
        None,
        description="Subtask description/notes"
    )
    assignee: Optional[str] = Field(
        None,
        description="Assignee GID"
    )
    due_on: Optional[str] = Field(
        None,
        description="Due date (YYYY-MM-DD format)"
    )


class SetParentInput(BaseModel):
    """Input schema for set_parent"""
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
    task_gid: str = Field(
        description="Task GID to set parent for"
    )
    parent_gid: str = Field(
        description="Parent task GID"
    )
    insert_after: Optional[str] = Field(
        None,
        description="Insert after this subtask GID (for positioning)"
    )
    insert_before: Optional[str] = Field(
        None,
        description="Insert before this subtask GID (for positioning)"
    )


# Tool handler functions

async def add_dependencies_handler(client, params: dict) -> str:
    """Add dependencies to a task (tasks that must complete before this one)"""
    from ..utils.formatters import format_error

    try:
        task_gid = params["task_gid"]
        dependencies = params["dependencies"].split(",")
        dependencies = [d.strip() for d in dependencies if d.strip()]

        if not dependencies:
            return "⚠️ No dependencies provided. Please specify at least one task GID."

        # Add dependencies
        await client.add_dependencies(task_gid, dependencies)

        dep_count = len(dependencies)
        return f"✅ Added {dep_count} dependenc{'y' if dep_count == 1 else 'ies'} to task {task_gid}.\n\nThis task now depends on (cannot start until these complete):\n" + "\n".join([f"  • {d}" for d in dependencies])

    except Exception as e:
        return format_error(e, f"adding dependencies to task {params.get('task_gid')}")


async def add_dependents_handler(client, params: dict) -> str:
    """Add dependents to a task (tasks that depend on this one completing)"""
    from ..utils.formatters import format_error

    try:
        task_gid = params["task_gid"]
        dependents = params["dependents"].split(",")
        dependents = [d.strip() for d in dependents if d.strip()]

        if not dependents:
            return "⚠️ No dependents provided. Please specify at least one task GID."

        # Add dependents
        await client.add_dependents(task_gid, dependents)

        dep_count = len(dependents)
        return f"✅ Added {dep_count} dependent{'s' if dep_count != 1 else ''} to task {task_gid}.\n\nThese tasks now depend on this task completing:\n" + "\n".join([f"  • {d}" for d in dependents])

    except Exception as e:
        return format_error(e, f"adding dependents to task {params.get('task_gid')}")


async def create_subtask_handler(client, params: dict) -> str:
    """Create a subtask under a parent task"""
    from ..utils.formatters import format_task, format_error

    try:
        parent_gid = params["parent_gid"]

        # Build subtask data
        subtask_data = {"name": params["name"]}

        if params.get("notes"):
            subtask_data["notes"] = params["notes"]
        if params.get("assignee"):
            subtask_data["assignee"] = params["assignee"]
        if params.get("due_on"):
            subtask_data["due_on"] = params["due_on"]

        # Create subtask
        subtask = await client.create_subtask(parent_gid, subtask_data)

        return f"✅ Subtask created successfully under parent task {parent_gid}!\n\n{format_task(subtask, detailed=True)}"

    except Exception as e:
        return format_error(e, f"creating subtask under {params.get('parent_gid')}")


async def set_parent_handler(client, params: dict) -> str:
    """Set a task's parent (convert to subtask)"""
    from ..utils.formatters import format_error

    try:
        task_gid = params["task_gid"]
        parent_gid = params["parent_gid"]
        insert_after = params.get("insert_after")
        insert_before = params.get("insert_before")

        # Set parent
        await client.set_parent(
            task_gid,
            parent_gid,
            insert_after=insert_after,
            insert_before=insert_before
        )

        position_info = ""
        if insert_after:
            position_info = f"\nPositioned after subtask: {insert_after}"
        elif insert_before:
            position_info = f"\nPositioned before subtask: {insert_before}"

        return f"✅ Task {task_gid} is now a subtask of {parent_gid}.{position_info}"

    except Exception as e:
        return format_error(e, f"setting parent for task {params.get('task_gid')}")


# Tool definitions for MCP server registration
RELATIONSHIP_TOOLS = [
    {
        "name": "asana_add_task_dependencies",
        "description": """Add dependencies to a task (tasks that must be completed before this task can start).

Dependencies create a blocking relationship: the dependent task cannot be started until all its dependencies are completed.

Example: Task "Deploy to production" depends on "Run tests" and "Get approval" - those tasks must complete first.

Provide comma-separated list of task GIDs that this task depends on.""",
        "inputSchema": AddDependenciesInput.model_json_schema(),
        "handler": add_dependencies_handler
    },
    {
        "name": "asana_add_task_dependents",
        "description": """Add dependents to a task (tasks that cannot start until this task is completed).

Dependents create a blocking relationship: the dependent tasks are blocked until this task is completed.

Example: Task "Design review" blocks tasks "Implement design" and "Create assets" - they cannot start until design is approved.

Provide comma-separated list of task GIDs that depend on this task.""",
        "inputSchema": AddDependentsInput.model_json_schema(),
        "handler": add_dependents_handler
    },
    {
        "name": "asana_create_subtask",
        "description": """Create a new subtask under a parent task.

Subtasks are child tasks that belong to a parent task. They're useful for breaking down large tasks into smaller actionable items.

Example: Parent task "Implement feature X" has subtasks "Write code", "Write tests", "Update docs".

The subtask inherits the parent's project and workspace automatically.""",
        "inputSchema": CreateSubtaskInput.model_json_schema(),
        "handler": create_subtask_handler
    },
    {
        "name": "asana_set_parent_for_task",
        "description": """Convert an existing task into a subtask by setting its parent.

This allows you to reorganize tasks into parent-child relationships after creation.

Optional: Specify insert_after or insert_before to position the subtask relative to other subtasks.

Example: Convert task "Write documentation" into a subtask of "Complete project" and position it after "Write code".""",
        "inputSchema": SetParentInput.model_json_schema(),
        "handler": set_parent_handler
    }
]
