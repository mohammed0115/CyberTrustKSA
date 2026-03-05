# Unit Tests Documentation

## Overview

This document provides comprehensive guidance for running, writing, and maintaining unit tests in the CyberTrust KSA project. The test suite covers all 5 AI-powered features implemented in Steps 1-4.

## Test Structure

```
cybertrust/
├── apps/
│   ├── ai_engine/
│   │   ├── test_services.py          # Chatbot, Arabic Analysis, Remediation tests
│   │   └── test_views.py             # API endpoint and view tests
│   ├── organizations/
│   │   └── test_services.py          # Questionnaire service tests
│   └── controls/
│       └── test_services.py          # Cloud guides service tests
└── config/
    └── settings/
        └── test.py                    # Test-specific Django settings
```

## Running Tests

### Prerequisites

```bash
pip install pytest pytest-django pytest-cov
```

### Run All Tests

```bash
# Using Django's test runner
python manage.py test

# Using pytest
pytest

# Using custom test runner
python tests_runner.py
```

### Run Specific Test Suite

```bash
# AI Engine services
pytest cybertrust/apps/ai_engine/test_services.py

# Specific test class
pytest cybertrust/apps/ai_engine/test_services.py::ChatbotServiceTests

# Specific test method
pytest cybertrust/apps/ai_engine/test_services.py::ChatbotServiceTests::test_get_ciso_system_prompt_english
```

### Run with Coverage Report

```bash
# Generate coverage report
pytest --cov=cybertrust --cov-report=html

# View coverage (opens in browser)
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Run Tests with Output

```bash
# Verbose output
pytest -v

# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Show slowest 10 tests
pytest --durations=10
```

### Run Specific Test Categories

```bash
# All model tests
pytest -k "Model"

# All service tests
pytest -k "Services"

# All API tests
pytest -k "API"

# All authentication tests
pytest -k "Authentication"
```

## Test Coverage

### AI Engine Tests (`test_services.py` - 450+ lines)

#### Chatbot Service Tests
- ✅ System prompt generation (English/Arabic)
- ✅ Send message to Virtual CISO with OpenAI API
- ✅ Conversation context handling
- ✅ Retrieve conversation history
- ✅ Clear conversation history
- ✅ Error handling without API key
- ✅ Message persistence

**Methods Tested:**
- `get_ciso_system_prompt(language="en")`
- `chat_with_ciso(user_message, organization, user, language, conversation_context)`
- `get_conversation_history(org, user)`
- `clear_conversation_history(org, user)`

#### Arabic Analysis Service Tests
- ✅ Arabic evidence analysis with OpenAI
- ✅ Bilingual analysis result creation
- ✅ Document extraction and analysis
- ✅ Arabic compliance report generation

**Methods Tested:**
- `analyze_evidence_arabic(evidence_text, control, language)`
- `create_bilingual_analysis_result(org, evidence, control, analysis_data, model_name)`
- `extract_and_analyze_arabic_document(file_path, control)`
- `get_arabic_compliance_report(organization)`

#### Remediation Service Tests
- ✅ Remediation template generation
- ✅ Default remediation fallback
- ✅ RemediationTracker creation
- ✅ Progress tracking
- ✅ Completion tracking

**Methods Tested:**
- `generate_remediation_template(control, missing_points, org, language)`
- `get_default_remediation(control, missing_points, language)`
- `RemediationTracker.create(control, org, assigned_to_role)`
- `RemediationTracker.track_progress(percent_complete)`

#### Model Tests
- ✅ ChatMessage creation (user/assistant)
- ✅ Message ordering by timestamp
- ✅ Arabic language support
- ✅ AIAnalysisResult creation
- ✅ Bilingual summaries storage

### Organizations Tests (`test_services.py` - 550+ lines)

#### Question Generation Tests
- ✅ OpenAI-based question generation
- ✅ API key missing fallback
- ✅ API error fallback
- ✅ Question categorization

**Methods Tested:**
- `generate_assessment_questions(num_questions=5)`
- `create_assessment_for_organization(organization)`

#### Assessment Tests
- ✅ Assessment creation
- ✅ Assessment uniqueness per org
- ✅ Low-risk assessment (GENERAL vendor)
- ✅ High-risk assessment (HIGH_RISK vendor)
- ✅ Organization vendor_type update
- ✅ Completion timestamp

**Methods Tested:**
- `submit_assessment_response(assessment, responses)`
- `calculate_risk_score(responses)`

#### Risk Scoring Tests
- ✅ Empty responses scoring
- ✅ All yes/high responses
- ✅ All no/low responses
- ✅ Numeric rating responses
- ✅ Boundary score at 60 (HIGH_RISK threshold)

#### Model Tests
- ✅ VendorAssessment creation
- ✅ Status choices validation
- ✅ Risk score range validation
- ✅ AssessmentQuestion ordering
- ✅ Question categories validation

### Controls Tests (`test_services.py` - 500+ lines)

#### Cloud Guide Generation Tests
- ✅ AWS guide generation
- ✅ Azure guide generation
- ✅ Alibaba Cloud guide generation
- ✅ Arabic language support
- ✅ API error fallback
- ✅ Code snippet formatting

**Methods Tested:**
- `generate_cloud_guide(provider, requirement, control, language)`
- `get_all_cloud_guides(control)`
- `generate_integration_checklist(provider, control)`

#### Multi-Cloud Support Tests
- ✅ All major providers supported
- ✅ Guide structure consistency
- ✅ Requirement types support
- ✅ Code snippet formatting
- ✅ Step ordering

#### Error Handling Tests
- ✅ Timeout fallback
- ✅ Invalid JSON response fallback
- ✅ Missing control handling

### API Views Tests (`test_views.py` - 450+ lines)

#### Chatbot API Tests
- ✅ Send message to Virtual CISO
- ✅ Conversation history retrieval
- ✅ Arabic chatbot responses
- ✅ Message with context

#### Assessment API Tests
- ✅ Start assessment
- ✅ Submit assessment responses
- ✅ Retrieve assessment results

#### Cloud Guide API Tests
- ✅ Get single cloud guide
- ✅ List all guides
- ✅ Generate integration checklist

#### Remediation API Tests
- ✅ Generate remediation template
- ✅ Get remediation templates
- ✅ Track remediation progress

#### Authentication Tests
- ✅ Unauthenticated access prevention
- ✅ Organization isolation
- ✅ Role-based access

#### Error Response Tests
- ✅ Missing required fields
- ✅ OpenAI API failures
- ✅ Invalid control IDs

#### Bilingual Support Tests
- ✅ English responses
- ✅ Arabic responses
- ✅ Bilingual question support

## Test Statistics

| Component | Tests | Methods | Coverage |
|-----------|-------|---------|----------|
| AI Engine | 18 classes, 67+ methods | chatbot, analysis, remediation | High |
| Organizations | 10 classes, 45+ methods | questionnaire, risk scoring | High |
| Controls | 13 classes, 52+ methods | cloud guides, checklists | High |
| Views/API | 12 classes, 40+ methods | all endpoints | Medium |
| **Total** | **53 test classes** | **200+ test methods** | **Comprehensive** |

## Writing New Tests

### Test Class Structure

```python
from django.test import TestCase
from rest_framework.test import APITestCase

class MyServiceTests(TestCase):
    """Test MyService functionality."""
    
    def setUp(self):
        """Setup test data."""
        self.org = Organization.objects.create(
            name="Test Org",
            slug="test-org"
        )
    
    def tearDown(self):
        """Cleanup after tests."""
        pass
    
    def test_my_feature_success(self):
        """Test successful feature operation."""
        # Arrange
        test_data = {"key": "value"}
        
        # Act
        result = my_service_function(test_data)
        
        # Assert
        self.assertEqual(result.status, "success")
```

### Mocking OpenAI API Calls

```python
from unittest.mock import patch, MagicMock

@patch("cybertrust.apps.ai_engine.services.chatbot.OpenAI")
def test_chat_with_mocked_openai(self, mock_openai):
    """Test with mocked OpenAI API."""
    # Setup mock
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    
    # Configure response
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Mocked response"
    mock_client.chat.completions.create.return_value = mock_response
    
    # Call function
    result = chat_with_ciso("Test message")
    
    # Assert
    self.assertEqual(result["response"], "Mocked response")
```

### Testing Async Functions

```python
import asyncio

def test_async_chatbot(self):
    """Test async chatbot function."""
    result = asyncio.run(
        chat_with_ciso("Test message")
    )
    
    self.assertIn("response", result)
```

### Database Transaction Tests

```python
from django.db import transaction

def test_assessment_atomic_transaction(self):
    """Test assessment submission is atomic."""
    with transaction.atomic():
        assessment = create_assessment_for_organization(self.org)
        submit_assessment_response(assessment, {1: "yes"})
    
    # Verify changes persisted
    self.assertEqual(
        VendorAssessment.objects.count(), 1
    )
```

## Common Assertions

```python
# Value assertions
self.assertEqual(value, expected)
self.assertNotEqual(value, not_expected)
self.assertTrue(condition)
self.assertFalse(condition)

# Collection assertions
self.assertIn(item, collection)
self.assertNotIn(item, collection)
self.assertEqual(len(collection), 3)
self.assertGreater(value, 5)
self.assertLess(value, 10)

# Exception assertions
with self.assertRaises(Exception):
    problematic_function()

# Database assertions
self.assertEqual(Model.objects.count(), 5)
self.assertTrue(Model.objects.filter(field=value).exists())

# Setup assertions
self.assertIsNotNone(self.org)
self.assertEqual(ChatMessage.objects.filter(org=self.org).count(), 0)
```

## Debugging Tests

### Run with Debugging

```bash
# Print debugging output
pytest -s -v

# Drop into pdb on failure
pytest --pdb

# Run specific test with pdb
pytest --pdb -k test_name

# Show local variables on failure
pytest -l
```

### Add Debugging Statements

```python
def test_my_function(self):
    result = my_function()
    print(f"Result: {result}")  # Shows when pytest -s is used
    self.assertEqual(result, expected)
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - run: pip install -r requirements.txt
      - run: pytest --cov
      - uses: codecov/codecov-action@v2
```

### Pre-commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash
pytest --co -q > /dev/null
if [ $? -ne 0 ]; then
  echo "Tests not found. Commit aborted."
  exit 1
fi
```

## Best Practices

### ✅ DO

- ✅ Write tests alongside code
- ✅ Mock external API calls (OpenAI)
- ✅ Test both success and failure paths
- ✅ Use descriptive test names
- ✅ Keep tests isolated and independent
- ✅ Use setUp/tearDown for common operations
- ✅ Test edge cases and boundaries
- ✅ Keep tests small and focused
- ✅ Test bilingual (AR/EN) support
- ✅ Document complex test logic

### ❌ DON'T

- ❌ Test implementation details
- ❌ Create dependencies between tests
- ❌ Hardcode data (use factories)
- ❌ Make actual API calls in tests
- ❌ Use time.sleep() for synchronization
- ❌ Skip tests with @skip decorator
- ❌ Write overly complex test logic
- ❌ Test multiple features in one method
- ❌ Modify global settings in tests
- ❌ Leave test data in production database

## Troubleshooting

### Issue: Tests fail with "OPENAI_API_KEY not configured"

**Solution:** Set the environment variable for tests:
```bash
export OPENAI_API_KEY="sk-test-key"
python manage.py test
```

### Issue: Database migration errors

**Solution:** Use test settings that disable migrations:
```bash
export DJANGO_SETTINGS_MODULE=cybertrust.config.settings.test
pytest
```

### Issue: Async function tests fail

**Solution:** Use `asyncio.run()`:
```python
import asyncio

result = asyncio.run(async_function())
```

### Issue: TimeoutError in OpenAI mocks

**Solution:** Increase mock timeout or use shorter timeouts in tests:
```python
@patch("cybertrust.apps.ai_engine.services.chatbot.OpenAI", timeout=1)
def test_timeout_handling(self, mock_openai):
    mock_openai.side_effect = TimeoutError()
```

## Performance Optimization

### Test Execution Time

Current execution times (approximate):
- AI Engine tests: 2-3 seconds
- Organizations tests: 1-2 seconds
- Controls tests: 2-3 seconds
- Views/API tests: 3-4 seconds
- **Total: ~10-15 seconds**

### Optimization Tips

```bash
# Run in parallel (requires pytest-xdist)
pip install pytest-xdist
pytest -n auto

# Run only fast tests
pytest -m "not slow"

# Show slowest tests
pytest --durations=10
```

## Continuous Monitoring

### Coverage Goals

```bash
# Minimum coverage thresholds
pytest --cov=cybertrust --cov-fail-under=80

# Coverage badges
pip install coverage-badge
coverage report > coverage.txt
```

### Test Health Dashboard

```bash
# Generate test report
pytest --html=report.html --self-contained-html

# View report
open report.html  # macOS
```

## Integration with Development Workflow

### Pre-commit Testing

Add to `.git/hooks/pre-commit`:
```bash
#!/bin/bash
pytest --co -q || exit 1
```

### Pre-push Testing

Add to `.git/hooks/pre-push`:
```bash
#!/bin/bash
pytest || exit 1
```

## Final Notes

- All tests are isolated and can run independently
- OpenAI API is mocked to avoid external dependencies
- Test database is in-memory for speed
- Tests are executable without additional setup
- Coverage report generation requires pytest-cov

For more information, see individual test files and Django documentation.
