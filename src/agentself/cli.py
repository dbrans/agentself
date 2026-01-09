"""Command-line interface for the self-improving agent.

This provides a simple REPL for interacting with the agent.
"""

from __future__ import annotations

import argparse
import sys

from agentself.agent import Agent


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="A self-improving coding agent",
        prog="agentself",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Model to use (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--system-prompt",
        default=None,
        help="Custom system prompt",
    )
    return parser


def repl(agent: Agent) -> None:
    """Run an interactive REPL session with the agent."""
    print("agentself - A self-improving coding agent")
    print("Type 'quit' or 'exit' to end the session")
    print("Type '/tools' to list available tools")
    print("Type '/changes' to see uncommitted changes")
    print("-" * 50)
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        # Handle special commands
        if user_input == "/tools":
            print("\n" + agent.list_tools())
            print()
            continue

        if user_input == "/changes":
            print("\n" + agent.get_uncommitted_changes())
            print()
            continue

        if user_input == "/state":
            print("\n" + agent.get_my_state())
            print()
            continue

        # Regular chat
        try:
            response = agent.chat(user_input)
            print(f"\nAgent: {response}\n")
        except Exception as e:
            print(f"\nError: {e}\n")


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Create agent
    kwargs = {"model": args.model}
    if args.system_prompt:
        kwargs["system_prompt"] = args.system_prompt

    agent = Agent(**kwargs)

    # Run REPL
    repl(agent)

    return 0


if __name__ == "__main__":
    sys.exit(main())
