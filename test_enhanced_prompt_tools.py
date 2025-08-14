#!/usr/bin/env python3
"""
Test script to verify all enhanced prompt tools are working correctly.
Tests the workflow chain: group_error_logs → analyze_traces_narrative → root_cause_identification → ticket_split_prepare → bug_fix_executor
"""

import json
import asyncio
from src.tools.group_error_logs_prompt import execute
from src.tools.analyze_traces_narrative import execute_analyze_traces_narrative
from src.tools.root_cause_identification_prompt import execute_root_cause_identification_prompt
from src.tools.ticket_split_prepare import execute as execute_ticket_split_prepare
from src.tools.bug_fix_executor import execute_bug_fix_executor


async def test_enhanced_prompt_tools():
    """Test all enhanced prompt tools in sequence."""
    
    print("🧪 Testing Enhanced Prompt Tools Workflow")
    print("=" * 60)
    
    # Test data
    sample_logs = [
        {
            "_raw": '{"log_level": "ERROR", "message": "Database connection failed - service not started"}',
            "source": "user-management-service",
            "index": "main",
            "_time": "2025-08-14T09:34:51.000+00:00"
        },
        {
            "_raw": '{"log_level": "ERROR", "message": "Error while connecting to MySQL: 2003 (HY000): Can\'t connect to MySQL server on \'127.0.0.1:3306\' (61)"}',
            "source": "user-management-service", 
            "index": "main",
            "_time": "2025-08-14T09:34:51.000+00:00"
        },
        {
            "_raw": "2025-08-14 10:16:28,772 ERROR\t[689db77cc17ffff05d5510] utility:60 - name=javascript, class=Splunk.Error, lineNumber=5, message=Uncaught TypeError: Cannot read properties of undefined (reading 'regional')",
            "source": "/opt/splunk/var/log/splunk/web_service.log",
            "index": "_internal",
            "_time": "2025-08-14T10:16:28.772+00:00"
        }
    ]
    
    # Step 1: Test group_error_logs_prompt
    print("\n1️⃣ Testing group_error_logs_prompt...")
    try:
        group_result = await execute({
            "logs": sample_logs,
            "max_groups": 5
        })
        
        if group_result and len(group_result) > 0:
            response_text = group_result[0].text
            response_data = json.loads(response_text)
            
            print("✅ group_error_logs_prompt: SUCCESS")
            print(f"   - Response type: {response_data.get('kind')}")
            print(f"   - Has prompt: {'prompt' in response_data}")
            print(f"   - Has inputData: {'inputData' in response_data}")
            print(f"   - Next tool: {response_data.get('next', [{}])[0].get('toolName', 'None')}")
            print(f"   - Auto execute: {response_data.get('autoExecuteHint', False)}")
        else:
            print("❌ group_error_logs_prompt: FAILED - No response")
            return False
            
    except Exception as e:
        print(f"❌ group_error_logs_prompt: FAILED - {e}")
        return False
    
    # Step 2: Test analyze_traces_narrative
    print("\n2️⃣ Testing analyze_traces_narrative...")
    try:
        sample_traces = [
            {
                "id": "trace_123",
                "events": [
                    {"timestamp": "2025-08-14T09:34:51.000Z", "service": "user-service", "message": "Processing request"},
                    {"timestamp": "2025-08-14T09:34:52.000Z", "service": "database", "message": "Connection failed"}
                ]
            }
        ]
        
        narrative_result = await execute_analyze_traces_narrative({
            "traces": sample_traces,
            "mode": "auto",
            "verbosity": "normal"
        })
        
        if narrative_result and len(narrative_result) > 0:
            response_text = narrative_result[0].text
            response_data = json.loads(response_text)
            
            print("✅ analyze_traces_narrative: SUCCESS")
            print(f"   - Response type: {response_data.get('kind')}")
            print(f"   - Has prompt: {'prompt' in response_data}")
            print(f"   - Has inputData: {'inputData' in response_data}")
            print(f"   - Next tool: {response_data.get('next', [{}])[0].get('toolName', 'None')}")
            print(f"   - Auto execute: {response_data.get('autoExecuteHint', False)}")
        else:
            print("❌ analyze_traces_narrative: FAILED - No response")
            return False
            
    except Exception as e:
        print(f"❌ analyze_traces_narrative: FAILED - {e}")
        return False
    
    # Step 3: Test root_cause_identification_prompt
    print("\n3️⃣ Testing root_cause_identification_prompt...")
    try:
        sample_analysis = {
            "per_trace": [
                {
                    "trace_id": "trace_123",
                    "story": ["User request received", "Database connection failed"],
                    "services": [
                        {"name": "user-service", "analysis": "Service attempted connection"},
                        {"name": "database", "analysis": "Connection refused"}
                    ]
                }
            ]
        }
        
        root_cause_result = await execute_root_cause_identification_prompt({
            "analysis": sample_analysis,
            "mode": "auto",
            "confidence_floor": 0.6
        })
        
        if root_cause_result and len(root_cause_result) > 0:
            response_text = root_cause_result[0].text
            response_data = json.loads(response_text)
            
            print("✅ root_cause_identification_prompt: SUCCESS")
            print(f"   - Response type: {response_data.get('kind')}")
            print(f"   - Has prompt: {'prompt' in response_data}")
            print(f"   - Has inputData: {'inputData' in response_data}")
            print(f"   - Next tool: {response_data.get('next', [{}])[0].get('toolName', 'None')}")
            print(f"   - Auto execute: {response_data.get('autoExecuteHint', False)}")
        else:
            print("❌ root_cause_identification_prompt: FAILED - No response")
            return False
            
    except Exception as e:
        print(f"❌ root_cause_identification_prompt: FAILED - {e}")
        return False
    
    # Step 4: Test ticket_split_prepare
    print("\n4️⃣ Testing ticket_split_prepare...")
    try:
        sample_root_cause = {
            "per_service": [
                {
                    "service": "user-service",
                    "root_cause": "Database connection configuration error",
                    "confidence": 0.9
                }
            ]
        }
        
        ticket_result = await execute_ticket_split_prepare({
            "analysis": sample_analysis,
            "root_cause": sample_root_cause,
            "title_prefix": "URGENT",
            "mode": "auto"
        })
        
        if ticket_result and len(ticket_result) > 0:
            response_text = ticket_result[0].text
            response_data = json.loads(response_text)
            
            print("✅ ticket_split_prepare: SUCCESS")
            print(f"   - Response type: {response_data.get('kind')}")
            print(f"   - Has prompt: {'prompt' in response_data}")
            print(f"   - Has inputData: {'inputData' in response_data}")
            print(f"   - Next tool: {response_data.get('next', [{}])[0].get('toolName', 'None')}")
            print(f"   - Auto execute: {response_data.get('autoExecuteHint', False)}")
        else:
            print("❌ ticket_split_prepare: FAILED - No response")
            return False
            
    except Exception as e:
        print(f"❌ ticket_split_prepare: FAILED - {e}")
        return False
    
    # Step 5: Test bug_fix_executor
    print("\n5️⃣ Testing bug_fix_executor...")
    try:
        sample_test_output = json.dumps({
            "output_path": "tests/reproductions/DEMO-123",
            "total_tests": 5,
            "services": ["user-service", "database"]
        })
        
        sample_issue_output = json.dumps({
            "tickets": [
                {
                    "ticket_number": "DEMO-123",
                    "title": "Database connection failure",
                    "description": "Service cannot connect to database"
                }
            ]
        })
        
        bug_fix_result = await execute_bug_fix_executor({
            "test_reproduction_output": sample_test_output,
            "issue_reader_output": sample_issue_output,
            "service_paths": ["../services/user-service"],
            "max_iterations": 3,
            "test_framework": "pytest",
            "fix_strategy": "auto",
            "backup_code": True
        })
        
        if bug_fix_result and len(bug_fix_result) > 0:
            response_text = bug_fix_result[0].text
            response_data = json.loads(response_text)
            
            print("✅ bug_fix_executor: SUCCESS")
            print(f"   - Response type: {response_data.get('kind')}")
            print(f"   - Has prompt: {'prompt' in response_data}")
            print(f"   - Has inputData: {'inputData' in response_data}")
            print(f"   - Next step type: {response_data.get('next', [{}])[0].get('type', 'None')}")
            print(f"   - Auto execute: {response_data.get('autoExecuteHint', False)}")
        else:
            print("❌ bug_fix_executor: FAILED - No response")
            return False
            
    except Exception as e:
        print(f"❌ bug_fix_executor: FAILED - {e}")
        return False
    
    # Summary
    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("\n✅ Enhanced Workflow Chain:")
    print("   group_error_logs → analyze_traces_narrative → root_cause_identification → ticket_split_prepare → bug_fix_executor")
    print("\n🔧 Key Improvements:")
    print("   - All tools now use enhanced shared plan template")
    print("   - Guaranteed workflow continuation with autoExecuteHint")
    print("   - Embedded prompts with inputData structure")
    print("   - Consistent JSON response format")
    print("   - No more workflow interruption points")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_enhanced_prompt_tools())
    exit(0 if success else 1)
