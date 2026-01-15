"""State persistence for the REPL harness.

Serializes and restores REPL state including functions, variables,
capabilities, and execution history.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentself.paths import STATE_DIR

# Optional dill import for complex object serialization
try:
    import dill
    HAS_DILL = True
except ImportError:
    HAS_DILL = False


STATE_VERSION = 1


@dataclass
class SavedFunction:
    """A serialized function definition."""
    name: str
    source: str
    signature: str
    docstring: str = ""


@dataclass
class SavedVariable:
    """A serialized variable."""
    name: str
    var_type: str  # "json", "dill", or "repr"
    value: Any  # JSON value, base64-encoded dill bytes, or repr string


@dataclass
class SavedCapability:
    """A serialized capability configuration."""
    name: str
    cap_type: str  # "relay" or "native"
    command: str | None = None  # For relay capabilities
    source: str | None = None  # For native capabilities


@dataclass
class SavedState:
    """Complete serialized REPL state."""
    version: int = STATE_VERSION
    saved_at: str = ""
    functions: list[SavedFunction] = field(default_factory=list)
    variables: list[SavedVariable] = field(default_factory=list)
    capabilities: list[SavedCapability] = field(default_factory=list)
    history: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "version": self.version,
            "saved_at": self.saved_at,
            "functions": [
                {
                    "name": f.name,
                    "source": f.source,
                    "signature": f.signature,
                    "docstring": f.docstring,
                }
                for f in self.functions
            ],
            "variables": [
                {
                    "name": v.name,
                    "type": v.var_type,
                    "value": v.value,
                }
                for v in self.variables
            ],
            "capabilities": [
                {
                    "name": c.name,
                    "type": c.cap_type,
                    "command": c.command,
                    "source": c.source,
                }
                for c in self.capabilities
            ],
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SavedState":
        """Create from JSON dict."""
        return cls(
            version=data.get("version", 1),
            saved_at=data.get("saved_at", ""),
            functions=[
                SavedFunction(
                    name=f["name"],
                    source=f["source"],
                    signature=f["signature"],
                    docstring=f.get("docstring", ""),
                )
                for f in data.get("functions", [])
            ],
            variables=[
                SavedVariable(
                    name=v["name"],
                    var_type=v["type"],
                    value=v["value"],
                )
                for v in data.get("variables", [])
            ],
            capabilities=[
                SavedCapability(
                    name=c["name"],
                    cap_type=c["type"],
                    command=c.get("command"),
                    source=c.get("source"),
                )
                for c in data.get("capabilities", [])
            ],
            history=data.get("history", []),
        )


class StateManager:
    """Manages saving and loading REPL state."""

    def __init__(self, state_dir: Path | str | None = None):
        """Initialize state manager.

        Args:
            state_dir: Directory for state files. Defaults to .agentself/state in the repo.
        """
        if state_dir is None:
            state_dir = STATE_DIR
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _get_state_path(self, name: str) -> Path:
        """Get path for a named state file."""
        # Sanitize name
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        return self.state_dir / f"{safe_name}.json"

    def save(self, state: SavedState, name: str = "default") -> Path:
        """Save state to disk.

        Args:
            state: State to save.
            name: Name for the state file.

        Returns:
            Path to the saved file.
        """
        state.saved_at = datetime.now(timezone.utc).isoformat()
        path = self._get_state_path(name)
        with open(path, "w") as f:
            json.dump(state.to_dict(), f, indent=2)
        return path

    def load(self, name: str = "default") -> SavedState | None:
        """Load state from disk.

        Args:
            name: Name of the state file.

        Returns:
            Loaded state or None if not found.
        """
        path = self._get_state_path(name)
        if not path.exists():
            return None
        with open(path) as f:
            data = json.load(f)
        return SavedState.from_dict(data)

    def list_states(self) -> list[str]:
        """List available state files.

        Returns:
            List of state names.
        """
        return [p.stem for p in self.state_dir.glob("*.json")]

    def delete(self, name: str) -> bool:
        """Delete a state file.

        Args:
            name: Name of the state to delete.

        Returns:
            True if deleted, False if not found.
        """
        path = self._get_state_path(name)
        if path.exists():
            path.unlink()
            return True
        return False


def serialize_variable(name: str, value: Any) -> SavedVariable:
    """Serialize a variable for persistence.

    Tries JSON first, then dill, then falls back to repr.
    """
    # Try JSON serialization
    try:
        json.dumps(value)
        return SavedVariable(name=name, var_type="json", value=value)
    except (TypeError, ValueError):
        pass

    # Try dill serialization
    if HAS_DILL:
        try:
            pickled = dill.dumps(value)
            encoded = base64.b64encode(pickled).decode("ascii")
            return SavedVariable(name=name, var_type="dill", value=encoded)
        except Exception:
            pass

    # Fall back to repr
    return SavedVariable(name=name, var_type="repr", value=repr(value))


def deserialize_variable(saved: SavedVariable) -> tuple[str, Any, bool]:
    """Deserialize a variable.

    Returns:
        Tuple of (name, value, success). If success is False,
        value is the error message.
    """
    if saved.var_type == "json":
        return (saved.name, saved.value, True)

    if saved.var_type == "dill":
        if not HAS_DILL:
            return (saved.name, "dill not installed", False)
        try:
            pickled = base64.b64decode(saved.value)
            value = dill.loads(pickled)
            return (saved.name, value, True)
        except Exception as e:
            return (saved.name, f"dill decode failed: {e}", False)

    # repr type - can't restore
    return (saved.name, f"repr-only value: {saved.value}", False)
