---
name: asana-mcp-field-guide
description: Execution-ready reference for Asana MCP operations optimized for minimal context bloat and maximum query efficiency. Use when performing Asana task searches, project discovery, custom field queries, or date range filtering to ensure optimal API usage and token efficiency.
---

# Asana MCP Field Guide for Claude Code

**Purpose:** Execution-ready reference for Asana MCP operations optimized for minimal context bloat and maximum query efficiency.

---

## Quick Decision Tree

```
USER REQUEST → Identify Intent → Select Approach

├─ "Find [object]" / "Get ID for..."
│  └─ ALWAYS: asana_typeahead_search → Never skip this step
│
├─ "Show tasks in [project/section]" (single filter)
│  └─ Use: asana_get_tasks with workspace + single filter
│
├─ "Find tasks that..." (multiple criteria/dates)
│  └─ Use: asana_search_tasks with bounded parameters
│
└─ "Tell me about [specific task]" (after getting GID)
   └─ Use: asana_get_task with minimal opt_fields
```

**Critical Rule:** Discovery = typeahead first. Detail = get/search second.

---

## Field Selection Matrix

### By Query Intent

| Intent | Fields Required | Example Query |
|--------|----------------|---------------|
| **Count/Existence** | `gid,name` | "How many overdue tasks?" |
| **List View** | `gid,name,assignee.name,due_on,completed,projects.name` | "Show Andrea's tasks" |
| **Context/Detail** | Add `notes,memberships.section.name` | "What's blocking X?" |
| **Custom Fields** | `gid,name,custom_fields.(name\|display_value)` | "What's the status?" |

### Token Impact by Field Choice

```
Minimal (gid,name):
  → 100 tasks = ~3K tokens

Standard List View (assignee,due,projects):
  → 100 tasks = ~8K tokens

With Notes:
  → 100 tasks = ~15K tokens

Full custom_fields (NEVER DO):
  → 100 tasks = ~200K tokens (enum definitions per task)
```

**Performance Gain:** Filtered custom_fields reduces response 30-50x.

---

## Date Range Patterns (Critical)

### The Core Principle
**Always define BOTH boundaries for ranges.** Single boundary = all historical data.

```python
# ❌ WRONG - Returns ALL overdue tasks ever created
due_on_before: "2025-11-08"

# ✅ RIGHT - Returns overdue from last 30 days
due_on_after: "2025-10-09"
due_on_before: "2025-11-08"
```

### Common Scenarios

**Overdue (Last 30 Days):**
```
completed: false
due_on_after: [today - 30]
due_on_before: [today]
```

**Due This Week:**
```
completed: false
due_on_after: [week_start]
due_on_before: [week_end]
```

**Recently Completed:**
```
completed: true
completed_at_after: [today - 7]
sort_by: "completed_at"
sort_ascending: false
```

---

## Custom Field Handling

### The Problem
Requesting `custom_fields` without filtering returns:
- All enum option definitions (colors, enabled status)
- Creator metadata, resource types
- 30-50 lines per field × multiple fields = 200+ lines of bloat

### The Solutions

```python
# For lists (don't need values)
opt_fields: "gid,name,assignee.name,due_on"
# Omit custom_fields entirely

# For values (need specific data)
opt_fields: "gid,name,custom_fields.(name|display_value)"
# Only name and current value

# For project setup (one-time discovery)
# Fetch project once, extract field GIDs
# Store in memory/notes for future use
```

---

## Query Templates

### Template: Workload Check
**Use:** Before assigning new work
```python
asana_search_tasks(
    workspace_gid="[stored_id]",
    assignee_any=["user_gid"],
    completed=False,
    due_on_after="[today]",
    due_on_before="[today+7d]",
    opt_fields="gid,name,due_on,projects.name"
)
```

### Template: Priority List
**Use:** Daily task review
```python
asana_search_tasks(
    workspace_gid="[stored_id]",
    assignee_any=["user_gid"],
    completed=False,
    due_on_before="[today+7d]",
    sort_by="due_date",
    opt_fields="gid,name,due_on,projects.name"
)
```

### Template: Overdue Analysis
**Use:** Finding stalled work
```python
asana_search_tasks(
    workspace_gid="[stored_id]",
    completed=False,
    due_on_after="[today-30d]",  # ← CRITICAL
    due_on_before="[today]",
    sort_by="due_date",
    opt_fields="gid,name,assignee.name,due_on,projects.name"
)
```

### Template: Milestone Review
**Use:** Project progress check
```python
asana_search_tasks(
    workspace_gid="[stored_id]",
    projects_any=["project_gid"],
    resource_subtype="milestone",
    completed_at_after="[today-90d]",
    sort_by="completed_at",
    sort_ascending=False,
    opt_fields="gid,name,due_on,completed_at"
)
```

### Template: Project Discovery
**Use:** Finding client projects
```python
# Step 1: Discovery
asana_typeahead_search(
    query="project_keyword",
    resource_type="project",
    workspace_gid="[stored_id]"
)

# Step 2: Details
asana_get_project(
    project_id="[from_step1]",
    opt_fields="name,owner.name,notes"  # NOT custom_fields
)

# Step 3: Structure
asana_get_project_sections(
    project_id="[from_step1]"
)
```

---

## API Limitations

### Cannot Do Via API
- ❌ Create sections → Manual UI required
- ❌ Delete projects → Manual UI required
- ❌ Create automations/rules → Manual UI required
- ❌ Filter by custom field values → Fetch and filter in code

### Response Pattern
When user requests impossible operation:
1. State limitation immediately
2. Offer concrete workaround
3. Don't attempt failed API call
4. Provide manual steps if needed

**Example:** "Section creation isn't available via API. Options: (1) Create sections in Asana UI, then I'll populate them, or (2) Create tasks now, you organize sections later."

---

## Anti-Patterns (What NOT To Do)

| ❌ Anti-Pattern | ✅ Correct Approach |
|----------------|---------------------|
| `custom_fields` without filtering | `custom_fields.(name\|display_value)` |
| `due_on_before: today` (no after) | Both `due_on_after` AND `due_on_before` |
| Including `notes` in list queries | Reserve `notes` for detail queries |
| 15 individual `get_task` calls | 1 optimized `search_tasks` |
| Skipping typeahead for discovery | ALWAYS typeahead → then detail |
| Forgetting workspace_gid | Store and apply automatically |

---

## Common Errors & Fixes

### Error: Query returns too many old tasks
**Cause:** Missing `due_on_after` or `created_at_after`
**Fix:** Add both boundaries for date ranges

### Error: Response is 200K+ tokens
**Cause:** Fetching `custom_fields` without filtering
**Fix:** Use `custom_fields.(name|display_value)` or omit entirely

### Error: Can't find project by name
**Cause:** Using `search_tasks` with text query instead of typeahead
**Fix:** Use `asana_typeahead_search` first

### Error: Section creation fails
**Cause:** API limitation - sections can't be created programmatically
**Fix:** Inform user, offer manual creation or milestone workaround

---

## Optimization Benchmarks

Based on observed patterns:

| Operation | Inefficient | Optimized | Savings |
|-----------|-------------|-----------|---------|
| List 100 tasks | Full custom_fields | Filtered fields | 30-50x tokens |
| Overdue search | No date window | 30-day window | 10-100x fewer results |
| Project discovery | search_tasks text | typeahead → get | 2-3x faster |
| Workload check | Individual gets | Single search | N queries → 1 query |

**Rule of Thumb:** Every unfiltered custom_field adds 30-50 lines. Every missing date boundary adds hundreds of irrelevant results.

---

## Response Structure Guidelines

### For Task Lists
```
Summary: [count] tasks found
├─ Group by assignee/status/project
├─ Show minimal fields: name, assignee, due_on
└─ Include task links: https://app.asana.com/0/0/[gid]
```

### For Task Details
```
Current State: [status summary]
├─ Assignee: [name]
├─ Due: [date]
├─ Blockers: [dependencies if any]
└─ Link: [task_url]
```

### For Analysis
```
Key Finding: [insight - who/what/why]
├─ Supporting data: [relevant metrics]
└─ Skip: Fields that don't support the finding
```

---

## Memory Integration

### What to Store
- Custom field GIDs (for reuse)
- Workspace/user IDs
- Project naming patterns
- Successful query patterns

### What NOT to Store
- Query syntax (use this guide)
- Temporary task GIDs
- One-time data

### Check Memory First
Before any query:
1. Search for stored field GIDs
2. Apply workspace ID automatically
3. Use known optimization patterns

---

## Pre-Query Checklist

Before executing ANY Asana query:

- [ ] Using typeahead for discovery?
- [ ] Fields match query intent (count vs list vs detail)?
- [ ] Date ranges have BOTH boundaries?
- [ ] Custom fields filtered or omitted?
- [ ] Workspace ID included?
- [ ] Could this be batched?

---

## When to Reference This Guide

**Always before:**
- Multi-filter search_tasks queries
- Date range queries
- Project-level data retrieval
- Unsure which tool to use

**Quick reference for:**
- "What fields minimize bloat?"
- "How do I filter dates correctly?"
- "Why is response huge?"
- "Can I do X via API?"

---

## Key Takeaways

1. **Discovery pattern:** typeahead → get/search → detail
2. **Date ranges:** ALWAYS both `after` and `before`
3. **Custom fields:** NEVER unfiltered, use `.(name|display_value)`
4. **Field selection:** Match intent (count ≠ list ≠ detail)
5. **API limits:** Know what can't be done, offer alternatives
6. **Performance:** Minimal fields = 30-50x token reduction

**Bottom Line:** Optimization isn't about clever tricks—it's about systematically applying field filtering and date boundaries to every query.
