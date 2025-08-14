#!/bin/bash

# Test runner script for ticket DEMO-123
# Generated on 2025-08-14 11:04:20

set -e  # Exit on any error

echo "🧪 Running tests for ticket DEMO-123"
echo "Services: authentication, is, user-service, users"
echo "Test types: reproduction, unit, integration, regression"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to run tests with proper error handling
run_test_suite() {
    local test_path="$1"
    local test_name="$2"
    
    echo -e "${BLUE}Running ${test_name}...${NC}"
    
    if [ -f "$test_path" ]; then
        if python -m pytest "$test_path" -v --tb=short; then
            echo -e "${GREEN}✅ ${test_name} passed${NC}"
            return 0
        else
            echo -e "${RED}❌ ${test_name} failed${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️  ${test_name} not found: ${test_path}${NC}"
        return 0
    fi
}

# Initialize counters
total_tests=0
passed_tests=0
failed_tests=0

echo "📋 Test Execution Plan:"
echo "======================"

# Run tests for each service

echo "🔧 Testing service: authentication"
echo "Language: javascript"
echo "Framework: unknown"
echo ""

# Run each test type for this service
if run_test_suite "authentication/test_reproduction.py" "authentication reproduction tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
if run_test_suite "authentication/test_unit.py" "authentication unit tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
if run_test_suite "authentication/test_integration.py" "authentication integration tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
if run_test_suite "authentication/test_regression.py" "authentication regression tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
echo ""
echo "🔧 Testing service: is"
echo "Language: javascript"
echo "Framework: unknown"
echo ""

# Run each test type for this service
if run_test_suite "is/test_reproduction.py" "is reproduction tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
if run_test_suite "is/test_unit.py" "is unit tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
if run_test_suite "is/test_integration.py" "is integration tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
if run_test_suite "is/test_regression.py" "is regression tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
echo ""
echo "🔧 Testing service: user-service"
echo "Language: javascript"
echo "Framework: unknown"
echo ""

# Run each test type for this service
if run_test_suite "user-service/test_reproduction.py" "user-service reproduction tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
if run_test_suite "user-service/test_unit.py" "user-service unit tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
if run_test_suite "user-service/test_integration.py" "user-service integration tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
if run_test_suite "user-service/test_regression.py" "user-service regression tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
echo ""
echo "🔧 Testing service: users"
echo "Language: javascript"
echo "Framework: unknown"
echo ""

# Run each test type for this service
if run_test_suite "users/test_reproduction.py" "users reproduction tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
if run_test_suite "users/test_unit.py" "users unit tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
if run_test_suite "users/test_integration.py" "users integration tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
if run_test_suite "users/test_regression.py" "users regression tests"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))
echo ""

# Summary
echo "📊 Test Results Summary:"
echo "======================="
echo -e "Total test suites: $total_tests"
echo -e "${GREEN}Passed: $passed_tests${NC}"
echo -e "${RED}Failed: $failed_tests${NC}"

if [ $failed_tests -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}💥 Some tests failed. Please check the output above.${NC}"
    exit 1
fi
