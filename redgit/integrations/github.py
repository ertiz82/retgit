import os
import requests


class GithubIntegration:
    """GitHub integration - PR creation and issue management"""
    name = "github"

    def __init__(self):
        self.enabled = False
        self.token = ""
        self.owner = ""
        self.repo = ""
        self.session = None

    def setup(self, config: dict):
        """
        Setup GitHub connection.

        Config example (.redgit/config.yaml):
            integrations:
              github:
                enabled: true
                owner: "username"
                repo: "repo-name"
                # Token: GITHUB_TOKEN env variable
        """
        self.token = config.get("token") or os.getenv("GITHUB_TOKEN")
        self.owner = config.get("owner", "")
        self.repo = config.get("repo", "")

        if not self.token:
            self.enabled = False
            return

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        })
        self.enabled = True

    def on_commit(self, group: dict, jobid: str):
        """Post-commit actions (optional PR creation, etc.)"""
        if not self.enabled:
            return

    def create_pull_request(self, title: str, body: str, head: str, base: str = "main"):
        """Create a pull request"""
        if not self.enabled or not self.owner or not self.repo:
            return None

        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def add_labels(self, issue_number: int, labels: list):
        """Add labels to issue/PR"""
        if not self.enabled or not self.owner or not self.repo:
            return

        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{issue_number}/labels"
        self.session.post(url, json={"labels": labels})