from __future__ import annotations

import json
import os
import re
import asyncio
import subprocess
import shutil
from pathlib import Path
from string import Template
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog
from mcp.types import Tool, TextContent
from .prompt import BasePromptTool

logger = structlog.get_logger(__name__)


class BugFixExecutorTool(BasePromptTool):
    """MCP tool for executing tests and fixing bugs iteratively."""
    
    def __init__(self):
        super().__init__(
            tool_name="bug_fix_executor",
            description="Execute tests from test_reproduction and iteratively fix bugs until tests pass. "
                       "Takes test reproduction output and issue reader context to implement fixes.",
            prompt_filename="bug_fix_executor.txt"
        )
        # Load the plan template for chaining
        self._plan_tpl_path = Path(__file__).parent.parent / "prompts" / "shared_plan_template.txt"
        self._plan_tpl = Template(self._plan_tpl_path.read_text(encoding="utf-8"))
        
        # Initialize components
        self.test_runner = TestRunner()
        self.code_modifier = CodeModifier()
        
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for bug_fix_executor."""
        return Tool(
            name=self.tool_name,
            description=self.description,
            inputSchema={
                "type": "object",
                "properties": {
                    "test_reproduction_output": {
                        "type": "string",
                        "description": "JSON output from test_reproduction containing test paths and ticket info"
                    },
                    "issue_reader_output": {
                        "type": "string", 
                        "description": "JSON output from issue_reader containing ticket details and root cause analysis"
                    },
                    "service_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Paths to service source code directories",
                        "default": []
                    },
                    "max_iterations": {
                        "type": "integer",
                        "description": "Maximum number of fix iterations",
                        "default": 5
                    },
                    "test_framework": {
                        "type": "string",
                        "enum": ["pytest", "jest", "junit", "auto"],
                        "description": "Test framework to use",
                        "default": "auto"
                    },
                    "fix_strategy": {
                        "type": "string",
                        "enum": ["conservative", "aggressive", "auto"],
                        "description": "How aggressively to apply fixes",
                        "default": "auto"
                    },
                    "backup_code": {
                        "type": "boolean",
                        "description": "Whether to backup original code before fixing",
                        "default": True
                    }
                },
                "required": ["test_reproduction_output", "issue_reader_output"],
                "title": "bug_fix_executorArguments"
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the bug fix executor tool."""
        try:
            logger.info("Starting bug fix execution", arguments=arguments)
            
            # Parse inputs
            test_repro_data = self._parse_test_reproduction_output(arguments["test_reproduction_output"])
            issue_data = self._parse_issue_reader_output(arguments["issue_reader_output"])
            
            if not test_repro_data or not issue_data:
                return [TextContent(
                    type="text",
                    text="❌ **Invalid Input Data**\n\n"
                         "Could not parse test reproduction or issue reader output. "
                         "Please ensure both inputs contain valid JSON data."
                )]
            
            # Extract configuration
            service_paths = arguments.get("service_paths", [])
            max_iterations = arguments.get("max_iterations", 5)
            test_framework = arguments.get("test_framework", "auto")
            fix_strategy = arguments.get("fix_strategy", "auto")
            backup_code = arguments.get("backup_code", True)
            
            # Initialize fix session
            fix_session = FixSession(
                test_repro_data=test_repro_data,
                issue_data=issue_data,
                service_paths=service_paths,
                max_iterations=max_iterations,
                test_framework=test_framework,
                fix_strategy=fix_strategy,
                backup_code=backup_code
            )
            
            # Execute the bug fixing workflow
            results = await self._execute_fix_workflow(fix_session)
            
            # Generate comprehensive report
            return self._generate_fix_report(results)
            
        except Exception as e:
            logger.error("Error in bug fix executor", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Bug Fix Execution Failed**\n\n"
                     f"An error occurred during bug fixing: {e}\n\n"
                     f"Please check your input parameters and try again."
            )]
    
    def _parse_test_reproduction_output(self, output: str) -> Optional[Dict[str, Any]]:
        """Parse test reproduction output."""
        try:
            # Try direct JSON parsing
            if output.strip().startswith('{'):
                return json.loads(output)
            
            # Extract from markdown
            json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            
            # Parse from text output
            lines = output.split('\n')
            test_data = {}
            
            for line in lines:
                if "Output Path:" in line:
                    path_match = re.search(r'`([^`]+)`', line)
                    if path_match:
                        test_data["output_path"] = path_match.group(1)
                elif "Total tickets processed:" in line:
                    count_match = re.search(r'(\d+)', line)
                    if count_match:
                        test_data["total_tickets"] = int(count_match.group(1))
            
            return test_data if test_data else None
            
        except Exception as e:
            logger.warning("Failed to parse test reproduction output", error=str(e))
            return None
    
    def _parse_issue_reader_output(self, output: str) -> Optional[Dict[str, Any]]:
        """Parse issue reader output."""
        try:
            # Try direct JSON parsing
            if output.strip().startswith('{'):
                return json.loads(output)
            
            # Extract from markdown
            json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            
            return None
            
        except Exception as e:
            logger.warning("Failed to parse issue reader output", error=str(e))
            return None
    
    async def _execute_fix_workflow(self, fix_session: 'FixSession') -> Dict[str, Any]:
        """Execute the complete bug fixing workflow."""
        
        workflow_results = {
            "session_id": fix_session.session_id,
            "start_time": datetime.now(),
            "iterations": [],
            "final_status": "unknown",
            "total_fixes_applied": 0,
            "tests_initially_failing": 0,
            "tests_finally_passing": 0,
            "success_rate": 0.0
        }
        
        try:
            # Phase 1: Initial test execution
            logger.info("Phase 1: Running initial tests")
            initial_results = await self.test_runner.run_tests(fix_session)
            
            workflow_results["tests_initially_failing"] = initial_results.get("total_failures", 0)
            
            if initial_results.get("total_failures", 0) == 0:
                workflow_results["final_status"] = "no_fixes_needed"
                workflow_results["tests_finally_passing"] = initial_results.get("total_tests", 0)
                workflow_results["success_rate"] = 100.0
                return workflow_results
            
            # Phase 2: Iterative fixing
            logger.info("Phase 2: Starting iterative bug fixing")
            
            current_results = initial_results
            
            for iteration in range(fix_session.max_iterations):
                logger.info(f"Fix iteration {iteration + 1}/{fix_session.max_iterations}")
                
                iteration_data = {
                    "iteration": iteration + 1,
                    "start_time": datetime.now(),
                    "test_results": current_results,
                    "fixes_applied": [],
                    "status": "in_progress"
                }
                
                # Use LLM to analyze failures and generate fixes
                fix_analysis = await self._analyze_and_generate_fixes(current_results, fix_session, iteration + 1)
                
                if not fix_analysis or not fix_analysis.get("fixes"):
                    iteration_data["status"] = "no_fixes_generated"
                    workflow_results["iterations"].append(iteration_data)
                    break
                
                # Apply fixes
                applied_fixes = await self.code_modifier.apply_fixes(
                    fix_analysis["fixes"], fix_session
                )
                
                iteration_data["fixes_applied"] = applied_fixes
                workflow_results["total_fixes_applied"] += len(applied_fixes)
                
                # Run tests again
                new_results = await self.test_runner.run_tests(fix_session)
                
                iteration_data["end_time"] = datetime.now()
                iteration_data["new_test_results"] = new_results
                
                # Check if we've improved
                new_failures = new_results.get("total_failures", 0)
                old_failures = current_results.get("total_failures", 0)
                
                if new_failures == 0:
                    iteration_data["status"] = "success"
                    workflow_results["final_status"] = "fixed"
                    workflow_results["tests_finally_passing"] = new_results.get("total_tests", 0)
                    workflow_results["iterations"].append(iteration_data)
                    break
                elif new_failures < old_failures:
                    iteration_data["status"] = "improved"
                    current_results = new_results
                else:
                    iteration_data["status"] = "no_improvement"
                
                workflow_results["iterations"].append(iteration_data)
                current_results = new_results
            
            # Calculate final metrics
            if workflow_results["final_status"] == "unknown":
                workflow_results["final_status"] = "max_iterations_reached"
            
            final_passing = workflow_results.get("tests_finally_passing", 0)
            if final_passing == 0 and workflow_results["iterations"]:
                last_iteration = workflow_results["iterations"][-1]
                final_results = last_iteration.get("new_test_results", {})
                final_passing = final_results.get("total_tests", 0) - final_results.get("total_failures", 0)
                workflow_results["tests_finally_passing"] = final_passing
            
            total_tests = workflow_results.get("tests_initially_failing", 0) + final_passing
            if total_tests > 0:
                workflow_results["success_rate"] = (final_passing / total_tests) * 100
            
            workflow_results["end_time"] = datetime.now()
            
            return workflow_results
            
        except Exception as e:
            logger.error("Error in fix workflow", error=str(e))
            workflow_results["final_status"] = "error"
            workflow_results["error"] = str(e)
            workflow_results["end_time"] = datetime.now()
            return workflow_results
    
    async def _analyze_and_generate_fixes(self, test_results: Dict[str, Any], fix_session: 'FixSession', iteration: int) -> Optional[Dict[str, Any]]:
        """Use LLM to analyze failures and generate fixes."""
        try:
            # Prepare context for LLM
            context = {
                "test_results": test_results,
                "ticket_information": fix_session.issue_data,
                "service_paths": fix_session.service_paths,
                "iteration": iteration,
                "fix_strategy": fix_session.fix_strategy,
                "previous_iterations": []  # Could include previous attempts
            }
            
            # Call the parent's execute method to use the LLM prompt
            llm_outputs = await super().execute(context)
            
            if not llm_outputs or not getattr(llm_outputs[0], "text", None):
                return None
            
            raw_text = llm_outputs[0].text
            
            # Try to parse JSON response
            try:
                return json.loads(raw_text)
            except json.JSONDecodeError:
                logger.warning("LLM returned non-JSON response", response=raw_text)
                return None
                
        except Exception as e:
            logger.error("Error in LLM analysis", error=str(e))
            return None
    
    def _generate_fix_report(self, results: Dict[str, Any]) -> List[TextContent]:
        """Generate comprehensive bug fix report."""
        
        session_id = results.get("session_id", "unknown")
        final_status = results.get("final_status", "unknown")
        total_iterations = len(results.get("iterations", []))
        total_fixes = results.get("total_fixes_applied", 0)
        success_rate = results.get("success_rate", 0.0)
        
        # Calculate duration
        start_time = results.get("start_time")
        end_time = results.get("end_time")
        duration = "unknown"
        if start_time and end_time:
            duration_seconds = (end_time - start_time).total_seconds()
            duration = f"{duration_seconds:.1f} seconds"
        
        # Status emoji and message
        status_info = self._get_status_info(final_status, success_rate)
        
        report = f"{status_info['emoji']} **Bug Fix Execution Report**\n\n"
        report += f"**Session ID:** {session_id}\n"
        report += f"**Status:** {status_info['message']}\n"
        report += f"**Duration:** {duration}\n"
        report += f"**Iterations:** {total_iterations}\n"
        report += f"**Fixes Applied:** {total_fixes}\n"
        report += f"**Success Rate:** {success_rate:.1f}%\n\n"
        
        # Test results summary
        initially_failing = results.get("tests_initially_failing", 0)
        finally_passing = results.get("tests_finally_passing", 0)
        
        report += f"## 📊 Test Results Summary\n\n"
        report += f"- **Initially Failing:** {initially_failing} tests\n"
        report += f"- **Finally Passing:** {finally_passing} tests\n"
        report += f"- **Improvement:** {finally_passing - max(0, initially_failing - finally_passing)} tests fixed\n\n"
        
        # Iteration details
        iterations = results.get("iterations", [])
        if iterations:
            report += f"## 🔄 Fix Iterations\n\n"
            
            for i, iteration in enumerate(iterations, 1):
                iter_status = iteration.get("status", "unknown")
                fixes_count = len(iteration.get("fixes_applied", []))
                
                iter_emoji = {
                    "success": "✅",
                    "improved": "📈", 
                    "no_improvement": "⚠️",
                    "no_fixes_generated": "❌",
                    "in_progress": "🔄"
                }.get(iter_status, "❓")
                
                report += f"### {iter_emoji} Iteration {i}\n"
                report += f"**Status:** {iter_status.replace('_', ' ').title()}\n"
                report += f"**Fixes Applied:** {fixes_count}\n"
                
                # Show applied fixes
                fixes_applied = iteration.get("fixes_applied", [])
                if fixes_applied:
                    report += f"**Changes Made:**\n"
                    for fix in fixes_applied[:3]:  # Show first 3 fixes
                        file_path = fix.get("file", "unknown")
                        fix_type = fix.get("type", "unknown")
                        description = fix.get("description", "No description")
                        report += f"- `{file_path}`: {fix_type} - {description}\n"
                    
                    if len(fixes_applied) > 3:
                        report += f"- ... and {len(fixes_applied) - 3} more changes\n"
                
                # Show test results
                test_results = iteration.get("new_test_results", {})
                if test_results:
                    failures = test_results.get("total_failures", 0)
                    total = test_results.get("total_tests", 0)
                    passing = total - failures
                    report += f"**Test Results:** {passing}/{total} passing\n"
                
                report += "\n"
        
        # Add next steps or completion message
        if final_status == "fixed":
            report += f"## 🎉 Success!\n\n"
            report += f"All tests are now passing. The bugs have been successfully fixed.\n\n"
            report += f"**Next Steps:**\n"
            report += f"- Review the applied changes\n"
            report += f"- Run additional tests to ensure no regressions\n"
            report += f"- Commit the fixes to version control\n"
            report += f"- Deploy to staging/production environments\n"
        elif final_status == "max_iterations_reached":
            report += f"## ⚠️ Maximum Iterations Reached\n\n"
            report += f"The fixing process reached the maximum number of iterations ({total_iterations}).\n"
            report += f"Some progress was made, but not all tests are passing yet.\n\n"
            report += f"**Recommendations:**\n"
            report += f"- Review the applied fixes manually\n"
            report += f"- Run the tool again with increased iterations\n"
            report += f"- Consider manual debugging for remaining issues\n"
        elif final_status == "no_fixes_needed":
            report += f"## ✅ No Fixes Needed\n\n"
            report += f"All tests were already passing. No bugs to fix!\n"
        else:
            report += f"## ❌ Fixing Incomplete\n\n"
            report += f"The bug fixing process encountered issues and could not complete successfully.\n"
            report += f"Please review the logs and try again with different parameters.\n"
        
        return [TextContent(type="text", text=report)]
    
    def _get_status_info(self, status: str, success_rate: float) -> Dict[str, str]:
        """Get status emoji and message."""
        if status == "fixed":
            return {"emoji": "🎉", "message": "All tests passing - bugs fixed!"}
        elif status == "no_fixes_needed":
            return {"emoji": "✅", "message": "No fixes needed - tests already passing"}
        elif status == "max_iterations_reached":
            if success_rate > 80:
                return {"emoji": "📈", "message": "Significant progress made - manual review needed"}
            elif success_rate > 50:
                return {"emoji": "⚠️", "message": "Some progress made - more work needed"}
            else:
                return {"emoji": "❌", "message": "Limited progress - manual intervention required"}
        elif status == "error":
            return {"emoji": "💥", "message": "Error occurred during fixing process"}
        else:
            return {"emoji": "❓", "message": "Unknown status"}


class FixSession:
    """Represents a bug fixing session with all context."""
    
    def __init__(self, test_repro_data, issue_data, service_paths, max_iterations, 
                 test_framework, fix_strategy, backup_code):
        self.session_id = f"fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.test_repro_data = test_repro_data
        self.issue_data = issue_data
        self.service_paths = service_paths
        self.max_iterations = max_iterations
        self.test_framework = test_framework
        self.fix_strategy = fix_strategy
        self.backup_code = backup_code
        self.backups = {}


class TestRunner:
    """Runs tests and parses results."""
    
    async def run_tests(self, fix_session: FixSession) -> Dict[str, Any]:
        """Run tests and return structured results."""
        try:
            test_path = fix_session.test_repro_data.get("output_path")
            if not test_path or not Path(test_path).exists():
                return {"error": "Test path not found", "total_tests": 0, "total_failures": 0}
            
            # Determine test framework
            framework = fix_session.test_framework
            if framework == "auto":
                framework = self._detect_test_framework(test_path)
            
            # Run tests based on framework
            if framework == "pytest":
                return await self._run_pytest(test_path)
            elif framework == "jest":
                return await self._run_jest(test_path)
            elif framework == "junit":
                return await self._run_junit(test_path)
            else:
                return {"error": f"Unsupported test framework: {framework}", "total_tests": 0, "total_failures": 0}
                
        except Exception as e:
            logger.error("Error running tests", error=str(e))
            return {"error": str(e), "total_tests": 0, "total_failures": 0}
    
    def _detect_test_framework(self, test_path: str) -> str:
        """Auto-detect test framework from test files."""
        test_dir = Path(test_path)
        
        # Check for pytest files
        if list(test_dir.rglob("test_*.py")) or list(test_dir.rglob("*_test.py")):
            return "pytest"
        
        # Check for jest files
        if list(test_dir.rglob("*.test.js")) or list(test_dir.rglob("*.spec.js")):
            return "jest"
        
        # Check for junit files
        if list(test_dir.rglob("*Test.java")) or list(test_dir.rglob("*Tests.java")):
            return "junit"
        
        return "pytest"  # Default fallback
    
    async def _run_pytest(self, test_path: str) -> Dict[str, Any]:
        """Run pytest and parse results."""
        try:
            process = await asyncio.create_subprocess_exec(
                "python", "-m", "pytest", test_path, "-v", "--tb=short",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=test_path
            )
            
            stdout, stderr = await process.communicate()
            
            # Parse pytest output
            results = {
                "framework": "pytest",
                "total_tests": 0,
                "total_failures": 0,
                "failures": [],
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "return_code": process.returncode
            }
            
            # Parse test results from output
            output_lines = stdout.decode().split('\n')
            for line in output_lines:
                if "failed" in line and "passed" in line:
                    # Parse line like "2 failed, 3 passed in 1.23s"
                    failed_match = re.search(r'(\d+) failed', line)
                    passed_match = re.search(r'(\d+) passed', line)
                    
                    if failed_match:
                        results["total_failures"] = int(failed_match.group(1))
                    if passed_match:
                        results["total_tests"] = results["total_failures"] + int(passed_match.group(1))
                
                # Capture failure details
                if "FAILED" in line:
                    results["failures"].append(line.strip())
            
            return results
            
        except Exception as e:
            return {"error": str(e), "total_tests": 0, "total_failures": 0}
    
    async def _run_jest(self, test_path: str) -> Dict[str, Any]:
        """Run jest and parse results."""
        try:
            process = await asyncio.create_subprocess_exec(
                "npm", "test", "--", "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=test_path
            )
            
            stdout, stderr = await process.communicate()
            
            results = {
                "framework": "jest",
                "total_tests": 0,
                "total_failures": 0,
                "failures": [],
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "return_code": process.returncode
            }
            
            # Parse jest JSON output
            try:
                jest_results = json.loads(stdout.decode())
                results["total_tests"] = jest_results.get("numTotalTests", 0)
                results["total_failures"] = jest_results.get("numFailedTests", 0)
                
                # Extract failure details
                for test_result in jest_results.get("testResults", []):
                    for assertion in test_result.get("assertionResults", []):
                        if assertion.get("status") == "failed":
                            results["failures"].append(assertion.get("title", "Unknown test"))
            except json.JSONDecodeError:
                pass
            
            return results
            
        except Exception as e:
            return {"error": str(e), "total_tests": 0, "total_failures": 0}
    
    async def _run_junit(self, test_path: str) -> Dict[str, Any]:
        """Run junit and parse results."""
        try:
            # This is a simplified implementation - would need actual Java/Maven/Gradle setup
            process = await asyncio.create_subprocess_exec(
                "mvn", "test",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=test_path
            )
            
            stdout, stderr = await process.communicate()
            
            results = {
                "framework": "junit",
                "total_tests": 0,
                "total_failures": 0,
                "failures": [],
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "return_code": process.returncode
            }
            
            # Parse Maven test output
            output_lines = stdout.decode().split('\n')
            for line in output_lines:
                if "Tests run:" in line:
                    # Parse line like "Tests run: 5, Failures: 2, Errors: 0, Skipped: 0"
                    tests_match = re.search(r'Tests run: (\d+)', line)
                    failures_match = re.search(r'Failures: (\d+)', line)
                    
                    if tests_match:
                        results["total_tests"] = int(tests_match.group(1))
                    if failures_match:
                        results["total_failures"] = int(failures_match.group(1))
            
            return results
            
        except Exception as e:
            return {"error": str(e), "total_tests": 0, "total_failures": 0}


class CodeModifier:
    """Applies fixes to source code files."""
    
    async def apply_fixes(self, fixes: List[Dict[str, Any]], fix_session: FixSession) -> List[Dict[str, Any]]:
        """Apply fixes to code files."""
        
        applied_fixes = []
        
        for fix in fixes:
            try:
                if await self._apply_single_fix(fix, fix_session):
                    applied_fixes.append(fix)
                    logger.info(f"Applied fix: {fix.get('description')}")
                else:
                    logger.warning(f"Failed to apply fix: {fix.get('description')}")
                    
            except Exception as e:
                logger.error(f"Error applying fix: {fix.get('description')}", error=str(e))
        
        return applied_fixes
    
    async def _apply_single_fix(self, fix: Dict[str, Any], fix_session: FixSession) -> bool:
        """Apply a single fix to a file."""
        
        file_path = fix.get("file")
        if not file_path:
            return False
        
        file_path = Path(file_path)
        if not file_path.exists():
            # Try to find the file in service paths
            for service_path in fix_session.service_paths:
                potential_path = Path(service_path) / file_path.name
                if potential_path.exists():
                    file_path = potential_path
                    break
            else:
                logger.warning(f"File not found: {file_path}")
                return False
        
        try:
            # Backup original file if requested
            if fix_session.backup_code:
                await self._backup_file(file_path, fix_session)
            
            # Read file content
            content = file_path.read_text()
            
            # Apply fix based on search pattern
            search_pattern = fix.get("search_pattern")
            replacement = fix.get("replacement")
            
            if search_pattern and replacement:
                new_content = re.sub(search_pattern, replacement, content)
                
                if new_content != content:
                    file_path.write_text(new_content)
                    return True
                else:
                    logger.warning(f"No matches found for pattern: {search_pattern}")
                    return False
            else:
                logger.warning(f"Missing search pattern or replacement in fix: {fix}")
                return False
                
        except Exception as e:
            logger.error(f"Error applying fix to {file_path}", error=str(e))
            return False
    
    async def _backup_file(self, file_path: Path, fix_session: FixSession):
        """Create backup of original file."""
        backup_path = file_path.with_suffix(f"{file_path.suffix}.backup_{fix_session.session_id}")
        shutil.copy2(file_path, backup_path)
        fix_session.backups[str(file_path)] = str(backup_path)


# Global instance / exports
_bug_fix_executor_tool = BugFixExecutorTool()

def get_bug_fix_executor_tool() -> BugFixExecutorTool:
    return _bug_fix_executor_tool

def get_tool_definition() -> Tool:
    return _bug_fix_executor_tool.get_tool_definition()

async def execute_bug_fix_executor(arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Execute the bug_fix_executor tool.
    
    Expected args:
      {
        "test_reproduction_output": string,     # JSON output from test_reproduction
        "issue_reader_output": string,          # JSON output from issue_reader  
        "service_paths": array<string>,         # Paths to service source code
        "max_iterations": integer,              # Maximum fix iterations (default: 5)
        "test_framework": string,               # pytest|jest|junit|auto (default: auto)
        "fix_strategy": string,                 # conservative|aggressive|auto (default: auto)
        "backup_code": boolean                  # Whether to backup code (default: true)
      }
    Returns:
      - Comprehensive bug fix execution report with iteration details and results
    """
    return await _bug_fix_executor_tool.execute(arguments)
