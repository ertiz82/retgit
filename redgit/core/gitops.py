import contextlib
import subprocess
from pathlib import Path
from typing import List, Generator, Optional
import git
from git.exc import InvalidGitRepositoryError

from ..utils.security import is_excluded
from .constants import (
    MAX_DIFF_LENGTH,
    GIT_CONFLICT_STATUSES,
    GIT_DELETED_CONFLICT_STATUSES,
)


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
            List of {"file": path, "status": "U"|"M"|"A"|"D"|"C"} dicts
            C = Conflict (unmerged)
        """
        changes = []
        seen = set()

        # First, check for merge conflicts (unmerged files)
        # These need special handling as they don't appear in normal diffs
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.repo.working_dir
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    # Porcelain format: XY filename
                    # X = index status, Y = worktree status
                    # Unmerged statuses: DD, AU, UD, UA, DU, AA, UU
                    if len(line) >= 3:
                        xy = line[:2]
                        filepath = line[3:].strip()
                        # Handle renamed files (old -> new format)
                        if " -> " in filepath:
                            filepath = filepath.split(" -> ")[-1]
                        # Check for unmerged (conflict) statuses
                        if xy in GIT_CONFLICT_STATUSES:
                            if filepath not in seen:
                                seen.add(filepath)
                                if include_excluded or not is_excluded(filepath):
                                    # For "deleted by them" (UD) or "deleted by us" (DU),
                                    # mark as deleted if we want to accept the deletion
                                    if xy in GIT_DELETED_CONFLICT_STATUSES:
                                        changes.append({"file": filepath, "status": "D", "conflict": True})
                                    else:
                                        changes.append({"file": filepath, "status": "C", "conflict": True})
        except Exception:
            pass

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

    def get_diffs_for_files(self, files: List[str]) -> str:
        """
        Get combined diff output for a list of files.

        Args:
            files: List of file paths to get diffs for

        Returns:
            Combined diff string for all specified files
        """
        import subprocess

        diffs = []

        for file_path in files:
            try:
                # Try to get diff for staged or unstaged changes
                # First try unstaged
                result = subprocess.run(
                    ["git", "diff", "--", file_path],
                    capture_output=True,
                    text=True,
                    cwd=self.repo.working_dir
                )

                if result.stdout.strip():
                    diffs.append(f"# {file_path}\n{result.stdout}")
                    continue

                # Try staged
                result = subprocess.run(
                    ["git", "diff", "--cached", "--", file_path],
                    capture_output=True,
                    text=True,
                    cwd=self.repo.working_dir
                )

                if result.stdout.strip():
                    diffs.append(f"# {file_path}\n{result.stdout}")
                    continue

                # For untracked files, show the file content as "new file"
                from pathlib import Path
                path = Path(self.repo.working_dir) / file_path
                if path.exists() and path.is_file():
                    try:
                        content = path.read_text(encoding='utf-8', errors='ignore')
                        # Truncate large files
                        if len(content) > MAX_DIFF_LENGTH:
                            content = content[:MAX_DIFF_LENGTH] + "\n... (truncated)"
                        diffs.append(f"# {file_path} (new file)\n+++ {file_path}\n{content}")
                    except Exception:
                        pass

            except Exception:
                continue

        return "\n\n".join(diffs)

    def _find_stash_index(self, message_pattern: str) -> Optional[int]:
        """
        Find a stash index by its message pattern.

        Args:
            message_pattern: The pattern to search for in stash messages

        Returns:
            The stash index (0-based) if found, None otherwise
        """
        try:
            result = self.repo.git.stash("list")
            if not result:
                return None

            for line in result.split("\n"):
                if message_pattern in line:
                    # Format: stash@{0}: On branch: message
                    # Extract the index from stash@{N}
                    start = line.find("stash@{") + 7
                    end = line.find("}", start)
                    if start > 6 and end > start:
                        return int(line[start:end])
            return None
        except Exception:
            return None

    def _pop_stash_by_message(self, message_pattern: str) -> bool:
        """
        Pop a specific stash entry by its message pattern.

        This prevents mixing up stash entries when multiple groups are being processed.
        If the specific stash is not found, it will NOT pop any stash to avoid
        accidentally restoring unrelated files.

        Args:
            message_pattern: The pattern to search for in stash messages

        Returns:
            True if stash was found and popped, False otherwise
        """
        stash_index = self._find_stash_index(message_pattern)
        if stash_index is not None:
            try:
                self.repo.git.stash("pop", f"stash@{{{stash_index}}}")
                return True
            except Exception:
                return False
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

        # Get git root directory for resolving relative paths
        git_root = Path(self.repo.working_dir)

        safe_files = []
        deleted_files = []
        for f in files:
            if is_excluded(f):
                continue
            # Check if file is deleted (either in git status or doesn't exist)
            # Use git root to resolve paths correctly when running from subdirectory
            file_path = git_root / f
            status = current_changes.get(f)

            if status == "D":
                # Explicitly marked as deleted in git status
                deleted_files.append(f)
            elif not file_path.exists():
                # File doesn't exist - treat as deleted (even if not in current_changes)
                deleted_files.append(f)
            elif file_path.exists():
                # File exists - add to safe files
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

            # 3. Pop stash to get files back (use message pattern to avoid mixing stashes)
            if stash_created:
                self._pop_stash_by_message(f"redgit-temp-{branch_name}")

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

            # 5b. Stage deleted files using git add -A (handles all deletion cases)
            for f in deleted_files:
                try:
                    # git add -A stages deletions properly
                    self.repo.git.add("-A", "--", f)
                except Exception:
                    # Fallback: try git rm
                    try:
                        self.repo.index.remove([f], working_tree=False)
                    except Exception:
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

            # 11. Pop remaining stash (use message pattern to avoid mixing stashes)
            if remaining_stashed:
                self._pop_stash_by_message(f"redgit-remaining-{branch_name}")

            return True

        except Exception as e:
            # Try to recover - go back to base branch
            try:
                self.repo.git.checkout(base_branch)
            except Exception:
                pass
            # Try to pop our stashes (both temp and remaining, in case either exists)
            self._pop_stash_by_message(f"redgit-temp-{branch_name}")
            self._pop_stash_by_message(f"redgit-remaining-{branch_name}")
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

        # Get git root directory for resolving relative paths
        git_root = Path(self.repo.working_dir)

        for f in files:
            # Skip excluded files - NEVER stage them
            if is_excluded(f):
                excluded.append(f)
                continue

            # Check if file exists relative to git root (not current directory)
            file_path = git_root / f
            if file_path.exists():
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

    def remote_branch_exists(self, branch_name: str, remote: str = "origin") -> bool:
        """
        Check if a branch exists on the remote.

        Args:
            branch_name: Name of the branch to check
            remote: Remote name (default: "origin")

        Returns:
            True if branch exists on remote, False otherwise
        """
        try:
            result = self.repo.git.ls_remote("--heads", remote, branch_name)
            return bool(result.strip())
        except Exception:
            return False

    def checkout_or_create_branch(
        self,
        branch_name: str,
        from_branch: str = None,
        pull_if_exists: bool = True
    ) -> tuple:
        """
        Checkout existing branch (pulling from remote if exists) or create new one.

        Args:
            branch_name: Name of the branch
            from_branch: Base branch to create from (if creating new)
            pull_if_exists: Whether to pull from remote if branch exists

        Returns:
            (success: bool, is_new: bool, error_message: str or None)
        """
        # Stash current changes first
        stash_created = False
        try:
            self.repo.git.stash("push", "-u", "-m", f"redgit-checkout-{branch_name}")
            stash_created = True
        except Exception:
            pass

        try:
            # Check if branch exists on remote
            if self.remote_branch_exists(branch_name):
                # Fetch the branch
                try:
                    self.repo.git.fetch("origin", branch_name)
                except Exception:
                    pass

                # Try to checkout (might exist locally already)
                try:
                    self.repo.git.checkout(branch_name)
                except Exception:
                    # Branch doesn't exist locally, create tracking branch
                    try:
                        self.repo.git.checkout("-b", branch_name, f"origin/{branch_name}")
                    except Exception as e:
                        if stash_created:
                            self._pop_stash_by_message(f"redgit-checkout-{branch_name}")
                        return False, False, f"Failed to checkout remote branch: {e}"

                # Pull latest changes
                if pull_if_exists:
                    try:
                        self.repo.git.pull("origin", branch_name)
                    except Exception as e:
                        # Pop stash before returning error
                        if stash_created:
                            self._pop_stash_by_message(f"redgit-checkout-{branch_name}")
                        return False, False, f"Pull failed (possible conflict): {e}"

                # Pop stash (use message pattern to avoid mixing stashes)
                if stash_created:
                    self._pop_stash_by_message(f"redgit-checkout-{branch_name}")
                return True, False, None

            # Check if branch exists locally
            local_branches = [b.name for b in self.repo.branches]
            if branch_name in local_branches:
                self.repo.git.checkout(branch_name)
                if stash_created:
                    self._pop_stash_by_message(f"redgit-checkout-{branch_name}")
                return True, False, None

            # Create new branch
            base = from_branch or self.original_branch
            self.repo.git.checkout("-b", branch_name, base)

            if stash_created:
                self._pop_stash_by_message(f"redgit-checkout-{branch_name}")
            return True, True, None

        except Exception as e:
            # Recovery - try to go back
            if stash_created:
                self._pop_stash_by_message(f"redgit-checkout-{branch_name}")
            return False, False, str(e)

    def merge_branch(
        self,
        source_branch: str,
        target_branch: str,
        delete_source: bool = True,
        no_ff: bool = True
    ) -> tuple:
        """
        Merge source branch into target branch.

        Args:
            source_branch: Branch to merge from
            target_branch: Branch to merge into
            delete_source: Delete source branch after merge
            no_ff: Use --no-ff for merge (creates merge commit)

        Returns:
            (success: bool, error_message: str or None)
        """
        try:
            # Checkout target
            self.repo.git.checkout(target_branch)

            # Merge source
            if no_ff:
                try:
                    self.repo.git.merge(source_branch, "--no-ff", "-m", f"Merge {source_branch}")
                except Exception:
                    # Try fast-forward merge
                    self.repo.git.merge(source_branch)
            else:
                self.repo.git.merge(source_branch)

            # Delete source if requested
            if delete_source:
                try:
                    self.repo.git.branch("-d", source_branch)
                except Exception:
                    # Force delete if needed
                    try:
                        self.repo.git.branch("-D", source_branch)
                    except Exception:
                        pass

            return True, None

        except Exception as e:
            # Try to abort merge if in conflict state
            try:
                self.repo.git.merge("--abort")
            except Exception:
                pass
            return False, str(e)

    def create_subtask_branch_and_commit(
        self,
        subtask_branch: str,
        parent_branch: str,
        files: List[str],
        message: str
    ) -> bool:
        """
        Create a subtask branch from parent, commit files, merge back to parent.

        This is used for subtask mode where subtask branches are created from
        the parent task branch and merged back to it.

        Args:
            subtask_branch: Name of the subtask branch
            parent_branch: Parent branch to branch from and merge back to
            files: List of files to commit
            message: Commit message

        Returns:
            True if successful (committed and merged)
        """
        # Filter out excluded files (but keep deleted files)
        current_changes = {c["file"]: c["status"] for c in self.get_changes()}
        git_root = Path(self.repo.working_dir)

        safe_files = []
        deleted_files = []
        for f in files:
            if is_excluded(f):
                continue
            file_path = git_root / f
            status = current_changes.get(f)

            if status == "D":
                deleted_files.append(f)
            elif not file_path.exists():
                deleted_files.append(f)
            elif file_path.exists():
                safe_files.append(f)

        if not safe_files and not deleted_files:
            return False

        actual_branch_name = subtask_branch

        try:
            # 1. Stash all changes (including untracked)
            stash_created = False
            try:
                self.repo.git.stash("push", "-u", "-m", f"redgit-subtask-{subtask_branch}")
                stash_created = True
            except Exception:
                pass

            # 2. Create and checkout subtask branch from parent
            try:
                self.repo.git.checkout("-b", subtask_branch, parent_branch)
            except Exception:
                # Branch might exist, try checkout
                try:
                    self.repo.git.checkout(subtask_branch)
                except Exception:
                    # Try with suffix
                    actual_branch_name = f"{subtask_branch}-v2"
                    self.repo.git.checkout("-b", actual_branch_name, parent_branch)

            # 3. Pop stash to get files back (use message pattern to avoid mixing stashes)
            if stash_created:
                self._pop_stash_by_message(f"redgit-subtask-{subtask_branch}")

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

            # 5b. Stage deleted files
            for f in deleted_files:
                try:
                    self.repo.git.add("-A", "--", f)
                except Exception:
                    try:
                        self.repo.index.remove([f], working_tree=False)
                    except Exception:
                        pass

            # 6. Commit
            self.repo.index.commit(message)

            # 7. Stash remaining changes before switching
            remaining_stashed = False
            try:
                self.repo.git.stash("push", "-u", "-m", f"redgit-remaining-{subtask_branch}")
                remaining_stashed = True
            except Exception:
                pass

            # 8. Checkout parent branch
            self.repo.git.checkout(parent_branch)

            # 9. Merge subtask branch
            try:
                self.repo.git.merge(actual_branch_name, "--no-ff", "-m", f"Merge {actual_branch_name}")
            except Exception:
                # Fast-forward merge
                self.repo.git.merge(actual_branch_name)

            # 10. Delete subtask branch (it's merged now)
            try:
                self.repo.git.branch("-d", actual_branch_name)
            except Exception:
                pass

            # 11. Pop remaining stash (use message pattern to avoid mixing stashes)
            if remaining_stashed:
                self._pop_stash_by_message(f"redgit-remaining-{subtask_branch}")

            return True

        except Exception as e:
            # Try to recover - go back to parent branch
            try:
                self.repo.git.checkout(parent_branch)
            except Exception:
                pass
            # Try to pop our stashes (both subtask and remaining, in case either exists)
            self._pop_stash_by_message(f"redgit-subtask-{subtask_branch}")
            self._pop_stash_by_message(f"redgit-remaining-{subtask_branch}")
            raise e