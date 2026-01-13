"""File system capability with scoped access.

Provides read/write access to files, restricted to configured allowed paths.
"""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from agentself.capabilities.base import Capability
from agentself.capabilities.path_guard import (
    build_path_patterns,
    is_path_allowed,
    normalize_paths,
)

if TYPE_CHECKING:
    from agentself.core import CapabilityContract

logger = logging.getLogger(__name__)

class FileSystemCapability(Capability):
    """Read and write files within allowed paths."""

    name = "fs"
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
        self.allowed_paths = normalize_paths(allowed_paths)
        self.read_only = read_only

    def contract(self) -> "CapabilityContract":
        """Declare what this capability might do."""
        from agentself.core import CapabilityContract

        # Build path patterns from allowed_paths
        if self.allowed_paths:
            path_patterns = build_path_patterns(self.allowed_paths)
        else:
            path_patterns = ["file:**"]

        return CapabilityContract(
            reads=path_patterns,
            writes=[] if self.read_only else path_patterns,
        )

    def derive(self, **restrictions) -> "FileSystemCapability":
        """Create a more restricted version.

        Args:
            read_only: If True, disable write operations.
            allowed_paths: Restrict to these paths (must be subset of current).
        """
        new_read_only = restrictions.get("read_only", self.read_only)
        new_paths = restrictions.get("allowed_paths", self.allowed_paths)

        # Ensure new paths are subset of current paths
        if self.allowed_paths and new_paths:
            validated_paths = []
            for new_path in new_paths:
                new_resolved = Path(new_path).expanduser().resolve()
                if is_path_allowed(new_resolved, self.allowed_paths):
                    validated_paths.append(new_resolved)
            new_paths = validated_paths

        return FileSystemCapability(
            allowed_paths=new_paths,
            read_only=new_read_only or self.read_only,  # Can only make more restrictive
        )
    
    def _is_path_allowed(self, path: Path) -> bool:
        """Check if a path is within allowed paths."""
        if not self.allowed_paths:
            return True  # No restrictions
        resolved = path.resolve()
        return is_path_allowed(resolved, self.allowed_paths)
    
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
        logger.debug("fs read path=%s", resolved)
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
        logger.debug("fs write path=%s bytes=%s", resolved, len(content))
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
                logger.debug("fs list root=%s pattern=%s", allowed, pattern)
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
            logger.debug("fs exists path=%s", resolved)
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
        logger.debug("fs mkdir path=%s", resolved)
        resolved.mkdir(parents=True, exist_ok=True)
        return True
