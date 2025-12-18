"""
Scout - AI-powered project analysis and task planning.

Core module for project analysis, task planning, and team management.
This is a built-in core feature, not an integration.

Commands:
- rg scout analyze       : Analyze project structure
- rg scout show          : Show current analysis
- rg scout plan          : Generate task plan from analysis
- rg scout sync          : Sync tasks to task management system
- rg scout team          : Manage team configuration
- rg scout team-init     : Initialize team from task management
- rg scout assign        : Auto-assign tasks to team
- rg scout timeline      : Show project timeline
"""

import json
import yaml
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class SyncStrategy(Enum):
    """Sync strategy for task management"""
    FULL = "full"           # Create hierarchy, links, and assignments
    STRUCTURE = "structure"  # Only create issue hierarchy
    INCREMENTAL = "incremental"  # Only sync new/changed tasks


class Scout:
    """
    Scout - AI-powered project analysis and task planning.

    Analyzes project structure, generates detailed task plans,
    and syncs with task management systems.
    """

    def __init__(self):
        self.task_management = None
        self.analysis_file = ".redgit/scout.yaml"
        self.plan_file = ".redgit/scout-plan.yaml"
        self.include_patterns = ["**/*"]
        self.exclude_patterns = [
            "node_modules/**", "vendor/**", ".git/**", "__pycache__/**",
            "*.pyc", "*.log", "dist/**", "build/**", ".venv/**"
        ]
        self.max_files = 500
        self.analysis_depth = "detailed"

    def setup(self, config: dict):
        """Initialize scout with config"""
        self.task_management = config.get("task_management")
        self.include_patterns = config.get("include_patterns", self.include_patterns)
        self.exclude_patterns = config.get("exclude_patterns", self.exclude_patterns)
        max_files = config.get("max_files", self.max_files)
        self.max_files = int(max_files) if isinstance(max_files, str) else max_files
        self.analysis_depth = config.get("analysis_depth", self.analysis_depth)

    def analyze(self, path: str = ".") -> Dict[str, Any]:
        """
        Analyze project structure using AI.

        Returns analysis with:
        - Project overview
        - Architecture summary
        - Main components/modules
        - Tech stack
        - Suggested improvements
        """
        from ..llm import LLMClient
        from ..config import ConfigManager

        config = ConfigManager().load()
        llm = LLMClient(config.get("llm", {}))

        # Gather project info
        project_info = self._gather_project_info(path)

        # Build analysis prompt
        prompt = self._build_analysis_prompt(project_info)

        # Get AI analysis
        response = llm.chat(prompt)

        # Parse and structure the response
        analysis = self._parse_analysis_response(response, project_info)

        # Store analysis
        self._save_analysis(analysis)

        return analysis

    def get_analysis(self) -> Optional[Dict[str, Any]]:
        """Get stored analysis results"""
        analysis_path = Path(self.analysis_file)
        if not analysis_path.exists():
            return None

        with open(analysis_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def generate_plan(self, analysis: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Generate task plan from analysis.

        Returns list of tasks with:
        - title: Task title
        - description: Detailed description
        - type: epic, story, task, subtask
        - estimate: Time estimate (hours)
        - priority: high, medium, low
        - dependencies: List of task IDs this depends on
        - phase: Development phase (1, 2, 3...)
        """
        from ..llm import LLMClient
        from ..config import ConfigManager

        if analysis is None:
            analysis = self.get_analysis()

        if not analysis:
            raise ValueError("No analysis found. Run 'rg scout analyze' first.")

        config = ConfigManager().load()
        llm = LLMClient(config.get("llm", {}))

        # Build plan prompt
        prompt = self._build_plan_prompt(analysis)

        # Get AI plan
        response = llm.chat(prompt)

        # Parse tasks
        tasks = self._parse_plan_response(response)

        # Save plan
        self._save_plan(tasks)

        return tasks

    def get_plan(self) -> Optional[List[Dict[str, Any]]]:
        """Get stored plan"""
        plan_path = Path(self.plan_file)
        if not plan_path.exists():
            return None

        with open(plan_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("tasks", [])

    def sync_to_task_management(self, tasks: List[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Sync tasks to task management system.

        Returns dict of local_id -> issue_key mapping
        """
        from ...integrations.registry import get_task_management
        from ..config import ConfigManager

        if tasks is None:
            tasks = self.get_plan()

        if not tasks:
            raise ValueError("No plan found. Run 'rg scout plan' first.")

        if not self.task_management:
            raise ValueError("No task management integration configured for scout.")

        config = ConfigManager().load()
        task_mgmt = get_task_management(config, self.task_management)

        if not task_mgmt:
            raise ValueError(f"Task management '{self.task_management}' not found or not configured.")

        # Create tasks in order (respecting dependencies)
        created = {}
        tasks_by_id = {t.get("id", str(i)): t for i, t in enumerate(tasks)}

        # Sort by phase and dependencies
        sorted_tasks = self._sort_tasks_by_dependencies(tasks)

        for task in sorted_tasks:
            task_id = task.get("id", "")

            # Build description with dependencies
            description = task.get("description", "")
            if task.get("dependencies"):
                dep_keys = [created.get(d, d) for d in task["dependencies"] if d in created]
                if dep_keys:
                    description += f"\n\nDepends on: {', '.join(dep_keys)}"

            # Determine issue type
            issue_type = self._map_task_type(task.get("type", "task"))

            # Create issue
            issue_key = task_mgmt.create_issue(
                summary=task.get("title", "Untitled Task"),
                description=description,
                issue_type=issue_type,
                story_points=task.get("estimate")
            )

            if issue_key:
                created[task_id] = issue_key

        # Update plan with issue keys
        self._update_plan_with_keys(created)

        return created

    def _gather_project_info(self, path: str) -> Dict[str, Any]:
        """Gather project information for analysis"""
        from pathlib import Path
        import fnmatch

        root = Path(path)
        info = {
            "path": str(root.absolute()),
            "name": root.name,
            "files": [],
            "directories": [],
            "config_files": [],
            "readme": None,
            "package_info": {}
        }

        # Find files
        all_files = []
        for p in root.rglob("*"):
            if p.is_file():
                rel_path = str(p.relative_to(root))

                # Check exclusions
                excluded = False
                for pattern in self.exclude_patterns:
                    if fnmatch.fnmatch(rel_path, pattern):
                        excluded = True
                        break

                if not excluded:
                    all_files.append(rel_path)

        # Limit files
        info["files"] = all_files[:self.max_files]
        info["total_files"] = len(all_files)

        # Find directories (top-level)
        info["directories"] = [
            d.name for d in root.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

        # Detect config files
        config_patterns = [
            "package.json", "composer.json", "pyproject.toml", "setup.py",
            "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
            "Makefile", "Dockerfile", "docker-compose.yml",
            ".env.example", "requirements.txt", "Gemfile"
        ]

        for pattern in config_patterns:
            if (root / pattern).exists():
                info["config_files"].append(pattern)

                # Read some config files for more info
                if pattern == "package.json":
                    try:
                        with open(root / pattern, "r") as f:
                            pkg = json.load(f)
                            info["package_info"]["name"] = pkg.get("name")
                            info["package_info"]["description"] = pkg.get("description")
                            info["package_info"]["dependencies"] = list(pkg.get("dependencies", {}).keys())
                    except Exception:
                        pass

                elif pattern == "pyproject.toml":
                    try:
                        import tomllib
                        with open(root / pattern, "rb") as f:
                            toml = tomllib.load(f)
                            project = toml.get("project", {})
                            info["package_info"]["name"] = project.get("name")
                            info["package_info"]["description"] = project.get("description")
                    except Exception:
                        pass

        # Read README if exists
        for readme in ["README.md", "README.rst", "README.txt", "README"]:
            readme_path = root / readme
            if readme_path.exists():
                try:
                    content = readme_path.read_text(encoding="utf-8")
                    info["readme"] = content[:3000]  # Limit size
                except Exception:
                    pass
                break

        return info

    def _build_analysis_prompt(self, project_info: Dict[str, Any]) -> str:
        """Build prompt for project analysis"""
        prompt = f"""Analyze this software project and provide a structured analysis.

Project: {project_info.get('name', 'Unknown')}
Path: {project_info.get('path', '.')}

Config Files: {', '.join(project_info.get('config_files', []))}
Top Directories: {', '.join(project_info.get('directories', []))}
Total Files: {project_info.get('total_files', 0)}

Sample Files:
{chr(10).join(project_info.get('files', [])[:50])}

"""

        if project_info.get("readme"):
            prompt += f"""README Content:
{project_info['readme'][:2000]}

"""

        if project_info.get("package_info"):
            pkg = project_info["package_info"]
            prompt += f"""Package Info:
Name: {pkg.get('name', 'N/A')}
Description: {pkg.get('description', 'N/A')}
Dependencies: {', '.join(pkg.get('dependencies', [])[:20])}

"""

        prompt += """Provide analysis in YAML format with these sections:

```yaml
overview:
  name: "Project name"
  description: "Brief description"
  type: "web-app|api|library|cli|mobile|other"
  maturity: "prototype|development|production"

tech_stack:
  languages:
    - name: "Python"
      percentage: 60
  frameworks:
    - "FastAPI"
    - "React"
  databases:
    - "PostgreSQL"
  tools:
    - "Docker"
    - "Redis"

architecture:
  pattern: "monolith|microservices|serverless|modular"
  summary: "Brief architecture description"
  components:
    - name: "API"
      path: "src/api"
      description: "REST API endpoints"
    - name: "Database"
      path: "src/models"
      description: "Database models and migrations"

modules:
  - name: "Authentication"
    path: "src/auth"
    description: "User authentication and authorization"
    status: "complete|in-progress|planned"
  - name: "API Endpoints"
    path: "src/api"
    description: "REST API implementation"
    status: "in-progress"

improvements:
  - category: "security"
    title: "Add input validation"
    priority: "high"
    description: "Implement input validation on all API endpoints"
  - category: "performance"
    title: "Add caching layer"
    priority: "medium"
    description: "Implement Redis caching for frequently accessed data"

next_steps:
  - "Complete authentication module"
  - "Add unit tests"
  - "Set up CI/CD pipeline"
```

Only output the YAML block, nothing else."""

        return prompt

    def _parse_analysis_response(self, response: str, project_info: Dict[str, Any]) -> Dict[str, Any]:
        """Parse AI response into structured analysis"""
        # Extract YAML from response
        yaml_content = response

        if "```yaml" in response:
            start = response.find("```yaml") + 7
            end = response.find("```", start)
            yaml_content = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            yaml_content = response[start:end].strip()

        try:
            analysis = yaml.safe_load(yaml_content)
        except Exception:
            # Fallback to basic structure
            analysis = {
                "overview": {
                    "name": project_info.get("name", "Unknown"),
                    "description": "Analysis failed to parse",
                    "type": "unknown",
                    "maturity": "unknown"
                },
                "raw_response": response
            }

        # Add metadata
        analysis["_meta"] = {
            "analyzed_at": datetime.now().isoformat(),
            "project_path": project_info.get("path"),
            "total_files": project_info.get("total_files", 0)
        }

        return analysis

    def _build_plan_prompt(self, analysis: Dict[str, Any]) -> str:
        """Build prompt for task plan generation"""
        prompt = f"""Based on this project analysis, generate a detailed task plan.

Project Analysis:
```yaml
{yaml.dump(analysis, default_flow_style=False)}
```

Generate a comprehensive task plan in YAML format. Include:
1. Epic-level tasks for major features/modules
2. Story-level tasks for each feature
3. Task-level items for specific implementation work
4. Proper dependencies between tasks
5. Time estimates in hours
6. Development phases

```yaml
tasks:
  - id: "EPIC-1"
    type: "epic"
    title: "User Authentication System"
    description: "Complete authentication and authorization implementation"
    estimate: 40  # hours
    priority: "high"
    phase: 1
    dependencies: []

  - id: "STORY-1-1"
    type: "story"
    title: "User Registration"
    description: "Implement user registration with email verification"
    estimate: 16
    priority: "high"
    phase: 1
    dependencies: ["EPIC-1"]

  - id: "TASK-1-1-1"
    type: "task"
    title: "Create registration API endpoint"
    description: "POST /api/auth/register endpoint with validation"
    estimate: 4
    priority: "high"
    phase: 1
    dependencies: ["STORY-1-1"]

  - id: "TASK-1-1-2"
    type: "task"
    title: "Add email verification"
    description: "Send verification email and handle confirmation"
    estimate: 6
    priority: "high"
    phase: 1
    dependencies: ["TASK-1-1-1"]
```

Rules:
- Use realistic time estimates
- Ensure proper dependency chains (tasks depend on their parent story, stories on epics)
- Group related tasks into phases
- Prioritize foundational work in earlier phases
- Include testing tasks where appropriate

Only output the YAML block, nothing else."""

        return prompt

    def _parse_plan_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse AI response into task list"""
        yaml_content = response

        if "```yaml" in response:
            start = response.find("```yaml") + 7
            end = response.find("```", start)
            yaml_content = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            yaml_content = response[start:end].strip()

        try:
            data = yaml.safe_load(yaml_content)
            tasks = data.get("tasks", [])
        except Exception:
            tasks = []

        return tasks

    def _sort_tasks_by_dependencies(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort tasks by phase and dependencies"""
        # Simple topological sort
        tasks_by_id = {t.get("id", str(i)): t for i, t in enumerate(tasks)}
        sorted_tasks = []
        visited = set()

        def visit(task_id):
            if task_id in visited:
                return
            task = tasks_by_id.get(task_id)
            if not task:
                return

            # Visit dependencies first
            for dep in task.get("dependencies", []):
                visit(dep)

            visited.add(task_id)
            sorted_tasks.append(task)

        # Sort by phase first, then visit
        sorted_by_phase = sorted(tasks, key=lambda t: (t.get("phase", 999), t.get("priority", "medium")))

        for task in sorted_by_phase:
            visit(task.get("id", ""))

        return sorted_tasks

    def _map_task_type(self, task_type: str) -> str:
        """Map scout task type to task management issue type"""
        mapping = {
            "epic": "epic",
            "story": "story",
            "task": "task",
            "subtask": "subtask",
            "bug": "bug"
        }
        return mapping.get(task_type.lower(), "task")

    def _save_analysis(self, analysis: Dict[str, Any]):
        """Save analysis to file"""
        analysis_path = Path(self.analysis_file)
        analysis_path.parent.mkdir(parents=True, exist_ok=True)

        with open(analysis_path, "w", encoding="utf-8") as f:
            yaml.dump(analysis, f, default_flow_style=False, allow_unicode=True)

    def _save_plan(self, tasks: List[Dict[str, Any]]):
        """Save plan to file"""
        plan_path = Path(self.plan_file)
        plan_path.parent.mkdir(parents=True, exist_ok=True)

        plan = {
            "created_at": datetime.now().isoformat(),
            "task_management": self.task_management,
            "tasks": tasks
        }

        with open(plan_path, "w", encoding="utf-8") as f:
            yaml.dump(plan, f, default_flow_style=False, allow_unicode=True)

    def _update_plan_with_keys(self, mapping: Dict[str, str]):
        """Update plan file with issue keys"""
        plan = self.get_plan()
        if not plan:
            return

        for task in plan:
            task_id = task.get("id", "")
            if task_id in mapping:
                task["issue_key"] = mapping[task_id]

        self._save_plan(plan)

    # ==================== Team-Aware Planning ====================

    def generate_plan_with_team(
        self,
        analysis: Dict[str, Any] = None,
        team_config: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate task plan with team-aware skill matching.

        Returns tasks with suggested_assignee based on team skills.
        """
        from ..llm import LLMClient
        from ..config import ConfigManager
        from .team import TeamManager

        if analysis is None:
            analysis = self.get_analysis()

        if not analysis:
            raise ValueError("No analysis found. Run 'rg scout analyze' first.")

        # Load team
        team_mgr = TeamManager()
        if not team_mgr.load():
            # Fall back to regular plan
            return self.generate_plan(analysis)

        config = ConfigManager().load()
        llm = LLMClient(config.get("llm", {}))

        # Build enhanced prompt with team info
        prompt = self._build_team_plan_prompt(analysis, team_mgr)

        # Get AI plan
        response = llm.chat(prompt)

        # Parse tasks
        tasks = self._parse_plan_response(response)

        # Validate and adjust assignments
        tasks = self._validate_assignments(tasks, team_mgr)

        # Save plan
        self._save_plan(tasks)

        return tasks

    def _build_team_plan_prompt(self, analysis: Dict[str, Any], team_mgr) -> str:
        """Build prompt including team information"""
        base_prompt = self._build_plan_prompt(analysis)

        team_context = team_mgr.to_prompt_context()

        enhanced_prompt = base_prompt.replace(
            "Only output the YAML block, nothing else.",
            f"""
{team_context}

For each task, add:
- skills_required: List of skills needed for this task
- suggested_assignee: Name of the best team member based on skills

Example:
```yaml
  - id: "TASK-1"
    type: "task"
    title: "Implement API authentication"
    description: "Add JWT authentication to API endpoints"
    estimate: 8
    priority: "high"
    phase: 1
    dependencies: []
    skills_required: ["python", "security", "api"]
    suggested_assignee: "John Doe"
```

Only output the YAML block, nothing else."""
        )

        return enhanced_prompt

    def _validate_assignments(
        self,
        tasks: List[Dict[str, Any]],
        team_mgr
    ) -> List[Dict[str, Any]]:
        """Validate and adjust AI-suggested assignments"""
        for task in tasks:
            suggested = task.get("suggested_assignee", "")
            if suggested:
                member = team_mgr.get_member(suggested)
                if member:
                    task["assignee_id"] = member.account_id
                else:
                    # Try to find best match
                    skills = task.get("skills_required", [])
                    best = team_mgr.suggest_assignee({
                        "skills_required": skills,
                        "estimate": task.get("estimate", 0)
                    })
                    if best:
                        task["suggested_assignee"] = best.name
                        task["assignee_id"] = best.account_id

        return tasks

    def assign_tasks_to_team(
        self,
        tasks: List[Dict[str, Any]] = None,
        strategy: str = "balanced"
    ) -> Dict[str, str]:
        """
        Assign tasks to team members using TeamManager.

        Args:
            tasks: Task list (default: current plan)
            strategy: Assignment strategy (balanced, skill_first, capacity_first)

        Returns:
            Dict of {task_id: account_id}
        """
        from .team import TeamManager

        if tasks is None:
            tasks = self.get_plan()

        if not tasks:
            raise ValueError("No plan found.")

        team_mgr = TeamManager()
        if not team_mgr.load():
            raise ValueError("No team configuration found.")

        # Assign using TeamManager
        assignments = team_mgr.balance_workload(tasks, strategy)

        # Update tasks with assignments
        for task in tasks:
            task_id = task.get("id")
            if task_id in assignments:
                member = team_mgr.get_member(assignments[task_id])
                if member:
                    task["suggested_assignee"] = member.name
                    task["assignee_id"] = member.account_id

        # Save updated plan
        self._save_plan(tasks)

        return assignments

    def calculate_timeline(
        self,
        tasks: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate project timeline based on current assignments.

        Returns timeline info with per-member breakdown.
        """
        from .team import TeamManager

        if tasks is None:
            tasks = self.get_plan()

        if not tasks:
            return {"error": "No plan found"}

        team_mgr = TeamManager()
        if not team_mgr.load():
            # Simple calculation without team
            total_hours = sum(t.get("estimate", 0) for t in tasks)
            return {
                "total_hours": total_hours,
                "elapsed_days": total_hours / 8,
                "by_member": {},
                "note": "No team configuration"
            }

        # Get current assignments
        assignments = {}
        for task in tasks:
            task_id = task.get("id")
            assignee_id = task.get("assignee_id")
            if task_id and assignee_id:
                assignments[task_id] = assignee_id

        return team_mgr.calculate_timeline(tasks, assignments)

    # ==================== Enhanced Sync ====================

    def sync_to_task_management_enhanced(
        self,
        tasks: List[Dict[str, Any]] = None,
        strategy: SyncStrategy = SyncStrategy.FULL,
        sprint_id: str = None
    ) -> Dict[str, str]:
        """
        Enhanced sync with hierarchy, links, and assignments.

        Args:
            tasks: Task list (default: current plan)
            strategy: Sync strategy
            sprint_id: Target sprint ID (None = active sprint)

        Returns:
            Dict of local_id -> issue_key mapping
        """
        from ...integrations.registry import get_task_management
        from ..config import ConfigManager

        if tasks is None:
            tasks = self.get_plan()

        if not tasks:
            raise ValueError("No plan found.")

        if not self.task_management:
            raise ValueError("No task management configured.")

        config = ConfigManager().load()
        task_mgmt = get_task_management(config, self.task_management)

        if not task_mgmt:
            raise ValueError(f"Task management '{self.task_management}' not found.")

        # Build hierarchy
        epics = [t for t in tasks if t.get("type") == "epic"]
        stories = [t for t in tasks if t.get("type") == "story"]
        task_items = [t for t in tasks if t.get("type") in ["task", "subtask", "bug"]]

        created = {}
        links_to_create = []

        # Phase 1: Create Epics
        for epic in epics:
            issue = self._create_issue_enhanced(task_mgmt, epic, None, strategy)
            if issue:
                created[epic.get("id")] = issue.key

        # Phase 2: Create Stories under Epics
        for story in stories:
            # Find parent epic
            parent_key = None
            for dep in story.get("dependencies", []):
                if dep in created and any(e.get("id") == dep for e in epics):
                    parent_key = created[dep]
                    break

            issue = self._create_issue_enhanced(task_mgmt, story, parent_key, strategy)
            if issue:
                created[story.get("id")] = issue.key

        # Phase 3: Create Tasks
        for task_item in task_items:
            # Find parent story
            parent_key = None
            for dep in task_item.get("dependencies", []):
                if dep in created:
                    # Check if it's a story
                    if any(s.get("id") == dep for s in stories):
                        parent_key = created[dep]
                        break

            issue = self._create_issue_enhanced(task_mgmt, task_item, parent_key, strategy)
            if issue:
                created[task_item.get("id")] = issue.key

            # Track dependency links
            for dep in task_item.get("dependencies", []):
                if dep in created and dep != task_item.get("id"):
                    links_to_create.append((created[dep], issue.key if issue else None))

        # Phase 4: Create Links (dependencies)
        if strategy == SyncStrategy.FULL and hasattr(task_mgmt, "link_issues"):
            for source_key, target_key in links_to_create:
                if source_key and target_key:
                    try:
                        task_mgmt.link_issues(source_key, target_key, "Blocks")
                    except Exception:
                        pass

        # Phase 5: Move to Sprint
        if sprint_id or (strategy == SyncStrategy.FULL and hasattr(task_mgmt, "move_issues_to_sprint")):
            issue_keys = list(created.values())
            target_sprint = sprint_id

            if not target_sprint and hasattr(task_mgmt, "get_active_sprint"):
                sprint = task_mgmt.get_active_sprint()
                if sprint:
                    target_sprint = sprint.id

            if target_sprint and issue_keys:
                try:
                    task_mgmt.move_issues_to_sprint(issue_keys, target_sprint)
                except Exception:
                    pass

        # Update plan with keys
        self._update_plan_with_keys(created)

        return created

    def _create_issue_enhanced(
        self,
        task_mgmt,
        task: Dict[str, Any],
        parent_key: str = None,
        strategy: SyncStrategy = SyncStrategy.FULL
    ):
        """Create a single issue with enhanced options"""
        issue_type = self._map_task_type(task.get("type", "task"))

        # Build description
        description = task.get("description", "")
        if task.get("skills_required"):
            description += f"\n\nRequired Skills: {', '.join(task['skills_required'])}"

        # Determine labels
        labels = []
        if task.get("phase"):
            labels.append(f"phase-{task['phase']}")
        if task.get("priority"):
            labels.append(f"priority-{task['priority']}")

        # Get assignee
        assignee_id = task.get("assignee_id") if strategy == SyncStrategy.FULL else None

        # Create issue
        if hasattr(task_mgmt, "create_issue_with_parent"):
            issue = task_mgmt.create_issue_with_parent(
                summary=task.get("title", "Untitled"),
                description=description,
                issue_type=issue_type,
                parent_key=parent_key,
                story_points=task.get("estimate"),
                labels=labels if labels else None,
                assignee_id=assignee_id
            )
        else:
            # Fallback to basic create
            issue_key = task_mgmt.create_issue(
                summary=task.get("title", "Untitled"),
                description=description,
                issue_type=issue_type,
                story_points=task.get("estimate")
            )
            if issue_key:
                issue = task_mgmt.get_issue(issue_key)
            else:
                issue = None

        return issue

    # ==================== Sprint Planning ====================

    def plan_sprints(
        self,
        tasks: List[Dict[str, Any]] = None,
        sprint_duration: int = 14,  # days
        team_capacity_per_day: float = None
    ) -> List[Dict[str, Any]]:
        """
        Distribute tasks across sprints based on capacity.

        Args:
            tasks: Task list (default: current plan)
            sprint_duration: Sprint duration in days
            team_capacity_per_day: Total team hours per day (auto-calculated if None)

        Returns:
            List of sprint dicts with assigned tasks
        """
        from .team import TeamManager

        if tasks is None:
            tasks = self.get_plan()

        if not tasks:
            return []

        # Calculate team capacity
        team_mgr = TeamManager()
        if team_mgr.load() and team_capacity_per_day is None:
            team_capacity_per_day = sum(m.capacity for m in team_mgr.members)
        else:
            team_capacity_per_day = team_capacity_per_day or 40  # Default 5 people x 8 hours

        sprint_capacity = team_capacity_per_day * sprint_duration

        # Sort tasks by phase and priority
        sorted_tasks = sorted(
            tasks,
            key=lambda t: (
                t.get("phase", 999),
                {"high": 0, "medium": 1, "low": 2}.get(t.get("priority", "medium"), 1)
            )
        )

        # Distribute to sprints
        sprints = []
        current_sprint = {
            "number": 1,
            "capacity": sprint_capacity,
            "used": 0,
            "tasks": []
        }

        for task in sorted_tasks:
            estimate = task.get("estimate", 0)

            # Check if task fits in current sprint
            if current_sprint["used"] + estimate > current_sprint["capacity"]:
                # Start new sprint
                sprints.append(current_sprint)
                current_sprint = {
                    "number": len(sprints) + 1,
                    "capacity": sprint_capacity,
                    "used": 0,
                    "tasks": []
                }

            current_sprint["tasks"].append(task.get("id"))
            current_sprint["used"] += estimate
            task["sprint"] = current_sprint["number"]

        # Add last sprint
        if current_sprint["tasks"]:
            sprints.append(current_sprint)

        # Save updated plan
        self._save_plan(tasks)

        return sprints


def get_scout(config: dict = None) -> Scout:
    """
    Get configured Scout instance.

    Args:
        config: Optional scout config dict. If not provided, loads from ConfigManager.

    Returns:
        Configured Scout instance
    """
    from ..config import ConfigManager

    scout = Scout()

    if config is None:
        full_config = ConfigManager().load()
        config = full_config.get("scout", {})

    scout.setup(config)
    return scout