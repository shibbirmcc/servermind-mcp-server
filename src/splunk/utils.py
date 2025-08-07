"""Splunk utility functions module."""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger(__name__)


def _validate_date(date_str: str) -> bool:
    """Validate date string in YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def _validate_datetime(datetime_str: str) -> bool:
    """Validate datetime string in ISO format."""
    try:
        # Try different ISO formats
        formats = [
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%S.%fZ'
        ]
        for fmt in formats:
            try:
                datetime.strptime(datetime_str.rstrip('Z'), fmt)
                return True
            except ValueError:
                continue
        return False
    except ValueError:
        return False


def _validate_us_datetime(datetime_str: str) -> bool:
    """Validate US datetime string in MM/dd/yyyy:HH:mm:ss format."""
    try:
        datetime.strptime(datetime_str, '%m/%d/%Y:%H:%M:%S')
        return True
    except ValueError:
        return False


def validate_spl_query(query: str) -> tuple[bool, Optional[str]]:
    """Validate SPL query syntax.
    
    Args:
        query: SPL query string
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not query or not query.strip():
        return False, "Query cannot be empty"
    
    query = query.strip()
    
    # Basic validation checks
    if not query.startswith(('search ', 'index=', '|', 'savedsearch')):
        # If it doesn't start with common SPL patterns, prepend 'search'
        query = f"search {query}"
    
    # Check for potentially dangerous commands
    dangerous_commands = ['delete', 'drop', 'truncate', 'alter']
    query_lower = query.lower()
    
    for cmd in dangerous_commands:
        if f' {cmd} ' in query_lower or query_lower.startswith(f'{cmd} '):
            return False, f"Potentially dangerous command '{cmd}' detected"
    
    # Check for balanced pipes and quotes
    pipe_count = query.count('|')
    if pipe_count > 50:  # Reasonable limit
        return False, "Too many pipe operations (limit: 50)"
    
    # Check for balanced quotes
    single_quotes = query.count("'")
    double_quotes = query.count('"')
    
    if single_quotes % 2 != 0:
        return False, "Unbalanced single quotes"
    
    if double_quotes % 2 != 0:
        return False, "Unbalanced double quotes"
    
    return True, None


def parse_time_range(time_str: str) -> Optional[str]:
    """Parse and validate time range string.
    
    Args:
        time_str: Time range string (e.g., '-24h', '-1d', 'now')
        
    Returns:
        str: Validated time string or None if invalid
    """
    if not time_str:
        return None
    
    time_str = time_str.strip()
    
    # Common time patterns
    relative_patterns = [
        r'^-\d+[smhdwMy]$',  # -1s, -5m, -2h, -3d, -1w, -1M, -1y
        r'^-\d+[smhdwMy]@[smhdwMy]$',  # -1d@d (snap to day)
        r'^now$',
        r'^earliest$',
        r'^latest$',
        r'^rt$',  # real-time
        r'^rt-\d+[smh]$',  # rt-5m
    ]
    
    # Check relative patterns
    for pattern in relative_patterns:
        if re.match(pattern, time_str, re.IGNORECASE):
            return time_str
    
    # Check absolute time patterns with validation
    absolute_patterns = [
        (r'^\d{4}-\d{2}-\d{2}$', _validate_date),  # 2023-01-01
        (r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', _validate_datetime),  # 2023-01-01T12:00:00
        (r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z?$', _validate_datetime),  # ISO format
        (r'^\d{2}/\d{2}/\d{4}:\d{2}:\d{2}:\d{2}$', _validate_us_datetime),  # MM/dd/yyyy:HH:mm:ss
    ]
    
    for pattern, validator in absolute_patterns:
        if re.match(pattern, time_str):
            if validator(time_str):
                return time_str
            else:
                logger.warning("Invalid date/time format", time_str=time_str)
                return None
    
    # Check epoch time
    try:
        epoch = float(time_str)
        if 0 < epoch < 2147483647:  # Valid epoch range
            return time_str
    except ValueError:
        pass
    
    logger.warning("Invalid time format", time_str=time_str)
    return None


def format_search_results(results: List[Dict[str, Any]], 
                         max_field_length: int = 100) -> List[Dict[str, Any]]:
    """Format search results for display.
    
    Args:
        results: Raw search results
        max_field_length: Maximum length for field values
        
    Returns:
        List[Dict[str, Any]]: Formatted results
    """
    formatted_results = []
    
    for result in results:
        formatted_result = {}
        
        for key, value in result.items():
            # Convert value to string and truncate if necessary
            str_value = str(value) if value is not None else ""
            
            if len(str_value) > max_field_length:
                str_value = str_value[:max_field_length] + "..."
            
            formatted_result[key] = str_value
        
        formatted_results.append(formatted_result)
    
    return formatted_results


def extract_field_statistics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract field statistics from search results.
    
    Args:
        results: Search results
        
    Returns:
        Dict[str, Any]: Field statistics
    """
    if not results:
        return {}
    
    field_stats = {}
    total_results = len(results)
    
    # Analyze each field
    all_fields = set()
    for result in results:
        all_fields.update(result.keys())
    
    for field in all_fields:
        values = []
        null_count = 0
        
        for result in results:
            value = result.get(field)
            if value is None or value == "":
                null_count += 1
            else:
                values.append(str(value))
        
        # Calculate statistics
        unique_values = set(values)
        
        field_stats[field] = {
            'total_count': total_results,
            'non_null_count': len(values),
            'null_count': null_count,
            'unique_count': len(unique_values),
            'coverage_percent': round((len(values) / total_results) * 100, 2),
            'top_values': list(unique_values)[:10] if len(unique_values) <= 10 else []
        }
        
        # Add numeric statistics if applicable
        if values:
            try:
                numeric_values = [float(v) for v in values if v.replace('.', '').replace('-', '').isdigit()]
                if numeric_values:
                    field_stats[field]['numeric_stats'] = {
                        'min': min(numeric_values),
                        'max': max(numeric_values),
                        'avg': sum(numeric_values) / len(numeric_values),
                        'count': len(numeric_values)
                    }
            except (ValueError, TypeError):
                pass
    
    return field_stats


def generate_spl_suggestions(query: str, results: List[Dict[str, Any]]) -> List[str]:
    """Generate SPL query suggestions based on results.
    
    Args:
        query: Original query
        results: Search results
        
    Returns:
        List[str]: List of suggested queries
    """
    suggestions = []
    
    if not results:
        return suggestions
    
    # Extract common fields
    field_stats = extract_field_statistics(results)
    common_fields = [field for field, stats in field_stats.items() 
                    if stats['coverage_percent'] > 50 and not field.startswith('_')]
    
    # Time-based suggestions
    if any('_time' in result for result in results):
        suggestions.extend([
            f"{query} | timechart count",
            f"{query} | timechart span=1h count",
            f"{query} | bucket _time span=1h | stats count by _time"
        ])
    
    # Field analysis suggestions
    for field in common_fields[:3]:
        suggestions.extend([
            f"{query} | stats count by {field}",
            f"{query} | top limit=10 {field}",
            f"{query} | rare limit=10 {field}"
        ])
    
    # Error analysis suggestions
    error_terms = ['error', 'fail', 'exception', 'warning']
    if any(term in query.lower() for term in error_terms):
        suggestions.extend([
            f"{query} | stats count by host, source",
            f"{query} | eval error_type=case(match(_raw, \"(?i)error\"), \"error\", match(_raw, \"(?i)warning\"), \"warning\", 1=1, \"other\") | stats count by error_type"
        ])
    
    # Performance suggestions
    suggestions.extend([
        f"{query} | head 100",
        f"{query} | tail 100",
        f"{query} | dedup host, source | table host, source, _time"
    ])
    
    return suggestions[:10]  # Return top 10 suggestions


def sanitize_field_name(field_name: str) -> str:
    """Sanitize field name for SPL usage.
    
    Args:
        field_name: Original field name
        
    Returns:
        str: Sanitized field name
    """
    # Remove or replace invalid characters
    sanitized = re.sub(r'[^\w\-_.]', '_', field_name)
    
    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = f"field_{sanitized}"
    
    return sanitized


def estimate_search_cost(query: str, time_range: str = "-24h") -> Dict[str, Any]:
    """Estimate the computational cost of a search query.
    
    Args:
        query: SPL query
        time_range: Time range for the search
        
    Returns:
        Dict[str, Any]: Cost estimation
    """
    cost_factors = {
        'time_range_score': 1,
        'complexity_score': 1,
        'field_count_score': 1,
        'command_count_score': 1
    }
    
    # Time range scoring
    if 'rt' in time_range.lower():
        cost_factors['time_range_score'] = 5  # Real-time is expensive
    elif '-1y' in time_range or '-365d' in time_range:
        cost_factors['time_range_score'] = 4
    elif '-30d' in time_range or '-1M' in time_range:
        cost_factors['time_range_score'] = 3
    elif '-7d' in time_range or '-1w' in time_range:
        cost_factors['time_range_score'] = 2
    
    # Query complexity scoring
    expensive_commands = ['join', 'append', 'union', 'lookup', 'transaction', 'cluster']
    for cmd in expensive_commands:
        if cmd in query.lower():
            cost_factors['complexity_score'] += 2  # More aggressive scoring
    
    # Field and command counting
    pipe_count = query.count('|')
    cost_factors['command_count_score'] = min(pipe_count / 3, 5)  # More aggressive scoring
    
    # Calculate overall cost
    total_score = sum(cost_factors.values())
    
    if total_score <= 5:
        cost_level = "Low"
    elif total_score <= 10:
        cost_level = "Medium"
    elif total_score <= 15:
        cost_level = "High"
    else:
        cost_level = "Very High"
    
    return {
        'cost_level': cost_level,
        'total_score': total_score,
        'factors': cost_factors,
        'recommendations': _get_cost_recommendations(cost_level, cost_factors)
    }


def _get_cost_recommendations(cost_level: str, factors: Dict[str, Any]) -> List[str]:
    """Get recommendations to reduce search cost.
    
    Args:
        cost_level: Estimated cost level
        factors: Cost factors
        
    Returns:
        List[str]: Recommendations
    """
    recommendations = []
    
    if cost_level in ["High", "Very High"]:
        if factors['time_range_score'] > 3:
            recommendations.append("Consider reducing the time range to improve performance")
        
        if factors['complexity_score'] > 2:
            recommendations.append("Consider simplifying the query by reducing expensive commands")
        
        if factors['command_count_score'] > 3:
            recommendations.append("Consider breaking the query into smaller parts")
        
        recommendations.append("Add specific index and sourcetype filters to improve performance")
        recommendations.append("Use 'head' or 'tail' commands to limit results if appropriate")
    
    return recommendations
