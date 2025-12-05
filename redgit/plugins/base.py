from abc import ABC, abstractmethod
from typing import Optional
import requests


class Plugin(ABC):
    """
    Plugin base class.

    Plugins can:
    - Detect project type (match)
    - Provide custom file grouping logic (get_groups)
    - Provide custom prompts (get_prompt)
    """
    name = "base"

    @abstractmethod
    def match(self) -> bool:
        """Check if this plugin should be active for the current project"""
        pass

    def get_groups(self, changes: list) -> list:
        """
        Custom file grouping logic.

        Args:
            changes: List of file changes

        Returns:
            List of groups or empty list to use default AI grouping
        """
        return []

    def get_prompt(self) -> Optional[str]:
        """
        Return a custom prompt for this plugin.

        Can return:
        - None: Use default prompt
        - str: Hardcoded prompt text
        - Use _fetch_prompt() for URL-based prompts

        Returns:
            Prompt text or None
        """
        return None

    def _fetch_prompt(self, url: str, timeout: int = 10) -> str:
        """
        Fetch prompt from a URL.

        Args:
            url: URL to fetch prompt from
            timeout: Request timeout in seconds

        Returns:
            Prompt text

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except Exception as e:
            raise RuntimeError(f"Failed to fetch prompt from {url}: {e}")