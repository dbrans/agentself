"""Command line capability for executing shell commands.

Provides controlled access to shell command execution with optional allowlisting.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from agentself.capabilities.base import Capability


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
        timeout: int = 30,
    ):
        """Initialize command line capability.
        
        Args:
            allowed_commands: List of allowed command prefixes (e.g., ["git", "npm"]).
                            If None, all commands are allowed.
            allowed_cwd: List of allowed working directories.
                        If None, all directories are allowed.
            timeout: Maximum seconds a command can run.
        """
        self.allowed_commands = allowed_commands
        self.allowed_cwd = [Path(p).resolve() for p in (allowed_cwd or [])]
        self.timeout = timeout
    
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
        
        cwd_path = Path(cwd) if cwd else None
        if not self._is_cwd_allowed(cwd_path):
            allowed_str = ", ".join(str(p) for p in self.allowed_cwd)
            raise PermissionError(
                f"Working directory not allowed. Allowed: {allowed_str}"
            )
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd_path,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            return CommandResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {self.timeout} seconds",
            )
        except Exception as e:
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
