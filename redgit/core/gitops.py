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

    def create_branch_and_commit(
        self,
        branch_name: str,
        files: List[str],
        message: str,
        strategy: str = "local-merge"
    ) -> bool:
        """
        Create a branch and commit specific files without losing working directory changes.

        Args:
            branch_name: Name of the branch to create
            files: List of files to commit
            message: Commit message
            strategy: "local-merge" (merge immediately) or "merge-request" (keep branch for PR)

        Returns:
            True if successful, False otherwise

        Strategy for local-merge:
        1. Stash all changes (including untracked)
        2. Create and checkout feature branch from base
        3. Pop stash to get files back
        4. Reset index (unstage everything)
        5. Stage only the specific files
        6. Commit
        7. Stash remaining changes before switching
        8. Checkout base branch
        9. Merge feature branch
        10. Delete feature branch (it's merged now)
        11. Pop remaining stash

        Strategy for merge-request:
        1. Stash all changes (including untracked)
        2. Create and checkout feature branch from base
        3. Pop stash to get files back
        4. Reset index (unstage everything)
        5. Stage only the specific files
        6. Commit
        7. Stash remaining changes before switching
        8. Checkout base branch (branch is kept for later push)
        9. Pop remaining stash
        """
        base_branch = self.original_branch
        is_empty_repo = not self.has_commits()

        # Filter out excluded files (but keep deleted files)
        # Get current changes to check for deleted files
        current_changes = {c["file"]: c["status"] for c in self.get_changes()}

        safe_files = []
        deleted_files = []
        for f in files:
            if is_excluded(f):
                continue
            # Check if file is deleted (either in git status or doesn't exist)
            if current_changes.get(f) == "D" or (f in current_changes and not Path(f).exists()):
                deleted_files.append(f)
            elif Path(f).exists():
                safe_files.append(f)

        if not safe_files and not deleted_files:
            return False

        actual_branch_name = branch_name

        # Special handling for empty repos (no commits yet)
        if is_empty_repo:
            return self._commit_to_empty_repo(
                branch_name, safe_files, deleted_files, message, strategy
            )

        try:
            # 1. Stash all changes (including untracked)
            stash_created = False
            try:
                self.repo.git.stash("push", "-u", "-m", f"redgit-temp-{branch_name}")
                stash_created = True
            except Exception:
                pass

            # 2. Create and checkout feature branch from base
            try:
                self.repo.git.checkout("-b", branch_name, base_branch)
            except Exception:
                # Branch might exist, try checkout
                try:
                    self.repo.git.checkout(branch_name)
                except Exception:
                    # Try with suffix
                    actual_branch_name = f"{branch_name}-v2"
                    self.repo.git.checkout("-b", actual_branch_name, base_branch)

            # 3. Pop stash to get files back
            if stash_created:
                try:
                    self.repo.git.stash("pop")
                except Exception:
                    pass

            # 4. Reset index (unstage everything)
            try:
                self.repo.git.reset("HEAD")
            except Exception:
                pass

            # 5. Stage only the specific files
            for f in safe_files:
                try:
                    self.repo.index.add([f])
                except Exception:
                    pass

            # 5b. Stage deleted files (git rm)
            for f in deleted_files:
                try:
                    self.repo.index.remove([f], working_tree=False)
                except Exception:
                    # Try git rm directly
                    try:
                        self.repo.git.rm("--cached", f)
                    except Exception:
                        pass

            # 6. Commit
            self.repo.index.commit(message)

            # 7. Stash remaining changes before switching
            remaining_stashed = False
            try:
                self.repo.git.stash("push", "-u", "-m", f"redgit-remaining-{branch_name}")
                remaining_stashed = True
            except Exception:
                pass

            # 8. Checkout base branch
            self.repo.git.checkout(base_branch)

            # For local-merge strategy: merge and delete branch
            if strategy == "local-merge":
                # 9. Merge feature branch
                try:
                    self.repo.git.merge(actual_branch_name, "--no-ff", "-m", f"Merge {actual_branch_name}")
                except Exception:
                    # Fast-forward merge
                    self.repo.git.merge(actual_branch_name)

                # 10. Delete feature branch (it's merged now)
                try:
                    self.repo.git.branch("-d", actual_branch_name)
                except Exception:
                    pass
            # For merge-request strategy: branch is kept for later push

            # 11. Pop remaining stash
            if remaining_stashed:
                try:
                    self.repo.git.stash("pop")
                except Exception:
                    pass

            return True

        except Exception as e:
            # Try to recover - go back to base branch
            try:
                self.repo.git.checkout(base_branch)
            except Exception:
                pass
            # Try to pop any stash
            try:
                self.repo.git.stash("pop")
            except Exception:
                pass
            raise e

    @contextlib.contextmanager
    def isolated_branch(self, branch_name: str) -> Generator[None, None, None]:
        """
        DEPRECATED: Use create_branch_and_commit instead.

        Create an isolated branch for committing specific files.
        This method has issues with file preservation across multiple groups.
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

    def _commit_to_empty_repo(
        self,
        branch_name: str,
        safe_files: List[str],
        deleted_files: List[str],
        message: str,
        strategy: str = "local-merge"
    ) -> bool:
        """
        Handle commits in a repository with no commits yet.

        For empty repos, we can't create branches from a base since there's no commit.
        Instead, we commit directly to the current branch.

        After the first commit, subsequent commits in the same session will use
        the normal branch-based flow since the repo will have commits.

        Args:
            branch_name: Intended branch name (used for naming only in message)
            safe_files: List of files to commit
            deleted_files: List of deleted files to stage
            message: Commit message
            strategy: "local-merge" or "merge-request" (ignored for first commit)

        Returns:
            True if successful
        """
        try:
            # In empty repo, just stage and commit directly to current branch
            # The branch will be created on first commit

            # Stage the files
            for f in safe_files:
                try:
                    self.repo.index.add([f])
                except Exception:
                    pass

            # Stage deleted files (unlikely in empty repo but handle anyway)
            for f in deleted_files:
                try:
                    self.repo.index.remove([f], working_tree=False)
                except Exception:
                    pass

            # Commit - this creates the initial commit and the branch
            self.repo.index.commit(message)

            # Update original_branch now that we have a commit
            # This is crucial for subsequent commits to use normal branch flow
            self.original_branch = self.repo.active_branch.name

            return True

        except Exception as e:
            raise e