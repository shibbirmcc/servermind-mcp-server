#!/usr/bin/env python3
"""
Demo script showing the complete workflow from issue reader to test reproduction.
This demonstrates how to use the issue_reader and test_reproduction tools together.
"""

import asyncio
import json
from src.tools.issue_reader import get_issue_reader_tool
from src.tools.test_reproduction import get_test_reproduction_tool

async def demo_workflow():
    """Demonstrate the complete workflow."""
    
    print("🚀 Starting Issue Reader to Test Reproduction Workflow Demo")
    print("=" * 60)
    
    # Sample issue reader output (simulating what would come from actual issues)
    sample_issue_output = {
        "tickets": [
            {
                "ticket_number": "DEMO-123",
                "platform": "github",
                "title": "Database connection timeout in user-service",
                "description": "Users are experiencing timeouts when trying to authenticate. The user-service is failing to connect to the database after 30 seconds. Error logs show 'Connection timeout after 30000ms' in the authentication module.",
                "status": "open",
                "labels": ["bug", "high-priority", "database"],
                "assignees": ["dev-team"],
                "services": ["user-service", "auth-service"],
                "bug_analysis": "Database connection pool exhaustion causing timeouts",
                "root_cause": "Connection pool size too small for current load",
                "error_patterns": ["Connection timeout after 30000ms", "Pool exhausted"],
                "stack_traces": []
            },
            {
                "ticket_number": "DEMO-456", 
                "platform": "jira",
                "title": "Payment processing fails with null pointer exception",
                "description": "Payment service throws NullPointerException when processing credit card payments. This happens intermittently, about 5% of the time. Stack trace shows the error occurs in PaymentValidator.validateCard() method.",
                "status": "in-progress",
                "labels": ["bug", "payment", "critical"],
                "assignees": ["payment-team"],
                "services": ["payment-service"],
                "bug_analysis": "Null pointer exception in payment validation",
                "root_cause": "Missing null check for card expiry date",
                "error_patterns": ["NullPointerException", "PaymentValidator.validateCard"],
                "stack_traces": ["at PaymentValidator.validateCard(PaymentValidator.java:45)"]
            }
        ]
    }
    
    print("📋 Sample Issue Data:")
    print(f"   - {len(sample_issue_output['tickets'])} tickets")
    for ticket in sample_issue_output['tickets']:
        print(f"   - {ticket['ticket_number']}: {ticket['title']}")
        print(f"     Services: {', '.join(ticket['services'])}")
    print()
    
    # Step 2: Generate tests using test_reproduction tool
    print("🧪 Generating Test Reproduction...")
    test_tool = get_test_reproduction_tool()
    
    test_arguments = {
        "issue_reader_output": json.dumps(sample_issue_output),
        "test_types": ["reproduction", "unit", "integration", "regression"],
        "service_discovery_mode": "local",
        "local_search_paths": ["../", "../../"],
        "test_framework": "pytest",
        "output_directory": "demo_tests"
    }
    
    try:
        test_results = await test_tool.execute(test_arguments)
        
        if test_results:
            print("✅ Test Reproduction Results:")
            print(test_results[0].text)
        else:
            print("❌ No results from test reproduction")
            
    except Exception as e:
        print(f"❌ Error in test reproduction: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 Workflow Demo Complete!")
    print("\nNext Steps:")
    print("1. Check the 'demo_tests' directory for generated test files")
    print("2. Customize the generated tests with actual service implementations")
    print("3. Run the tests using the generated run_tests.sh script")
    print("4. Use the tests to reproduce bugs and verify fixes")

if __name__ == "__main__":
    asyncio.run(demo_workflow())
