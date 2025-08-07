"""Splunk API client module."""

import splunklib.client as client
import splunklib.results as results
from typing import Dict, Any, List, Optional, Iterator
import structlog
from ..config import SplunkConfig

logger = structlog.get_logger(__name__)


class SplunkConnectionError(Exception):
    """Exception raised when connection to Splunk fails."""
    pass


class SplunkAuthenticationError(Exception):
    """Exception raised when authentication to Splunk fails."""
    pass


class SplunkSearchError(Exception):
    """Exception raised when search execution fails."""
    pass


class SplunkClient:
    """Splunk API client for connecting to Splunk instances."""
    
    def __init__(self, config: SplunkConfig):
        """Initialize Splunk client.
        
        Args:
            config: Splunk configuration
        """
        self.config = config
        self._service: Optional[client.Service] = None
        self._connected = False
    
    def connect(self) -> None:
        """Connect to Splunk instance.
        
        Raises:
            SplunkConnectionError: If connection fails
            SplunkAuthenticationError: If authentication fails
        """
        if self._connected and self._service is not None:
            return
        
        logger.info("Connecting to Splunk", host=self.config.host, port=self.config.port)
        
        try:
            # Create service connection - use token if available, otherwise username/password
            if self.config.token:
                self._service = client.connect(
                    host=self.config.host,
                    port=self.config.port,
                    token=self.config.token,
                    scheme=self.config.scheme,
                    verify=self.config.verify_ssl,
                    timeout=self.config.timeout,
                    autologin=True
                )
            else:
                self._service = client.connect(
                    host=self.config.host,
                    port=self.config.port,
                    username=self.config.username,
                    password=self.config.password,
                    scheme=self.config.scheme,
                    verify=self.config.verify_ssl,
                    timeout=self.config.timeout,
                    autologin=True
                )
            
            # Test connection by getting server info
            info = self._service.info
            logger.info("Connected to Splunk successfully", 
                       version=info.get('version'), 
                       build=info.get('build'))
            
            self._connected = True
            
        except Exception as e:
            error_msg = str(e).lower()
            if 'authentication' in error_msg or 'login' in error_msg or 'unauthorized' in error_msg:
                raise SplunkAuthenticationError(f"Authentication failed: {e}")
            else:
                raise SplunkConnectionError(f"Connection failed: {e}")
    
    def disconnect(self) -> None:
        """Disconnect from Splunk instance."""
        if self._service is not None:
            try:
                self._service.logout()
                logger.info("Disconnected from Splunk")
            except Exception as e:
                logger.warning("Error during disconnect", error=str(e))
            finally:
                self._service = None
                self._connected = False
    
    def is_connected(self) -> bool:
        """Check if client is connected to Splunk.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self._connected and self._service is not None
    
    def get_service(self) -> client.Service:
        """Get the Splunk service instance.
        
        Returns:
            client.Service: Splunk service instance
            
        Raises:
            SplunkConnectionError: If not connected
        """
        if not self.is_connected():
            self.connect()
        
        if self._service is None:
            raise SplunkConnectionError("Not connected to Splunk")
        
        return self._service
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to Splunk and return server info.
        
        Returns:
            Dict[str, Any]: Server information
            
        Raises:
            SplunkConnectionError: If connection test fails
        """
        try:
            service = self.get_service()
            info = service.info
            
            return {
                'connected': True,
                'version': info.get('version'),
                'build': info.get('build'),
                'server_name': info.get('serverName'),
                'license_state': info.get('licenseState'),
                'mode': info.get('mode')
            }
        except Exception as e:
            logger.error("Connection test failed", error=str(e))
            raise SplunkConnectionError(f"Connection test failed: {e}")
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information.
        
        Returns:
            Dict[str, Any]: Server information
            
        Raises:
            SplunkConnectionError: If getting server info fails
        """
        try:
            service = self.get_service()
            info = service.info
            
            return {
                'version': info.get('version'),
                'build': info.get('build'),
                'server_name': info.get('serverName'),
                'license_state': info.get('licenseState'),
                'mode': info.get('mode'),
                'host': info.get('host'),
                'product_type': info.get('product_type')
            }
        except Exception as e:
            logger.error("Failed to get server info", error=str(e))
            raise SplunkConnectionError(f"Failed to get server info: {e}")
    
    def search(self, query: str, earliest_time: str = "-24h", latest_time: str = "now", 
               max_results: int = 100, **kwargs) -> List[Dict[str, Any]]:
        """Execute a search query.
        
        Args:
            query: SPL search query
            earliest_time: Start time for search
            latest_time: End time for search
            max_results: Maximum number of results
            **kwargs: Additional search parameters
            
        Returns:
            List[Dict[str, Any]]: Search results
            
        Raises:
            SplunkSearchError: If search fails
        """
        return self.execute_search(
            query=query,
            earliest_time=earliest_time,
            latest_time=latest_time,
            max_results=max_results,
            **kwargs
        )
    
    def get_indexes(self, filter_pattern: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of available indexes.
        
        Args:
            filter_pattern: Optional pattern to filter index names
            
        Returns:
            List[Dict[str, Any]]: List of index information
            
        Raises:
            SplunkConnectionError: If operation fails
        """
        try:
            service = self.get_service()
            indexes = service.indexes
            
            index_list = []
            for index in indexes:
                index_info = {
                    'name': index.name,
                    'earliest_time': getattr(index, 'earliest_time', None),
                    'latest_time': getattr(index, 'latest_time', None),
                    'total_event_count': getattr(index, 'totalEventCount', 0),
                    'current_db_size_mb': getattr(index, 'currentDBSizeMB', 0),
                    'max_data_size': getattr(index, 'maxDataSize', 'auto'),
                    'disabled': getattr(index, 'disabled', False)
                }
                
                # Apply filter if provided
                if filter_pattern is None or filter_pattern.lower() in index.name.lower():
                    index_list.append(index_info)
            
            logger.info("Retrieved indexes", count=len(index_list))
            return index_list
            
        except Exception as e:
            logger.error("Failed to get indexes", error=str(e))
            raise SplunkConnectionError(f"Failed to get indexes: {e}")
    
    def create_search_job(self, query: str, **kwargs) -> client.Job:
        """Create a search job.
        
        Args:
            query: SPL search query
            **kwargs: Additional search parameters
            
        Returns:
            client.Job: Search job instance
            
        Raises:
            SplunkSearchError: If search job creation fails
        """
        try:
            service = self.get_service()
            
            # Ensure query starts with 'search' command if it doesn't already
            normalized_query = query.strip()
            if not normalized_query.lower().startswith('search ') and not normalized_query.startswith('|'):
                normalized_query = f"search {normalized_query}"
            
            # Set default search parameters
            search_kwargs = {
                'exec_mode': 'normal',
                'earliest_time': kwargs.get('earliest_time', '-24h'),
                'latest_time': kwargs.get('latest_time', 'now'),
                'max_count': kwargs.get('max_results', 100),
                'timeout': kwargs.get('timeout', self.config.timeout)
            }
            
            # Override with provided kwargs
            search_kwargs.update({k: v for k, v in kwargs.items() 
                                if k not in ['max_results']})
            
            logger.info("Creating search job", query=normalized_query, **search_kwargs)
            
            job = service.jobs.create(normalized_query, **search_kwargs)
            
            logger.info("Search job created", sid=job.sid)
            return job
            
        except Exception as e:
            logger.error("Failed to create search job", query=query, error=str(e))
            raise SplunkSearchError(f"Failed to create search job: {e}")
    
    def wait_for_job(self, job: client.Job, timeout: Optional[int] = None) -> None:
        """Wait for search job to complete.
        
        Args:
            job: Search job instance
            timeout: Timeout in seconds
            
        Raises:
            SplunkSearchError: If job fails or times out
        """
        try:
            timeout = timeout or self.config.timeout
            
            logger.info("Waiting for search job to complete", sid=job.sid, timeout=timeout)
            
            # Wait for job to complete
            while not job.is_done():
                job.refresh()
                
                # Check for job failure
                if job.state == 'FAILED':
                    raise SplunkSearchError(f"Search job failed: {job.sid}")
            
            logger.info("Search job completed", 
                       sid=job.sid, 
                       result_count=job.resultCount,
                       event_count=job.eventCount)
            
        except Exception as e:
            logger.error("Error waiting for search job", sid=job.sid, error=str(e))
            raise SplunkSearchError(f"Error waiting for search job: {e}")
    
    def get_job_results(self, job: client.Job, output_mode: str = 'json') -> Iterator[Dict[str, Any]]:
        """Get results from completed search job.
        
        Args:
            job: Completed search job
            output_mode: Output format ('json', 'csv', 'xml')
            
        Returns:
            Iterator[Dict[str, Any]]: Search results
            
        Raises:
            SplunkSearchError: If getting results fails
        """
        try:
            logger.info("Getting search results", sid=job.sid, output_mode=output_mode)
            
            # Get results
            result_stream = job.results(output_mode=output_mode)
            
            if output_mode == 'json':
                # Parse JSON results
                reader = results.JSONResultsReader(result_stream)
                for result in reader:
                    if isinstance(result, dict):
                        yield result
            else:
                # For other formats, yield raw data
                for line in result_stream:
                    yield {'raw': line.decode('utf-8') if isinstance(line, bytes) else line}
            
            logger.info("Search results retrieved", sid=job.sid)
            
        except Exception as e:
            logger.error("Failed to get search results", sid=job.sid, error=str(e))
            raise SplunkSearchError(f"Failed to get search results: {e}")
    
    def execute_search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Execute a search and return results.
        
        Args:
            query: SPL search query
            **kwargs: Search parameters
            
        Returns:
            List[Dict[str, Any]]: Search results
            
        Raises:
            SplunkSearchError: If search execution fails
        """
        job = None
        try:
            # Create search job
            job = self.create_search_job(query, **kwargs)
            
            # Wait for completion
            self.wait_for_job(job, kwargs.get('timeout'))
            
            # Get results
            results_list = list(self.get_job_results(job))
            
            logger.info("Search executed successfully", 
                       query=query, 
                       result_count=len(results_list))
            
            return results_list
            
        except Exception as e:
            logger.error("Search execution failed", query=query, error=str(e))
            raise SplunkSearchError(f"Search execution failed: {e}")
        finally:
            # Clean up job
            if job is not None:
                try:
                    job.cancel()
                except Exception as e:
                    logger.warning("Failed to cancel search job", sid=job.sid, error=str(e))
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
