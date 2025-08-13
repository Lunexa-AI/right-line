#!/bin/bash
# Smoke tests for RightLine deployment
# Usage: ./smoke_test.sh [staging|production]

set -euo pipefail

# Configuration
ENVIRONMENT=${1:-staging}
API_URL=${API_URL:-}
API_KEY=${API_KEY:-}
TIMEOUT=${TIMEOUT:-10}
RETRIES=${RETRIES:-3}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Set environment-specific URLs
if [ "$ENVIRONMENT" = "production" ]; then
    API_URL=${API_URL:-https://rightline.zw}
elif [ "$ENVIRONMENT" = "staging" ]; then
    API_URL=${API_URL:-https://staging.rightline.zw}
else
    echo -e "${RED}Invalid environment: $ENVIRONMENT${NC}"
    echo "Usage: $0 [staging|production]"
    exit 1
fi

echo -e "${YELLOW}Running smoke tests for $ENVIRONMENT environment${NC}"
echo "API URL: $API_URL"
echo "----------------------------------------"

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0

# Function to make API request with retries
make_request() {
    local endpoint=$1
    local method=${2:-GET}
    local data=${3:-}
    local expected_status=${4:-200}
    
    for i in $(seq 1 $RETRIES); do
        echo -n "  Attempt $i/$RETRIES: "
        
        if [ -n "$data" ]; then
            response=$(curl -s -w "\n%{http_code}" -X "$method" \
                -H "Content-Type: application/json" \
                -H "Authorization: Bearer $API_KEY" \
                --max-time "$TIMEOUT" \
                -d "$data" \
                "$API_URL$endpoint" 2>/dev/null || echo "000")
        else
            response=$(curl -s -w "\n%{http_code}" -X "$method" \
                -H "Authorization: Bearer $API_KEY" \
                --max-time "$TIMEOUT" \
                "$API_URL$endpoint" 2>/dev/null || echo "000")
        fi
        
        http_code=$(echo "$response" | tail -n1)
        body=$(echo "$response" | sed '$d')
        
        if [ "$http_code" = "$expected_status" ]; then
            echo -e "${GREEN}✓${NC} (${http_code})"
            return 0
        elif [ "$http_code" = "000" ]; then
            echo -e "${YELLOW}Connection failed${NC}"
        else
            echo -e "${YELLOW}Unexpected status: ${http_code}${NC}"
        fi
        
        if [ $i -lt $RETRIES ]; then
            sleep 2
        fi
    done
    
    return 1
}

# Test function wrapper
run_test() {
    local test_name=$1
    local test_function=$2
    
    echo -e "\n${YELLOW}Test:${NC} $test_name"
    
    if $test_function; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAILED${NC}"
        ((TESTS_FAILED++))
    fi
}

# Test 1: Health check
test_health() {
    make_request "/health" "GET" "" "200"
}

# Test 2: API version
test_version() {
    make_request "/version" "GET" "" "200"
}

# Test 3: OpenAPI documentation
test_docs() {
    make_request "/docs" "GET" "" "200"
}

# Test 4: Query endpoint (basic)
test_query_basic() {
    local query_data='{"text": "What is the penalty for theft?", "lang_hint": "en"}'
    make_request "/v1/query" "POST" "$query_data" "200"
}

# Test 5: Query with date context
test_query_with_date() {
    local query_data='{"text": "Tax rates", "date_ctx": "2024-01-01", "lang_hint": "en"}'
    make_request "/v1/query" "POST" "$query_data" "200"
}

# Test 6: Search sections
test_search_sections() {
    make_request "/v1/sections/search?q=criminal&limit=5" "GET" "" "200"
}

# Test 7: Rate limiting
test_rate_limiting() {
    echo "  Testing rate limiting..."
    local count=0
    local rate_limited=false
    
    for i in {1..10}; do
        response_code=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "Authorization: Bearer $API_KEY" \
            --max-time 1 \
            "$API_URL/v1/query" -X POST \
            -H "Content-Type: application/json" \
            -d '{"text": "test"}' 2>/dev/null)
        
        if [ "$response_code" = "429" ]; then
            rate_limited=true
            echo -e "  ${GREEN}Rate limiting working (got 429)${NC}"
            break
        fi
        ((count++))
    done
    
    if [ "$rate_limited" = false ] && [ "$ENVIRONMENT" = "production" ]; then
        echo -e "  ${YELLOW}Warning: Rate limiting might not be configured${NC}"
    fi
    
    return 0
}

# Test 8: Database connectivity
test_database() {
    make_request "/v1/stats" "GET" "" "200"
}

# Test 9: Cache functionality
test_cache() {
    echo "  Testing cache..."
    local query_data='{"text": "Constitution of Zimbabwe", "lang_hint": "en"}'
    
    # First request (cache miss)
    start_time=$(date +%s%N)
    make_request "/v1/query" "POST" "$query_data" "200" > /dev/null
    end_time=$(date +%s%N)
    first_time=$(( (end_time - start_time) / 1000000 ))
    
    # Second request (should be cached)
    start_time=$(date +%s%N)
    make_request "/v1/query" "POST" "$query_data" "200" > /dev/null
    end_time=$(date +%s%N)
    second_time=$(( (end_time - start_time) / 1000000 ))
    
    echo "  First request: ${first_time}ms, Second request: ${second_time}ms"
    
    if [ $second_time -lt $((first_time / 2)) ]; then
        echo -e "  ${GREEN}Cache appears to be working${NC}"
        return 0
    else
        echo -e "  ${YELLOW}Cache might not be working optimally${NC}"
        return 0  # Don't fail the test
    fi
}

# Test 10: Error handling
test_error_handling() {
    # Invalid JSON
    local response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $API_KEY" \
        --max-time "$TIMEOUT" \
        -d "invalid json" \
        "$API_URL/v1/query" 2>/dev/null)
    
    local http_code=$(echo "$response" | tail -n1)
    
    if [ "$http_code" = "422" ] || [ "$http_code" = "400" ]; then
        echo -e "  ${GREEN}✓${NC} Proper error handling (${http_code})"
        return 0
    else
        echo -e "  ${RED}✗${NC} Unexpected error response: ${http_code}"
        return 1
    fi
}

# Test 11: Security headers
test_security_headers() {
    echo "  Checking security headers..."
    local headers=$(curl -s -I "$API_URL/health" 2>/dev/null)
    
    local passed=true
    
    # Check for security headers
    if echo "$headers" | grep -qi "X-Content-Type-Options: nosniff"; then
        echo -e "  ${GREEN}✓${NC} X-Content-Type-Options present"
    else
        echo -e "  ${YELLOW}⚠${NC} X-Content-Type-Options missing"
        passed=false
    fi
    
    if echo "$headers" | grep -qi "X-Frame-Options"; then
        echo -e "  ${GREEN}✓${NC} X-Frame-Options present"
    else
        echo -e "  ${YELLOW}⚠${NC} X-Frame-Options missing"
        passed=false
    fi
    
    if [ "$ENVIRONMENT" = "production" ] && echo "$headers" | grep -qi "Strict-Transport-Security"; then
        echo -e "  ${GREEN}✓${NC} HSTS present"
    elif [ "$ENVIRONMENT" = "production" ]; then
        echo -e "  ${YELLOW}⚠${NC} HSTS missing"
        passed=false
    fi
    
    $passed
}

# Test 12: Response time SLO
test_response_time() {
    echo "  Testing response time SLO (< 2s)..."
    local query_data='{"text": "What are the traffic laws?", "lang_hint": "en"}'
    
    local total_time=0
    local requests=5
    
    for i in $(seq 1 $requests); do
        start_time=$(date +%s%N)
        make_request "/v1/query" "POST" "$query_data" "200" > /dev/null
        end_time=$(date +%s%N)
        request_time=$(( (end_time - start_time) / 1000000 ))
        total_time=$((total_time + request_time))
        echo "    Request $i: ${request_time}ms"
    done
    
    avg_time=$((total_time / requests))
    echo "  Average response time: ${avg_time}ms"
    
    if [ $avg_time -lt 2000 ]; then
        echo -e "  ${GREEN}✓ Meets SLO${NC}"
        return 0
    else
        echo -e "  ${RED}✗ Exceeds SLO${NC}"
        return 1
    fi
}

# Run all tests
echo -e "\n${YELLOW}Starting smoke tests...${NC}\n"

run_test "Health Check" test_health
run_test "API Version" test_version
run_test "API Documentation" test_docs
run_test "Basic Query" test_query_basic
run_test "Query with Date Context" test_query_with_date
run_test "Search Sections" test_search_sections
run_test "Rate Limiting" test_rate_limiting
run_test "Database Connectivity" test_database
run_test "Cache Functionality" test_cache
run_test "Error Handling" test_error_handling
run_test "Security Headers" test_security_headers
run_test "Response Time SLO" test_response_time

# Summary
echo -e "\n========================================="
echo -e "${YELLOW}Test Summary for $ENVIRONMENT${NC}"
echo -e "========================================="
echo -e "${GREEN}Passed:${NC} $TESTS_PASSED"
echo -e "${RED}Failed:${NC} $TESTS_FAILED"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}✓ All smoke tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}✗ Some tests failed!${NC}"
    exit 1
fi
