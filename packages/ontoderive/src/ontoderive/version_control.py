from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""


import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Constraint: '[!!] AUTO_ADDED_METADATA'
Summary: 'Auto-generated metadata for version_control.py'
Tags:
- auto-metadata
Authority: organs/D-Logos/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Version Control ≡ Module
# 内涵 ≝ {Version, Control}
# 外延 ≝ {e | e ∈ D-Logos ∧ implements(e, VersionControl)}
# 功能 ⊢ {Version_Control, Init_Version, Validate_Control}
# =============================================================================


"""Git Version Control for D-Logos

提供基于git的轻量级版本控制功能，支持文档变更记录、历史查询、版本回滚和变更摘要生成。

Usage:
    from organs.D_Logos.organs import GitVC

    # 初始化版本控制
    vc = GitVC(repo_path="docs")

    # 记录变更
    vc.commit(message="更新文档", files=["README.md", "guide.md"])

    # 查询历史
    history = vc.history(limit=10)

    # 版本回滚
    vc.rollback(commit_hash="abc123")

    # 生成变更摘要
    changelog = vc.changelog(since="v1.0.0")
"""

_log = logging.getLogger(__name__)


@dataclass
class VersionCommit:
    """版本提交记录"""

    hash: str
    short_hash: str
    message: str
    author: str
    date: datetime
    files_changed: list[str]


@dataclass
class ChangeSummary:
    """变更摘要"""

    total_commits: int
    commits: list[dict]
    added_files: list[str]
    modified_files: list[str]
    deleted_files: list[str]


class GitVC:
    """基于git的轻量级版本控制器

    使用subprocess调用git命令，为D-Logos管理的文档提供版本控制能力。
    """

    def __init__(self, repo_path: str = ".") -> None:
        """初始化版本控制器

        Args:
            repo_path: git仓库路径，默认为当前目录
        """
        self.repo_path = Path(repo_path).resolve()
        self._ensure_git_repo()

    def _run_git(self, args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
        """执行git命令

        Args:
            args: git命令参数列表
            cwd: 执行目录，默认使用self.repo_path

        Returns:
            subprocess.CompletedProcess对象
        """
        if cwd is None:
            cwd = self.repo_path

        result = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)

        if result.returncode != 0 and "warning:" not in result.stderr.lower():
            raise RuntimeError(f"Git command failed: {result.stderr}")

        return result

    def _ensure_git_repo(self) -> None:
        """确保目录是git仓库"""
        if not self.repo_path.exists():
            raise FileNotFoundError(f"Path does not exist: {self.repo_path}")

        # 检查是否是git仓库（直接使用subprocess，不通过_run_git避免抛出异常）
        result = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=self.repo_path, capture_output=True, text=True)
        if result.returncode != 0:
            # 初始化新仓库
            subprocess.run(["git", "init"], cwd=self.repo_path, capture_output=True, text=True)

    def commit(self, message: str, files: list[str] | None = None) -> str:
        """记录文档变更

        Args:
            message: 提交信息
            files: 要提交的文件列表，None表示提交所有变更

        Returns:
            提交hash
        """
        # 添加文件到暂存区
        if files:
            for f in files:
                file_path = self.repo_path / f
                if file_path.exists():
                    self._run_git(["add", str(file_path.relative_to(self.repo_path))])
                else:
                    raise FileNotFoundError(f"File not found: {f}")
        else:
            self._run_git(["add", "-A"])

        # 检查是否有变更需要提交
        result = self._run_git(["status", "--porcelain"])
        if not result.stdout.strip():
            raise ValueError("No changes to commit")

        # 执行提交
        self._run_git(["commit", "-m", message])

        # 获取提交hash
        result = self._run_git(["rev-parse", "HEAD"])
        return cast("str", result.stdout.strip())

    def history(self, limit: int = 10, file: str | None = None) -> list[VersionCommit]:
        """查询变更历史

        Args:
            limit: 返回的提交数量限制
            file: 可选，仅查询特定文件的提交历史

        Returns:
            提交记录列表
        """
        # 构建git log命令
        args = [
            "log",
            f"-{limit}",
            "--format=%H|%h|%s|%an|%ai",
        ]

        if file:
            args.extend(["--", file])

        result = self._run_git(args)

        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split("|")
            if len(parts) >= 5:
                hash_str, short_hash, message, author, date_str = parts[:5]
                try:
                    date = datetime.fromisoformat(date_str.strip())
                except ValueError:
                    date = datetime.now()

                # 获取变更的文件列表
                files_result = self._run_git(["diff-tree", "--no-commit-id", "--name-only", "-r", hash_str])
                files_changed = [f.strip() for f in files_result.stdout.strip().split("\n") if f.strip()]

                commits.append(
                    VersionCommit(
                        hash=hash_str,
                        short_hash=short_hash,
                        message=message,
                        author=author,
                        date=date,
                        files_changed=files_changed,
                    )
                )

        return commits

    def rollback(self, commit_hash: str) -> None:
        """版本回滚到指定版本

        Args:
            commit_hash: 目标提交hash（完整或短hash）
        """
        # 验证commit hash存在
        result = self._run_git(["cat-file", "-t", commit_hash])
        if result.returncode != 0:
            raise ValueError(f"Invalid commit hash: {commit_hash}")

        # 使用git reset回滚到指定版本
        self._run_git(["reset", "--hard", commit_hash])

    def changelog(self, since: str | None = None, until: str | None = None) -> ChangeSummary:
        """生成变更摘要

        Args:
            since: 起始版本/提交（包含）
            until: 结束版本/提交（包含），默认为HEAD

        Returns:
            变更摘要对象
        """
        # 构建git log命令
        args = ["log", "--format=%H|%s|%an"]

        if since:
            args.append(f"{since}..HEAD" if not until else f"{since}..{until}")
        elif until:
            args.append(f"HEAD~1..{until}")

        result = self._run_git(args)

        commits_list = []
        commit_hashes = []

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split("|")
            if len(parts) >= 3:
                commit_hash, message, author = parts[:3]
                commit_hashes.append(commit_hash)
                commits_list.append({"hash": commit_hash[:8], "message": message, "author": author})

        # 统计文件变更
        added_files = []
        modified_files = []
        deleted_files = []

        if commit_hashes:
            # 使用git diff统计，需要至少2个提交才能比较
            if len(commit_hashes) >= 2:
                # 获取起始点
                since_commit = f"{since}^" if since else "HEAD~1"
                since_commit = since_commit if since else "HEAD~1"

                # 使用git diff统计
                diff_result = self._run_git(["diff", "--stat", f"{since}..HEAD" if since else "HEAD~1..HEAD"])

                # 解析diff统计
                for line in diff_result.stdout.strip().split("\n"):
                    if "|" in line:
                        parts = line.split("|")
                        if len(parts) == 2:
                            filename = parts[0].strip()
                            stats = parts[1].strip()
                            if stats.startswith("+") and "+" in stats[1:]:
                                added_files.append(filename)
                            elif "-" in stats and "+" not in stats:
                                deleted_files.append(filename)
                            elif "+" in stats or "-" in stats:
                                modified_files.append(filename)
            elif len(commit_hashes) == 1:
                # 只有一个提交，获取该提交变更的文件
                diff_result = self._run_git(["diff-tree", "--no-commit-id", "--name-status", "-r", commit_hashes[0]])
                for line in diff_result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        status = parts[0].strip()
                        filename = parts[1].strip()
                        if status == "A":
                            added_files.append(filename)
                        elif status == "D":
                            deleted_files.append(filename)
                        elif status == "M":
                            modified_files.append(filename)

        # 如果没有文件信息（初始提交），直接从当前工作目录获取文件列表
        if not added_files and not modified_files and not deleted_files:
            try:
                status_result = self._run_git(["status", "--porcelain"])
                for line in status_result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    status = line[:2].strip()
                    filename = line[3:].strip()
                    if status == "A" or status == "??":
                        added_files.append(filename)
            except RuntimeError:
                pass

        return ChangeSummary(
            total_commits=len(commits_list),
            commits=commits_list,
            added_files=added_files,
            modified_files=modified_files,
            deleted_files=deleted_files,
        )

    def get_current_version(self) -> str | None:
        """获取当前版本hash

        Returns:
            当前HEAD的commit hash，如果没有提交返回None
        """
        try:
            result = self._run_git(["rev-parse", "HEAD"])
            return cast("str | None", result.stdout.strip())
        except RuntimeError:
            return None

    def get_current_branch(self) -> str:
        """获取当前分支名

        Returns:
            当前分支名称
        """
        try:
            result = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
            return cast("str", result.stdout.strip())
        except RuntimeError:
            return "main"

    def list_branches(self) -> list[str]:
        """列出所有分支

        Returns:
            分支名称列表
        """
        result = self._run_git(["branch", "-a"])
        branches = []
        for line in result.stdout.strip().split("\n"):
            branch = line.strip().replace("* ", "")
            if branch:
                branches.append(branch)
        return branches
