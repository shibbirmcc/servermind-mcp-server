"""Unit tests for utility functions."""

import pytest
from src.splunk.utils import (
    validate_spl_query,
    parse_time_range,
    format_search_results,
    extract_field_statistics,
    generate_spl_suggestions,
    sanitize_field_name,
    estimate_search_cost
)


class TestSPLValidation:
    """Test SPL query validation."""
    
    def test_valid_queries(self):
        """Test validation of valid SPL queries."""
        valid_queries = [
            "index=main error",
            "search error",
            "| stats count by host",
            "index=web_logs | head 100",
            "savedsearch my_search"
        ]
        
        for query in valid_queries:
            is_valid, error = validate_spl_query(query)
            assert is_valid, f"Query '{query}' should be valid, but got error: {error}"
    
    def test_invalid_queries(self):
        """Test validation of invalid SPL queries."""
        invalid_queries = [
            "",  # Empty query
            "   ",  # Whitespace only
            "index=main | delete *",  # Dangerous command
            "drop table users",  # Dangerous command
        ]
        
        for query in invalid_queries:
            is_valid, error = validate_spl_query(query)
            assert not is_valid, f"Query '{query}' should be invalid"
            assert error is not None
    
    def test_unbalanced_quotes(self):
        """Test detection of unbalanced quotes."""
        queries_with_unbalanced_quotes = [
            'index=main "error',  # Unbalanced double quote
            "index=main 'error",  # Unbalanced single quote
        ]
        
        for query in queries_with_unbalanced_quotes:
            is_valid, error = validate_spl_query(query)
            assert not is_valid
            assert "quote" in error.lower()
    
    def test_too_many_pipes(self):
        """Test detection of too many pipe operations."""
        query = "index=main" + " | head 1" * 51  # 51 pipes
        is_valid, error = validate_spl_query(query)
        assert not is_valid
        assert "pipe" in error.lower()


class TestTimeRangeParsing:
    """Test time range parsing."""
    
    def test_valid_relative_times(self):
        """Test parsing of valid relative time ranges."""
        valid_times = [
            "-1h", "-24h", "-1d", "-7d", "-1w", "-1M", "-1y",
            "-1d@d", "-1w@w", "now", "earliest", "latest",
            "rt", "rt-5m", "rt-1h"
        ]
        
        for time_str in valid_times:
            result = parse_time_range(time_str)
            assert result == time_str, f"Time '{time_str}' should be valid"
    
    def test_valid_absolute_times(self):
        """Test parsing of valid absolute time ranges."""
        valid_times = [
            "2023-01-01",
            "2023-01-01T12:00:00",
            "2023-01-01T12:00:00.000Z",
            "01/01/2023:12:00:00",
            "1672531200"  # Epoch time
        ]
        
        for time_str in valid_times:
            result = parse_time_range(time_str)
            assert result == time_str, f"Time '{time_str}' should be valid"
    
    def test_invalid_times(self):
        """Test parsing of invalid time ranges."""
        invalid_times = [
            "invalid",
            "1h",  # Missing minus sign
            "2023-13-01",  # Invalid month
            "not-a-time"
        ]
        
        for time_str in invalid_times:
            result = parse_time_range(time_str)
            assert result is None, f"Time '{time_str}' should be invalid"
    
    def test_empty_time(self):
        """Test parsing of empty time string."""
        assert parse_time_range("") is None
        assert parse_time_range(None) is None


class TestResultFormatting:
    """Test search result formatting."""
    
    def test_format_search_results(self):
        """Test formatting of search results."""
        results = [
            {"_time": "2023-01-01T12:00:00", "host": "server1", "message": "test"},
            {"_time": "2023-01-01T12:01:00", "host": "server2", "message": "a" * 150}
        ]
        
        formatted = format_search_results(results, max_field_length=100)
        
        assert len(formatted) == 2
        assert formatted[0]["message"] == "test"
        assert len(formatted[1]["message"]) <= 103  # 100 + "..."
        assert formatted[1]["message"].endswith("...")
    
    def test_format_empty_results(self):
        """Test formatting of empty results."""
        formatted = format_search_results([])
        assert formatted == []
    
    def test_format_with_none_values(self):
        """Test formatting with None values."""
        results = [{"field1": None, "field2": "value"}]
        formatted = format_search_results(results)
        
        assert formatted[0]["field1"] == ""
        assert formatted[0]["field2"] == "value"


class TestFieldStatistics:
    """Test field statistics extraction."""
    
    def test_extract_field_statistics(self):
        """Test extraction of field statistics."""
        results = [
            {"host": "server1", "status": "200", "bytes": "1024"},
            {"host": "server1", "status": "404", "bytes": "512"},
            {"host": "server2", "status": "200", "bytes": None},
        ]
        
        stats = extract_field_statistics(results)
        
        assert "host" in stats
        assert stats["host"]["total_count"] == 3
        assert stats["host"]["non_null_count"] == 3
        assert stats["host"]["unique_count"] == 2
        assert stats["host"]["coverage_percent"] == 100.0
        
        assert "bytes" in stats
        assert stats["bytes"]["null_count"] == 1
        assert stats["bytes"]["coverage_percent"] == 66.67
    
    def test_extract_statistics_empty_results(self):
        """Test statistics extraction with empty results."""
        stats = extract_field_statistics([])
        assert stats == {}
    
    def test_numeric_statistics(self):
        """Test numeric statistics extraction."""
        results = [
            {"value": "100"},
            {"value": "200"},
            {"value": "300"},
        ]
        
        stats = extract_field_statistics(results)
        
        assert "numeric_stats" in stats["value"]
        numeric_stats = stats["value"]["numeric_stats"]
        assert numeric_stats["min"] == 100.0
        assert numeric_stats["max"] == 300.0
        assert numeric_stats["avg"] == 200.0
        assert numeric_stats["count"] == 3


class TestSPLSuggestions:
    """Test SPL suggestion generation."""
    
    def test_generate_suggestions_with_results(self):
        """Test suggestion generation with results."""
        query = "index=main error"
        results = [
            {"_time": "2023-01-01T12:00:00", "host": "server1", "level": "error"},
            {"_time": "2023-01-01T12:01:00", "host": "server2", "level": "warning"},
        ]
        
        suggestions = generate_spl_suggestions(query, results)
        
        assert len(suggestions) > 0
        assert any("timechart" in suggestion for suggestion in suggestions)
        assert any("stats count by" in suggestion for suggestion in suggestions)
    
    def test_generate_suggestions_empty_results(self):
        """Test suggestion generation with empty results."""
        suggestions = generate_spl_suggestions("index=main", [])
        assert suggestions == []
    
    def test_error_analysis_suggestions(self):
        """Test error-specific suggestions."""
        query = "index=main error"
        results = [{"host": "server1", "source": "app.log"}]
        
        suggestions = generate_spl_suggestions(query, results)
        
        # Should include error analysis suggestions
        error_suggestions = [s for s in suggestions if "error_type" in s or "host, source" in s]
        assert len(error_suggestions) > 0


class TestFieldSanitization:
    """Test field name sanitization."""
    
    def test_sanitize_valid_field_names(self):
        """Test sanitization of valid field names."""
        valid_names = ["host", "source_type", "field-name", "field.name"]
        
        for name in valid_names:
            sanitized = sanitize_field_name(name)
            assert sanitized == name
    
    def test_sanitize_invalid_field_names(self):
        """Test sanitization of invalid field names."""
        test_cases = [
            ("field name", "field_name"),  # Space
            ("field@name", "field_name"),  # Special character
            ("123field", "field_123field"),  # Starts with number
            ("field!@#$%", "field_____"),  # Multiple special characters
        ]
        
        for original, expected in test_cases:
            sanitized = sanitize_field_name(original)
            assert sanitized == expected


class TestSearchCostEstimation:
    """Test search cost estimation."""
    
    def test_low_cost_search(self):
        """Test estimation of low-cost search."""
        query = "index=main | head 10"
        time_range = "-1h"
        
        cost = estimate_search_cost(query, time_range)
        
        assert cost["cost_level"] == "Low"
        assert cost["total_score"] <= 5
    
    def test_high_cost_search(self):
        """Test estimation of high-cost search."""
        query = "index=* | join host [search index=other] | transaction host | cluster field=message"
        time_range = "-1y"
        
        cost = estimate_search_cost(query, time_range)
        
        assert cost["cost_level"] in ["High", "Very High"]
        assert len(cost["recommendations"]) > 0
    
    def test_real_time_search_cost(self):
        """Test cost estimation for real-time searches."""
        query = "index=main"
        time_range = "rt-5m"
        
        cost = estimate_search_cost(query, time_range)
        
        assert cost["factors"]["time_range_score"] == 5  # Real-time is expensive
    
    def test_cost_recommendations(self):
        """Test that high-cost searches include recommendations."""
        query = "index=* | join host [search index=other] | transaction host"
        time_range = "-30d"
        
        cost = estimate_search_cost(query, time_range)
        
        if cost["cost_level"] in ["High", "Very High"]:
            assert len(cost["recommendations"]) > 0
            assert any("performance" in rec.lower() for rec in cost["recommendations"])
