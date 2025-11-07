# Asana MCP v1.1.0 - Complete Tool List

## Total: 42 Tools (Parity with Official Asana MCP ✓)

### Task Management (15 tools)
1. **asana_list_workspaces** - List all accessible workspaces
2. **asana_search_tasks** - Search tasks with advanced filters
3. **asana_get_task** - Get detailed task information
4. **asana_get_multiple_tasks_by_gid** - Batch get multiple tasks
5. **asana_create_task** - Create a new task
6. **asana_update_task** - Update existing task
7. **asana_delete_task** ⭐ NEW - Delete a task permanently
8. **asana_duplicate_task** ⭐ NEW - Duplicate task with properties
9. **asana_get_task_stories** - Get task comments/activity
10. **asana_create_task_story** - Add comment to task
11. **asana_get_subtasks** ⭐ NEW - Get all subtasks of a task
12. **asana_get_tasks_from_project** ⭐ NEW - Get all tasks in a project
13. **asana_get_tasks_from_section** ⭐ NEW - Get all tasks in a section
14. **asana_add_followers_to_task** - Add task followers
15. **asana_remove_followers_from_task** - Remove task followers

### Project Management (10 tools)
16. **asana_search_projects** - Search projects in workspace
17. **asana_get_project** - Get project details
18. **asana_create_project** ⭐ NEW - Create new project
19. **asana_update_project** ⭐ NEW - Update project properties
20. **asana_delete_project** ⭐ NEW - Delete a project
21. **asana_duplicate_project** ⭐ NEW - Duplicate project with tasks
22. **asana_get_project_task_counts** ⭐ NEW - Get task count statistics
23. **asana_get_project_sections** - List project sections
24. **asana_get_project_statuses** - Get status updates
25. **asana_create_project_status** - Create status update

### Section Management (5 tools)
26. **asana_create_section** ⭐ NEW - Create section in project
27. **asana_get_section** ⭐ NEW - Get section details
28. **asana_update_section** ⭐ NEW - Update section name
29. **asana_delete_section** ⭐ NEW - Delete a section
30. **asana_add_task_to_section** ⭐ NEW - Move task to section

### Task Relationships (8 tools)
31. **asana_add_task_dependencies** - Add blocking tasks
32. **asana_add_task_dependents** - Add blocked tasks
33. **asana_get_task_dependencies** ⭐ NEW - Get tasks this depends on
34. **asana_get_task_dependents** ⭐ NEW - Get tasks depending on this
35. **asana_remove_task_dependencies** ⭐ NEW - Remove dependencies
36. **asana_remove_task_dependents** ⭐ NEW - Remove dependents
37. **asana_create_subtask** - Create child task
38. **asana_set_parent_for_task** - Convert to subtask

### Task Organization (4 tools)
39. **asana_add_project_to_task** ⭐ NEW - Add task to project
40. **asana_remove_project_from_task** ⭐ NEW - Remove from project
41. **asana_add_tag_to_task** ⭐ NEW - Add tag to task
42. **asana_remove_tag_from_task** ⭐ NEW - Remove tag from task

### Workspace & Tags (2 tools - from original 19)
- **asana_get_tags_for_workspace** - List workspace tags
- **asana_get_tasks_for_tag** - Get tasks by tag

---

## Changes from v1.0.0 → v1.1.0

### Added 23 New Tools:

**Phase 1 (18 tools):**
- Complete CRUD for tasks (delete, duplicate)
- Complete CRUD for projects (create, update, delete, duplicate, task counts)
- Task hierarchy (get_subtasks, get_tasks_from_project/section)
- Dependency viewing (get_task_dependencies, get_task_dependents)
- Task organization (add/remove project, add/remove tag)
- Section creation and task assignment

**Phase 2 (5 tools):**
- Dependency removal (remove_dependencies, remove_dependents)
- Complete section CRUD (get, update, delete)

### Tool Distribution:
- **Original (v1.0.0)**: 19 tools
- **Phase 1 Added**: 18 tools
- **Phase 2 Added**: 5 tools
- **Total (v1.1.0)**: 42 tools ✓

---

## Feature Completeness

✅ **Task Operations**: Full CRUD + Search + Batch + Hierarchy
✅ **Project Operations**: Full CRUD + Search + Sections + Status
✅ **Section Operations**: Full CRUD + Task Assignment
✅ **Dependencies**: Add, Remove, View (both directions)
✅ **Subtasks**: Create, Get, Set Parent
✅ **Tags**: Add, Remove, List, Search
✅ **Comments**: Create, List
✅ **Organization**: Projects, Tags, Sections

---

## API Coverage

This implementation now provides **full parity** with the official Asana MCP (42 tools), covering all essential Asana workflows for task and project management through Claude Code CLI.

Additional API endpoints available for future expansion:
- User management (get users, teams, favorites)
- Attachments (upload, download, delete)
- Portfolios (premium feature)
- Custom fields (premium feature)
- Goals (premium feature)
- Webhooks (real-time notifications)

**Next Release Target (v1.2.0)**: Add user/team management + attachments (8-10 additional tools)
