from typing import Dict
import requests
from fastmcp import Tool, ToolCall

class GitHubIssueTool(Tool):
    def __init__(self, api_token: str, api_url: str = "https://api.github.com"):
        super().__init__()
        self.api_url = api_url.rstrip('/')
        self.headers = {
            "Authorization": f"token {api_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
    async def create_issue(self, call: ToolCall) -> Dict:
        owner = call.parameters.get("owner")
        repo = call.parameters.get("repo")
        title = call.parameters.get("title")
        body = call.parameters.get("body")
        labels = call.parameters.get("labels", [])

        url = f"{self.api_url}/repos/{owner}/{repo}/issues"
        payload = {
            "title": title,
            "body": body,
            "labels": labels
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return {
                "issue_number": response.json()["number"],
                "issue_url": response.json()["html_url"]
            }
        except Exception as e:
            return {"error": str(e)}

    def get_tool_definition(self) -> Dict:
        return {
            "name": "create_github_issue",
            "description": "Creates a new GitHub issue",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "Repository owner/organization"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name"
                    },
                    "title": {
                        "type": "string",
                        "description": "Issue title"
                    },
                    "body": {
                        "type": "string",
                        "description": "Issue description"
                    },
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Issue labels",
                        "default": []
                    }
                },
                "required": ["owner", "repo", "title", "body"]
            }
        }