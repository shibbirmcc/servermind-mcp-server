#!/usr/bin/env python3
"""
Test script to verify the split workflow:
1. group_error_logs -> 2. extract_trace_ids_for_search -> 3. splunk_trace_search_by_ids
"""

import asyncio
import json
import sys
sys.path.append('.')

from src.tools.group_error_logs_prompt import execute as execute_group_error_logs
from src.tools.extract_trace_ids_for_search import execute as execute_extract_trace_ids

async def test_split_workflow():
    print("🧪 Testing Split Workflow: group_error_logs -> extract_trace_ids_for_search")
    print("=" * 70)
    
    # Sample error logs data
    sample_logs = [
        {
            'message': 'Failed to connect to database server mysql-prod-01',
            'trace_id': 'abc123def456ghi789jkl012',
            'service_name': 'user-service',
            'timestamp': '2023-01-01T10:00:00Z',
            'level': 'ERROR'
        },
        {
            'message': 'Failed to connect to database server mysql-prod-02', 
            'trace_id': 'mno345pqr678stu901vwx234',
            'service_name': 'user-service',
            'timestamp': '2023-01-01T10:01:00Z',
            'level': 'ERROR'
        },
        {
            'message': 'Authentication failed for user john.doe@example.com',
            'trace_id': 'def456ghi789jkl012mno345',
            'service_name': 'auth-service', 
            'timestamp': '2023-01-01T10:02:00Z',
            'level': 'ERROR'
        },
        {
            'message': 'Authentication failed for user jane.smith@example.com',
            'trace_id': 'pqr678stu901vwx234yzab567',
            'service_name': 'auth-service',
            'timestamp': '2023-01-01T10:03:00Z', 
            'level': 'ERROR'
        }
    ]
    
    print(f"📥 Input: {len(sample_logs)} sample error log events")
    
    # Step 1: Group error logs
    print("\n🔄 Step 1: Grouping error logs...")
    group_arguments = {
        'logs': sample_logs,
        'max_groups': 5
    }
    
    group_results = await execute_group_error_logs(group_arguments)
    if not group_results:
        print("❌ No results from group_error_logs")
        return
    
    group_output = group_results[0].text
    print("✅ Group error logs completed")
    
    try:
        group_json = json.loads(group_output)
        print(f"   - Kind: {group_json.get('kind')}")
        print(f"   - Next tool: {group_json.get('next', [{}])[0].get('toolName')}")
        print(f"   - Step info: {group_json.get('stepInfo')}")
        
        # Extract the prompt result (this would normally be done by the LLM)
        # For testing, we'll simulate a grouped result
        simulated_grouped_logs = [
            {
                "pattern": "Database connection failed",
                "template": "failed to connect to database server <VAL>",
                "count": 2,
                "chosen_id": "abc123def456ghi789jkl012",
                "all_ids": ["abc123def456ghi789jkl012", "mno345pqr678stu901vwx234"],
                "sample_events": sample_logs[:2]
            },
            {
                "pattern": "Authentication error", 
                "template": "authentication failed for user <VAL>",
                "count": 2,
                "chosen_id": "def456ghi789jkl012mno345",
                "all_ids": ["def456ghi789jkl012mno345", "pqr678stu901vwx234yzab567"],
                "sample_events": sample_logs[2:]
            }
        ]
        
    except json.JSONDecodeError:
        print("⚠️  Could not parse group output as JSON, using simulated data")
        simulated_grouped_logs = [
            {
                "pattern": "Database connection failed",
                "chosen_id": "abc123def456ghi789jkl012",
                "count": 2
            },
            {
                "pattern": "Authentication error",
                "chosen_id": "def456ghi789jkl012mno345", 
                "count": 2
            }
        ]
    
    # Step 2: Extract trace IDs
    print("\n🔄 Step 2: Extracting trace IDs...")
    extract_arguments = {
        'grouped_logs': json.dumps(simulated_grouped_logs),
        'deduplicate': True,
        'earliest_time': '-24h',
        'latest_time': 'now',
        'max_results': 4000
    }
    
    extract_results = await execute_extract_trace_ids(extract_arguments)
    if not extract_results:
        print("❌ No results from extract_trace_ids_for_search")
        return
        
    extract_output = extract_results[0].text
    print("✅ Extract trace IDs completed")
    
    try:
        extract_json = json.loads(extract_output)
        print(f"   - Kind: {extract_json.get('kind')}")
        print(f"   - Summary: {extract_json.get('summary')}")
        print(f"   - Extracted IDs: {extract_json.get('extracted_trace_ids')}")
        print(f"   - Total trace IDs: {extract_json.get('total_trace_ids')}")
        print(f"   - Next tool: {extract_json.get('next', [{}])[0].get('toolName')}")
        print(f"   - Step info: {extract_json.get('stepInfo')}")
        
        # Verify the workflow chain
        next_tool = extract_json.get('next', [{}])[0].get('toolName')
        if next_tool == 'splunk_trace_search_by_ids':
            print("✅ Workflow chain is correct: group_error_logs -> extract_trace_ids_for_search -> splunk_trace_search_by_ids")
        else:
            print(f"⚠️  Expected next tool to be 'splunk_trace_search_by_ids', got '{next_tool}'")
            
    except json.JSONDecodeError as e:
        print(f"⚠️  Could not parse extract output as JSON: {e}")
        print(f"Raw output: {extract_output[:200]}...")
    
    print("\n🎉 Split workflow test completed!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_split_workflow())
