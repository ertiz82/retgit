# Scout Integration

AI-powered project analysis, planning, and task management integration. Scout analyzes your codebase, generates development plans, manages teams, and syncs tasks to your task management system.

## Installation

```bash
rg integration install scout
```

## Configuration

```yaml
# .redgit/config.yaml
active:
  task_management: jira  # Scout syncs to active task management

integrations:
  scout:
    model: gpt-4          # AI model for analysis
    auto_analyze: false   # Auto-analyze on propose
    cache_analysis: true  # Cache analysis results
    sync_strategy: full   # full | structure | incremental
```

## Environment Variables

```bash
# Required (one of these)
export OPENAI_API_KEY="your-api-key"
# or
export ANTHROPIC_API_KEY="your-api-key"
```

## CLI Commands

### Analysis Commands

```bash
# Analyze current codebase
rg scout analyze

# Show cached analysis
rg scout show

# Force fresh analysis
rg scout analyze --force
```

### Planning Commands

```bash
# Generate development plan
rg scout plan

# Generate plan with team assignments
rg scout plan --with-team

# Plan specific feature
rg scout plan "Add user authentication"

# Output:
# Development Plan
# ================
# Phase 1: Foundation (8 tasks)
#   EPIC: Authentication System
#     STORY: User Registration [8h] -> Ahmet (backend)
#     STORY: User Login [5h] -> Ahmet (backend)
#     STORY: Password Reset [3h] -> Ayse (fullstack)
# ...
```

### Team Commands

```bash
# Show team configuration
rg scout team

# Output:
# Team Configuration
# ==================
# Members (4):
#   Ahmet Yilmaz (senior)
#     Skills: python(expert), django(advanced), react(intermediate)
#     Areas: backend, api
#     Capacity: 6h/day
#
#   Ayse Demir (mid)
#     Skills: react(expert), typescript(expert), css(advanced)
#     Areas: frontend, ui
#     Capacity: 8h/day
# ...

# Initialize team from Jira
rg scout team-init

# Output:
# Fetching users from Jira...
# Found 8 active users
#
# Configure skills for each member:
# [1/8] Ahmet Yilmaz
#   Skills (comma-separated, e.g., python:expert,react:intermediate): python:expert,django:advanced
#   Areas (comma-separated): backend,api
#   Daily capacity (hours): 6
# ...
# Team configuration saved to .redgit/team.yaml
```

### Assignment Commands

```bash
# Preview task assignments
rg scout assign

# Output:
# Task Assignments (Preview)
# ==========================
# Based on skills and workload:
#
# PROJ-101 [Login API] -> Ahmet Yilmaz
#   Reason: Expert in python, backend area
#
# PROJ-102 [Login UI] -> Ayse Demir
#   Reason: Expert in react, frontend area
#
# PROJ-103 [Database Schema] -> Mehmet Kaya
#   Reason: Available capacity, intermediate in postgresql
#
# Apply these assignments? [y/N]
```

### Timeline Commands

```bash
# Show project timeline
rg scout timeline

# Output:
# Project Timeline
# ================
# Total: 156 hours across 4 members
# Estimated: 5.2 days (parallel work)
#
# By Member:
#   Ahmet Yilmaz: 48h (8.0 days at 6h/day)
#   Ayse Demir: 40h (5.0 days at 8h/day)
#   Mehmet Kaya: 36h (4.5 days at 8h/day)
#   Zeynep Oz: 32h (4.0 days at 8h/day)
#
# Bottleneck: Ahmet Yilmaz (backend tasks)
# Recommendation: Consider parallelizing backend work
```

### Sprint Planning

```bash
# Plan sprints based on capacity
rg scout sprints

# Output:
# Sprint Planning
# ===============
# Sprint duration: 14 days
# Team capacity: 280h per sprint
#
# Sprint 1 (280h):
#   - EPIC-1: Authentication System
#     - STORY-1: User Registration
#     - STORY-2: User Login
#   - EPIC-2: Profile Management (partial)
#
# Sprint 2 (260h):
#   - EPIC-2: Profile Management (remaining)
#   - EPIC-3: Dashboard
# ...

# Custom sprint duration
rg scout sprints --duration 7  # 1-week sprints
```

### Sync Commands

```bash
# Sync plan to task management
rg scout sync

# Sync with specific strategy
rg scout sync --strategy full        # Full hierarchy + links + assignments
rg scout sync --strategy structure   # Only issue hierarchy
rg scout sync --strategy incremental # Only new/changed tasks

# Sync and add to sprint
rg scout sync --sprint 123           # Specific sprint ID
rg scout sync --sprint active        # Current active sprint
```

## Team Configuration

### File Location

Team configuration is stored in `.redgit/team.yaml`:

```yaml
members:
  - name: "Ahmet Yilmaz"
    account_id: "5f9a8b7c6d5e4f3a2b1c0d9e"  # Jira account ID
    role: "senior"
    capacity: 6  # hours per day
    skills:
      python: expert
      django: advanced
      react: intermediate
      postgresql: advanced
    areas:
      - backend
      - api
      - database

  - name: "Ayse Demir"
    account_id: "5f9a8b7c6d5e4f3a2b1c0d9f"
    role: "mid"
    capacity: 8
    skills:
      react: expert
      typescript: expert
      css: advanced
      nextjs: intermediate
    areas:
      - frontend
      - ui

  - name: "Mehmet Kaya"
    account_id: "5f9a8b7c6d5e4f3a2b1c0da0"
    role: "junior"
    capacity: 8
    skills:
      python: intermediate
      javascript: intermediate
      postgresql: beginner
    areas:
      - backend
      - frontend

  - name: "Zeynep Oz"
    account_id: "5f9a8b7c6d5e4f3a2b1c0da1"
    role: "senior"
    capacity: 8
    skills:
      devops: expert
      kubernetes: advanced
      terraform: advanced
      python: intermediate
    areas:
      - infrastructure
      - devops
      - ci-cd
```

### Skill Levels

| Level | Aliases | Description |
|-------|---------|-------------|
| `beginner` | junior | Basic knowledge, needs guidance |
| `intermediate` | mid | Independent work, some guidance |
| `advanced` | senior | Deep knowledge, mentors others |
| `expert` | lead | Domain expert, designs solutions |

### Skill Format

Skills can be defined in two formats:

```yaml
# Dict format (recommended)
skills:
  python: expert
  react: intermediate

# List format (simple)
skills:
  - python
  - react
  # Defaults to intermediate level
```

## Sync Strategies

### Full Sync

Creates complete issue hierarchy with all features:

```bash
rg scout sync --strategy full
```

- Creates Epics for major features
- Creates Stories under Epics
- Creates Tasks under Stories
- Sets up issue links (dependencies)
- Assigns to team members
- Adds labels (phase, skill area)
- Sets story points
- Adds to sprint

### Structure Sync

Creates issue hierarchy without assignments:

```bash
rg scout sync --strategy structure
```

- Creates Epics, Stories, Tasks
- Sets up issue links
- Adds labels
- No assignments (for manual review)

### Incremental Sync

Only syncs new or changed tasks:

```bash
rg scout sync --strategy incremental
```

- Checks existing issues in task management
- Creates only missing tasks
- Updates changed task details
- Preserves manual assignments

## Workflow Examples

### New Project Setup

```bash
# 1. Analyze the codebase
rg scout analyze

# 2. Initialize team from Jira
rg scout team-init

# 3. Generate plan with team assignments
rg scout plan --with-team

# 4. Review timeline
rg scout timeline

# 5. Plan sprints
rg scout sprints

# 6. Sync to Jira
rg scout sync --strategy full --sprint active
```

### Adding a Feature

```bash
# 1. Plan the feature
rg scout plan "Add payment processing"

# 2. Preview assignments
rg scout assign

# 3. Check timeline impact
rg scout timeline

# 4. Sync to task management
rg scout sync
```

### Sprint Planning Session

```bash
# 1. View current analysis
rg scout show

# 2. Generate sprint breakdown
rg scout sprints --duration 14

# 3. Review workload balance
rg scout timeline

# 4. Create sprint in Jira
rg jira create-sprint "Sprint 15" --goal "Authentication module"

# 5. Sync and assign to sprint
rg scout sync --strategy full --sprint 123
```

## Assignment Algorithm

Scout uses a multi-factor algorithm for task assignment:

### Factors

1. **Skill Match (70% weight)**
   - Matches required skills to team member skills
   - Higher skill levels get higher scores
   - Area expertise adds bonus points

2. **Available Capacity (30% weight)**
   - Considers current workload
   - Prefers members with more availability
   - Ensures even distribution

### Scoring Formula

```
score = (skill_score * 0.7) + (capacity_score * 0.3)

skill_score = sum(skill_levels) / required_skills
capacity_score = available_hours / total_capacity
```

### Example

For a task requiring `python` and `security`:

| Member | Python | Security | Capacity | Score |
|--------|--------|----------|----------|-------|
| Ahmet | Expert (4) | None (0) | 4h/6h | 0.35 + 0.20 = 0.55 |
| Ayse | Inter (2) | None (0) | 8h/8h | 0.175 + 0.30 = 0.475 |
| Mehmet | Inter (2) | Beginner (1) | 6h/8h | 0.26 + 0.225 = 0.485 |

**Winner: Ahmet** (highest skill match despite lower capacity)

## Plan Structure

Scout generates hierarchical plans:

```yaml
phases:
  - phase: 1
    name: "Foundation"
    tasks:
      - id: "EPIC-1"
        type: epic
        title: "Authentication System"
        description: "User authentication and authorization"
        children:
          - id: "STORY-1-1"
            type: story
            title: "User Registration"
            estimate: 8
            skills_required: [python, django, postgresql]
            suggested_assignee: "Ahmet Yilmaz"
            children:
              - id: "TASK-1-1-1"
                type: task
                title: "Create user model"
                estimate: 2
                skills_required: [python, django]
              - id: "TASK-1-1-2"
                type: task
                title: "Registration API endpoint"
                estimate: 3
                skills_required: [python, django]
            dependencies: []

          - id: "STORY-1-2"
            type: story
            title: "User Login"
            estimate: 5
            skills_required: [python, security]
            suggested_assignee: "Ahmet Yilmaz"
            dependencies: ["STORY-1-1"]
```

## Integration with Jira

Scout leverages Jira integration features:

| Scout Feature | Jira Feature Used |
|---------------|-------------------|
| Epic creation | `create_issue(type=epic)` |
| Story/Task hierarchy | `create_issue_with_parent()` |
| Dependencies | `link_issues()` |
| Assignments | `assign_issue()` |
| Story points | `set_story_points()` |
| Labels | `add_labels()` |
| Sprint assignment | `move_issues_to_sprint()` |
| Bulk operations | `bulk_create_issues()` |

## API Reference

### ScoutIntegration Class

```python
from redgit.integrations.scout import ScoutIntegration

scout = ScoutIntegration()
scout.initialize(config)

# Analysis
analysis = scout.analyze_codebase()
scout.show_analysis()

# Planning
plan = scout.generate_plan(analysis)
plan_with_team = scout.generate_plan_with_team(analysis, team_config)

# Team
assignments = scout.assign_tasks_to_team(tasks, strategy="balanced")
timeline = scout.calculate_timeline(tasks)

# Sync
result = scout.sync_to_task_management_enhanced(
    tasks=plan["tasks"],
    strategy=SyncStrategy.FULL,
    sprint_id="123"
)

# Sprint planning
sprints = scout.plan_sprints(tasks, sprint_duration=14, team_capacity=40)
```

### TeamManager Class

```python
from redgit.integrations.scout.team import TeamManager, SkillLevel

team = TeamManager()
team.load()

# Find members by skill
backend_devs = team.get_members_by_skill("python", SkillLevel.ADVANCED)

# Find members by area
frontend_devs = team.get_members_by_area("frontend")

# Suggest assignee
assignee = team.suggest_assignee(task={
    "skills_required": ["python", "django"],
    "estimate": 8,
    "priority": "high"
})

# Balance workload
assignments = team.balance_workload(tasks, strategy="balanced")

# Calculate timeline
timeline = team.calculate_timeline(tasks, assignments)
```

## Troubleshooting

### "No team configuration found"

Create team config manually or from Jira:

```bash
# From Jira users
rg scout team-init

# Or create manually
touch .redgit/team.yaml
```

### "Analysis cache expired"

Force fresh analysis:

```bash
rg scout analyze --force
```

### "Sync failed: No task management configured"

Ensure a task management integration is active:

```yaml
# .redgit/config.yaml
active:
  task_management: jira
```

### "Assignment failed: No suitable member"

This happens when:
1. No member has required skills
2. All members are at capacity

Solutions:
- Adjust skill requirements in plan
- Increase team capacity
- Add team members with required skills

### "Timeline shows bottleneck"

When one member has too much work:
1. Review task assignments manually
2. Consider parallel work distribution
3. Re-assign some tasks to other members

```bash
# Re-run assignment with different strategy
rg scout assign --strategy capacity_first
```

## See Also

- [Integrations Overview](../integrations.md)
- [Jira Integration](jira.md) - Task management backend
- [GitHub Integration](github.md) - Code hosting
