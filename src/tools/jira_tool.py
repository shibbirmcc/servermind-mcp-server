from typing import Dict
import requests
from fastmcp import Tool, ToolCall

class JiraTicketTool(Tool):
    def __init__(self, base_url: str, username: str, api_token: str):
        super().__init__()
        self.base_url = base_url.rstrip('/')
        self.auth = (username, api_token)
        
    async def create_ticket(self, call: ToolCall) -> Dict:
        project = call.parameters.get("project")
        summary = call.parameters.get("summary")
        description = call.parameters.get("description")
        issue_type = call.parameters.get("issue_type", "Task")

        url = f"{self.base_url}/rest/api/2/issue"
        payload = {
            "fields": {
                "project": {"key": project},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type}
            }
        }
        
        try:
            response = requests.post(url, json=payload, auth=self.auth)
            response.raise_for_status()
            return {"ticket_key": response.json()["key"]}
        except Exception as e:
            return {"error": str(e)}

    def get_tool_definition(self) -> Dict:
        return {
            "name": "create_jira_ticket",
            "description": "Creates a new Jira ticket",
            "parameters": {
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Jira project key"
                    },
                    "summary": {
                        "type": "string",
                        "description": "Ticket summary/title"
                    },
                    "description": {
                        "type": "string",
                        "description": "Ticket description"
                    },
                    "issue_type": {
                        "type": "string",
                        "description": "Type of issue (Task, Bug, etc)",
                        "default": "Task"
                    }
                },
                "required": ["project", "summary", "description"]
            }
        }