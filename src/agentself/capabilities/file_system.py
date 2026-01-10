"""File system capability with scoped access.

Provides read/write access to files, restricted to configured allowed paths.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from agentself.capabilities.base import Capability


class FileSystemCapability(Capability):
    """Read and write files within allowed paths."""
    
    name = "file_system"
    description = "Read and write files within allowed paths."
    
    def __init__(
        self,
        allowed_paths: list[Path | str] | None = None,
        read_only: bool = False,
    ):
        """Initialize with allowed paths and read-only flag.
        
        Args:
            allowed_paths: List of paths the agent can access. If None, all paths allowed.
            read_only: If True, write operations are disabled.
        """
        self.allowed_paths = [Path(p).resolve() for p in (allowed_paths or [])]
        self.read_only = read_only
    
    def _is_path_allowed(self, path: Path) -> bool:
        """Check if a path is within allowed paths."""
        if not self.allowed_paths:
            return True  # No restrictions
        
        resolved = path.resolve()
        return any(
            resolved == allowed or allowed in resolved.parents
            for allowed in self.allowed_paths
        )
    
    def _check_path(self, path: str | Path) -> Path:
        """Validate and resolve a path, raising if not allowed."""
        resolved = Path(path).resolve()
        if not self._is_path_allowed(resolved):
            allowed_str = ", ".join(str(p) for p in self.allowed_paths)
            raise PermissionError(
                f"Access denied: '{path}' is outside allowed paths ({allowed_str})"
            )
        return resolved
    
    def read(self, path: str) -> str:
        """Read file contents.
        
        Args:
            path: Path to the file to read.
            
        Returns:
            The file contents as a string.
            
        Raises:
            PermissionError: If path is outside allowed paths.
            FileNotFoundError: If file doesn't exist.
        """
        resolved = self._check_path(path)
        return resolved.read_text()
    
    def write(self, path: str, content: str) -> bool:
        """Write content to a file.
        
        Args:
            path: Path to the file to write.
            content: Content to write.
            
        Returns:
            True if successful.
            
        Raises:
            PermissionError: If capability is read-only or path is outside allowed paths.
        """
        if self.read_only:
            raise PermissionError("This file system capability is read-only")
        
        resolved = self._check_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content)
        return True
    
    def list(self, pattern: str = "*") -> list[str]:
        """List files matching a pattern within allowed paths.
        
        Args:
            pattern: Glob pattern to match files (e.g., "*.py", "**/*.txt").
            
        Returns:
            List of matching file paths as strings.
        """
        results = []
        
        for allowed in self.allowed_paths or [Path(".")]:
            if allowed.is_dir():
                for match in allowed.glob(pattern):
                    results.append(str(match))
        
        return sorted(results)
    
    def exists(self, path: str) -> bool:
        """Check if a path exists.
        
        Args:
            path: Path to check.
            
        Returns:
            True if the path exists and is within allowed paths.
        """
        try:
            resolved = self._check_path(path)
            return resolved.exists()
        except PermissionError:
            return False
    
    def mkdir(self, path: str) -> bool:
        """Create a directory (and parents if needed).
        
        Args:
            path: Path to the directory to create.
            
        Returns:
            True if successful.
            
        Raises:
            PermissionError: If capability is read-only or path is outside allowed paths.
        """
        if self.read_only:
            raise PermissionError("This file system capability is read-only")
        
        resolved = self._check_path(path)
        resolved.mkdir(parents=True, exist_ok=True)
        return True
