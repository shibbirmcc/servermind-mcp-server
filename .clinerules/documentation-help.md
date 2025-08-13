Routing rule:
If the user expresses intent to start the test tool planning workflow — e.g., they say “test tool planning,” “run Chain 1,” “start the planning test,” or “kick off the planning chain” — then call the chain1_planner_start tool with the argument { "userIntent": "<user's full message>" }.
After any tool returns a JSON object with "kind":"plan", follow the next list:
If autoExecuteHint:true and the first item is a tool, invoke it with its args.
Otherwise, present the next actions to the user for selection.