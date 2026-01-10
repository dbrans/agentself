# Core and Capabilities
Now that we have a prototype of a repl agent that can modify its own live source, we can start to think about extending it.

## Core
- Agent lives inside of a very locked down python repl. No access to the file system or the network. Just primitives and a few libraries.

## Capabilities
- objects can be introduced into the repl as capabilities.
- These objects could have a self-documenting interface. 

### Ideas of capabilities:
- read, modify, and  and experiment with its own live source 
- communicate with the user
- read, write, files and directories 
- use the command line
- search for and install other capabilities 
- task-list to track agent tasks
- sub agents and parallel and background
- async and or parallel capability execution

### Permissioned Capabilities
We can run the python output by the llm with just proxies first to see what capabilities it is trying to use and with what arguments. Then request permission from the user for those capabilities with those arguments. Then run the with the real capabilities.

Questions:
- How might capabilities overlap with claude plugins or skills or mcp? 

