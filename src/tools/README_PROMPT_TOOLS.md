# Prompt Tools - Inheritance Pattern

This directory contains a base class system for creating MCP prompt tools that serve ready-to-use prompts from text files.

## Architecture

- **BasePromptTool** (`prompt.py`) - Base class with all the common functionality
- **Concrete Tools** (e.g., `analysis_prompt.py`) - Specific implementations that extend the base class
- **Prompt Files** (`src/prompts/*.txt`) - Text files containing the actual prompt content

## How to Create a New Prompt Tool

### Step 1: Create the Prompt File
Create a new text file in `src/prompts/` with your prompt content:
```
src/prompts/my_new_prompt.txt
```

### Step 2: Create the Tool Class
Create a new Python file in `src/tools/` that extends `BasePromptTool`:

```python
"""My new prompt tool implementation for MCP."""

from typing import Dict, Any, List
from mcp.types import Tool, TextContent
from prompt import BasePromptTool

class MyNewPromptTool(BasePromptTool):
    """MCP tool for serving my new prompts."""
    
    def __init__(self):
        super().__init__(
            tool_name="get_my_new_prompt",
            description="Get a ready-to-use prompt for my specific use case",
            prompt_filename="my_new_prompt.txt"
        )

# Global prompt tool instance
_my_new_prompt_tool = MyNewPromptTool()

def get_my_new_prompt_tool() -> MyNewPromptTool:
    """Get the global my new prompt tool instance."""
    return _my_new_prompt_tool

def get_tool_definition() -> Tool:
    """Get the MCP tool definition for get_my_new_prompt."""
    return _my_new_prompt_tool.get_tool_definition()

async def execute_my_new_prompt(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the get_my_new_prompt tool."""
    return await _my_new_prompt_tool.execute(arguments)
```

### Step 3: Register in Server
Add your new tool to `server.py` to make it available via MCP.

## Benefits of This Pattern

1. **No Code Duplication** - All common functionality is in the base class
2. **Easy to Extend** - Just inherit from `BasePromptTool` and specify your parameters
3. **Separation of Concerns** - Prompt content is in text files, logic is in Python
4. **Consistent Interface** - All prompt tools work the same way
5. **Easy Maintenance** - Update prompts by editing text files, no code changes needed

## Existing Tools

### General Analysis Tools
- `AnalysisPromptTool` - General analysis prompts (`analysis_prompt.txt`)
- `InvestigationPromptTool` - Investigation prompts (`investigation_prompt.txt`)  
- `SecurityPromptTool` - Security analysis prompts (`security_prompt.txt`)

### Splunk & Logs Tools
- `SplunkSearchQueryPromptTool` - Splunk search query generation (`splunk_search_query_prompt.txt`)
- `LogsAnalyzationPromptTool` - Log data analysis (`logs_analyzation_prompt.txt`)

### Incident Management Tools
- `RootCauseIdentificationPromptTool` - Root cause analysis (`root_cause_identification_prompt.txt`)
- `TicketDescriptionPromptTool` - Ticket description creation (`ticket_description_prompt.txt`)
- `TicketSystemIdentificationPromptTool` - Ticket system routing (`ticket_system_identification_prompt.txt`)

## Python Inheritance Explained

In Python, inheritance works like this:
- `class Child(Parent):` - Child inherits from Parent
- `super().__init__()` - Call the parent's constructor
- Child gets all Parent methods and can override them if needed
- This is equivalent to Java's `extends` keyword
