"""
Phase 1 Additional Task Tools

New tools to reach parity with official Asana MCP.
"""

from typing import Optional
from pydantic import BaseModel, Field


# Delete Task

class DeleteTaskInput(BaseModel):
    """Input schema for delete_task"""
    task_gid: str = Field(
        description="Task GID to delete"
    )


async def delete_task_handler(client, params: dict) -> str:
    """Delete a task"""
    from ..utils.formatters import format_error

    try:
        task_gid = params["task_gid"]
        await client.delete_task(task_gid)
        return f"Task {task_gid} deleted successfully."

    except Exception as e:
        return format_error(e, f"deleting task {params.get('task_gid')}")


# Duplicate Task

class DuplicateTaskInput(BaseModel):
    """Input schema for duplicate_task"""
    task_gid: str = Field(
        description="Task GID to duplicate"
    )
    name: Optional[str] = Field(
        None,
        description="Name for duplicated task (default: 'Copy of [original name]')"
    )
    include: Optional[str] = Field(
        "notes,assignee,subtasks,tags,followers,projects,dates",
        description="Comma-separated fields to include (notes,assignee,subtasks,attachments,tags,followers,projects,dates)"
    )


async def duplicate_task_handler(client, params: dict) -> str:
    """Duplicate a task"""
    from ..utils.formatters import format_task, format_error

    try:
        task_gid = params["task_gid"]
        name = params.get("name")
        include = params.get("include")

        task = await client.duplicate_task(task_gid, include=include, name=name)
        return f"Task duplicated successfully!\n\n{format_task(task, detailed=True)}"

    except Exception as e:
        return format_error(e, f"duplicating task {params.get('task_gid')}")


# Get Subtasks

class GetSubtasksInput(BaseModel):
    """Input schema for get_subtasks"""
    task_gid: str = Field(
        description="Task GID to get subtasks for"
    )
    opt_fields: Optional[str] = Field(
        "name,completed,due_on,assignee.name",
        description="Comma-separated fields to return"
    )


async def get_subtasks_handler(client, params: dict) -> str:
    """Get subtasks of a task"""
    from ..utils.formatters import format_tasks, format_error

    try:
        task_gid = params["task_gid"]
        opt_fields = params.get("opt_fields")

        subtasks = await client.get_subtasks(task_gid, opt_fields=opt_fields)

        if not subtasks:
            return f"No subtasks found for task {task_gid}."

        return f"Found {len(subtasks)} subtask(s):\n\n{format_tasks(subtasks, detailed=False)}"

    except Exception as e:
        return format_error(e, f"getting subtasks for task {params.get('task_gid')}")


# Get Tasks from Project

class GetTasksFromProjectInput(BaseModel):
    """Input schema for get_tasks_from_project"""
    project_gid: str = Field(
        description="Project GID to get tasks from"
    )
    completed_since: Optional[str] = Field(
        None,
        description="Only tasks completed after this date (ISO 8601)"
    )
    opt_fields: Optional[str] = Field(
        "name,completed,due_on,assignee.name",
        description="Comma-separated fields to return"
    )


async def get_tasks_from_project_handler(client, params: dict) -> str:
    """Get all tasks in a project"""
    from ..utils.formatters import format_tasks, format_error

    try:
        project_gid = params["project_gid"]

        query_params = {}
        if params.get("completed_since"):
            query_params["completed_since"] = params["completed_since"]
        if params.get("opt_fields"):
            query_params["opt_fields"] = params["opt_fields"]

        tasks = await client.get_tasks_from_project(project_gid, params=query_params)

        if not tasks:
            return f"No tasks found in project {project_gid}."

        return f"Found {len(tasks)} task(s) in project:\n\n{format_tasks(tasks, detailed=False)}"

    except Exception as e:
        return format_error(e, f"getting tasks from project {params.get('project_gid')}")


# Get Tasks from Section

class GetTasksFromSectionInput(BaseModel):
    """Input schema for get_tasks_from_section"""
    section_gid: str = Field(
        description="Section GID to get tasks from"
    )
    opt_fields: Optional[str] = Field(
        "name,completed,due_on,assignee.name",
        description="Comma-separated fields to return"
    )


async def get_tasks_from_section_handler(client, params: dict) -> str:
    """Get all tasks in a section"""
    from ..utils.formatters import format_tasks, format_error

    try:
        section_gid = params["section_gid"]
        opt_fields = params.get("opt_fields")

        tasks = await client.get_tasks_from_section(section_gid, opt_fields=opt_fields)

        if not tasks:
            return f"No tasks found in section {section_gid}."

        return f"Found {len(tasks)} task(s) in section:\n\n{format_tasks(tasks, detailed=False)}"

    except Exception as e:
        return format_error(e, f"getting tasks from section {params.get('section_gid')}")


# Get Task Dependencies

class GetTaskDependenciesInput(BaseModel):
    """Input schema for get_task_dependencies"""
    task_gid: str = Field(
        description="Task GID to get dependencies for"
    )
    opt_fields: Optional[str] = Field(
        "name,completed,due_on,assignee.name",
        description="Comma-separated fields to return"
    )


async def get_task_dependencies_handler(client, params: dict) -> str:
    """Get dependencies of a task (tasks this task depends on)"""
    from ..utils.formatters import format_tasks, format_error

    try:
        task_gid = params["task_gid"]
        opt_fields = params.get("opt_fields")

        dependencies = await client.get_task_dependencies(task_gid, opt_fields=opt_fields)

        if not dependencies:
            return f"Task {task_gid} has no dependencies."

        return f"Task {task_gid} depends on {len(dependencies)} task(s) (must complete before this can start):\n\n{format_tasks(dependencies, detailed=False)}"

    except Exception as e:
        return format_error(e, f"getting dependencies for task {params.get('task_gid')}")


# Get Task Dependents

class GetTaskDependentsInput(BaseModel):
    """Input schema for get_task_dependents"""
    task_gid: str = Field(
        description="Task GID to get dependents for"
    )
    opt_fields: Optional[str] = Field(
        "name,completed,due_on,assignee.name",
        description="Comma-separated fields to return"
    )


async def get_task_dependents_handler(client, params: dict) -> str:
    """Get dependents of a task (tasks that depend on this task)"""
    from ..utils.formatters import format_tasks, format_error

    try:
        task_gid = params["task_gid"]
        opt_fields = params.get("opt_fields")

        dependents = await client.get_task_dependents(task_gid, opt_fields=opt_fields)

        if not dependents:
            return f"No tasks depend on task {task_gid}."

        return f"{len(dependents)} task(s) depend on task {task_gid} (blocked until this completes):\n\n{format_tasks(dependents, detailed=False)}"

    except Exception as e:
        return format_error(e, f"getting dependents for task {params.get('task_gid')}")


# Add Project to Task

class AddProjectToTaskInput(BaseModel):
    """Input schema for add_project_to_task"""
    task_gid: str = Field(
        description="Task GID"
    )
    project_gid: str = Field(
        description="Project GID to add task to"
    )
    section: Optional[str] = Field(
        None,
        description="Section GID to add task to within the project"
    )
    insert_after: Optional[str] = Field(
        None,
        description="Task GID to insert after (for positioning)"
    )
    insert_before: Optional[str] = Field(
        None,
        description="Task GID to insert before (for positioning)"
    )


async def add_project_to_task_handler(client, params: dict) -> str:
    """Add a task to a project"""
    from ..utils.formatters import format_error

    try:
        task_gid = params["task_gid"]
        project_gid = params["project_gid"]
        section = params.get("section")
        insert_after = params.get("insert_after")
        insert_before = params.get("insert_before")

        await client.add_project_to_task(
            task_gid,
            project_gid,
            section=section,
            insert_after=insert_after,
            insert_before=insert_before
        )

        msg = f"Task {task_gid} added to project {project_gid}"
        if section:
            msg += f" in section {section}"
        msg += "."

        return msg

    except Exception as e:
        return format_error(e, f"adding project to task {params.get('task_gid')}")


# Remove Project from Task

class RemoveProjectFromTaskInput(BaseModel):
    """Input schema for remove_project_from_task"""
    task_gid: str = Field(
        description="Task GID"
    )
    project_gid: str = Field(
        description="Project GID to remove task from"
    )


async def remove_project_from_task_handler(client, params: dict) -> str:
    """Remove a task from a project"""
    from ..utils.formatters import format_error

    try:
        task_gid = params["task_gid"]
        project_gid = params["project_gid"]

        await client.remove_project_from_task(task_gid, project_gid)
        return f"Task {task_gid} removed from project {project_gid}."

    except Exception as e:
        return format_error(e, f"removing project from task {params.get('task_gid')}")


# Add Tag to Task

class AddTagToTaskInput(BaseModel):
    """Input schema for add_tag_to_task"""
    task_gid: str = Field(
        description="Task GID"
    )
    tag_gid: str = Field(
        description="Tag GID to add to task"
    )


async def add_tag_to_task_handler(client, params: dict) -> str:
    """Add a tag to a task"""
    from ..utils.formatters import format_error

    try:
        task_gid = params["task_gid"]
        tag_gid = params["tag_gid"]

        await client.add_tag_to_task(task_gid, tag_gid)
        return f"Tag {tag_gid} added to task {task_gid}."

    except Exception as e:
        return format_error(e, f"adding tag to task {params.get('task_gid')}")


# Remove Tag from Task

class RemoveTagFromTaskInput(BaseModel):
    """Input schema for remove_tag_from_task"""
    task_gid: str = Field(
        description="Task GID"
    )
    tag_gid: str = Field(
        description="Tag GID to remove from task"
    )


async def remove_tag_from_task_handler(client, params: dict) -> str:
    """Remove a tag from a task"""
    from ..utils.formatters import format_error

    try:
        task_gid = params["task_gid"]
        tag_gid = params["tag_gid"]

        await client.remove_tag_from_task(task_gid, tag_gid)
        return f"Tag {tag_gid} removed from task {task_gid}."

    except Exception as e:
        return format_error(e, f"removing tag from task {params.get('task_gid')}")


# Tool definitions for Phase 1 task tools

PHASE1_TASK_TOOLS = [
    {
        "name": "asana_delete_task",
        "description": "Delete a task permanently. This action cannot be undone. The task will be removed from all projects and the workspace.",
        "inputSchema": DeleteTaskInput.model_json_schema(),
        "handler": delete_task_handler
    },
    {
        "name": "asana_duplicate_task",
        "description": """Duplicate a task with its properties.

By default includes: notes, assignee, subtasks, tags, followers, projects, and dates.
You can customize what to include with the 'include' parameter.

The duplicated task gets a default name of 'Copy of [original name]' unless you specify a custom name.

Useful for creating template tasks or repeating similar work.""",
        "inputSchema": DuplicateTaskInput.model_json_schema(),
        "handler": duplicate_task_handler
    },
    {
        "name": "asana_get_subtasks",
        "description": "Get all subtasks of a task. Subtasks are child tasks that help break down large tasks into smaller actionable items. Returns list of subtasks with their details.",
        "inputSchema": GetSubtasksInput.model_json_schema(),
        "handler": get_subtasks_handler
    },
    {
        "name": "asana_get_tasks_from_project",
        "description": """Get all tasks in a project.

Returns all tasks associated with the project, regardless of section or completion status.
Use completed_since to filter for recently completed tasks.

Essential for viewing project contents and tracking progress.""",
        "inputSchema": GetTasksFromProjectInput.model_json_schema(),
        "handler": get_tasks_from_project_handler
    },
    {
        "name": "asana_get_tasks_from_section",
        "description": """Get all tasks in a specific section.

Sections organize tasks within a project (e.g., 'To Do', 'In Progress', 'Done').
Use this to view tasks in a specific workflow stage.

Essential for board/kanban views and workflow management.""",
        "inputSchema": GetTasksFromSectionInput.model_json_schema(),
        "handler": get_tasks_from_section_handler
    },
    {
        "name": "asana_get_task_dependencies",
        "description": """Get tasks that this task depends on (blocking tasks).

Dependencies are tasks that must be completed before this task can start.
Use this to understand what's blocking a task from starting.

Example: If task A depends on tasks B and C, this returns B and C.""",
        "inputSchema": GetTaskDependenciesInput.model_json_schema(),
        "handler": get_task_dependencies_handler
    },
    {
        "name": "asana_get_task_dependents",
        "description": """Get tasks that depend on this task (blocked tasks).

Dependents are tasks that cannot start until this task is completed.
Use this to understand what tasks are waiting on this one.

Example: If tasks B and C depend on task A, this returns B and C when called on A.""",
        "inputSchema": GetTaskDependentsInput.model_json_schema(),
        "handler": get_task_dependents_handler
    },
    {
        "name": "asana_add_project_to_task",
        "description": """Add a task to a project.

Tasks can belong to multiple projects. Use this to add a task to an additional project.
Optionally specify which section within the project to add it to.

Example: Add a task to both 'Engineering' and 'Marketing' projects.""",
        "inputSchema": AddProjectToTaskInput.model_json_schema(),
        "handler": add_project_to_task_handler
    },
    {
        "name": "asana_remove_project_from_task",
        "description": """Remove a task from a project.

If the task belongs to multiple projects, this removes it from just the specified project.
If it's the task's only project, consider deleting the task instead.

Example: Remove a task from 'Archive' project while keeping it in 'Active Work'.""",
        "inputSchema": RemoveProjectFromTaskInput.model_json_schema(),
        "handler": remove_project_from_task_handler
    },
    {
        "name": "asana_add_tag_to_task",
        "description": """Add a tag to a task for categorization.

Tags are labels for organizing tasks across projects (e.g., 'urgent', 'bug', 'documentation').
Tasks can have multiple tags.

Example: Tag a task as both 'high-priority' and 'customer-facing'.""",
        "inputSchema": AddTagToTaskInput.model_json_schema(),
        "handler": add_tag_to_task_handler
    },
    {
        "name": "asana_remove_tag_from_task",
        "description": """Remove a tag from a task.

Removes the tag classification without affecting the task's other tags or properties.

Example: Remove 'in-review' tag after review is complete.""",
        "inputSchema": RemoveTagFromTaskInput.model_json_schema(),
        "handler": remove_tag_from_task_handler
    }
]
