# Test Suites

## Test Organization

### unit/
Fast, isolated tests for individual functions and classes.
- Target: 70% code coverage
- Run time: < 1 minute

### integration/
Tests for service interactions and database operations.
- Target: 20% code coverage
- Run time: < 5 minutes

### e2e/
End-to-end tests simulating real user scenarios.
- Target: 10% code coverage
- Run time: < 10 minutes

## Running Tests

```bash
# All tests
make test

# Specific suite
make test-unit
make test-integration
make test-e2e

# With coverage
make test-coverage
```

## Golden Dataset

The `golden/` directory contains curated test cases for accuracy evaluation.
