"""Find Splunk index in repo tool implementation for MCP."""

from __future__ import annotations

from typing import Dict, Any, List
from mcp.types import Tool, TextContent
from .prompt import BasePromptTool


class FindSplunkIndexInRepoTool(BasePromptTool):
    """
    MCP tool for searching the user's repository (or a parent folder containing multiple services)
    to discover Splunk index definitions for a given environment.

    Behavior / Contract:
    - Input args are expected to include:
        {
          "env": "<free-form env name>",          # e.g., "prod", "staging", "playground"
          "attempt"?: <int>,                      # optional loop counter for retries
          "broaden"?: <bool>                      # optional hint to broaden search on retry
        }

    - The tool runs a prompt (see find_splunk_index_in_repo.txt) that instructs Cline to:
        1) Search common config locations and patterns for Splunk indices.
        2) Handle monorepo/parent-folder cases and collect ALL candidates.
        3) Return a JSON plan that immediately calls the resolver again with:
            {
              "env": "<env>",
              "status": "found" | "not_found" | "ambiguous",
              "foundIndices"?: [
                { "index": "<string>", "env": "<string|null>", "servicePath": "<string|null>", "sourceFile": "<string>" },
                ...
              ],
              "diagnostics"?: ["..."],
              "attempt": <int>
            }

    - Note: We do NOT pick a single index here. We pass all candidates back to the resolver.
    """

    def __init__(self):
        super().__init__(
            tool_name="find_splunk_index_in_repo",
            description=(
                "Search the user's codebase and configuration files to find the Splunk index name(s) "
                "for a specific environment (e.g., prod, staging, qa, uat, preprod, dev, canary, preview, "
                "playground, sandbox, demo, beta, or custom). The user may be in a parent directory that "
                "contains multiple codebases or services, so collect ALL candidate indices you find. "
                "Look for environment-to-index mappings in files such as: config/splunk/index.map.json, "
                "Helm charts (values.yaml), Kubernetes manifests, application.yml/properties, .env files, "
                "Terraform/Ansible configs, and logback/log4j configuration. Use ripgrep or similar to "
                "locate patterns like 'SPLUNK_INDEX', 'splunk.index', or 'index='. "
                "Return a JSON plan that immediately calls the resolve_splunk_index tool again with "
                "status ('found' | 'not_found' | 'ambiguous'), the env, and when available a foundIndices "
                "array of candidates (objects with index/env/servicePath/sourceFile)."
            ),
            prompt_filename="find_splunk_index_in_repo.txt",
        )


# Global tool instance
_find_splunk_index_in_repo_tool = FindSplunkIndexInRepoTool()


def get_find_splunk_index_in_repo_tool() -> FindSplunkIndexInRepoTool:
    """Get the global find splunk index in repo tool instance."""
    return _find_splunk_index_in_repo_tool


def get_tool_definition() -> Tool:
    """Get the MCP tool definition for find splunk index in repo."""
    return _find_splunk_index_in_repo_tool.get_tool_definition()


async def execute_find_splunk_index_in_repo(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Execute the find splunk index in repo tool.

    The BasePromptTool will render the prompt template with the provided `arguments`
    (e.g., env/attempt/broaden) and return the plan text produced by Cline.
    """
    # Ensure standard keys exist so the prompt template can safely render {{env}} and {{attempt}}
    arguments = dict(arguments or {})
    arguments.setdefault("env", "")
    arguments.setdefault("attempt", 0)

    return await _find_splunk_index_in_repo_tool.execute(arguments)
