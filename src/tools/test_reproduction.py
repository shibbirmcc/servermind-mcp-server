"""Test reproduction tool for MCP - generates tests from issue reader output."""

import json
import os
import re
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import structlog
from mcp.types import Tool, TextContent

logger = structlog.get_logger(__name__)


class TestReproductionTool:
    """MCP tool for generating comprehensive tests from issue reader output."""
    
    def __init__(self):
        """Initialize the test reproduction tool."""
        self.service_discovery = ServiceDiscovery()
        self.test_generator = TestGenerator()
        
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for test_reproduction."""
        return Tool(
            name="test_reproduction",
            description="Generate comprehensive tests from issue reader output. "
                       "Creates unit tests, integration tests, and reproduction tests for each ticket. "
                       "Supports service discovery from local filesystem or git repositories.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_reader_output": {
                        "type": "string",
                        "description": "JSON output from issue_reader containing multiple tickets with descriptions and analysis"
                    },
                    "test_types": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["unit", "integration", "reproduction", "regression"]},
                        "description": "Types of tests to generate",
                        "default": ["unit", "integration", "reproduction"]
                    },
                    "service_discovery_mode": {
                        "type": "string",
                        "enum": ["local", "git", "both"],
                        "description": "How to discover services",
                        "default": "both"
                    },
                    "local_search_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Local paths to search for service folders",
                        "default": ["../", "../../", "../../../"]
                    },
                    "git_repositories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Git repository URLs to search for services",
                        "default": []
                    },
                    "test_framework": {
                        "type": "string",
                        "enum": ["pytest", "unittest", "jest", "junit", "auto"],
                        "description": "Preferred testing framework",
                        "default": "auto"
                    },
                    "output_directory": {
                        "type": "string",
                        "description": "Directory to output generated tests",
                        "default": "tests/reproductions"
                    }
                },
                "required": ["issue_reader_output"],
                "title": "test_reproductionArguments"
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the test reproduction tool."""
        try:
            logger.info("Starting test reproduction", arguments=arguments)
            
            # Parse issue reader output
            issue_data = self._parse_issue_reader_output(arguments["issue_reader_output"])
            if not issue_data:
                return [TextContent(
                    type="text",
                    text="❌ **Invalid Issue Reader Output**\n\n"
                         "Could not parse the issue reader output. Please ensure it's valid JSON."
                )]
            
            # Extract configuration
            test_types = arguments.get("test_types", ["unit", "integration", "reproduction"])
            service_discovery_mode = arguments.get("service_discovery_mode", "both")
            local_search_paths = arguments.get("local_search_paths", ["../", "../../", "../../../"])
            git_repositories = arguments.get("git_repositories", [])
            test_framework = arguments.get("test_framework", "auto")
            output_directory = arguments.get("output_directory", "tests/reproductions")
            
            # Process tickets
            results = []
            successful_reproductions = []
            failed_reproductions = []
            
            tickets = issue_data.get("tickets", [])
            if not tickets:
                return [TextContent(
                    type="text",
                    text="❌ **No Tickets Found**\n\n"
                         "No tickets found in the issue reader output."
                )]
            
            logger.info(f"Processing {len(tickets)} tickets for test reproduction")
            
            for i, ticket in enumerate(tickets, 1):
                logger.info(f"Processing ticket {i}/{len(tickets)}", ticket=ticket.get("ticket_number"))
                
                try:
                    # Extract ticket information
                    ticket_info = self._extract_ticket_info(ticket)
                    
                    # Discover services for this ticket
                    services = await self.service_discovery.discover_services(
                        ticket_info,
                        service_discovery_mode,
                        local_search_paths,
                        git_repositories
                    )
                    
                    # Generate tests for each service
                    ticket_tests = await self.test_generator.generate_tests(
                        ticket_info,
                        services,
                        test_types,
                        test_framework,
                        output_directory
                    )
                    
                    successful_reproductions.append({
                        "ticket_number": ticket_info["ticket_number"],
                        "services": [s["name"] for s in services],
                        "tests_generated": ticket_tests,
                        "output_path": ticket_tests.get("output_path")
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing ticket {i}", error=str(e), ticket=ticket)
                    failed_reproductions.append({
                        "ticket_number": ticket.get("ticket_number", f"ticket_{i}"),
                        "error": str(e)
                    })
            
            # Generate summary report
            return self._generate_summary_report(
                successful_reproductions,
                failed_reproductions,
                output_directory
            )
            
        except Exception as e:
            logger.error("Error in test reproduction", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Test Reproduction Failed**\n\n"
                     f"An error occurred during test reproduction: {e}\n\n"
                     f"Please check your input parameters and try again."
            )]
    
    def _parse_issue_reader_output(self, output: str) -> Optional[Dict[str, Any]]:
        """Parse issue reader output JSON."""
        try:
            # Try to parse as JSON directly
            if output.strip().startswith('{') or output.strip().startswith('['):
                return json.loads(output)
            
            # Extract JSON from markdown code blocks
            json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            
            # Look for structured data section
            if "Structured Data (JSON)" in output:
                lines = output.split('\n')
                in_json = False
                json_lines = []
                
                for line in lines:
                    if line.strip() == "```json":
                        in_json = True
                        continue
                    elif line.strip() == "```" and in_json:
                        break
                    elif in_json:
                        json_lines.append(line)
                
                if json_lines:
                    return json.loads('\n'.join(json_lines))
            
            return None
            
        except Exception as e:
            logger.warning("Failed to parse issue reader output", error=str(e))
            return None
    
    def _extract_ticket_info(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant information from a ticket."""
        return {
            "ticket_number": ticket.get("ticket_number", "unknown"),
            "platform": ticket.get("platform", "unknown"),
            "title": ticket.get("title", ""),
            "description": ticket.get("description", ""),
            "status": ticket.get("status", ""),
            "labels": ticket.get("labels", []),
            "assignees": ticket.get("assignees", []),
            "services": self._extract_services_from_ticket(ticket),
            "bug_analysis": self._extract_bug_analysis(ticket),
            "root_cause": self._extract_root_cause(ticket),
            "error_patterns": self._extract_error_patterns(ticket),
            "stack_traces": self._extract_stack_traces(ticket)
        }
    
    def _extract_services_from_ticket(self, ticket: Dict[str, Any]) -> List[str]:
        """Extract service names from ticket title and description."""
        services = []
        text = f"{ticket.get('title', '')} {ticket.get('description', '')}"
        
        # Common service name patterns
        service_patterns = [
            r'\b(\w+[-_]?service)\b',
            r'\b(\w+[-_]?api)\b',
            r'\b(\w+[-_]?app)\b',
            r'\b(\w+[-_]?microservice)\b',
            r'service[:\s]+(\w+)',
            r'in\s+(\w+)\s+service',
            r'(\w+)\s+component',
            r'(\w+)\s+module'
        ]
        
        for pattern in service_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            services.extend(matches)
        
        # Remove duplicates and common words
        common_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        services = list(set([s.lower() for s in services if s.lower() not in common_words]))
        
        return services
    
    def _extract_bug_analysis(self, ticket: Dict[str, Any]) -> str:
        """Extract bug analysis from ticket description."""
        description = ticket.get("description", "")
        
        # Look for analysis sections
        analysis_patterns = [
            r'(?:bug analysis|analysis|issue analysis)[:\s]*(.*?)(?:\n\n|\n#|\nroot cause|$)',
            r'(?:problem|issue)[:\s]*(.*?)(?:\n\n|\n#|\nroot cause|$)',
            r'(?:description|summary)[:\s]*(.*?)(?:\n\n|\n#|\nroot cause|$)'
        ]
        
        for pattern in analysis_patterns:
            match = re.search(pattern, description, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        # Fallback to first paragraph
        paragraphs = description.split('\n\n')
        return paragraphs[0] if paragraphs else description
    
    def _extract_root_cause(self, ticket: Dict[str, Any]) -> str:
        """Extract root cause from ticket description."""
        description = ticket.get("description", "")
        
        # Look for root cause sections
        root_cause_patterns = [
            r'(?:root cause|cause|reason)[:\s]*(.*?)(?:\n\n|\n#|$)',
            r'(?:identified|found|discovered)[:\s]*(.*?)(?:\n\n|\n#|$)',
            r'(?:due to|because of|caused by)[:\s]*(.*?)(?:\n\n|\n#|$)'
        ]
        
        for pattern in root_cause_patterns:
            match = re.search(pattern, description, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return ""
    
    def _extract_error_patterns(self, ticket: Dict[str, Any]) -> List[str]:
        """Extract error patterns from ticket description."""
        description = ticket.get("description", "")
        patterns = []
        
        # Look for error messages
        error_patterns = [
            r'error[:\s]*([^\n]+)',
            r'exception[:\s]*([^\n]+)',
            r'failed[:\s]*([^\n]+)',
            r'timeout[:\s]*([^\n]+)',
            r'connection[:\s]*([^\n]+)'
        ]
        
        for pattern in error_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            patterns.extend(matches)
        
        return list(set(patterns))
    
    def _extract_stack_traces(self, ticket: Dict[str, Any]) -> List[str]:
        """Extract stack traces from ticket description."""
        description = ticket.get("description", "")
        traces = []
        
        # Look for stack trace patterns
        trace_patterns = [
            r'```(?:python|java|javascript|js)?\s*\n(.*?)\n```',
            r'Traceback.*?(?:\n\s+.*?)*',
            r'at\s+\w+.*?(?:\n\s+at\s+.*?)*'
        ]
        
        for pattern in trace_patterns:
            matches = re.findall(pattern, description, re.DOTALL)
            traces.extend(matches)
        
        return traces
    
    def _generate_summary_report(
        self,
        successful: List[Dict[str, Any]],
        failed: List[Dict[str, Any]],
        output_directory: str
    ) -> List[TextContent]:
        """Generate summary report of test reproduction results."""
        
        total_tickets = len(successful) + len(failed)
        
        report = f"🧪 **Test Reproduction Results**\n\n"
        report += f"**Summary:**\n"
        report += f"- Total tickets processed: {total_tickets}\n"
        report += f"- Successfully reproduced: {len(successful)}\n"
        report += f"- Failed to reproduce: {len(failed)}\n"
        report += f"- Success rate: {(len(successful) / total_tickets * 100):.1f}%\n\n"
        
        if successful:
            report += f"## ✅ Successfully Reproduced ({len(successful)})\n\n"
            for i, result in enumerate(successful, 1):
                report += f"**{i}. {result['ticket_number']}**\n"
                report += f"   - **Services:** {', '.join(result['services'])}\n"
                report += f"   - **Tests Generated:** {result['tests_generated'].get('total_tests', 0)}\n"
                report += f"   - **Output Path:** `{result.get('output_path', 'N/A')}`\n"
                
                test_types = result['tests_generated'].get('test_types', {})
                if test_types:
                    report += f"   - **Test Types:** "
                    type_details = []
                    for test_type, count in test_types.items():
                        type_details.append(f"{test_type}({count})")
                    report += ", ".join(type_details) + "\n"
                report += "\n"
        
        if failed:
            report += f"## ❌ Failed to Reproduce ({len(failed)})\n\n"
            for i, result in enumerate(failed, 1):
                report += f"**{i}. {result['ticket_number']}**\n"
                report += f"   - **Error:** {result['error']}\n\n"
        
        # Add usage instructions
        report += f"---\n\n"
        report += f"## 🚀 Running Generated Tests\n\n"
        report += f"Navigate to the output directory and run tests:\n\n"
        report += f"```bash\n"
        report += f"cd {output_directory}\n"
        report += f"# Run all reproduction tests\n"
        report += f"find . -name 'test_*.py' -exec python -m pytest {{}} \\;\n"
        report += f"# Or run specific ticket tests\n"
        report += f"python -m pytest ticket_*/\n"
        report += f"```\n\n"
        
        report += f"## 📁 Generated Test Structure\n\n"
        report += f"```\n"
        report += f"{output_directory}/\n"
        for result in successful:
            ticket_num = result['ticket_number']
            report += f"├── {ticket_num}/\n"
            for service in result['services']:
                report += f"│   ├── {service}/\n"
                report += f"│   │   ├── test_reproduction.py\n"
                report += f"│   │   ├── test_unit.py\n"
                report += f"│   │   └── test_integration.py\n"
            report += f"│   ├── README.md\n"
            report += f"│   └── run_tests.sh\n"
        report += f"└── shared/\n"
        report += f"    ├── fixtures/\n"
        report += f"    ├── mocks/\n"
        report += f"    └── utilities/\n"
        report += f"```\n\n"
        
        report += f"*Generated tests include reproduction scenarios, unit tests for identified issues, and integration tests for service interactions.*"
        
        return [TextContent(type="text", text=report)]


class ServiceDiscovery:
    """Service discovery engine for finding matching services."""
    
    async def discover_services(
        self,
        ticket_info: Dict[str, Any],
        mode: str,
        local_paths: List[str],
        git_repos: List[str]
    ) -> List[Dict[str, Any]]:
        """Discover services mentioned in the ticket."""
        services = []
        service_names = ticket_info.get("services", [])
        
        if not service_names:
            # Try to extract from title/description if not found
            service_names = self._extract_service_names_fallback(ticket_info)
        
        for service_name in service_names:
            service_info = await self._find_service(service_name, mode, local_paths, git_repos)
            if service_info:
                services.append(service_info)
        
        # If no services found, create a generic service entry
        if not services:
            services.append({
                "name": "unknown_service",
                "path": None,
                "language": "python",
                "framework": "generic",
                "test_framework": "pytest"
            })
        
        return services
    
    def _extract_service_names_fallback(self, ticket_info: Dict[str, Any]) -> List[str]:
        """Fallback method to extract service names."""
        text = f"{ticket_info.get('title', '')} {ticket_info.get('description', '')}"
        
        # Look for common service indicators
        words = re.findall(r'\b\w+\b', text.lower())
        service_indicators = ['service', 'api', 'app', 'server', 'component', 'module']
        
        potential_services = []
        for i, word in enumerate(words):
            if word in service_indicators and i > 0:
                potential_services.append(words[i-1])
            elif word.endswith('service') or word.endswith('api'):
                potential_services.append(word)
        
        return list(set(potential_services))[:3]  # Limit to 3 services
    
    async def _find_service(
        self,
        service_name: str,
        mode: str,
        local_paths: List[str],
        git_repos: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Find a specific service."""
        
        if mode in ["local", "both"]:
            # Search locally first
            local_service = await self._search_local_service(service_name, local_paths)
            if local_service:
                return local_service
        
        if mode in ["git", "both"]:
            # Search in git repositories
            git_service = await self._search_git_service(service_name, git_repos)
            if git_service:
                return git_service
        
        return None
    
    async def _search_local_service(
        self,
        service_name: str,
        local_paths: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Search for service in local filesystem."""
        
        for base_path in local_paths:
            try:
                base_path = Path(base_path).resolve()
                if not base_path.exists():
                    continue
                
                # Search for directories matching service name
                for item in base_path.rglob("*"):
                    if item.is_dir() and self._is_service_match(item.name, service_name):
                        service_info = await self._analyze_service_directory(item)
                        if service_info:
                            service_info["name"] = service_name
                            service_info["path"] = str(item)
                            return service_info
                        
            except Exception as e:
                logger.warning(f"Error searching local path {base_path}", error=str(e))
        
        return None
    
    async def _search_git_service(
        self,
        service_name: str,
        git_repos: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Search for service in git repositories."""
        
        for repo_url in git_repos:
            try:
                # Clone or update repository
                repo_path = await self._clone_or_update_repo(repo_url)
                if repo_path:
                    # Search in the cloned repository
                    local_service = await self._search_local_service(service_name, [str(repo_path)])
                    if local_service:
                        return local_service
                        
            except Exception as e:
                logger.warning(f"Error searching git repo {repo_url}", error=str(e))
        
        return None
    
    def _is_service_match(self, dir_name: str, service_name: str) -> bool:
        """Check if directory name matches service name."""
        dir_name = dir_name.lower()
        service_name = service_name.lower()
        
        # Exact match
        if dir_name == service_name:
            return True
        
        # Fuzzy matching
        if service_name in dir_name or dir_name in service_name:
            return True
        
        # Remove common suffixes/prefixes
        cleaned_dir = re.sub(r'[-_](service|api|app|server)$', '', dir_name)
        cleaned_service = re.sub(r'[-_](service|api|app|server)$', '', service_name)
        
        return cleaned_dir == cleaned_service
    
    async def _analyze_service_directory(self, service_path: Path) -> Optional[Dict[str, Any]]:
        """Analyze service directory to determine language and framework."""
        
        # Check for common files to determine language and framework
        files = list(service_path.glob("*"))
        file_names = [f.name for f in files]
        
        service_info = {
            "language": "unknown",
            "framework": "unknown",
            "test_framework": "unknown",
            "dependencies": []
        }
        
        # Python detection
        if any(f in file_names for f in ["requirements.txt", "setup.py", "pyproject.toml", "Pipfile"]):
            service_info["language"] = "python"
            service_info["test_framework"] = "pytest"
            
            # Framework detection
            if "app.py" in file_names or "main.py" in file_names:
                if any("flask" in f.read_text().lower() for f in files if f.name.endswith(".py")):
                    service_info["framework"] = "flask"
                elif any("fastapi" in f.read_text().lower() for f in files if f.name.endswith(".py")):
                    service_info["framework"] = "fastapi"
                elif any("django" in f.read_text().lower() for f in files if f.name.endswith(".py")):
                    service_info["framework"] = "django"
        
        # JavaScript/Node.js detection
        elif "package.json" in file_names:
            service_info["language"] = "javascript"
            service_info["test_framework"] = "jest"
            
            try:
                package_json = json.loads((service_path / "package.json").read_text())
                deps = {**package_json.get("dependencies", {}), **package_json.get("devDependencies", {})}
                
                if "express" in deps:
                    service_info["framework"] = "express"
                elif "react" in deps:
                    service_info["framework"] = "react"
                elif "vue" in deps:
                    service_info["framework"] = "vue"
                    
            except Exception:
                pass
        
        # Java detection
        elif any(f in file_names for f in ["pom.xml", "build.gradle", "build.gradle.kts"]):
            service_info["language"] = "java"
            service_info["test_framework"] = "junit"
            
            if "pom.xml" in file_names:
                service_info["framework"] = "maven"
            else:
                service_info["framework"] = "gradle"
        
        return service_info if service_info["language"] != "unknown" else None
    
    async def _clone_or_update_repo(self, repo_url: str) -> Optional[Path]:
        """Clone or update a git repository."""
        try:
            # Create a temporary directory for cloned repos
            clone_dir = Path("temp_repos")
            clone_dir.mkdir(exist_ok=True)
            
            # Extract repo name from URL
            repo_name = repo_url.split("/")[-1].replace(".git", "")
            repo_path = clone_dir / repo_name
            
            if repo_path.exists():
                # Update existing repo
                process = await asyncio.create_subprocess_exec(
                    "git", "pull",
                    cwd=repo_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
            else:
                # Clone new repo
                process = await asyncio.create_subprocess_exec(
                    "git", "clone", repo_url, str(repo_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
            
            return repo_path if repo_path.exists() else None
            
        except Exception as e:
            logger.warning(f"Error cloning/updating repo {repo_url}", error=str(e))
            return None


class TestGenerator:
    """Test generator for creating various types of tests."""
    
    async def generate_tests(
        self,
        ticket_info: Dict[str, Any],
        services: List[Dict[str, Any]],
        test_types: List[str],
        test_framework: str,
        output_directory: str
    ) -> Dict[str, Any]:
        """Generate tests for a ticket across multiple services."""
        
        ticket_number = ticket_info["ticket_number"]
        ticket_dir = Path(output_directory) / ticket_number
        ticket_dir.mkdir(parents=True, exist_ok=True)
        
        total_tests = 0
        test_type_counts = {}
        
        # Generate tests for each service
        for service in services:
            service_dir = ticket_dir / service["name"]
            service_dir.mkdir(exist_ok=True)
            
            # Determine test framework if auto
            framework = test_framework
            if framework == "auto":
                framework = service.get("test_framework", "pytest")
            
            # Generate different types of tests
            for test_type in test_types:
                test_count = await self._generate_test_type(
                    ticket_info,
                    service,
                    test_type,
                    framework,
                    service_dir
                )
                total_tests += test_count
                test_type_counts[test_type] = test_type_counts.get(test_type, 0) + test_count
        
        # Generate shared utilities and fixtures
        await self._generate_shared_resources(ticket_info, services, ticket_dir)
        
        # Generate README and run script
        await self._generate_documentation(ticket_info, services, test_types, ticket_dir)
        
        return {
            "total_tests": total_tests,
            "test_types": test_type_counts,
            "output_path": str(ticket_dir)
        }
    
    async def _generate_test_type(
        self,
        ticket_info: Dict[str, Any],
        service: Dict[str, Any],
        test_type: str,
        framework: str,
        output_dir: Path
    ) -> int:
        """Generate a specific type of test."""
        
        if framework == "pytest":
            return await self._generate_pytest_tests(ticket_info, service, test_type, output_dir)
        elif framework == "jest":
            return await self._generate_jest_tests(ticket_info, service, test_type, output_dir)
        elif framework == "junit":
            return await self._generate_junit_tests(ticket_info, service, test_type, output_dir)
        else:
            return await self._generate_generic_tests(ticket_info, service, test_type, output_dir)
    
    async def _generate_pytest_tests(
        self,
        ticket_info: Dict[str, Any],
        service: Dict[str, Any],
        test_type: str,
        output_dir: Path
    ) -> int:
        """Generate pytest tests."""
        
        test_file = output_dir / f"test_{test_type}.py"
        
        # Generate test content based on type
        if test_type == "reproduction":
            content = self._generate_reproduction_test_pytest(ticket_info, service)
        elif test_type == "unit":
            content = self._generate_unit_test_pytest(ticket_info, service)
        elif test_type == "integration":
            content = self._generate_integration_test_pytest(ticket_info, service)
        elif test_type == "regression":
            content = self._generate_regression_test_pytest(ticket_info, service)
        else:
            content = self._generate_generic_test_pytest(ticket_info, service, test_type)
        
        test_file.write_text(content)
        return content.count("def test_")
    
    def _load_and_format_template(self, template_name: str, ticket_info: Dict[str, Any], service: Dict[str, Any]) -> str:
        """Load and format a template file."""
        try:
            template_path = Path(__file__).parent.parent / "prompts" / template_name
            template_content = template_path.read_text()
            
            # Format the template with ticket and service information
            return template_content.format(
                ticket_number=ticket_info["ticket_number"],
                service_name=service["name"],
                title=ticket_info["title"],
                bug_analysis=ticket_info.get("bug_analysis", ""),
                root_cause=ticket_info.get("root_cause", ""),
                error_patterns=ticket_info.get("error_patterns", []),
                services=ticket_info.get("services", [])
            )
        except Exception as e:
            logger.warning(f"Failed to load template {template_name}", error=str(e))
            return f"# Template {template_name} could not be loaded: {e}"
    
    def _generate_reproduction_test_pytest(self, ticket_info: Dict[str, Any], service: Dict[str, Any]) -> str:
        """Generate reproduction test in pytest format."""
        return self._load_and_format_template(
            "test_reproduction_pytest.txt",
            ticket_info,
            service
        )
    
    def _generate_unit_test_pytest(self, ticket_info: Dict[str, Any], service: Dict[str, Any]) -> str:
        """Generate unit test in pytest format."""
        return self._load_and_format_template(
            "test_unit_pytest.txt",
            ticket_info,
            service
        )
    
    def _generate_integration_test_pytest(self, ticket_info: Dict[str, Any], service: Dict[str, Any]) -> str:
        """Generate integration test in pytest format."""
        return self._load_and_format_template(
            "test_integration_pytest.txt",
            ticket_info,
            service
        )
    
    def _generate_regression_test_pytest(self, ticket_info: Dict[str, Any], service: Dict[str, Any]) -> str:
        """Generate regression test in pytest format."""
        return self._load_and_format_template(
            "test_regression_pytest.txt",
            ticket_info,
            service
        )
    
    def _generate_generic_test_pytest(self, ticket_info: Dict[str, Any], service: Dict[str, Any], test_type: str) -> str:
        """Generate generic test in pytest format."""
        
        ticket_number = ticket_info["ticket_number"]
        title = ticket_info["title"]
        
        content = f'''"""
{test_type.title()} tests for ticket {ticket_number}
Service: {service["name"]}
Title: {title}

This test file contains {test_type} tests for the ticket.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime


class Test{test_type.title()}:
    """Test class for {test_type} testing."""
    
    def setup_method(self):
        """Set up test environment."""
        self.service = Mock()
        self.test_data = {{"key": "value"}}
    
    def test_{test_type}_scenario(self):
        """Test {test_type} scenario for the ticket."""
        # TODO: Implement {test_type} test based on ticket analysis
        
        assert True, "Replace with actual {test_type} test implementation"
    
    def test_{test_type}_edge_cases(self):
        """Test {test_type} edge cases."""
        # TODO: Test edge cases for {test_type} testing
        
        edge_cases = [None, "", {{}}, {{"invalid": True}}]
        
        for case in edge_cases:
            # TODO: Test each edge case
            pass
        
        assert True, "Replace with actual edge case testing"


# {test_type.title()} test fixtures
@pytest.fixture
def {test_type}_test_data():
    """Provide test data for {test_type} tests."""
    return {{"test": "data"}}
'''
        
        return content
    
    async def _generate_jest_tests(self, ticket_info: Dict[str, Any], service: Dict[str, Any], test_type: str, output_dir: Path) -> int:
        """Generate Jest tests for JavaScript services."""
        
        test_file = output_dir / f"{test_type}.test.js"
        ticket_number = ticket_info["ticket_number"]
        title = ticket_info["title"]
        
        content = f'''/**
 * {test_type.title()} tests for ticket {ticket_number}
 * Service: {service["name"]}
 * Title: {title}
 */

const {{ describe, it, expect, beforeEach, afterEach, jest }} = require('@jest/globals');

describe('{service["name"]} - {test_type.title()} Tests', () => {{
    let service;
    let mockDependencies;
    
    beforeEach(() => {{
        // Set up test environment
        mockDependencies = {{
            database: jest.fn(),
            cache: jest.fn(),
            externalApi: jest.fn()
        }};
        
        // TODO: Replace with actual service instantiation
        service = {{
            // Mock service methods
            processData: jest.fn(),
            validateInput: jest.fn(),
            handleError: jest.fn()
        }};
    }});
    
    afterEach(() => {{
        jest.clearAllMocks();
    }});
    
    it('should handle the scenario from ticket {ticket_number}', async () => {{
        // TODO: Implement test based on ticket analysis
        
        const testData = {{ key: 'value' }};
        const expectedResult = {{ status: 'success' }};
        
        service.processData.mockResolvedValue(expectedResult);
        
        const result = await service.processData(testData);
        
        expect(result).toEqual(expectedResult);
        expect(service.processData).toHaveBeenCalledWith(testData);
    }});
    
    it('should handle error cases properly', async () => {{
        // TODO: Test error handling scenarios
        
        const invalidData = {{ key: null }};
        
        service.processData.mockRejectedValue(new Error('Invalid input'));
        
        await expect(service.processData(invalidData)).rejects.toThrow('Invalid input');
    }});
    
    it('should handle edge cases', () => {{
        // TODO: Test edge cases identified in the ticket
        
        const edgeCases = [null, undefined, '', {{}}, []];
        
        edgeCases.forEach(edgeCase => {{
            // TODO: Test each edge case
            expect(() => service.validateInput(edgeCase)).not.toThrow();
        }});
    }});
}});

// Additional test utilities
const TestUtils = {{
    createMockService: () => ({{
        // TODO: Create mock service instance
        processData: jest.fn(),
        validateInput: jest.fn()
    }}),
    
    createTestData: () => ({{
        valid: {{ key: 'value' }},
        invalid: {{ key: null }},
        edge: {{}}
    }})
}};

module.exports = {{ TestUtils }};
'''
        
        test_file.write_text(content)
        return content.count('it(')
    
    async def _generate_junit_tests(self, ticket_info: Dict[str, Any], service: Dict[str, Any], test_type: str, output_dir: Path) -> int:
        """Generate JUnit tests for Java services."""
        
        test_file = output_dir / f"{test_type.title()}Test.java"
        ticket_number = ticket_info["ticket_number"]
        title = ticket_info["title"]
        class_name = f"{test_type.title()}Test"
        
        content = f'''/**
 * {test_type.title()} tests for ticket {ticket_number}
 * Service: {service["name"]}
 * Title: {title}
 */

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@DisplayName("{service["name"]} - {test_type.title()} Tests")
public class {class_name} {{
    
    @Mock
    private ServiceDependency mockDependency;
    
    private ServiceClass serviceUnderTest;
    
    @BeforeEach
    void setUp() {{
        MockitoAnnotations.openMocks(this);
        // TODO: Replace with actual service instantiation
        serviceUnderTest = new ServiceClass(mockDependency);
    }}
    
    @AfterEach
    void tearDown() {{
        // Clean up resources if needed
    }}
    
    @Test
    @DisplayName("Should handle scenario from ticket {ticket_number}")
    void shouldHandleTicketScenario() {{
        // TODO: Implement test based on ticket analysis
        
        // Arrange
        TestData testData = new TestData("test", "value");
        ExpectedResult expectedResult = new ExpectedResult("success");
        when(mockDependency.process(any())).thenReturn(expectedResult);
        
        // Act
        Result actualResult = serviceUnderTest.processData(testData);
        
        // Assert
        assertNotNull(actualResult);
        assertEquals(expectedResult.getStatus(), actualResult.getStatus());
        verify(mockDependency).process(testData);
    }}
    
    @Test
    @DisplayName("Should handle error cases properly")
    void shouldHandleErrorCases() {{
        // TODO: Test error handling scenarios
        
        // Arrange
        TestData invalidData = new TestData(null, null);
        when(mockDependency.process(any())).thenThrow(new IllegalArgumentException("Invalid input"));
        
        // Act & Assert
        assertThrows(IllegalArgumentException.class, () -> {{
            serviceUnderTest.processData(invalidData);
        }});
    }}
    
    @Test
    @DisplayName("Should handle edge cases")
    void shouldHandleEdgeCases() {{
        // TODO: Test edge cases identified in the ticket
        
        TestData[] edgeCases = {{
            new TestData(null, "value"),
            new TestData("", ""),
            new TestData("key", null)
        }};
        
        for (TestData edgeCase : edgeCases) {{
            // TODO: Test each edge case
            assertDoesNotThrow(() -> {{
                serviceUnderTest.validateInput(edgeCase);
            }});
        }}
    }}
    
    // Helper classes for testing
    private static class TestData {{
        private String key;
        private String value;
        
        public TestData(String key, String value) {{
            this.key = key;
            this.value = value;
        }}
        
        // Getters and setters
        public String getKey() {{ return key; }}
        public String getValue() {{ return value; }}
    }}
    
    private static class ExpectedResult {{
        private String status;
        
        public ExpectedResult(String status) {{
            this.status = status;
        }}
        
        public String getStatus() {{ return status; }}
    }}
}}
'''
        
        test_file.write_text(content)
        return content.count('@Test')
    
    async def _generate_generic_tests(self, ticket_info: Dict[str, Any], service: Dict[str, Any], test_type: str, output_dir: Path) -> int:
        """Generate generic tests for unknown frameworks."""
        
        test_file = output_dir / f"test_{test_type}.txt"
        ticket_number = ticket_info["ticket_number"]
        title = ticket_info["title"]
        
        content = f'''# {test_type.title()} Test Plan for Ticket {ticket_number}

Service: {service["name"]}
Title: {title}
Framework: {service.get("framework", "unknown")}
Language: {service.get("language", "unknown")}

## Test Scenarios

### 1. Primary Test Scenario
- Description: Test the main functionality affected by the ticket
- Input: [Define test input based on ticket analysis]
- Expected Output: [Define expected behavior]
- Steps:
  1. Set up test environment
  2. Execute the functionality
  3. Verify results
  4. Clean up

### 2. Error Case Testing
- Description: Test error conditions mentioned in the ticket
- Input: [Define invalid/error inputs]
- Expected Output: [Define expected error handling]
- Steps:
  1. Prepare error conditions
  2. Execute functionality
  3. Verify error handling
  4. Check error messages

### 3. Edge Case Testing
- Description: Test boundary conditions and edge cases
- Test Cases:
  - Null/empty inputs
  - Maximum/minimum values
  - Invalid data types
  - Concurrent access scenarios

## Implementation Notes

TODO: Convert this test plan into actual test code for the {service.get("language", "unknown")} language.

### Required Dependencies
- Testing framework: {service.get("test_framework", "unknown")}
- Mocking library: [Specify based on language]
- Additional libraries: [List any specific requirements]

### Test Data
- Valid test data: [Define based on ticket analysis]
- Invalid test data: [Define error scenarios]
- Edge case data: [Define boundary conditions]

### Expected Results
- Success scenarios: [Define expected successful outcomes]
- Error scenarios: [Define expected error handling]
- Performance expectations: [Define if applicable]
'''
        
        test_file.write_text(content)
        return 3  # Return estimated number of test scenarios
    
    async def _generate_shared_resources(self, ticket_info: Dict[str, Any], services: List[Dict[str, Any]], ticket_dir: Path):
        """Generate shared resources like fixtures, mocks, and utilities."""
        
        shared_dir = ticket_dir / "shared"
        shared_dir.mkdir(exist_ok=True)
        
        # Create fixtures directory
        fixtures_dir = shared_dir / "fixtures"
        fixtures_dir.mkdir(exist_ok=True)
        
        # Create mocks directory
        mocks_dir = shared_dir / "mocks"
        mocks_dir.mkdir(exist_ok=True)
        
        # Create utilities directory
        utilities_dir = shared_dir / "utilities"
        utilities_dir.mkdir(exist_ok=True)
        
        # Generate shared fixtures
        await self._generate_shared_fixtures(ticket_info, services, fixtures_dir)
        
        # Generate shared mocks
        await self._generate_shared_mocks(ticket_info, services, mocks_dir)
        
        # Generate shared utilities
        await self._generate_shared_utilities(ticket_info, services, utilities_dir)
    
    async def _generate_shared_fixtures(self, ticket_info: Dict[str, Any], services: List[Dict[str, Any]], fixtures_dir: Path):
        """Generate shared test fixtures."""
        
        # Generate common fixtures file
        fixtures_file = fixtures_dir / "common_fixtures.py"
        
        content = f'''"""
Shared test fixtures for ticket {ticket_info["ticket_number"]}

This module contains common test fixtures that can be used across multiple test files.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock


@pytest.fixture
def ticket_context():
    """Provide ticket context for all tests."""
    return {{
        "ticket_number": "{ticket_info["ticket_number"]}",
        "title": "{ticket_info["title"]}",
        "services": {[s["name"] for s in services]},
        "timestamp": datetime.now(),
        "bug_analysis": "{ticket_info.get("bug_analysis", "")}",
        "root_cause": "{ticket_info.get("root_cause", "")}",
        "error_patterns": {ticket_info.get("error_patterns", [])}
    }}


@pytest.fixture
def test_database():
    """Provide a test database connection."""
    # TODO: Set up actual test database or mock
    mock_db = Mock()
    mock_db.query.return_value = []
    mock_db.insert.return_value = True
    mock_db.update.return_value = True
    mock_db.delete.return_value = True
    return mock_db


@pytest.fixture
def test_cache():
    """Provide a test cache instance."""
    mock_cache = Mock()
    mock_cache.get.return_value = None
    mock_cache.set.return_value = True
    mock_cache.delete.return_value = True
    return mock_cache


@pytest.fixture
def test_config():
    """Provide test configuration."""
    return {{
        "database_url": "sqlite:///:memory:",
        "cache_ttl": 300,
        "api_timeout": 30,
        "retry_attempts": 3,
        "debug": True
    }}


@pytest.fixture
def sample_data():
    """Provide sample data for testing."""
    return {{
        "valid_record": {{
            "id": 1,
            "name": "test_record",
            "created_at": datetime.now().isoformat(),
            "status": "active"
        }},
        "invalid_record": {{
            "id": None,
            "name": "",
            "created_at": None,
            "status": "invalid"
        }},
        "edge_cases": [
            {{}},  # Empty object
            None,  # Null value
            {{"id": 0}},  # Zero ID
            {{"id": -1}},  # Negative ID
            {{"name": "x" * 1000}}  # Very long name
        ]
    }}


@pytest.fixture
def mock_external_services():
    """Provide mocks for external services."""
    return {{
        "payment_service": Mock(),
        "notification_service": Mock(),
        "audit_service": Mock(),
        "logging_service": Mock()
    }}


@pytest.fixture(scope="session")
def test_session_data():
    """Provide session-level test data."""
    return {{
        "session_id": "test_session_123",
        "user_id": "test_user_456",
        "tenant_id": "test_tenant_789"
    }}
'''
        
        fixtures_file.write_text(content)
        
        # Generate service-specific fixtures
        for service in services:
            service_fixtures_file = fixtures_dir / f"{service['name']}_fixtures.py"
            
            service_content = f'''"""
Service-specific fixtures for {service["name"]}
"""

import pytest
from unittest.mock import Mock


@pytest.fixture
def {service["name"]}_instance():
    """Provide a {service["name"]} service instance."""
    # TODO: Replace with actual service instantiation
    mock_service = Mock()
    mock_service.process.return_value = {{"status": "success"}}
    mock_service.validate.return_value = True
    return mock_service


@pytest.fixture
def {service["name"]}_config():
    """Provide configuration for {service["name"]}."""
    return {{
        "service_name": "{service["name"]}",
        "language": "{service.get("language", "unknown")}",
        "framework": "{service.get("framework", "unknown")}",
        "test_framework": "{service.get("test_framework", "unknown")}"
    }}


@pytest.fixture
def {service["name"]}_test_data():
    """Provide test data specific to {service["name"]}."""
    return {{
        "input_data": {{"key": "value", "service": "{service["name"]}"}},
        "expected_output": {{"result": "processed", "service": "{service["name"]}"}},
        "error_data": {{"invalid": True, "service": "{service["name"]}"}}
    }}
'''
            
            service_fixtures_file.write_text(service_content)
    
    async def _generate_shared_mocks(self, ticket_info: Dict[str, Any], services: List[Dict[str, Any]], mocks_dir: Path):
        """Generate shared mock objects."""
        
        # Generate common mocks file
        mocks_file = mocks_dir / "common_mocks.py"
        
        content = f'''"""
Shared mock objects for ticket {ticket_info["ticket_number"]}

This module contains common mock objects that can be reused across tests.
"""

from unittest.mock import Mock, MagicMock
from datetime import datetime


class DatabaseMock:
    """Mock database class with common database operations."""
    
    def __init__(self):
        self.data = {{}}
        self.call_count = 0
    
    def query(self, sql, params=None):
        """Mock database query."""
        self.call_count += 1
        return []
    
    def insert(self, table, data):
        """Mock database insert."""
        self.call_count += 1
        record_id = len(self.data) + 1
        self.data[record_id] = data
        return record_id
    
    def update(self, table, data, where):
        """Mock database update."""
        self.call_count += 1
        return True
    
    def delete(self, table, where):
        """Mock database delete."""
        self.call_count += 1
        return True


class CacheMock:
    """Mock cache class with common cache operations."""
    
    def __init__(self):
        self.cache = {{}}
        self.call_count = 0
    
    def get(self, key):
        """Mock cache get."""
        self.call_count += 1
        return self.cache.get(key)
    
    def set(self, key, value, ttl=None):
        """Mock cache set."""
        self.call_count += 1
        self.cache[key] = value
        return True
    
    def delete(self, key):
        """Mock cache delete."""
        self.call_count += 1
        if key in self.cache:
            del self.cache[key]
        return True


class ExternalServiceMock:
    """Mock external service with common API operations."""
    
    def __init__(self, service_name="external_service"):
        self.service_name = service_name
        self.call_count = 0
        self.responses = {{}}
    
    def get(self, endpoint, params=None):
        """Mock GET request."""
        self.call_count += 1
        return self.responses.get(endpoint, {{"status": "success", "data": []}})
    
    def post(self, endpoint, data=None):
        """Mock POST request."""
        self.call_count += 1
        return {{"status": "created", "id": 123}}
    
    def put(self, endpoint, data=None):
        """Mock PUT request."""
        self.call_count += 1
        return {{"status": "updated"}}
    
    def delete(self, endpoint):
        """Mock DELETE request."""
        self.call_count += 1
        return {{"status": "deleted"}}
    
    def set_response(self, endpoint, response):
        """Set a specific response for an endpoint."""
        self.responses[endpoint] = response


class ServiceMockFactory:
    """Factory for creating service-specific mocks."""
    
    @staticmethod
    def create_service_mock(service_name, service_config=None):
        """Create a mock for a specific service."""
        mock = Mock()
        mock.name = service_name
        mock.config = service_config or {{}}
        mock.process.return_value = {{"status": "success", "service": service_name}}
        mock.validate.return_value = True
        mock.health_check.return_value = {{"status": "healthy"}}
        return mock
    
    @staticmethod
    def create_error_mock(service_name, error_message="Service error"):
        """Create a mock that raises errors."""
        mock = Mock()
        mock.name = service_name
        mock.process.side_effect = Exception(error_message)
        mock.validate.side_effect = ValueError("Validation error")
        return mock


# Pre-configured mocks for common scenarios
def get_database_mock():
    """Get a pre-configured database mock."""
    return DatabaseMock()


def get_cache_mock():
    """Get a pre-configured cache mock."""
    return CacheMock()


def get_external_service_mock(service_name="external_api"):
    """Get a pre-configured external service mock."""
    return ExternalServiceMock(service_name)


def get_error_service_mock(service_name="error_service"):
    """Get a mock that simulates service errors."""
    return ServiceMockFactory.create_error_mock(service_name)
'''
        
        mocks_file.write_text(content)
    
    async def _generate_shared_utilities(self, ticket_info: Dict[str, Any], services: List[Dict[str, Any]], utilities_dir: Path):
        """Generate shared utility functions."""
        
        # Generate test utilities file
        utilities_file = utilities_dir / "test_utils.py"
        
        content = f'''"""
Shared test utilities for ticket {ticket_info["ticket_number"]}

This module contains utility functions that can be used across multiple test files.
"""

import json
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch


class TestDataGenerator:
    """Generate test data for various scenarios."""
    
    @staticmethod
    def generate_valid_data(service_name: str) -> Dict[str, Any]:
        """Generate valid test data for a service."""
        return {{
            "id": 1,
            "service": service_name,
            "timestamp": datetime.now().isoformat(),
            "status": "active",
            "data": {{"key": "value", "number": 42}}
        }}
    
    @staticmethod
    def generate_invalid_data(service_name: str) -> Dict[str, Any]:
        """Generate invalid test data for a service."""
        return {{
            "id": None,
            "service": service_name,
            "timestamp": "invalid_date",
            "status": "",
            "data": None
        }}
    
    @staticmethod
    def generate_edge_case_data() -> List[Dict[str, Any]]:
        """Generate edge case test data."""
        return [
            {{}},  # Empty object
            None,  # Null value
            {{"id": 0}},  # Zero ID
            {{"id": -1}},  # Negative ID
            {{"very_long_field": "x" * 10000}},  # Very long data
            {{"unicode": "🚀🔥💯"}},  # Unicode characters
            {{"nested": {{"deep": {{"very": {{"deep": "value"}}}}}}}},  # Deep nesting
        ]


class TestAssertions:
    """Custom assertion helpers for tests."""
    
    @staticmethod
    def assert_service_response(response: Dict[str, Any], expected_status: str = "success"):
        """Assert that a service response has the expected format."""
        assert isinstance(response, dict), "Response should be a dictionary"
        assert "status" in response, "Response should have a status field"
        assert response["status"] == expected_status, f"Expected status {{expected_status}}, got {{response['status']}}"
    
    @staticmethod
    def assert_error_response(response: Dict[str, Any], expected_error_type: str = None):
        """Assert that an error response has the expected format."""
        assert isinstance(response, dict), "Error response should be a dictionary"
        assert "error" in response or "status" in response, "Error response should have error or status field"
        
        if expected_error_type:
            error_info = response.get("error", response.get("status", ""))
            assert expected_error_type.lower() in str(error_info).lower(), \\
                   f"Expected error type {{expected_error_type}} not found in {{error_info}}"
    
    @staticmethod
    def assert_performance_threshold(execution_time: float, max_time: float = 5.0):
        """Assert that execution time is within acceptable limits."""
        assert execution_time < max_time, \\
               f"Performance threshold exceeded: {{execution_time}}s > {{max_time}}s"


class TestEnvironment:
    """Utilities for setting up and tearing down test environments."""
    
    @staticmethod
    def setup_test_environment(services: List[str]) -> Dict[str, Mock]:
        """Set up a test environment with mocked services."""
        mocked_services = {{}}
        
        for service_name in services:
            mock_service = Mock()
            mock_service.name = service_name
            mock_service.process.return_value = {{"status": "success", "service": service_name}}
            mock_service.health_check.return_value = {{"status": "healthy"}}
            mocked_services[service_name] = mock_service
        
        return mocked_services
    
    @staticmethod
    def cleanup_test_environment(mocked_services: Dict[str, Mock]):
        """Clean up test environment."""
        for service_name, mock_service in mocked_services.items():
            mock_service.reset_mock()
    
    @staticmethod
    def create_test_database():
        """Create a test database instance."""
        # TODO: Implement actual test database setup
        mock_db = Mock()
        mock_db.query.return_value = []
        mock_db.insert.return_value = True
        return mock_db


class AsyncTestUtils:
    """Utilities for testing async operations."""
    
    @staticmethod
    async def run_with_timeout(coro, timeout: float = 5.0):
        """Run an async operation with a timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise AssertionError(f"Operation timed out after {{timeout}} seconds")
    
    @staticmethod
    async def simulate_async_delay(delay: float = 0.1):
        """Simulate an async delay for testing."""
        await asyncio.sleep(delay)
    
    @staticmethod
    def create_async_mock():
        """Create a mock that supports async operations."""
        mock = Mock()
        mock.async_method = AsyncMock()
        return mock


class PerformanceTestUtils:
    """Utilities for performance testing."""
    
    @staticmethod
    def measure_execution_time(func, *args, **kwargs):
        """Measure the execution time of a function."""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        return result, execution_time
    
    @staticmethod
    async def measure_async_execution_time(coro):
        """Measure the execution time of an async operation."""
        start_time = time.time()
        result = await coro
        end_time = time.time()
        execution_time = end_time - start_time
        return result, execution_time
    
    @staticmethod
    def create_load_test_data(count: int = 1000) -> List[Dict[str, Any]]:
        """Create a large dataset for load testing."""
        return [
            {{
                "id": i,
                "data": f"test_data_{{i}}",
                "timestamp": datetime.now().isoformat()
            }}
            for i in range(count)
        ]


# Convenience functions
def create_test_context(ticket_number: str, services: List[str]) -> Dict[str, Any]:
    """Create a test context with common test data."""
    return {{
        "ticket_number": ticket_number,
        "services": services,
        "timestamp": datetime.now(),
        "test_data": TestDataGenerator.generate_valid_data("test_service"),
        "mocked_services": TestEnvironment.setup_test_environment(services)
    }}


def assert_no_errors(response: Dict[str, Any]):
    """Assert that a response contains no errors."""
    assert "error" not in response or response["error"] is None, \\
           f"Unexpected error in response: {{response.get('error')}}"


def wait_for_condition(condition_func, timeout: float = 10.0, interval: float = 0.1):
    """Wait for a condition to become true."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(interval)
    
    raise AssertionError(f"Condition not met within {{timeout}} seconds")


# Import AsyncMock for Python 3.8+ compatibility
try:
    from unittest.mock import AsyncMock
except ImportError:
    # Fallback for older Python versions
    class AsyncMock(Mock):
        async def __call__(self, *args, **kwargs):
            return super().__call__(*args, **kwargs)
'''
        
        utilities_file.write_text(content)
    
    async def _generate_documentation(self, ticket_info: Dict[str, Any], services: List[Dict[str, Any]], test_types: List[str], ticket_dir: Path):
        """Generate README and run script for the ticket tests."""
        
        # Generate README
        readme_file = ticket_dir / "README.md"
        
        # Build service list
        services_list = []
        for service in services:
            lang = service.get('language', 'unknown')
            framework = service.get('framework', 'unknown')
            services_list.append(f"- **{service['name']}** ({lang} - {framework})")
        services_text = "\n".join(services_list)
        
        # Build test types list
        test_types_list = []
        for test_type in test_types:
            description = self._get_test_type_description(test_type)
            test_types_list.append(f"- **{test_type.title()}**: {description}")
        test_types_text = "\n".join(test_types_list)
        
        # Build directory structure
        service_dirs = []
        for service in services:
            service_dirs.append(f"├── {service['name']}/           # Tests for {service['name']} service")
        service_dirs_text = "\n".join(service_dirs)
        
        # Build test file lists
        test_files = []
        if "reproduction" in test_types:
            test_files.append("│   ├── test_reproduction.py  # Bug reproduction tests")
        if "unit" in test_types:
            test_files.append("│   ├── test_unit.py          # Unit tests")
        if "integration" in test_types:
            test_files.append("│   ├── test_integration.py   # Integration tests")
        if "regression" in test_types:
            test_files.append("│   └── test_regression.py    # Regression tests")
        test_files_text = "\n".join(test_files)
        
        readme_content = f'''# Test Reproduction for Ticket {ticket_info["ticket_number"]}

**Title:** {ticket_info["title"]}  
**Platform:** {ticket_info["platform"]}  
**Status:** {ticket_info["status"]}

## Overview

This directory contains comprehensive test reproduction for ticket {ticket_info["ticket_number"]}. The tests are designed to reproduce the original bug, verify fixes, and prevent regressions.

### Bug Analysis
{ticket_info.get("bug_analysis", "No analysis available")}

### Root Cause
{ticket_info.get("root_cause", "No root cause identified")}

### Error Patterns
{", ".join(ticket_info.get("error_patterns", ["No error patterns identified"]))}

## Services Involved

{services_text}

## Test Types Generated

{test_types_text}

## Directory Structure

```
{ticket_info["ticket_number"]}/
├── README.md                 # This file
├── run_tests.sh             # Script to run all tests
├── shared/                  # Shared test resources
│   ├── fixtures/           # Test fixtures
│   ├── mocks/              # Mock objects
│   └── utilities/          # Test utilities
{service_dirs_text}
{test_files_text}
```

## Running Tests

### Prerequisites

Make sure you have the required dependencies installed:

```bash
# For Python services
pip install pytest pytest-asyncio pytest-mock

# For JavaScript services  
npm install jest @jest/globals

# For Java services
# Ensure JUnit 5 and Mockito are in your classpath
```

### Run All Tests

```bash
# Make the run script executable
chmod +x run_tests.sh

# Run all tests
./run_tests.sh
```

### Run Specific Test Types

```bash
# Run only reproduction tests
find . -name "test_reproduction.py" -exec python -m pytest {{}} -v \\;

# Run only unit tests
find . -name "test_unit.py" -exec python -m pytest {{}} -v \\;

# Run only integration tests
find . -name "test_integration.py" -exec python -m pytest {{}} -v \\;

# Run only regression tests
find . -name "test_regression.py" -exec python -m pytest {{}} -v \\;
```

### Run Tests for Specific Service

```bash
# Run all tests for a specific service
python -m pytest {services[0]["name"] if services else "service_name"}/ -v

# Run specific test type for a service
python -m pytest {services[0]["name"] if services else "service_name"}/test_reproduction.py -v
```

## Test Implementation Status

⚠️ **Important**: The generated tests contain TODO comments and placeholder implementations. You need to:

1. **Replace placeholder implementations** with actual service calls
2. **Update mock configurations** to match your service interfaces
3. **Customize test data** based on your actual data structures
4. **Implement service instantiation** in test fixtures
5. **Configure test environment** (databases, external services, etc.)

## Expected Test Behavior

### Reproduction Tests
- **Initially FAIL** - These tests should reproduce the original bug
- **Pass after fix** - Once the bug is fixed, these tests should pass
- **Serve as regression tests** - Prevent the bug from reoccurring

### Unit Tests
- Test individual functions/methods identified in the root cause analysis
- Focus on the specific code paths that caused the bug
- Include edge cases and boundary conditions

### Integration Tests
- Test service interactions and API endpoints
- Verify data flow between services
- Test external service integrations

### Regression Tests
- Ensure the fix doesn't introduce new issues
- Test performance and memory usage
- Verify concurrent access scenarios

## Customization Guide

### 1. Service Integration

Replace mock service instances with actual service classes:

```python
# Replace this:
service = Mock()

# With this:
from your_service_module import YourServiceClass
service = YourServiceClass(dependencies)
```

### 2. Database Setup

Configure actual test databases:

```python
# Replace mock database:
mock_db = Mock()

# With test database:
test_db = create_test_database()
```

### 3. Test Data

Update test data to match your domain:

```python
# Customize test data based on your actual data structures
test_data = {{
    "field1": "actual_value",
    "field2": actual_object,
    # ... your actual fields
}}
```

### 4. Error Simulation

Implement actual error conditions:

```python
# Replace generic error simulation:
raise Exception("Simulated error")

# With actual error conditions:
# Simulate timeout, connection failure, data corruption, etc.
```

## Continuous Integration

Add these tests to your CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
- name: Run Reproduction Tests
  run: |
    cd tests/reproductions/{ticket_info["ticket_number"]}
    ./run_tests.sh
```

## Monitoring and Alerting

Consider adding monitoring for similar issues:

1. **Error Pattern Detection**: Monitor logs for similar error patterns
2. **Performance Monitoring**: Track performance metrics for affected services
3. **Health Checks**: Implement enhanced health checks to detect similar issues early

## Related Documentation

- [Original Ticket]({ticket_info.get("url", "#")})
- [Service Documentation](link-to-service-docs)
- [Testing Guidelines](link-to-testing-guidelines)

---

**Generated on:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Ticket:** {ticket_info["ticket_number"]}  
**Services:** {", ".join([s["name"] for s in services])}
'''
        
        readme_file.write_text(readme_content)
        
        # Generate run script
        run_script = ticket_dir / "run_tests.sh"
        
        # Build service test sections
        service_test_sections = []
        for service in services:
            service_name = service["name"]
            language = service.get("language", "unknown")
            framework = service.get("framework", "unknown")
            
            service_section = f'''
echo "🔧 Testing service: {service_name}"
echo "Language: {language}"
echo "Framework: {framework}"
echo ""

# Run each test type for this service'''
            
            for test_type in test_types:
                service_section += f'''
if run_test_suite "{service_name}/test_{test_type}.py" "{service_name} {test_type} tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))'''
            
            service_section += '''
echo ""'''
            service_test_sections.append(service_section)
        
        service_tests_text = "".join(service_test_sections)
        
        script_content = f'''#!/bin/bash

# Test runner script for ticket {ticket_info["ticket_number"]}
# Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

set -e  # Exit on any error

echo "🧪 Running tests for ticket {ticket_info["ticket_number"]}"
echo "Services: {', '.join([s['name'] for s in services])}"
echo "Test types: {', '.join(test_types)}"
echo ""

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m' # No Color

# Function to run tests with proper error handling
run_test_suite() {{
    local test_path="$1"
    local test_name="$2"
    
    echo -e "${{BLUE}}Running ${{test_name}}...${{NC}}"
    
    if [ -f "$test_path" ]; then
        if python -m pytest "$test_path" -v --tb=short; then
            echo -e "${{GREEN}}✅ ${{test_name}} passed${{NC}}"
            return 0
        else
            echo -e "${{RED}}❌ ${{test_name}} failed${{NC}}"
            return 1
        fi
    else
        echo -e "${{YELLOW}}⚠️  ${{test_name}} not found: ${{test_path}}${{NC}}"
        return 0
    fi
}}

# Initialize counters
total_tests=0
passed_tests=0
failed_tests=0

echo "📋 Test Execution Plan:"
echo "======================"

# Run tests for each service
{service_tests_text}

# Summary
echo "📊 Test Results Summary:"
echo "======================="
echo -e "Total test suites: $total_tests"
echo -e "${{GREEN}}Passed: $passed_tests${{NC}}"
echo -e "${{RED}}Failed: $failed_tests${{NC}}"

if [ $failed_tests -eq 0 ]; then
    echo -e "${{GREEN}}🎉 All tests passed!${{NC}}"
    exit 0
else
    echo -e "${{RED}}💥 Some tests failed. Please check the output above.${{NC}}"
    exit 1
fi
'''
        
        run_script.write_text(script_content)
        
        # Make the script executable
        import stat
        run_script.chmod(run_script.stat().st_mode | stat.S_IEXEC)
    
    def _get_test_type_description(self, test_type: str) -> str:
        """Get description for a test type."""
        descriptions = {
            "reproduction": "Reproduces the exact bug scenario described in the ticket",
            "unit": "Tests individual functions/methods identified in the root cause analysis", 
            "integration": "Tests service interactions and API endpoints",
            "regression": "Ensures the bug doesn't reoccur and prevents similar issues"
        }
        return descriptions.get(test_type, f"Tests for {test_type}")


# Global tool instance
_test_reproduction_tool = TestReproductionTool()


def get_test_reproduction_tool() -> TestReproductionTool:
    """Get the global test reproduction tool instance."""
    return _test_reproduction_tool


async def execute_test_reproduction(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the test reproduction tool."""
    return await _test_reproduction_tool.execute(arguments)
