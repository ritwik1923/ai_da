# Testing Guide for AI Data Analyst

## 📋 Overview

This project includes a comprehensive test suite to ensure reliability and correctness of the AI Data Analyst application.

## 🚀 Quick Start

### Run All Tests

```bash
# From backend directory
python run_tests.py

# Or use convenience scripts:
# Linux/Mac
./test.sh

# Windows
test.bat
```

### Run Specific Test Categories

```bash
# Unit tests only
python run_tests.py --category unit

# API endpoint tests
python run_tests.py --category api

# LLM provider tests
python run_tests.py --category llm

# Agent tests
python run_tests.py --category agent

# Quick tests (no LLM API calls)
python run_tests.py --category quick
```

### Run with Coverage

```bash
python run_tests.py --coverage
# Opens htmlcov/index.html for detailed coverage report
```

### Verbose Output

```bash
python run_tests.py --verbose
```

---

## 📁 Test Structure

```
backend/tests/
├── conftest.py                 # Pytest configuration
├── fixtures.py                 # Shared test fixtures
├── test_api_endpoints.py       # API integration tests
├── test_code_executor.py       # Code execution tests
├── test_data_analyst.py        # Agent functionality tests
├── test_llm_providers.py       # LLM provider tests
└── test_agent.py              # Original agent tests
```

---

## 🧪 Test Categories

### 1. **Unit Tests** (`test_code_executor.py`)
- Code execution safety
- Pandas code validation
- Error handling

```bash
pytest tests/test_code_executor.py -v
```

### 2. **API Tests** (`test_api_endpoints.py`)
- File upload/download
- Chat message endpoints
- Conversation history
- Session management

```bash
pytest tests/test_api_endpoints.py -v
```

### 3. **LLM Provider Tests** (`test_llm_providers.py`)
- Company GenAI API integration
- OpenAI integration
- Provider switching
- Model configuration

```bash
pytest tests/test_llm_providers.py -v
```

### 4. **Agent Tests** (`test_data_analyst.py`)
- Data analysis functionality
- Tool usage
- Memory management
- Query processing

```bash
pytest tests/test_data_analyst.py -v
```

---

## ⚙️ Configuration for Testing

### Environment Variables

Create a `.env.test` file or use your existing `.env`:

```bash
# For testing with Company API
LLM_PROVIDER=company
COMPANY_API_KEY=your-test-api-key
COMPANY_MODEL=ChatGPT4o-mini  # Use mini for faster/cheaper tests
COMPANY_USER_ID=test@motorolasolutions.com

# For testing with OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-test-key
OPENAI_MODEL=gpt-3.5-turbo  # Cheaper for testing
```

### Skip Tests Requiring API Keys

Tests automatically skip when API keys are not configured:

```python
@pytest.mark.skipif(
    not settings.COMPANY_API_KEY,
    reason="Company API key not configured"
)
```

---

## 🎯 Test Examples

### Test File Upload

```bash
pytest tests/test_api_endpoints.py::TestFileEndpoints::test_upload_csv_file -v
```

### Test LLM Integration

```bash
pytest tests/test_llm_providers.py::TestCompanyGenAILLM::test_company_llm_simple_query -v
```

### Test Agent Analysis

```bash
pytest tests/test_data_analyst.py::TestDataAnalystAgent::test_agent_simple_query -v
```

---

## 📊 Coverage Reports

### Generate Coverage Report

```bash
pytest --cov=app --cov-report=html tests/
```

### View Coverage

```bash
# Open in browser
open htmlcov/index.html  # Mac
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Coverage Goals

- **Overall**: > 80%
- **Core logic** (agents, utils): > 90%
- **API endpoints**: > 85%

---

## 🐛 Debugging Tests

### Run Single Test

```bash
pytest tests/test_api_endpoints.py::TestFileEndpoints::test_upload_csv_file -v -s
```

### Run with Debug Output

```bash
pytest tests/ -v -s --log-cli-level=DEBUG
```

### Run Failed Tests Only

```bash
pytest --lf  # Last failed
pytest --ff  # Failed first
```

---

## 🔍 Test Fixtures

### Available Fixtures

Located in `tests/fixtures.py`:

- `sample_sales_dataframe` - Basic sales data
- `sample_employee_dataframe` - Employee data
- `conversation_history` - Chat history
- `csv_file_bytes` - File upload testing
- `large_dataframe` - Performance testing

### Using Fixtures

```python
def test_with_fixture(sample_sales_dataframe):
    """Test using sample data"""
    assert len(sample_sales_dataframe) > 0
```

---

## 🚦 Continuous Integration

### GitHub Actions (Example)

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      - name: Run tests
        run: pytest tests/ --cov=app
```

---

## 📝 Writing New Tests

### Test Template

```python
"""
Test new feature
"""
import pytest
from app.your_module import YourClass


class TestYourFeature:
    """Test suite for your feature"""
    
    def test_basic_functionality(self):
        """Test basic functionality"""
        result = YourClass().method()
        assert result is not None
    
    @pytest.mark.skipif(condition, reason="...")
    def test_with_external_dependency(self):
        """Test that requires external service"""
        pass
```

---

## 🛠️ Troubleshooting

### Tests Fail with "No API Key"

**Solution:** Set environment variables in `.env` file

### Database Lock Errors

**Solution:** Tests use SQLite in-memory database. If issues persist:
```bash
rm test.db
pytest tests/
```

### Import Errors

**Solution:** Install test dependencies:
```bash
pip install -r requirements-test.txt
```

### Slow Tests

**Solution:** Use quick test category:
```bash
python run_tests.py --category quick
```

---

## 📈 Best Practices

1. **Run tests before committing**
   ```bash
   python run_tests.py --category quick
   ```

2. **Add tests for new features**
   - Write test first (TDD)
   - Ensure >80% coverage

3. **Use appropriate fixtures**
   - Reuse existing fixtures
   - Add new fixtures to `fixtures.py`

4. **Mock external services**
   - Don't rely on real API calls in CI
   - Use `@pytest.mark.skipif` for optional tests

5. **Keep tests fast**
   - Unit tests: < 1s each
   - Integration tests: < 5s each
   - Use `quick` category for development

---

## 📚 Resources

- **Pytest Documentation**: https://docs.pytest.org/
- **Coverage.py**: https://coverage.readthedocs.io/
- **FastAPI Testing**: https://fastapi.tiangolo.com/tutorial/testing/

---

## 🎯 Test Checklist

Before deploying:

- [ ] All unit tests pass
- [ ] API integration tests pass
- [ ] LLM provider tests pass (both providers)
- [ ] Coverage > 80%
- [ ] No security vulnerabilities
- [ ] Performance tests pass
- [ ] Documentation updated

---

## 💡 Quick Commands Reference

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=app tests/

# Run specific file
pytest tests/test_api_endpoints.py

# Run specific test
pytest tests/test_api_endpoints.py::TestFileEndpoints::test_upload_csv_file

# Run verbose
pytest -v tests/

# Run with output
pytest -s tests/

# Run failed tests
pytest --lf

# Run parallel (faster)
pytest -n auto tests/
```

Happy Testing! 🎉
