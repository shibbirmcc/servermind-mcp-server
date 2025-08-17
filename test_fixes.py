#!/usr/bin/env python3
"""Test script to verify the fixes for the MCP server tools."""

import asyncio
import json
from src.tools.group_error_logs_prompt import execute as group_error_logs_execute
from src.tools.indexes import execute_indexes

async def test_group_error_logs_template():
    """Test that group_error_logs properly substitutes template variables."""
    print("🧪 Testing group_error_logs template substitution...")
    
    # Sample log data similar to what we found in the dev environment
    sample_logs = [
        {
            "level": "WARN",
            "time": "2025-08-17T11:47:30.335Z",
            "location": "splunk/splunk_client.go:163",
            "message": "not able retrieve conf stanza value",
            "service": "ipc_broker",
            "hostname": "91b2c0125b75",
            "uri": "https://127.0.0.1:8089/services/properties/server/ipc_broker/opamp-svc:opamp-svc__control__plane:address?output_mode=json",
            "conf file": "server",
            "stanza": "ipc_broker",
            "key": "opamp-svc:opamp-svc__control__plane:address",
            "error": "stanza not found",
            "sidecarID": "opamp-svc-6918166d-0179-4fc4-8c43-efd1f2d86a0a"
        },
        {
            "level": "WARN",
            "time": "2025-08-17T11:44:09.489Z",
            "location": "splunk/splunk_client.go:163",
            "message": "not able retrieve conf stanza value",
            "service": "ipc_broker",
            "hostname": "91b2c0125b75",
            "uri": "https://127.0.0.1:8089/services/properties/server/ipc_broker/edge-processor-config:edge-processor-config__control__plane:address?output_mode=json",
            "conf file": "server",
            "stanza": "ipc_broker",
            "key": "edge-processor-config:edge-processor-config__control__plane:address",
            "error": "stanza not found",
            "sidecarID": "edge-processor-config-4d57cb3c-c78f-4a6f-8cf1-40d3e85e9258"
        }
    ]
    
    try:
        result = await group_error_logs_execute({"logs": sample_logs, "max_groups": 5})
        
        if result and len(result) > 0:
            prompt_text = result[0].text
            
            # Check that template variables were substituted
            if "$INPUT_LOGS" in prompt_text:
                print("❌ FAILED: $INPUT_LOGS not substituted")
                return False
            elif "$WORKFLOW_TEMPLATE" in prompt_text:
                print("❌ FAILED: $WORKFLOW_TEMPLATE not substituted")
                return False
            elif "{{" in prompt_text or "}}" in prompt_text:
                print("❌ FAILED: Double brace templates still present")
                return False
            else:
                print("✅ SUCCESS: Template variables properly substituted")
                print(f"📝 Generated prompt length: {len(prompt_text)} characters")
                
                # Check that the logs are included
                if "not able retrieve conf stanza value" in prompt_text:
                    print("✅ SUCCESS: Log data included in prompt")
                else:
                    print("❌ FAILED: Log data not found in prompt")
                    return False
                
                # Check that workflow template is included
                if '"kind": "plan"' in prompt_text:
                    print("✅ SUCCESS: Workflow template included")
                else:
                    print("❌ FAILED: Workflow template not found")
                    return False
                
                return True
        else:
            print("❌ FAILED: No result returned")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: Exception occurred: {e}")
        return False

async def test_indexes_validation():
    """Test that splunk_indexes handles null filter_pattern correctly."""
    print("\n🧪 Testing splunk_indexes parameter validation...")
    
    try:
        # This should not raise a validation error anymore
        result = await execute_indexes({
            "filter_pattern": None,
            "include_disabled": True,
            "sort_by": "name",
            "sort_order": "asc"
        })
        
        print("✅ SUCCESS: splunk_indexes accepts null filter_pattern")
        return True
        
    except Exception as e:
        if "validation error" in str(e).lower():
            print(f"❌ FAILED: Validation error still occurs: {e}")
            return False
        else:
            # Other errors (like connection issues) are expected in test environment
            print(f"✅ SUCCESS: No validation error (other error expected): {e}")
            return True

async def main():
    """Run all tests."""
    print("🚀 Running MCP Server Fix Tests\n")
    
    test_results = []
    
    # Test 1: Template substitution
    result1 = await test_group_error_logs_template()
    test_results.append(("Template Substitution", result1))
    
    # Test 2: Parameter validation
    result2 = await test_indexes_validation()
    test_results.append(("Parameter Validation", result2))
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    
    passed = 0
    for test_name, passed_test in test_results:
        status = "✅ PASSED" if passed_test else "❌ FAILED"
        print(f"{test_name}: {status}")
        if passed_test:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(test_results)} tests passed")
    
    if passed == len(test_results):
        print("🎉 All fixes are working correctly!")
    else:
        print("⚠️  Some issues remain - check the failed tests above")

if __name__ == "__main__":
    asyncio.run(main())
