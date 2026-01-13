"""CLI for listing and viewing skills."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agentself.skills import SkillRegistry


def main() -> None:
    parser = argparse.ArgumentParser(description="agentself skills helper")
    parser.add_argument(
        "--root",
        default=None,
        help="Skills root directory (defaults to ./skills or AGENTSELF_SKILLS_DIR)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List available skills")
    list_parser.add_argument("--json", action="store_true", help="Output JSON")

    show_parser = sub.add_parser("show", help="Show a skill")
    show_parser.add_argument("name", help="Skill name")

    path_parser = sub.add_parser("path", help="Print skill file path")
    path_parser.add_argument("name", help="Skill name")

    args = parser.parse_args()
    registry = SkillRegistry(root=args.root)

    if args.command == "list":
        if args.json:
            print(registry.list_json())
            return
        for skill in registry.list():
            line = f"{skill.name}\t{skill.description}".rstrip()
            print(line)
        return

    if args.command == "show":
        try:
            print(registry.show(args.name))
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        return

    if args.command == "path":
        try:
            print(registry.path(args.name))
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        return


if __name__ == "__main__":
    main()
