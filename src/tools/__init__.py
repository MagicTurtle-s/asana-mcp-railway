"""MCP Tools for Asana"""

from .tasks import TASK_TOOLS
from .projects import PROJECT_TOOLS
from .relationships import RELATIONSHIP_TOOLS
from .organization import ORGANIZATION_TOOLS
from .tasks_phase1 import PHASE1_TASK_TOOLS
from .projects_phase1 import PHASE1_PROJECT_TOOLS
from .sections_phase1 import PHASE1_SECTION_TOOLS
from .phase2 import PHASE2_TOOLS

# Combine all tool definitions
ALL_TOOLS = (
    TASK_TOOLS +
    PROJECT_TOOLS +
    RELATIONSHIP_TOOLS +
    ORGANIZATION_TOOLS +
    PHASE1_TASK_TOOLS +
    PHASE1_PROJECT_TOOLS +
    PHASE1_SECTION_TOOLS +
    PHASE2_TOOLS
)

__all__ = ["ALL_TOOLS"]
