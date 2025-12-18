"""
Scout CLI commands - AI-powered project analysis and task planning.

Commands:
- rg scout analyze       : Analyze project structure
- rg scout show          : Show current analysis
- rg scout plan          : Generate task plan from analysis
- rg scout sync          : Sync tasks to task management system
- rg scout team          : Show team configuration
- rg scout team-init     : Initialize team from task management
- rg scout assign        : Auto-assign tasks to team
- rg scout timeline      : Show project timeline
"""

import typer
import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.prompt import Prompt
from typing import Optional

from ..core.config import ConfigManager
from ..core.scout import Scout, SyncStrategy, get_scout

console = Console()
scout_app = typer.Typer(help="AI-powered project analysis and task planning")


def _get_scout() -> Scout:
    """Get configured scout instance"""
    config = ConfigManager().load()
    scout_config = config.get("scout", {})
    return get_scout(scout_config)


@scout_app.command("analyze")
def analyze_cmd(
    path: str = typer.Argument(".", help="Project path to analyze"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-analysis")
):
    """Analyze project structure using AI."""
    scout = _get_scout()

    # Check existing analysis
    existing = scout.get_analysis()
    if existing and not force:
        console.print("[yellow]Analysis already exists.[/yellow]")
        console.print(f"[dim]Last analyzed: {existing.get('_meta', {}).get('analyzed_at', 'unknown')}[/dim]")
        if not typer.confirm("Re-analyze?", default=False):
            console.print("[dim]Use 'rg scout show' to view existing analysis[/dim]")
            return

    console.print(f"\n[bold cyan]🔍 Analyzing project...[/bold cyan]\n")
    console.print(f"[dim]Path: {path}[/dim]")
    console.print(f"[dim]This may take a moment...[/dim]\n")

    try:
        with console.status("[bold green]Running AI analysis..."):
            analysis = scout.analyze(path)

        console.print("[bold green]✅ Analysis complete![/bold green]\n")

        # Show overview
        _show_analysis_summary(analysis)

        console.print("\n[dim]Full analysis saved to .redgit/scout.yaml[/dim]")
        console.print("[dim]Run 'rg scout show' to view details[/dim]")
        console.print("[dim]Run 'rg scout plan' to generate task plan[/dim]")

    except Exception as e:
        console.print(f"[red]Analysis failed: {e}[/red]")
        raise typer.Exit(1)


@scout_app.command("show")
def show_cmd(
    section: Optional[str] = typer.Argument(None, help="Section to show: overview, tech, architecture, modules, improvements")
):
    """Show current project analysis."""
    scout = _get_scout()

    analysis = scout.get_analysis()
    if not analysis:
        console.print("[yellow]No analysis found.[/yellow]")
        console.print("[dim]Run 'rg scout analyze' first[/dim]")
        raise typer.Exit(1)

    if section:
        _show_section(analysis, section)
    else:
        _show_full_analysis(analysis)


@scout_app.command("plan")
def plan_cmd(
    force: bool = typer.Option(False, "--force", "-f", help="Force regenerate plan"),
    with_team: bool = typer.Option(False, "--with-team", "-t", help="Include team skill matching")
):
    """Generate task plan from analysis."""
    scout = _get_scout()

    # Check existing plan
    existing = scout.get_plan()
    if existing and not force:
        console.print("[yellow]Plan already exists.[/yellow]")
        console.print(f"[dim]{len(existing)} tasks generated[/dim]")
        if not typer.confirm("Regenerate plan?", default=False):
            console.print("[dim]Use 'rg scout show-plan' to view existing plan[/dim]")
            return

    # Check analysis exists
    analysis = scout.get_analysis()
    if not analysis:
        console.print("[yellow]No analysis found.[/yellow]")
        console.print("[dim]Run 'rg scout analyze' first[/dim]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]📋 Generating task plan...[/bold cyan]\n")

    if with_team:
        console.print("[dim]Using team skills for assignment suggestions...[/dim]\n")

    try:
        with console.status("[bold green]AI is planning tasks..."):
            if with_team:
                tasks = scout.generate_plan_with_team(analysis)
            else:
                tasks = scout.generate_plan(analysis)

        console.print(f"[bold green]✅ Plan generated: {len(tasks)} tasks[/bold green]\n")

        # Show summary
        _show_plan_summary(tasks)

        # Show assignment info if with_team
        if with_team:
            assigned = [t for t in tasks if t.get("suggested_assignee")]
            if assigned:
                console.print(f"\n[bold]Suggested assignments:[/bold] {len(assigned)} tasks")

        console.print("\n[dim]Full plan saved to .redgit/scout-plan.yaml[/dim]")

        if scout.task_management:
            console.print(f"[dim]Run 'rg scout sync' to create tasks in {scout.task_management}[/dim]")

    except Exception as e:
        console.print(f"[red]Plan generation failed: {e}[/red]")
        raise typer.Exit(1)


@scout_app.command("show-plan")
def show_plan_cmd():
    """Show generated task plan."""
    scout = _get_scout()

    tasks = scout.get_plan()
    if not tasks:
        console.print("[yellow]No plan found.[/yellow]")
        console.print("[dim]Run 'rg scout plan' first[/dim]")
        raise typer.Exit(1)

    _show_full_plan(tasks)


@scout_app.command("sync")
def sync_cmd(
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview without creating"),
    strategy: str = typer.Option("full", "--strategy", "-s", help="Sync strategy: full, structure, incremental"),
    sprint: Optional[str] = typer.Option(None, "--sprint", help="Target sprint ID (default: active)")
):
    """Sync task plan to task management system."""
    scout = _get_scout()

    if not scout.task_management:
        console.print("[red]No task management integration configured.[/red]")
        console.print("[dim]Configure 'scout.task_management' in .redgit/config.yaml[/dim]")
        console.print("[dim]Example: task_management: jira[/dim]")
        raise typer.Exit(1)

    tasks = scout.get_plan()
    if not tasks:
        console.print("[yellow]No plan found.[/yellow]")
        console.print("[dim]Run 'rg scout plan' first[/dim]")
        raise typer.Exit(1)

    # Check for already synced tasks
    synced = [t for t in tasks if t.get("issue_key")]
    unsynced = [t for t in tasks if not t.get("issue_key")]

    # Parse strategy
    strategy_map = {
        "full": SyncStrategy.FULL,
        "structure": SyncStrategy.STRUCTURE,
        "incremental": SyncStrategy.INCREMENTAL
    }
    sync_strategy = strategy_map.get(strategy.lower(), SyncStrategy.FULL)

    console.print(f"\n[bold cyan]📤 Syncing to {scout.task_management}...[/bold cyan]\n")
    console.print(f"[dim]Strategy: {sync_strategy.value}[/dim]")
    console.print(f"[dim]Total tasks: {len(tasks)}[/dim]")
    console.print(f"[dim]Already synced: {len(synced)}[/dim]")
    console.print(f"[dim]To create: {len(unsynced)}[/dim]\n")

    if not unsynced:
        console.print("[green]All tasks already synced![/green]")
        return

    if dry_run:
        console.print("[yellow]Dry run - tasks that would be created:[/yellow]\n")
        for task in unsynced:
            assignee = f" → {task.get('suggested_assignee')}" if task.get('suggested_assignee') else ""
            console.print(f"  • [{task.get('type', 'task')}] {task.get('title')}{assignee}")
            if task.get('dependencies'):
                console.print(f"    [dim]Depends on: {', '.join(task['dependencies'])}[/dim]")
        return

    if not typer.confirm(f"Create {len(unsynced)} tasks in {scout.task_management}?"):
        return

    try:
        with console.status("[bold green]Creating tasks with hierarchy..."):
            mapping = scout.sync_to_task_management_enhanced(
                strategy=sync_strategy,
                sprint_id=sprint
            )

        console.print(f"\n[bold green]✅ Created {len(mapping)} tasks![/bold green]\n")

        # Show created tasks
        for local_id, issue_key in mapping.items():
            task = next((t for t in tasks if t.get("id") == local_id), None)
            if task:
                assignee = f" → {task.get('suggested_assignee')}" if task.get('suggested_assignee') else ""
                console.print(f"  ✓ {issue_key}: {task.get('title', '')[:40]}{assignee}")

    except Exception as e:
        console.print(f"[red]Sync failed: {e}[/red]")
        raise typer.Exit(1)


def _show_analysis_summary(analysis: dict):
    """Show brief analysis summary"""
    overview = analysis.get("overview", {})
    tech = analysis.get("tech_stack", {})

    # Project info
    panel = Panel(
        f"[bold]{overview.get('name', 'Unknown')}[/bold]\n"
        f"{overview.get('description', 'No description')}\n\n"
        f"[dim]Type: {overview.get('type', 'unknown')} | "
        f"Maturity: {overview.get('maturity', 'unknown')}[/dim]",
        title="📁 Project Overview"
    )
    console.print(panel)

    # Tech stack
    languages = tech.get("languages", [])
    frameworks = tech.get("frameworks", [])

    if languages or frameworks:
        tech_str = ""
        if languages:
            lang_names = [l.get("name", l) if isinstance(l, dict) else l for l in languages[:5]]
            tech_str += f"Languages: {', '.join(lang_names)}\n"
        if frameworks:
            tech_str += f"Frameworks: {', '.join(frameworks[:5])}"

        console.print(Panel(tech_str.strip(), title="🛠️  Tech Stack"))


def _show_section(analysis: dict, section: str):
    """Show specific section of analysis"""
    section_map = {
        "overview": "overview",
        "tech": "tech_stack",
        "architecture": "architecture",
        "modules": "modules",
        "improvements": "improvements",
        "next": "next_steps"
    }

    key = section_map.get(section, section)
    data = analysis.get(key)

    if not data:
        console.print(f"[yellow]Section '{section}' not found[/yellow]")
        console.print(f"[dim]Available: {', '.join(section_map.keys())}[/dim]")
        return

    console.print(f"\n[bold cyan]{section.upper()}[/bold cyan]\n")
    console.print(yaml.dump(data, default_flow_style=False, allow_unicode=True))


def _show_full_analysis(analysis: dict):
    """Show full analysis"""
    console.print("\n[bold cyan]📊 Project Analysis[/bold cyan]\n")

    # Overview
    overview = analysis.get("overview", {})
    console.print(f"[bold]Project:[/bold] {overview.get('name', 'Unknown')}")
    console.print(f"[bold]Type:[/bold] {overview.get('type', 'unknown')}")
    console.print(f"[bold]Maturity:[/bold] {overview.get('maturity', 'unknown')}")
    console.print(f"\n{overview.get('description', '')}\n")

    # Tech Stack
    tech = analysis.get("tech_stack", {})
    if tech:
        console.print("[bold]Tech Stack:[/bold]")
        for lang in tech.get("languages", [])[:5]:
            if isinstance(lang, dict):
                console.print(f"  • {lang.get('name')} ({lang.get('percentage', '?')}%)")
            else:
                console.print(f"  • {lang}")
        if tech.get("frameworks"):
            console.print(f"  Frameworks: {', '.join(tech['frameworks'][:5])}")
        console.print("")

    # Architecture
    arch = analysis.get("architecture", {})
    if arch:
        console.print(f"[bold]Architecture:[/bold] {arch.get('pattern', 'unknown')}")
        console.print(f"  {arch.get('summary', '')}\n")

    # Modules
    modules = analysis.get("modules", [])
    if modules:
        console.print("[bold]Modules:[/bold]")
        for mod in modules[:10]:
            status_color = "green" if mod.get("status") == "complete" else "yellow"
            console.print(f"  [{status_color}]●[/{status_color}] {mod.get('name')} - {mod.get('description', '')[:50]}")
        console.print("")

    # Improvements
    improvements = analysis.get("improvements", [])
    if improvements:
        console.print("[bold]Suggested Improvements:[/bold]")
        for imp in improvements[:5]:
            priority_color = {"high": "red", "medium": "yellow", "low": "blue"}.get(imp.get("priority"), "white")
            console.print(f"  [{priority_color}]●[/{priority_color}] {imp.get('title')}")
        console.print("")

    # Meta
    meta = analysis.get("_meta", {})
    console.print(f"[dim]Analyzed: {meta.get('analyzed_at', 'unknown')}[/dim]")
    console.print(f"[dim]Files scanned: {meta.get('total_files', '?')}[/dim]")


def _show_plan_summary(tasks: list):
    """Show brief plan summary"""
    # Count by type
    by_type = {}
    for task in tasks:
        t = task.get("type", "task")
        by_type[t] = by_type.get(t, 0) + 1

    # Count by phase
    phases = set(t.get("phase", 1) for t in tasks)

    # Total estimate
    total_hours = sum(t.get("estimate", 0) for t in tasks)

    console.print(f"[bold]Tasks by type:[/bold]")
    for t, count in sorted(by_type.items()):
        console.print(f"  • {t}: {count}")

    console.print(f"\n[bold]Phases:[/bold] {len(phases)}")
    console.print(f"[bold]Total estimate:[/bold] {total_hours} hours (~{total_hours/8:.1f} days)")


def _show_full_plan(tasks: list):
    """Show full task plan"""
    console.print("\n[bold cyan]📋 Task Plan[/bold cyan]\n")

    # Group by phase
    phases = {}
    for task in tasks:
        phase = task.get("phase", 1)
        if phase not in phases:
            phases[phase] = []
        phases[phase].append(task)

    for phase_num in sorted(phases.keys()):
        phase_tasks = phases[phase_num]
        phase_hours = sum(t.get("estimate", 0) for t in phase_tasks)

        console.print(f"\n[bold]Phase {phase_num}[/bold] ({len(phase_tasks)} tasks, {phase_hours}h)")
        console.print("─" * 50)

        for task in phase_tasks:
            type_icon = {"epic": "📦", "story": "📖", "task": "✓", "subtask": "  ·"}.get(task.get("type"), "•")
            priority_color = {"high": "red", "medium": "yellow", "low": "blue"}.get(task.get("priority"), "white")
            issue_key = task.get("issue_key", "")

            title_line = f"{type_icon} {task.get('title', 'Untitled')}"
            if issue_key:
                title_line += f" [green][{issue_key}][/green]"

            console.print(f"[{priority_color}]{title_line}[/{priority_color}]")

            if task.get("estimate"):
                console.print(f"   [dim]Est: {task['estimate']}h[/dim]", end="")
            if task.get("dependencies"):
                console.print(f"   [dim]Deps: {', '.join(task['dependencies'])}[/dim]", end="")
            if task.get("suggested_assignee"):
                console.print(f"   [dim]→ {task['suggested_assignee']}[/dim]", end="")
            console.print("")


# ==================== Team Commands ====================

@scout_app.command("team")
def team_cmd():
    """Show team configuration."""
    from ..core.scout.team import TeamManager

    team_mgr = TeamManager()
    if not team_mgr.load():
        console.print("[yellow]No team configuration found.[/yellow]")
        console.print("[dim]Run 'rg scout team-init' to create from task management[/dim]")
        console.print("[dim]Or create .redgit/team.yaml manually[/dim]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Team Configuration[/bold cyan]\n")

    table = Table(show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Role")
    table.add_column("Capacity", justify="right")
    table.add_column("Skills")
    table.add_column("Areas")

    for member in team_mgr.members:
        skills_str = ", ".join(
            f"{k}({v.name[:3].lower()})"
            for k, v in list(member.skills.items())[:4]
        )
        if len(member.skills) > 4:
            skills_str += f" +{len(member.skills) - 4}"

        areas_str = ", ".join(member.areas[:3])
        if len(member.areas) > 3:
            areas_str += f" +{len(member.areas) - 3}"

        table.add_row(
            member.name,
            member.role,
            f"{member.capacity}h/day",
            skills_str or "-",
            areas_str or "-"
        )

    console.print(table)
    console.print(f"\n[dim]Total capacity: {sum(m.capacity for m in team_mgr.members)}h/day[/dim]")
    console.print(f"[dim]Config: {team_mgr.config_path}[/dim]")


@scout_app.command("team-init")
def team_init_cmd():
    """Initialize team from task management users."""
    from ..core.scout.team import TeamManager, SkillLevel
    from ..integrations.registry import get_task_management

    scout = _get_scout()

    if not scout.task_management:
        console.print("[red]No task management configured.[/red]")
        console.print("[dim]Configure 'scout.task_management' in .redgit/config.yaml[/dim]")
        raise typer.Exit(1)

    config = ConfigManager().load()
    task_mgmt = get_task_management(config, scout.task_management)

    if not task_mgmt:
        console.print(f"[red]{scout.task_management} not configured.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Initializing team from {scout.task_management}...[/bold cyan]\n")

    # Get users from task management
    users = task_mgmt.get_project_users()
    if not users:
        console.print("[yellow]No users found in project.[/yellow]")
        raise typer.Exit(1)

    console.print(f"Found {len(users)} users:\n")

    for i, user in enumerate(users, 1):
        console.print(f"  [{i}] {user.get('display_name')} ({user.get('email', '-')})")

    console.print("")

    # Create TeamManager
    team_mgr = TeamManager()
    team_mgr.init_from_jira(users)

    # Interactive skill setup
    if typer.confirm("Would you like to set skills for team members?", default=True):
        console.print("\n[dim]For each member, enter skills (comma-separated) or press Enter to skip[/dim]")
        console.print("[dim]Format: skill:level (e.g., python:expert, react:intermediate)[/dim]\n")

        for member in team_mgr.members:
            skills_input = Prompt.ask(
                f"  {member.name} skills",
                default=""
            )

            if skills_input.strip():
                for skill_str in skills_input.split(","):
                    skill_str = skill_str.strip()
                    if ":" in skill_str:
                        skill, level = skill_str.split(":", 1)
                        member.skills[skill.strip().lower()] = SkillLevel.from_string(level.strip())
                    else:
                        member.skills[skill_str.lower()] = SkillLevel.INTERMEDIATE

            areas_input = Prompt.ask(
                f"  {member.name} areas",
                default=""
            )

            if areas_input.strip():
                member.areas = [a.strip().lower() for a in areas_input.split(",")]

    # Save
    team_mgr.save()
    console.print(f"\n[green]✓ Team configuration saved to {team_mgr.config_path}[/green]")
    console.print("[dim]Run 'rg scout team' to view[/dim]")


@scout_app.command("assign")
def assign_cmd(
    strategy: str = typer.Option("balanced", "--strategy", "-s", help="Strategy: balanced, skill_first"),
    preview: bool = typer.Option(True, "--preview/--no-preview", help="Preview assignments before saving")
):
    """Auto-assign tasks to team members."""
    from ..core.scout.team import TeamManager

    scout = _get_scout()

    tasks = scout.get_plan()
    if not tasks:
        console.print("[yellow]No plan found.[/yellow]")
        console.print("[dim]Run 'rg scout plan' first[/dim]")
        raise typer.Exit(1)

    team_mgr = TeamManager()
    if not team_mgr.load():
        console.print("[yellow]No team configuration found.[/yellow]")
        console.print("[dim]Run 'rg scout team-init' first[/dim]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Auto-assigning tasks...[/bold cyan]\n")
    console.print(f"[dim]Strategy: {strategy}[/dim]")
    console.print(f"[dim]Tasks: {len(tasks)}[/dim]")
    console.print(f"[dim]Team: {len(team_mgr.members)} members[/dim]\n")

    # Get assignments
    assignments = team_mgr.balance_workload(tasks, strategy)

    # Show assignments
    console.print("[bold]Proposed assignments:[/bold]\n")

    by_member = {}
    for task in tasks:
        task_id = task.get("id")
        if task_id in assignments:
            member = team_mgr.get_member(assignments[task_id])
            if member:
                if member.name not in by_member:
                    by_member[member.name] = {"hours": 0, "tasks": []}
                by_member[member.name]["hours"] += task.get("estimate", 0)
                by_member[member.name]["tasks"].append(task)

    for name, data in sorted(by_member.items()):
        console.print(f"[bold]{name}[/bold] ({data['hours']}h)")
        for task in data["tasks"][:5]:
            console.print(f"  • {task.get('id')}: {task.get('title', '')[:40]}")
        if len(data["tasks"]) > 5:
            console.print(f"  [dim]... and {len(data['tasks']) - 5} more[/dim]")
        console.print("")

    unassigned = len(tasks) - len(assignments)
    if unassigned > 0:
        console.print(f"[yellow]Unassigned: {unassigned} tasks (insufficient capacity)[/yellow]\n")

    if preview:
        if not typer.confirm("Save these assignments?"):
            return

    # Apply assignments
    scout.assign_tasks_to_team(tasks, strategy)
    console.print("[green]✓ Assignments saved to plan[/green]")


@scout_app.command("timeline")
def timeline_cmd():
    """Show project timeline based on assignments."""
    scout = _get_scout()

    tasks = scout.get_plan()
    if not tasks:
        console.print("[yellow]No plan found.[/yellow]")
        console.print("[dim]Run 'rg scout plan' first[/dim]")
        raise typer.Exit(1)

    timeline = scout.calculate_timeline(tasks)

    console.print(f"\n[bold cyan]Project Timeline[/bold cyan]\n")

    if timeline.get("error"):
        console.print(f"[red]{timeline['error']}[/red]")
        return

    console.print(f"[bold]Total effort:[/bold] {timeline['total_hours']} hours")
    console.print(f"[bold]Elapsed time:[/bold] ~{timeline['elapsed_days']} working days")

    if timeline.get("bottleneck"):
        console.print(f"[bold]Bottleneck:[/bold] {timeline['bottleneck']}")

    if timeline.get("by_member"):
        console.print(f"\n[bold]Workload by member:[/bold]\n")

        table = Table(show_header=True)
        table.add_column("Member")
        table.add_column("Hours", justify="right")
        table.add_column("Days", justify="right")
        table.add_column("Load")

        for member_id, data in timeline["by_member"].items():
            hours = data["hours"]
            days = data.get("days", hours / 8)
            capacity = data.get("capacity", 8)
            load_pct = (hours / (capacity * timeline["elapsed_days"])) * 100 if timeline["elapsed_days"] > 0 else 0

            load_color = "green" if load_pct < 80 else "yellow" if load_pct < 100 else "red"
            load_bar = "█" * int(load_pct / 10) + "░" * (10 - int(load_pct / 10))

            table.add_row(
                data.get("name", member_id),
                f"{hours}h",
                f"{days:.1f}",
                f"[{load_color}]{load_bar}[/{load_color}] {load_pct:.0f}%"
            )

        console.print(table)

    if timeline.get("note"):
        console.print(f"\n[dim]{timeline['note']}[/dim]")


@scout_app.command("sprints")
def sprints_cmd(
    duration: int = typer.Option(14, "--duration", "-d", help="Sprint duration in days")
):
    """Plan sprints based on capacity."""
    scout = _get_scout()

    tasks = scout.get_plan()
    if not tasks:
        console.print("[yellow]No plan found.[/yellow]")
        console.print("[dim]Run 'rg scout plan' first[/dim]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Sprint Planning[/bold cyan]\n")
    console.print(f"[dim]Sprint duration: {duration} days[/dim]\n")

    sprints = scout.plan_sprints(tasks, duration)

    if not sprints:
        console.print("[yellow]No sprints generated.[/yellow]")
        return

    for sprint in sprints:
        used_pct = (sprint["used"] / sprint["capacity"]) * 100 if sprint["capacity"] > 0 else 0
        console.print(f"[bold]Sprint {sprint['number']}[/bold] ({sprint['used']:.0f}h / {sprint['capacity']:.0f}h capacity, {used_pct:.0f}%)")
        console.print(f"  Tasks: {len(sprint['tasks'])}")

        # Show task types
        task_objs = [t for t in tasks if t.get("id") in sprint["tasks"]]
        by_type = {}
        for t in task_objs:
            tt = t.get("type", "task")
            by_type[tt] = by_type.get(tt, 0) + 1

        type_str = ", ".join(f"{count} {tt}s" for tt, count in sorted(by_type.items()))
        console.print(f"  [dim]{type_str}[/dim]")
        console.print("")

    console.print(f"[dim]Total: {len(sprints)} sprints[/dim]")
    console.print("[dim]Sprint assignments saved to plan[/dim]")