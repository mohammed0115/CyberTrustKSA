# Quick Test Reference

## Run All Tests
```bash
pytest
# or
python manage.py test
```

## Run Specific Test File
```bash
pytest cybertrust/apps/ai_engine/test_services.py
```

## Run with Coverage
```bash
pytest --cov=cybertrust --cov-report=html
open htmlcov/index.html
```

## Run Specific Test Class
```bash
pytest cybertrust/apps/ai_engine/test_services.py::ChatbotServiceTests
```

## Run Single Test
```bash
pytest cybertrust/apps/ai_engine/test_services.py::ChatbotServiceTests::test_get_ciso_system_prompt_english
```

## Run with Verbose Output
```bash
pytest -v -s
```

## Stop on First Failure
```bash
pytest -x
```

## Run Parallel Tests (faster)
```bash
pytest -n auto  # requires pytest-xdist
```

## Filter by Test Name Pattern
```bash
pytest -k "chatbot"    # Run all tests with 'chatbot' in name
pytest -k "not slow"   # Skip slow tests
```

## Show Print Statements
```bash
pytest -s
```

## Debugger on Failure
```bash
pytest --pdb
```

## Test Summary

### Test Files Created
- ✅ `cybertrust/apps/ai_engine/test_services.py` (450+ lines, 18 test classes)
- ✅ `cybertrust/apps/ai_engine/test_views.py` (450+ lines, 12 test classes)
- ✅ `cybertrust/apps/organizations/test_services.py` (550+ lines, 10 test classes)
- ✅ `cybertrust/apps/controls/test_services.py` (500+ lines, 13 test classes)

### Coverage
- ✅ 53 test classes
- ✅ 200+ test methods
- ✅ ALL service functions tested
- ✅ ALL models tested
- ✅ API endpoints tested
- ✅ Error handling tested
- ✅ Bilingual support tested
- ✅ Authentication tested

### Key Testing Areas
1. **Chatbot Service** - Message sending, context, history, Arabic support
2. **Arabic Analysis** - Document analysis, bilingual results, compliance reports
3. **Remediation** - Template generation, progress tracking, completion
4. **Questionnaire** - Question generation, risk scoring, vendor categorization
5. **Cloud Guides** - Multi-provider support, code snippets, checklists
6. **Models** - All CRUD operations, validation, relationships
7. **API Endpoints** - Authentication, authorization, data validation
8. **Error Handling** - Fallbacks, API failures, input validation
9. **Bilingual Support** - Arabic/English responses, question sets

## Test Settings
- Uses in-memory SQLite database (`:memory:`)
- Disables migrations for speed
- Mocks OpenAI API calls
- Fast password hashing for tests
- Reduced logging output

## Next Steps
After tests pass:
1. Run coverage report: `pytest --cov`
2. Deploy to staging environment
3. Implement monitoring & OpenAI cost tracking (Step 6)
