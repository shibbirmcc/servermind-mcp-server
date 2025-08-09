"""Continuous log monitoring tool implementation for MCP.

Note: This implementation supports one monitoring session at a time.
Multi-session monitoring is planned for future enhancement.
"""

import asyncio
import threading
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import structlog
from mcp.types import Tool, TextContent
from ..splunk.client import SplunkClient, SplunkSearchError, SplunkConnectionError
from ..config import get_config
import uuid
import json

logger = structlog.get_logger(__name__)


class MonitoringSession:
    """Represents the single active monitoring session."""
    
    def __init__(self, query: str, interval: int, **search_params):
        """Initialize monitoring session.
        
        Args:
            query: SPL query to monitor
            interval: Monitoring interval in seconds
            **search_params: Additional search parameters
        """
        self.query = query
        self.interval = interval
        self.search_params = search_params
        self.is_active = False
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.last_check_time: Optional[datetime] = None
        self.results_buffer: List[Dict[str, Any]] = []
        self.error_count = 0
        self.max_errors = 5
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        
    def start(self):
        """Start the monitoring session."""
        if self.is_active:
            return
            
        self.is_active = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("Monitoring session started")
        
    def stop(self):
        """Stop the monitoring session."""
        if not self.is_active:
            return
            
        self.is_active = False
        self.stop_event.set()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
            
        logger.info("Monitoring session stopped")
        
    def get_status(self) -> Dict[str, Any]:
        """Get current session status.
        
        Returns:
            Dict[str, Any]: Session status information
        """
        return {
            'query': self.query,
            'interval': self.interval,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'error_count': self.error_count,
            'results_in_buffer': len(self.results_buffer)
        }
        
    def get_buffered_results(self, clear_buffer: bool = True) -> List[Dict[str, Any]]:
        """Get results from buffer.
        
        Args:
            clear_buffer: Whether to clear buffer after getting results
            
        Returns:
            List[Dict[str, Any]]: Buffered results
        """
        results = self.results_buffer.copy()
        if clear_buffer:
            self.results_buffer.clear()
        return results
        
    def _monitor_loop(self):
        """Main monitoring loop running in separate thread."""
        config = get_config()
        client = SplunkClient(config.splunk)
        
        try:
            client.connect()
            logger.info("Connected to Splunk for monitoring")
            
            while not self.stop_event.is_set():
                try:
                    self._perform_check(client)
                    self.error_count = 0  # Reset error count on successful check
                    
                except Exception as e:
                    self.error_count += 1
                    logger.error("Error during monitoring check", 
                               error=str(e),
                               error_count=self.error_count)
                    
                    if self.error_count >= self.max_errors:
                        logger.error("Max errors reached, stopping monitoring session")
                        break
                
                # Wait for next interval or stop signal
                if self.stop_event.wait(timeout=self.interval):
                    break
                    
        except Exception as e:
            logger.error("Fatal error in monitoring loop", error=str(e))
        finally:
            try:
                client.disconnect()
            except Exception as e:
                logger.warning("Error disconnecting client", error=str(e))
            
            self.is_active = False
            
    def _perform_check(self, client: SplunkClient):
        """Perform a single monitoring check.
        
        Args:
            client: Connected Splunk client
        """
        now = datetime.now()
        
        # Determine time range for this check
        if self.last_check_time is None:
            # First check - use the interval as lookback
            earliest_time = f"-{self.interval}s"
        else:
            # Subsequent checks - from last check time to now
            earliest_time = self.last_check_time.strftime("%Y-%m-%dT%H:%M:%S")
            
        latest_time = now.strftime("%Y-%m-%dT%H:%M:%S")
        
        # Prepare search parameters
        search_params = {
            'earliest_time': earliest_time,
            'latest_time': latest_time,
            'max_results': self.search_params.get('max_results', 1000),
            'timeout': self.search_params.get('timeout', 60)
        }
        
        logger.debug("Performing monitoring check", 
                    earliest_time=earliest_time,
                    latest_time=latest_time)
        
        # Execute search
        results = client.execute_search(self.query, **search_params)
        
        if results:
            # Add metadata to results
            for result in results:
                result['_monitoring_check_time'] = now.isoformat()
                
            # Add to buffer
            self.results_buffer.extend(results)
            
            logger.info("Monitoring check completed", 
                       new_results=len(results),
                       total_buffered=len(self.results_buffer))
        else:
            logger.debug("No new results in monitoring check")
            
        self.last_check_time = now
        self.last_activity = now


class SplunkMonitorTool:
    """MCP tool for continuous Splunk log monitoring (single session)."""
    
    def __init__(self):
        """Initialize the monitoring tool."""
        self.config = get_config()
        self.current_session: Optional[MonitoringSession] = None
        self._lock = threading.Lock()
        
    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition for splunk_monitor."""
        return Tool(
            name="splunk_monitor",
            description=(
                "Start continuous monitoring of Splunk logs with specified intervals. "
                "This tool creates a single monitoring session that runs in the background, "
                "collecting logs at regular intervals and buffering results for analysis. "
                "Only one monitoring session can be active at a time."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "status", "get_results"],
                        "description": "Action to perform: start monitoring, stop monitoring, get status, or retrieve results"
                    },
                    "query": {
                        "type": "string",
                        "description": "SPL search query to monitor (required for 'start' action)"
                    },
                    "interval": {
                        "type": "integer",
                        "description": "Monitoring interval in seconds (required for 'start' action)",
                        "minimum": 10,
                        "maximum": 3600,
                        "default": 60
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results per monitoring check",
                        "default": 1000,
                        "minimum": 1,
                        "maximum": 10000
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Search timeout in seconds for each monitoring check",
                        "default": 60,
                        "minimum": 10,
                        "maximum": 300
                    },
                    "clear_buffer": {
                        "type": "boolean",
                        "description": "Whether to clear results buffer after retrieving (for get_results action)",
                        "default": True
                    }
                },
                "required": ["action"]
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute the splunk_monitor tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            List[TextContent]: Tool execution results
        """
        try:
            action = arguments.get("action")
            if not action:
                raise ValueError("Action parameter is required")
            
            if action == "start":
                return await self._start_monitoring(arguments)
            elif action == "stop":
                return await self._stop_monitoring()
            elif action == "status":
                return await self._get_status()
            elif action == "get_results":
                return await self._get_results(arguments)
            else:
                raise ValueError(f"Unknown action: {action}")
                
        except Exception as e:
            logger.error("Error in monitor tool execution", error=str(e))
            return [TextContent(
                type="text",
                text=f"❌ **Monitor Tool Error**\n\n"
                     f"Error: {e}\n\n"
                     f"Please check your parameters and try again."
            )]
    
    async def _start_monitoring(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Start a new monitoring session.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            List[TextContent]: Start monitoring results
        """
        query = arguments.get("query")
        if not query:
            raise ValueError("Query parameter is required for start action")
        
        interval = arguments.get("interval", 60)
        max_results = arguments.get("max_results", 1000)
        timeout = arguments.get("timeout", 60)
        
        # Validate parameters
        if interval < 10 or interval > 3600:
            raise ValueError("Interval must be between 10 and 3600 seconds")
        
        with self._lock:
            # Stop existing session if any
            if self.current_session and self.current_session.is_active:
                self.current_session.stop()
            
            # Create and start new monitoring session
            self.current_session = MonitoringSession(
                query=query,
                interval=interval,
                max_results=max_results,
                timeout=timeout
            )
            
            self.current_session.start()
        
        logger.info("Started monitoring session", 
                   query=query, 
                   interval=interval)
        
        return [TextContent(
            type="text",
            text=f"✅ **Monitoring Session Started**\n\n"
                 f"**Query:** `{query}`\n"
                 f"**Interval:** {interval} seconds\n"
                 f"**Max Results per Check:** {max_results}\n"
                 f"**Timeout:** {timeout} seconds\n\n"
                 f"The monitoring session is now running in the background. "
                 f"Use the available actions to check status, retrieve results, or stop monitoring.\n\n"
                 f"**Next Steps:**\n"
                 f"- Check status: `action: status`\n"
                 f"- Get results: `action: get_results`\n"
                 f"- Stop monitoring: `action: stop`"
        )]
    
    async def _stop_monitoring(self) -> List[TextContent]:
        """Stop the current monitoring session.
        
        Returns:
            List[TextContent]: Stop monitoring results
        """
        with self._lock:
            if not self.current_session:
                raise ValueError("No active monitoring session found")
            
            self.current_session.stop()
            self.current_session = None
        
        logger.info("Stopped monitoring session")
        
        return [TextContent(
            type="text",
            text=f"✅ **Monitoring Session Stopped**\n\n"
                 f"The monitoring session has been stopped and removed. "
                 f"Any buffered results have been discarded."
        )]
    
    async def _get_status(self) -> List[TextContent]:
        """Get status of the current monitoring session.
        
        Returns:
            List[TextContent]: Session status
        """
        with self._lock:
            if not self.current_session:
                return [TextContent(
                    type="text",
                    text="📭 **No Active Monitoring Session**\n\n"
                         "There is currently no active monitoring session. "
                         "Use `action: start` to create a new monitoring session."
                )]
            
            status = self.current_session.get_status()
        
        # Format status information
        status_text = f"📊 **Monitoring Session Status**\n\n"
        status_text += f"**Query:** `{status['query']}`\n"
        status_text += f"**Interval:** {status['interval']} seconds\n"
        status_text += f"**Status:** {'🟢 Active' if status['is_active'] else '🔴 Inactive'}\n"
        status_text += f"**Created:** {status['created_at']}\n"
        status_text += f"**Last Activity:** {status['last_activity']}\n"
        
        if status['last_check_time']:
            status_text += f"**Last Check:** {status['last_check_time']}\n"
        
        status_text += f"**Error Count:** {status['error_count']}\n"
        status_text += f"**Buffered Results:** {status['results_in_buffer']}\n\n"
        
        if status['results_in_buffer'] > 0:
            status_text += f"💡 **Tip:** Use `action: get_results` to retrieve buffered results."
        
        return [TextContent(type="text", text=status_text)]
    
    async def _get_results(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get results from the current monitoring session.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            List[TextContent]: Monitoring results
        """
        clear_buffer = arguments.get("clear_buffer", True)
        
        with self._lock:
            if not self.current_session:
                raise ValueError("No active monitoring session found")
            
            results = self.current_session.get_buffered_results(clear_buffer=clear_buffer)
        
        if not results:
            return [TextContent(
                type="text",
                text=f"📭 **No Results Available**\n\n"
                     f"No new results have been collected since the last retrieval. "
                     f"The monitoring session is still active and will continue collecting data."
            )]
        
        # Format results
        result_text = f"📊 **Monitoring Results**\n\n"
        result_text += f"**Results Count:** {len(results)}\n"
        result_text += f"**Buffer Cleared:** {'Yes' if clear_buffer else 'No'}\n\n"
        
        # Group results by check time for better organization
        results_by_check = {}
        for result in results:
            check_time = result.get('_monitoring_check_time', 'Unknown')
            if check_time not in results_by_check:
                results_by_check[check_time] = []
            results_by_check[check_time].append(result)
        
        # Display results grouped by check time
        for check_time, check_results in sorted(results_by_check.items()):
            result_text += f"**Check Time:** {check_time}\n"
            result_text += f"**Events:** {len(check_results)}\n\n"
            
            # Show first few results from this check
            for i, result in enumerate(check_results[:5], 1):
                result_text += f"**Event {i}:**\n"
                
                # Show key fields
                key_fields = ['_time', '_raw', 'host', 'source', 'sourcetype', 'index']
                for field in key_fields:
                    if field in result:
                        value = result[field]
                        if field == '_raw' and len(str(value)) > 200:
                            value = str(value)[:200] + "..."
                        result_text += f"  - **{field}:** {value}\n"
                
                result_text += "\n"
            
            if len(check_results) > 5:
                result_text += f"... and {len(check_results) - 5} more events from this check.\n\n"
            
            result_text += "---\n\n"
        
        # Add analysis suggestions
        result_text += self._generate_monitoring_analysis(results)
        
        return [TextContent(type="text", text=result_text)]
    
    def _generate_monitoring_analysis(self, results: List[Dict[str, Any]]) -> str:
        """Generate analysis suggestions for monitoring results.
        
        Args:
            results: Monitoring results
            
        Returns:
            str: Analysis suggestions
        """
        if not results:
            return ""
        
        analysis = "💡 **Analysis Suggestions:**\n\n"
        
        # Analyze patterns in the results
        hosts = set()
        sources = set()
        sourcetypes = set()
        
        for result in results:
            if 'host' in result:
                hosts.add(result['host'])
            if 'source' in result:
                sources.add(result['source'])
            if 'sourcetype' in result:
                sourcetypes.add(result['sourcetype'])
        
        if hosts:
            analysis += f"- **Host Analysis:** {len(hosts)} unique hosts detected\n"
            if len(hosts) <= 5:
                analysis += f"  Hosts: {', '.join(sorted(hosts))}\n"
        
        if sourcetypes:
            analysis += f"- **Source Type Analysis:** {len(sourcetypes)} unique source types\n"
            if len(sourcetypes) <= 5:
                analysis += f"  Types: {', '.join(sorted(sourcetypes))}\n"
        
        # Time-based analysis
        analysis += f"- **Volume Analysis:** {len(results)} events collected\n"
        
        # Check for potential issues
        error_keywords = ['error', 'fail', 'exception', 'critical', 'alert']
        error_count = 0
        
        for result in results:
            raw_data = str(result.get('_raw', '')).lower()
            if any(keyword in raw_data for keyword in error_keywords):
                error_count += 1
        
        if error_count > 0:
            analysis += f"- **⚠️ Alert:** {error_count} events contain error-related keywords\n"
        
        analysis += f"\n**Recommendations:**\n"
        analysis += f"- Continue monitoring to identify trends\n"
        analysis += f"- Consider setting up alerts for critical patterns\n"
        analysis += f"- Use statistical analysis for anomaly detection\n"
        
        return analysis
    
    def cleanup(self):
        """Clean up the monitoring session."""
        with self._lock:
            if self.current_session:
                try:
                    self.current_session.stop()
                except Exception as e:
                    logger.warning("Error stopping session during cleanup", error=str(e))
                
                self.current_session = None
        
        logger.info("Monitoring session cleaned up")


# Global monitor tool instance
_monitor_tool = SplunkMonitorTool()


def get_monitor_tool() -> SplunkMonitorTool:
    """Get the global monitor tool instance."""
    return _monitor_tool


def get_tool_definition() -> Tool:
    """Get the MCP tool definition for splunk_monitor."""
    return _monitor_tool.get_tool_definition()


async def execute_monitor(arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute the splunk_monitor tool."""
    return await _monitor_tool.execute(arguments)
