#!/usr/bin/env python3
"""
Simple test script to verify Splunk connection and authentication
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, 'src')

# Load environment variables
load_dotenv()

from src.config import get_config
from src.splunk.client import SplunkClient


class SplunkConnectionTester:
    """Simple class to test Splunk connection and basic search functionality"""
    
    def __init__(self):
        """Initialize with configuration from .env file"""
        self.config = get_config()
        self.client = None
        
    def print_config(self):
        """Print current configuration (without password)"""
        print("🔧 Splunk Configuration:")
        print(f"   Host: {self.config.splunk.host}")
        print(f"   Port: {self.config.splunk.port}")
        print(f"   Username: {self.config.splunk.username}")
        print(f"   Password: {'*' * len(self.config.splunk.password)}")
        print(f"   Scheme: {self.config.splunk.scheme}")
        print(f"   SSL Verify: {self.config.splunk.verify_ssl}")
        print(f"   Timeout: {self.config.splunk.timeout}")
        print()
    
    def test_connection(self):
        """Test basic connection to Splunk"""
        print("🔗 Testing Splunk Connection...")
        
        try:
            self.client = SplunkClient(self.config.splunk)
            print("✅ SplunkClient created successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to create SplunkClient: {e}")
            return False
    
    def test_authentication(self):
        """Test authentication by getting server info"""
        print("🔐 Testing Authentication...")
        
        try:
            server_info = self.client.get_server_info()
            print("✅ Authentication successful!")
            print(f"   Splunk Version: {server_info.get('version', 'Unknown')}")
            print(f"   Build: {server_info.get('build', 'Unknown')}")
            print(f"   Server Name: {server_info.get('serverName', 'Unknown')}")
            return True
            
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return False
    
    def test_basic_search(self):
        """Test a very basic search"""
        print("🔍 Testing Basic Search...")
        
        # Simple search that should work on any Splunk instance
        search_query = "| stats count"
        
        try:
            print(f"   Query: {search_query}")
            results = self.client.search(
                query=search_query,
                earliest_time="-1h",
                latest_time="now",
                max_results=10
            )
            
            if results:
                print(f"✅ Search successful! Found {len(results)} result(s)")
                
                # Print first result
                if results:
                    first_result = results[0]
                    print("   Sample result:")
                    for key, value in first_result.items():
                        if not key.startswith('_'):  # Skip internal fields
                            print(f"      {key}: {value}")
                
                return True
            else:
                print("⚠️  Search returned no results (but didn't fail)")
                return True
                
        except Exception as e:
            print(f"❌ Search failed: {e}")
            return False
    
    def test_index_search(self):
        """Test searching a specific index"""
        print("🗂️  Testing Index Search...")
        
        # Search for any events in any index
        search_query = "search * | head 1"
        
        try:
            print(f"   Query: {search_query}")
            results = self.client.search(
                query=search_query,
                earliest_time="-24h",
                latest_time="now",
                max_results=1
            )
            
            if results:
                print(f"✅ Index search successful! Found {len(results)} result(s)")
                
                # Print some fields from first result
                if results:
                    first_result = results[0]
                    print("   Sample event fields:")
                    field_count = 0
                    for key, value in first_result.items():
                        if field_count >= 5:  # Limit output
                            break
                        if not key.startswith('_time'):  # Skip time fields for brevity
                            value_str = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                            print(f"      {key}: {value_str}")
                            field_count += 1
                
                return True
            else:
                print("⚠️  No events found in any index (this might be normal for a new Splunk instance)")
                return True
                
        except Exception as e:
            print(f"❌ Index search failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🧪 Splunk Connection Test Suite")
        print("=" * 50)
        
        self.print_config()
        
        tests = [
            ("Connection Test", self.test_connection),
            ("Authentication Test", self.test_authentication),
            ("Basic Search Test", self.test_basic_search),
            ("Index Search Test", self.test_index_search),
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            try:
                results[test_name] = test_func()
                print()  # Add spacing between tests
            except Exception as e:
                print(f"❌ {test_name} crashed: {e}")
                results[test_name] = False
                print()
        
        # Summary
        print("=" * 50)
        print("📊 Test Results Summary:")
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {status} {test_name}")
        
        print(f"\n🎯 Overall: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Your Splunk connection is working perfectly.")
            print("\n📋 Your MCP server should work fine with these credentials.")
        else:
            print("⚠️  Some tests failed. Please check your Splunk configuration.")
            print("\n🔧 Troubleshooting tips:")
            print("1. Verify Splunk is running on https://127.0.0.1:8089")
            print("2. Check username/password are correct")
            print("3. Ensure SSL verification setting matches your Splunk setup")
            print("4. Try accessing Splunk web UI at https://127.0.0.1:8000")
        
        return passed == total


def main():
    """Main function to run the tests"""
    tester = SplunkConnectionTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
