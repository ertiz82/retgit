from rich.table import Table
from rich.console import Console

console = Console()

def render_groups_table(groups):
    table = Table(title=f"🎯 {len(groups)} grup")
    table.add_column("Grup", style="cyan")
    table.add_column("Amaç", style="green")
    table.add_column("Dosya", justify="right")
    for i, g in enumerate(groups, 1):
        table.add_row(str(i), g["purpose"][:40] + "...", str(len(g["files"])))
    console.print(table)