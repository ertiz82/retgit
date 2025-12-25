"""
Daily state management for tracking last run time.
"""

from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import yaml


DAILY_STATE_PATH = Path(".redgit/daily_state.yaml")


class DailyStateManager:
    """Manages daily command state (last run timestamp)."""

    def __init__(self):
        DAILY_STATE_PATH.parent.mkdir(exist_ok=True)

    def load(self) -> dict:
        """Load state from daily_state.yaml"""
        if DAILY_STATE_PATH.exists():
            return yaml.safe_load(DAILY_STATE_PATH.read_text()) or {}
        return {}

    def save(self, state: dict):
        """Save state to daily_state.yaml"""
        DAILY_STATE_PATH.write_text(yaml.dump(state, allow_unicode=True, sort_keys=False))

    def get_last_run(self) -> Optional[datetime]:
        """Get the timestamp of the last daily run."""
        state = self.load()
        last_run = state.get("last_run")
        if last_run:
            if isinstance(last_run, datetime):
                return last_run
            # Handle string format
            try:
                return datetime.fromisoformat(last_run)
            except (ValueError, TypeError):
                return None
        return None

    def set_last_run(self, timestamp: Optional[datetime] = None):
        """Set the last run timestamp (defaults to now)."""
        state = self.load()
        state["last_run"] = (timestamp or datetime.now()).isoformat()
        self.save(state)

    def get_since_timestamp(self) -> datetime:
        """
        Get the timestamp to use for 'since' filter.
        Returns last run time, or 24 hours ago if never run.
        """
        last_run = self.get_last_run()
        if last_run:
            return last_run
        return datetime.now() - timedelta(hours=24)

    def parse_since_option(self, since: str) -> datetime:
        """
        Parse a human-readable 'since' option.

        Supported formats:
        - '24h', '48h' - hours ago
        - '1d', '2d', '7d' - days ago
        - '1w' - weeks ago
        - 'yesterday' - start of yesterday
        - 'today' - start of today
        - ISO date: '2024-01-15' or '2024-01-15T10:00:00'
        """
        since = since.strip().lower()
        now = datetime.now()

        # Hours
        if since.endswith('h'):
            try:
                hours = int(since[:-1])
                return now - timedelta(hours=hours)
            except ValueError:
                pass

        # Days
        if since.endswith('d'):
            try:
                days = int(since[:-1])
                return now - timedelta(days=days)
            except ValueError:
                pass

        # Weeks
        if since.endswith('w'):
            try:
                weeks = int(since[:-1])
                return now - timedelta(weeks=weeks)
            except ValueError:
                pass

        # Special keywords
        if since == 'yesterday':
            yesterday = now - timedelta(days=1)
            return yesterday.replace(hour=0, minute=0, second=0, microsecond=0)

        if since == 'today':
            return now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Try ISO format
        try:
            return datetime.fromisoformat(since)
        except ValueError:
            pass

        # Fallback: 24 hours ago
        return now - timedelta(hours=24)
