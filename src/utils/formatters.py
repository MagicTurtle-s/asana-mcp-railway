"""
Response formatting utilities for MCP tools
"""

from typing import List, Dict, Any, Optional


def format_task(task: Dict[str, Any], detailed: bool = False) -> str:
    """
    Format a single task for LLM consumption.

    Args:
        task: Task data from Asana API
        detailed: Include all available fields

    Returns:
        Formatted task string
    """
    lines = []

    # Header
    name = task.get("name", "Untitled")
    gid = task.get("gid", "")
    lines.append(f"**{name}** (GID: {gid})")

    # Status
    if task.get("completed"):
        lines.append("  ✓ **Completed**")
    else:
        lines.append("  ○ In Progress")

    # Due date
    if task.get("due_on"):
        lines.append(f"  📅 Due: {task['due_on']}")
    elif task.get("due_at"):
        lines.append(f"  📅 Due: {task['due_at']}")

    # Assignee
    if task.get("assignee"):
        assignee_name = task["assignee"].get("name", "Unknown")
        lines.append(f"  👤 Assignee: {assignee_name}")

    # Projects
    if task.get("projects"):
        project_names = [p.get("name", "Unknown") for p in task["projects"]]
        lines.append(f"  📁 Projects: {', '.join(project_names)}")

    # Tags
    if task.get("tags"):
        tag_names = [t.get("name", "Unknown") for t in task["tags"]]
        lines.append(f"  🏷️  Tags: {', '.join(tag_names)}")

    if detailed:
        # Notes
        if task.get("notes"):
            notes = task["notes"][:200]  # Truncate long notes
            if len(task["notes"]) > 200:
                notes += "..."
            lines.append(f"  📝 Notes: {notes}")

        # Created/Modified
        if task.get("created_at"):
            lines.append(f"  ⏰ Created: {task['created_at']}")
        if task.get("modified_at"):
            lines.append(f"  ✏️  Modified: {task['modified_at']}")

        # Custom fields
        if task.get("custom_fields"):
            for field in task["custom_fields"]:
                field_name = field.get("name", "Unknown")
                field_value = field.get("display_value", field.get("text_value", "N/A"))
                lines.append(f"  🔧 {field_name}: {field_value}")

    return "\n".join(lines)


def format_tasks(tasks: List[Dict[str, Any]], detailed: bool = False) -> str:
    """
    Format a list of tasks.

    Args:
        tasks: List of task data from Asana API
        detailed: Include detailed information

    Returns:
        Formatted tasks string
    """
    if not tasks:
        return "No tasks found."

    lines = [f"Found {len(tasks)} task(s):\n"]

    for task in tasks:
        lines.append(format_task(task, detailed=detailed))
        lines.append("")  # Blank line between tasks

    return "\n".join(lines)


def format_project(project: Dict[str, Any], detailed: bool = False) -> str:
    """
    Format a single project.

    Args:
        project: Project data from Asana API
        detailed: Include detailed information

    Returns:
        Formatted project string
    """
    lines = []

    # Header
    name = project.get("name", "Untitled")
    gid = project.get("gid", "")
    lines.append(f"**{name}** (GID: {gid})")

    # Status
    if project.get("archived"):
        lines.append("  🗄️  Archived")
    else:
        lines.append("  📂 Active")

    # Owner
    if project.get("owner"):
        owner_name = project["owner"].get("name", "Unknown")
        lines.append(f"  👤 Owner: {owner_name}")

    # Dates
    if project.get("due_on"):
        lines.append(f"  📅 Due: {project['due_on']}")
    if project.get("start_on"):
        lines.append(f"  🚀 Start: {project['start_on']}")

    # Team
    if project.get("team"):
        team_name = project["team"].get("name", "Unknown")
        lines.append(f"  👥 Team: {team_name}")

    if detailed:
        # Notes
        if project.get("notes"):
            notes = project["notes"][:200]
            if len(project["notes"]) > 200:
                notes += "..."
            lines.append(f"  📝 Notes: {notes}")

        # Metrics
        if project.get("num_tasks") is not None:
            lines.append(f"  📊 Tasks: {project['num_tasks']}")
        if project.get("num_incomplete_tasks") is not None:
            lines.append(f"  ⏳ Incomplete: {project['num_incomplete_tasks']}")

        # Dates
        if project.get("created_at"):
            lines.append(f"  ⏰ Created: {project['created_at']}")
        if project.get("modified_at"):
            lines.append(f"  ✏️  Modified: {project['modified_at']}")

    return "\n".join(lines)


def format_projects(projects: List[Dict[str, Any]], detailed: bool = False) -> str:
    """Format a list of projects"""
    if not projects:
        return "No projects found."

    lines = [f"Found {len(projects)} project(s):\n"]

    for project in projects:
        lines.append(format_project(project, detailed=detailed))
        lines.append("")

    return "\n".join(lines)


def format_workspace(workspace: Dict[str, Any]) -> str:
    """Format a workspace"""
    name = workspace.get("name", "Untitled")
    gid = workspace.get("gid", "")
    return f"**{name}** (GID: {gid})"


def format_workspaces(workspaces: List[Dict[str, Any]]) -> str:
    """Format a list of workspaces"""
    if not workspaces:
        return "No workspaces found."

    lines = [f"Found {len(workspaces)} workspace(s):\n"]
    for ws in workspaces:
        lines.append(format_workspace(ws))

    return "\n".join(lines)


def format_section(section: Dict[str, Any]) -> str:
    """Format a project section"""
    name = section.get("name", "Untitled")
    gid = section.get("gid", "")
    return f"  • **{name}** (GID: {gid})"


def format_sections(sections: List[Dict[str, Any]]) -> str:
    """Format a list of sections"""
    if not sections:
        return "No sections found."

    lines = [f"Found {len(sections)} section(s):\n"]
    for section in sections:
        lines.append(format_section(section))

    return "\n".join(lines)


def format_tag(tag: Dict[str, Any]) -> str:
    """Format a tag"""
    name = tag.get("name", "Untitled")
    gid = tag.get("gid", "")
    color = tag.get("color", "")
    color_emoji = "🏷️"
    if color:
        color_map = {
            "red": "🔴",
            "orange": "🟠",
            "yellow": "🟡",
            "green": "🟢",
            "blue": "🔵",
            "purple": "🟣"
        }
        color_emoji = color_map.get(color, "🏷️")
    return f"  {color_emoji} **{name}** (GID: {gid})"


def format_tags(tags: List[Dict[str, Any]]) -> str:
    """Format a list of tags"""
    if not tags:
        return "No tags found."

    lines = [f"Found {len(tags)} tag(s):\n"]
    for tag in tags:
        lines.append(format_tag(tag))

    return "\n".join(lines)


def format_story(story: Dict[str, Any]) -> str:
    """Format a task story (comment/activity)"""
    story_type = story.get("type", "comment")
    created_at = story.get("created_at", "")
    created_by = story.get("created_by", {}).get("name", "Unknown")
    text = story.get("text", "")

    if story_type == "comment":
        return f"💬 **{created_by}** ({created_at}):\n   {text}"
    else:
        return f"📌 **{created_by}** {text} ({created_at})"


def format_stories(stories: List[Dict[str, Any]]) -> str:
    """Format a list of stories"""
    if not stories:
        return "No activity found."

    lines = [f"Found {len(stories)} activity item(s):\n"]
    for story in stories:
        lines.append(format_story(story))
        lines.append("")

    return "\n".join(lines)


def format_error(error: Exception, context: str = "") -> str:
    """
    Format an error for user-friendly display.

    Args:
        error: The exception
        context: Additional context about what was being attempted

    Returns:
        Formatted error message
    """
    from ..asana_client import RateLimitError, AsanaAPIError
    from ..oauth import AuthenticationError

    if isinstance(error, RateLimitError):
        return f"⚠️ Rate limit exceeded. Please wait {error.retry_after} seconds and try again."

    if isinstance(error, AuthenticationError):
        return f"🔒 Authentication error: {str(error)}. Please re-authenticate with Asana."

    if isinstance(error, AsanaAPIError):
        error_messages = {
            400: "Bad Request - Please check your parameters.",
            401: "Unauthorized - Your session has expired. Please re-authenticate.",
            403: "Forbidden - You don't have permission to access this resource.",
            404: "Not Found - The requested resource doesn't exist.",
            424: "Failed Dependency - A related operation failed.",
            500: "Asana Server Error - Please try again later.",
            503: "Service Unavailable - Asana may be under maintenance."
        }

        base_msg = error_messages.get(error.status_code, f"API Error ({error.status_code})")
        detail = str(error)

        if context:
            return f"❌ {context}: {base_msg}\nDetails: {detail}"
        return f"❌ {base_msg}\nDetails: {detail}"

    # Generic error
    if context:
        return f"❌ Error {context}: {str(error)}"
    return f"❌ Error: {str(error)}"


def truncate_text(text: str, max_length: int = 500) -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text with ellipsis if needed
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
