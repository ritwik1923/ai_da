# KPI Test Suite

Comprehensive test suite for KPI charts and analysis generation. Tests the KPI analysis pipeline using HTTP requests (curl-like) without importing backend functions.

## What It Tests

- ✅ File upload functionality (different file sizes)
- ✅ KPI analysis generation and timing
- ✅ KPI summary structure and data validation
- ✅ Metrics generation and validation
- ✅ Visual recommendations generation
- ✅ Chart data structure and completeness
- ✅ AI-generated insights and analysis
- ✅ Data quality indicators
- ✅ Performance metrics (analysis duration)

## Test Cases

The suite includes 3 test file sizes:

### 1. **Small File** (100 rows)
- Quick validation of basic functionality
- Fast analysis time expected (<5s)
- Tests: Summary, metrics, basic visualizations

### 2. **Medium File** (1,000 rows)
- Standard use case validation
- Typical analysis time (5-15s)
- Tests: All KPI components with AI insights

### 3. **Large File** (5,000 rows)
- Performance and scalability testing
- Longer analysis time (15-30s)
- Tests: Complex data patterns and AI analysis quality

## Usage

### Prerequisites
```bash
cd /Users/rwk3030/dev/ai_da/backend
source .venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Run the Test Suite
```bash
cd /Users/rwk3030/dev/ai_da/backend/test
python test_kpi_suite.py
```

### Run with Logging to File
```bash
python test_kpi_suite.py 2>&1 | tee test_run.log
```

## Output

### Console Output
```
🚀 Starting KPI Chart & Analysis Test Suite
Base URL: http://localhost:8000/api

============================================================
Testing KPI for small file
============================================================
✅ Created test file: test_small.csv (0.01MB, 100 rows)
✅ Uploaded small: file_id=1, rows=100
✅ KPI generated in 2.34s for file_id=1
✅ Summary validation passed (7/7)
✅ Metrics validation passed (7/10 valid)
✅ Visual {1}: Numeric KPI Overview (chart: yes)
✅ Visual recommendations validated (1/1 complete)
✅ AI Insights validation: 3/3 checks passed
   AI Summary: Dataset contains 100 records with 6 columns...

✅ PASS: KPI test for small file
  Duration: 2.34s
  Summary: True | Metrics: True | Visuals: True | AI: True

============================================================
KPI Test Suite Summary
============================================================
Files Uploaded: 2
KPI Generated: 2
KPI Failed: 0
Chart Validations Passed: 10
Chart Validations Failed: 0

Test Results: 2/2 passed (100.0%)
Average Duration: 5.67s
============================================================
```

### Report Files

Results are saved in `/Users/rwk3030/dev/ai_da/backend/test/reports/`:
- `kpi_test_report_YYYYMMDD_HHMMSS.json` - Detailed test report

#### Report Structure
```json
{
  "timestamp": "20260412_143022",
  "statistics": {
    "files_uploaded": 2,
    "kpi_generated": 2,
    "kpi_failed": 0,
    "chart_validations_passed": 10,
    "chart_validations_failed": 0
  },
  "uploaded_files": {
    "small": {
      "id": 1,
      "filename": "test_small.csv",
      "rows": 100,
      "size": 0.01
    }
  },
  "test_results": [
    {
      "file_key": "small",
      "file_id": 1,
      "duration_seconds": 2.34,
      "summary_valid": true,
      "metrics_valid": true,
      "visuals_valid": true,
      "insights_valid": true,
      "overall_pass": true
    }
  ],
  "summary": {
    "total_tests": 2,
    "passed": 2,
    "failed": 0,
    "success_rate": "100.0%"
  }
}
```

### Log Files

Detailed logs in `/Users/rwk3030/dev/ai_da/backend/test/logs/`:
- `kpi_test_YYYYMMDD_HHMMSS.log` - Full execution log

## Test Validations

### Summary Validation
- ✅ Has `rows` field (positive integer)
- ✅ Has `columns` field (positive integer)
- ✅ Has `numeric_columns` field
- ✅ Has `categorical_columns` field
- ✅ Has `missing_values` field
- ✅ Row count > 0
- ✅ Column count > 0

### Metrics Validation
- ✅ Is a list
- ✅ Has multiple items (>0)
- ✅ Each metric has `label` and `value` fields
- ✅ At least 80% of metrics are properly structured

### Visual Recommendations Validation
- ✅ Is a list
- ✅ Has recommendations (>0)
- ✅ Each visual has `title`, `description`, `suggested_query`
- ✅ Chart data present/generated

### AI Insights Validation
- ✅ Has `ai_summary` (optional but preferred)
- ✅ Has `analysis_insights` structure
- ✅ Has `data_quality` indicators

## Performance Expectations

| File Size | Rows | Expected Duration | Actual |
|-----------|------|-------------------|--------|
| Small     | 100  | <5s              | -      |
| Medium    | 1K   | 5-15s            | -      |
| Large     | 5K   | 15-30s           | -      |

## Troubleshooting

### Test Fails on File Upload
```
❌ Upload failed for small: Connection refused
```
**Solution**: Ensure backend is running on port 8000
```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Test Fails on KPI Generation
```
❌ KPI request timeout for file_id=1
```
**Solution**: Increase timeout or check if Ollama is running
```bash
# Check Ollama
ollama list
# Restart if needed
ollama serve
```

### Missing Test Files
```
⚠️ Test file not found, creating: small
```
**Solution**: Test files are auto-created if missing. No action needed.

## API Endpoints Tested

1. **File Upload**
   ```
   POST /api/files/upload
   ```

2. **Get KPI Data**
   ```
   GET /api/files/{file_id}/kpis
   ```

## Integration with CI/CD

To include in automated testing:

```bash
# Exit with status code based on results
python test_kpi_suite.py && echo "✅ All tests passed" || echo "❌ Tests failed"
```

## Performance Monitoring

The suite tracks:
- Average KPI analysis duration
- Success rate by file size
- Validation error patterns
- Resource utilization

Monitor these metrics over time to detect performance regressions.

## Notes

- Tests create temporary CSV files automatically
- All tests use HTTP API (no backend imports)
- Results are cumulative in reports (one report per run)
- Logs are preserved for auditing
- Tests are safe to run multiple times
