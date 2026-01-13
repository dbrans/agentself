"""Command line capability for executing shell commands.

Provides controlled access to shell command execution with optional allowlisting.
"""

from __future__ import annotations

import logging
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, TYPE_CHECKING

from agentself.capabilities.base import Capability
from agentself.capabilities.path_guard import (
    build_path_patterns,
    extract_path_args,
    is_path_allowed,
    normalize_paths,
    resolve_path_arg,
)

if TYPE_CHECKING:
    from agentself.core import CapabilityContract

logger = logging.getLogger(__name__)

@dataclass
class CommandResult:
    """Result of a command execution."""

    exit_code: int
    stdout: str
    stderr: str

    def __str__(self) -> str:
        """Format as readable output."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"[stderr] {self.stderr}")
        parts.append(f"[exit code: {self.exit_code}]")
        return "\n".join(parts)


class CommandLineCapability(Capability):
    """Execute shell commands with optional allowlist."""

    name = "cmd"
    description = "Execute shell commands (with optional allowlist)."

    def __init__(
        self,
        allowed_commands: list[str] | None = None,
        allowed_cwd: list[Path | str] | None = None,
        allowed_paths: list[Path | str] | None = None,
        timeout: int = 30,
        deny_shell_operators: bool = False,
    ):
        """Initialize command line capability.

        Args:
            allowed_commands: List of allowed command prefixes (e.g., ["git", "npm"]).
                            If None, all commands are allowed.
            allowed_cwd: List of allowed working directories.
                        If None, all directories are allowed.
            allowed_paths: List of allowed paths for path-like arguments.
            timeout: Maximum seconds a command can run.
            deny_shell_operators: If True, block shell chaining/operators like &&, |, ;.
        """
        self.allowed_commands = allowed_commands
        self.allowed_paths = normalize_paths(allowed_paths)
        cwd_paths = normalize_paths(allowed_cwd)
        if self.allowed_paths:
            if not cwd_paths:
                cwd_paths = list(self.allowed_paths)
            else:
                cwd_paths = [p for p in cwd_paths if is_path_allowed(p, self.allowed_paths)]
                if not cwd_paths:
                    cwd_paths = list(self.allowed_paths)
        self.allowed_cwd = cwd_paths
        self.timeout = timeout
        self.deny_shell_operators = deny_shell_operators

    def contract(self) -> "CapabilityContract":
        """Declare what this capability might do."""
        from agentself.core import CapabilityContract

        # Build command patterns from allowlist
        if self.allowed_commands:
            exec_patterns = [f"shell:{cmd} *" for cmd in self.allowed_commands]
        else:
            exec_patterns = ["shell:*"]

        reads = build_path_patterns(self.allowed_paths) if self.allowed_paths else ["file:**"]
        writes = build_path_patterns(self.allowed_paths) if self.allowed_paths else ["file:**"]

        return CapabilityContract(
            executes=exec_patterns,
            reads=reads,
            writes=writes,
        )

    def derive(self, **restrictions) -> "CommandLineCapability":
        """Create a more restricted version.

        Args:
            allowed_commands: Restrict to these commands (must be subset of current).
            allowed_cwd: Restrict to these directories.
            timeout: Set a shorter timeout.
        """
        new_commands = restrictions.get("allowed_commands", self.allowed_commands)
        new_cwd = restrictions.get("allowed_cwd", self.allowed_cwd)
        new_paths = restrictions.get("allowed_paths", self.allowed_paths)
        new_timeout = restrictions.get("timeout", self.timeout)
        new_deny_shell_operators = restrictions.get(
            "deny_shell_operators",
            self.deny_shell_operators,
        )

        # Ensure new commands are subset of current commands
        if self.allowed_commands and new_commands:
            new_commands = [c for c in new_commands if c in self.allowed_commands]

        # Timeout can only be shorter
        if self.timeout:
            new_timeout = min(new_timeout, self.timeout)

        if self.deny_shell_operators:
            new_deny_shell_operators = True

        new_paths = normalize_paths(new_paths)
        if self.allowed_paths and new_paths:
            new_paths = [p for p in new_paths if is_path_allowed(p, self.allowed_paths)]

        return CommandLineCapability(
            allowed_commands=new_commands,
            allowed_cwd=new_cwd or self.allowed_cwd,
            allowed_paths=new_paths or self.allowed_paths,
            timeout=new_timeout,
            deny_shell_operators=new_deny_shell_operators,
        )
    
    def _is_command_allowed(self, command: str) -> bool:
        """Check if a command is in the allowlist."""
        if self.allowed_commands is None:
            return True
        
        # Parse the command to get the executable
        try:
            parts = shlex.split(command)
            if not parts:
                return False
            executable = parts[0]
        except ValueError:
            return False
        
        return any(
            executable == allowed or executable.startswith(f"{allowed} ")
            for allowed in self.allowed_commands
        )
    
    def _is_cwd_allowed(self, cwd: Path | None) -> bool:
        """Check if a working directory is allowed."""
        if not self.allowed_cwd:
            return True
        
        if cwd is None:
            cwd = Path.cwd()
        
        resolved = cwd.resolve()
        return any(
            resolved == allowed or allowed in resolved.parents
            for allowed in self.allowed_cwd
        )

    def _check_path_args(self, command: str, cwd: Path) -> None:
        """Validate path-like arguments against allowed_paths."""
        if not self.allowed_paths:
            return

        try:
            parts = shlex.split(command)
        except ValueError as exc:
            raise PermissionError(f"Unable to parse command: {exc}") from exc

        path_args = extract_path_args(parts)
        for path_arg in path_args:
            resolved = resolve_path_arg(path_arg, cwd)
            if not is_path_allowed(resolved, self.allowed_paths):
                allowed_str = ", ".join(str(p) for p in self.allowed_paths)
                raise PermissionError(
                    f"Path argument not allowed: '{path_arg}' "
                    f"is outside allowed paths ({allowed_str})"
                )
    
    def run(self, command: str, cwd: str | None = None) -> CommandResult:
        """Run a shell command.
        
        Args:
            command: The command to run.
            cwd: Working directory (optional).
            
        Returns:
            CommandResult with exit_code, stdout, and stderr.
            
        Raises:
            PermissionError: If command is not in allowlist.
        """
        if not self._is_command_allowed(command):
            allowed_str = ", ".join(self.allowed_commands or [])
            raise PermissionError(
                f"Command not allowed. Allowed commands: {allowed_str}"
            )

        if self.deny_shell_operators:
            blocked = ["&&", "||", ";", "|", "`", "$(", ">", "<", "\n"]
            if any(token in command for token in blocked):
                raise PermissionError("Shell operators are not allowed")

        cwd_path = Path(cwd) if cwd else None
        if not self._is_cwd_allowed(cwd_path):
            allowed_str = ", ".join(str(p) for p in self.allowed_cwd)
            raise PermissionError(
                f"Working directory not allowed. Allowed: {allowed_str}"
            )

        resolved_cwd = (cwd_path or Path.cwd()).resolve()
        self._check_path_args(command, resolved_cwd)
        
        try:
            logger.debug("cmd run command=%s cwd=%s", command, cwd_path)
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd_path,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            logger.debug("cmd result exit_code=%s", result.returncode)
            return CommandResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            logger.debug("cmd timeout seconds=%s", self.timeout)
            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {self.timeout} seconds",
            )
        except Exception as e:
            logger.exception("cmd failed command=%s", command)
            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
            )
    
    def run_interactive(self, command: str, cwd: str | None = None) -> str:
        """Run a command and return combined output.
        
        Simpler interface that returns stdout or stderr as a single string.
        
        Args:
            command: The command to run.
            cwd: Working directory (optional).
            
        Returns:
            Combined output string.
        """
        result = self.run(command, cwd)
        if result.exit_code == 0:
            return result.stdout
        else:
            return f"Error (exit {result.exit_code}): {result.stderr or result.stdout}"
