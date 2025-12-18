"""
Scout Team Manager - Team skills, capacity, and task assignment.

Manages team configuration and provides intelligent task assignment
based on skills, capacity, and workload.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class SkillLevel(Enum):
    """Skill proficiency levels"""
    BEGINNER = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    EXPERT = 4

    @classmethod
    def from_string(cls, level: str) -> "SkillLevel":
        """Parse skill level from string"""
        level_map = {
            "beginner": cls.BEGINNER,
            "junior": cls.BEGINNER,
            "intermediate": cls.INTERMEDIATE,
            "mid": cls.INTERMEDIATE,
            "advanced": cls.ADVANCED,
            "senior": cls.ADVANCED,
            "expert": cls.EXPERT,
            "lead": cls.EXPERT
        }
        return level_map.get(level.lower(), cls.INTERMEDIATE)


@dataclass
class TeamMember:
    """Represents a team member with skills and capacity"""
    name: str
    account_id: str
    role: str = "developer"
    capacity: float = 8.0  # hours per day
    skills: Dict[str, SkillLevel] = field(default_factory=dict)
    areas: List[str] = field(default_factory=list)
    current_workload: float = 0.0  # hours assigned

    @classmethod
    def from_dict(cls, data: dict) -> "TeamMember":
        """Create TeamMember from config dict"""
        skills = {}
        raw_skills = data.get("skills", {})

        # Handle both list and dict formats
        if isinstance(raw_skills, list):
            # List format: ["python", "react"] or [{"python": "expert"}]
            for item in raw_skills:
                if isinstance(item, dict):
                    for skill, level in item.items():
                        skills[skill.lower()] = SkillLevel.from_string(str(level))
                else:
                    skills[str(item).lower()] = SkillLevel.INTERMEDIATE
        elif isinstance(raw_skills, dict):
            # Dict format: {"python": "expert", "react": "intermediate"}
            for skill, level in raw_skills.items():
                skills[skill.lower()] = SkillLevel.from_string(str(level))

        return cls(
            name=data.get("name", "Unknown"),
            account_id=data.get("account_id", ""),
            role=data.get("role", "developer"),
            capacity=float(data.get("capacity", 8)),
            skills=skills,
            areas=[a.lower() for a in data.get("areas", [])]
        )

    def has_skill(self, skill: str, min_level: SkillLevel = SkillLevel.BEGINNER) -> bool:
        """Check if member has skill at minimum level"""
        skill_lower = skill.lower()
        if skill_lower in self.skills:
            return self.skills[skill_lower].value >= min_level.value
        return False

    def get_skill_level(self, skill: str) -> Optional[SkillLevel]:
        """Get member's level for a skill"""
        return self.skills.get(skill.lower())

    def skill_score(self, required_skills: List[str]) -> float:
        """Calculate skill match score (0-1) for required skills"""
        if not required_skills:
            return 0.5  # Neutral score

        total_score = 0
        for skill in required_skills:
            level = self.get_skill_level(skill)
            if level:
                total_score += level.value / 4  # Normalize to 0-1
            # Also check areas
            if skill.lower() in self.areas:
                total_score += 0.25

        return min(1.0, total_score / len(required_skills))

    def available_capacity(self) -> float:
        """Get available hours (capacity - workload)"""
        return max(0, self.capacity - self.current_workload)


class TeamManager:
    """Manages team configuration and task assignments"""

    TEAM_CONFIG_PATH = ".redgit/team.yaml"

    def __init__(self, config_path: str = None):
        self.config_path = Path(config_path or self.TEAM_CONFIG_PATH)
        self.members: List[TeamMember] = []
        self._raw_config: dict = {}

    def load(self) -> bool:
        """Load team configuration from file"""
        if not self.config_path.exists():
            return False

        try:
            with open(self.config_path, "r") as f:
                self._raw_config = yaml.safe_load(f) or {}

            self.members = []
            for member_data in self._raw_config.get("members", []):
                self.members.append(TeamMember.from_dict(member_data))

            return True
        except Exception:
            return False

    def save(self):
        """Save team configuration to file"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert members back to dict format
        members_data = []
        for member in self.members:
            member_dict = {
                "name": member.name,
                "account_id": member.account_id,
                "role": member.role,
                "capacity": member.capacity,
                "skills": {k: v.name.lower() for k, v in member.skills.items()},
                "areas": member.areas
            }
            members_data.append(member_dict)

        self._raw_config["members"] = members_data

        with open(self.config_path, "w") as f:
            yaml.dump(self._raw_config, f, default_flow_style=False, allow_unicode=True)

    def get_member(self, name_or_id: str) -> Optional[TeamMember]:
        """Find member by name or account_id"""
        name_lower = name_or_id.lower()
        for member in self.members:
            if member.account_id == name_or_id:
                return member
            if member.name.lower() == name_lower:
                return member
        return None

    def get_members_by_skill(
        self,
        skill: str,
        min_level: SkillLevel = SkillLevel.INTERMEDIATE
    ) -> List[TeamMember]:
        """Get members with a specific skill at minimum level"""
        return [m for m in self.members if m.has_skill(skill, min_level)]

    def get_members_by_area(self, area: str) -> List[TeamMember]:
        """Get members who work in a specific area"""
        area_lower = area.lower()
        return [m for m in self.members if area_lower in m.areas]

    def suggest_assignee(
        self,
        task: dict,
        exclude_ids: List[str] = None
    ) -> Optional[TeamMember]:
        """
        Suggest best assignee for a task based on skills and workload.

        Args:
            task: Task dict with keys:
                - skills_required: List of required skills
                - estimate: Estimated hours
                - priority: high/medium/low
            exclude_ids: Account IDs to exclude

        Returns:
            Best matching TeamMember or None
        """
        exclude_ids = exclude_ids or []
        required_skills = task.get("skills_required", [])
        estimate = task.get("estimate", 0)

        candidates = []
        for member in self.members:
            if member.account_id in exclude_ids:
                continue

            # Check capacity
            if member.available_capacity() < estimate:
                continue

            # Calculate score
            skill_score = member.skill_score(required_skills)
            capacity_score = member.available_capacity() / member.capacity

            # Combined score (skill matters more)
            total_score = (skill_score * 0.7) + (capacity_score * 0.3)

            candidates.append((member, total_score))

        if not candidates:
            return None

        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def balance_workload(
        self,
        tasks: List[dict],
        strategy: str = "balanced"
    ) -> Dict[str, str]:
        """
        Assign tasks to team members with balanced workload.

        Args:
            tasks: List of task dicts with:
                - id: Task identifier
                - skills_required: List of skills
                - estimate: Hours estimate
            strategy: Assignment strategy
                - "balanced": Distribute evenly
                - "skill_first": Prioritize skill match
                - "capacity_first": Prioritize available capacity

        Returns:
            Dict of {task_id: account_id}
        """
        assignments = {}

        # Reset workloads
        for member in self.members:
            member.current_workload = 0

        # Sort tasks by priority and estimate (larger first)
        sorted_tasks = sorted(
            tasks,
            key=lambda t: (
                {"high": 0, "medium": 1, "low": 2}.get(t.get("priority", "medium"), 1),
                -t.get("estimate", 0)
            )
        )

        for task in sorted_tasks:
            task_id = task.get("id")
            estimate = task.get("estimate", 0)

            # Find best assignee
            assignee = self.suggest_assignee(task)
            if assignee:
                assignments[task_id] = assignee.account_id
                assignee.current_workload += estimate

        return assignments

    def calculate_timeline(
        self,
        tasks: List[dict],
        assignments: Dict[str, str]
    ) -> dict:
        """
        Calculate project timeline based on assignments.

        Returns:
            Dict with:
                - total_hours: Total estimated hours
                - elapsed_days: Days to complete (parallel work)
                - by_member: Hours per member
                - bottleneck: Member with most work
        """
        # Group tasks by assignee
        by_member = {}
        total_hours = 0

        for task in tasks:
            task_id = task.get("id")
            estimate = task.get("estimate", 0)
            total_hours += estimate

            assignee_id = assignments.get(task_id)
            if assignee_id:
                if assignee_id not in by_member:
                    member = self.get_member(assignee_id) or TeamMember(
                        name="Unknown",
                        account_id=assignee_id
                    )
                    by_member[assignee_id] = {
                        "name": member.name,
                        "hours": 0,
                        "capacity": member.capacity
                    }
                by_member[assignee_id]["hours"] += estimate

        # Find bottleneck (member with most hours)
        bottleneck = None
        max_days = 0
        for member_id, data in by_member.items():
            days = data["hours"] / data["capacity"] if data["capacity"] > 0 else float("inf")
            data["days"] = round(days, 1)
            if days > max_days:
                max_days = days
                bottleneck = data["name"]

        return {
            "total_hours": total_hours,
            "elapsed_days": round(max_days, 1),
            "by_member": by_member,
            "bottleneck": bottleneck
        }

    def to_prompt_context(self) -> str:
        """Generate team context for AI prompts"""
        if not self.members:
            return "No team configuration available."

        lines = ["Team Members:"]
        for member in self.members:
            skills_str = ", ".join(
                f"{k}({v.name.lower()})"
                for k, v in member.skills.items()
            )
            areas_str = ", ".join(member.areas) if member.areas else "general"
            lines.append(
                f"- {member.name} ({member.role}): "
                f"Skills: {skills_str or 'none'}; "
                f"Areas: {areas_str}; "
                f"Capacity: {member.capacity}h/day"
            )

        return "\n".join(lines)

    def init_from_jira(self, jira_users: List[dict]) -> List[TeamMember]:
        """
        Initialize team from Jira users.

        Args:
            jira_users: List of user dicts from Jira API

        Returns:
            List of created TeamMembers (without skills)
        """
        self.members = []

        for user in jira_users:
            if not user.get("active", True):
                continue

            member = TeamMember(
                name=user.get("display_name", "Unknown"),
                account_id=user.get("account_id", ""),
                role="developer",
                capacity=8.0,
                skills={},
                areas=[]
            )
            self.members.append(member)

        return self.members