import contextlib
import subprocess
from pathlib import Path
from typing import List, Generator, Optional
import git
from git.exc import InvalidGitRepositoryError

from ..utils.security import is_excluded


class NotAGitRepoError(Exception):
    """Raised when the current directory is not a git repository."""
    pass


def init_git_repo(remote_url: Optional[str] = None) -> git.Repo:
    """
    Initialize a new git repository in the current directory.

    Args:
        remote_url: Optional remote URL to add as origin

    Returns:
        The initialized git.Repo object
    """
    repo = git.Repo.init(".")

    # Add remote if provided
    if remote_url:
        repo.create_remote("origin", remote_url)

    return repo


class GitOps:
    def __init__(self, auto_init: bool = False, remote_url: Optional[str] = None):
        """
        Initialize GitOps.

        Args:
            auto_init: If True, automatically initialize git repo if not exists
            remote_url: Remote URL to add when auto-initializing
        """
        try:
            self.repo = git.Repo(".", search_parent_directories=True)
        except InvalidGitRepositoryError:
            if auto_init:
                self.repo = init_git_repo(remote_url)
            else:
                raise NotAGitRepoError(
                    "Not a git repository. Please run 'git init' first or navigate to a git repository."
                )
        self.original_branch = self.repo.active_branch.name if self.repo.head.is_valid() else "main"

    def get_changes(self, include_excluded: bool = False) -> List[dict]:
        """
        Get list of changed files in the repository.

        Args:
            include_excluded: If True, include sensitive/excluded files (not recommended)

        Returns:
            List of {"file": path, "status": "U"|"M"|"A"|"D"} dicts
        """
        changes = []
        seen = set()

        # Untracked files (new files not yet added to git)
        for f in self.repo.untracked_files:
            if f not in seen:
                seen.add(f)
                if include_excluded or not is_excluded(f):
                    changes.append({"file": f, "status": "U"})

        # Unstaged changes (modified in working directory but not staged)
        for item in self.repo.index.diff(None):
            f = item.a_path or item.b_path
            if f not in seen:
                seen.add(f)
                if include_excluded or not is_excluded(f):
                    status = "D" if item.deleted_file else "M"
                    changes.append({"file": f, "status": status})

        # Staged changes (added to index, ready to commit)
        if self.repo.head.is_valid():
            for item in self.repo.index.diff("HEAD"):
                f = item.a_path or item.b_path
                if f not in seen:
                    seen.add(f)
                    if include_excluded or not is_excluded(f):
                        if item.new_file:
                            status = "A"
                        elif item.deleted_file:
                            status = "D"
                        else:
                            status = "M"
                        changes.append({"file": f, "status": status})

        return changes

    def get_excluded_changes(self) -> List[str]:
        """
        Get list of excluded files that have changes.
        Useful for showing user what was filtered out.
        """
        excluded = []
        seen = set()

        # Check untracked files
        for f in self.repo.untracked_files:
            if f not in seen and is_excluded(f):
                seen.add(f)
                excluded.append(f)

        # Check unstaged changes
        for item in self.repo.index.diff(None):
            f = item.a_path or item.b_path
            if f not in seen and is_excluded(f):
                seen.add(f)
                excluded.append(f)

        # Check staged changes
        if self.repo.head.is_valid():
            for item in self.repo.index.diff("HEAD"):
                f = item.a_path or item.b_path
                if f not in seen and is_excluded(f):
                    seen.add(f)
                    excluded.append(f)

        return excluded

    def has_commits(self) -> bool:
        """Check if the repository has any commits."""
        try:
            self.repo.head.commit
            return True
        except ValueError:
            return False

    @contextlib.contextmanager
    def isolated_branch(self, branch_name: str) -> Generator[None, None, None]:
        """
        Create an isolated branch for committing specific files.

        Strategy:
        1. Create branch from current HEAD (or orphan if no commits)
        2. Stage and commit only the specified files inside the context
        3. Return to original branch
        4. Files committed to the branch are removed from working directory
        """
        is_new_repo = not self.has_commits()
        original_branch = self.original_branch

        try:
            if is_new_repo:
                # New repo without commits - create orphan branch
                try:
                    self.repo.git.checkout("--orphan", branch_name)
                except Exception:
                    pass
            else:
                # Existing repo - create branch from HEAD
                try:
                    self.repo.git.checkout("-b", branch_name)
                except Exception:
                    try:
                        self.repo.git.checkout("-b", f"{branch_name}-v2")
                    except Exception:
                        pass

            yield

        finally:
            # After commit, return to original branch
            if is_new_repo:
                # For new repos, after first commit we can switch branches normally
                try:
                    # Check if we made a commit
                    if self.has_commits():
                        # Create/checkout main branch
                        try:
                            self.repo.git.checkout("-b", original_branch)
                        except Exception:
                            try:
                                self.repo.git.checkout(original_branch)
                            except Exception:
                                pass
                except Exception:
                    pass
            else:
                try:
                    self.repo.git.checkout(original_branch)
                except Exception:
                    pass

    def stage_files(self, files: List[str]) -> tuple:
        """
        Stage files for commit, excluding sensitive files.

        Args:
            files: List of file paths to stage

        Returns:
            (staged_files, excluded_files) tuple
        """
        staged = []
        excluded = []

        for f in files:
            # Skip excluded files - NEVER stage them
            if is_excluded(f):
                excluded.append(f)
                continue

            # Only stage if file exists
            if Path(f).exists():
                self.repo.index.add([f])
                staged.append(f)

        return staged, excluded

    def commit(self, message: str, files: List[str] = None):
        """
        Create a commit with the staged files.

        Args:
            message: Commit message
            files: If provided, reset these files in working directory after commit
        """
        self.repo.index.commit(message)

        # After committing, the files are in the branch's history
        # We need to remove them from the working directory so they don't
        # appear as "modified" when we switch back to the original branch
        if files:
            for f in files:
                try:
                    # Reset the file to match HEAD (removes local changes)
                    self.repo.git.checkout("HEAD", "--", f)
                except Exception:
                    pass