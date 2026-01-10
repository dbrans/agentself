"""CLI for the sandboxed agent."""

import sys
from agentself import SandboxedAgent


def main():
    """Run the sandboxed agent in interactive mode."""
    print("Sandboxed Agent (type 'quit' to exit, 'describe' for status)")
    print("=" * 50)
    
    agent = SandboxedAgent.with_default_capabilities()
    
    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        
        if not user_input:
            continue
        
        if user_input.lower() == "quit":
            print("Goodbye!")
            break
        
        if user_input.lower() == "describe":
            print(agent.describe())
            continue
        
        if user_input.startswith("!"):
            # Direct sandbox execution
            code = user_input[1:].strip()
            result = agent.execute(code)
            print(result)
            continue
        
        try:
            response = agent.chat(user_input)
            print(response)
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
