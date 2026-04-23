#!/usr/bin/env python3
"""
KPI Charts & Analysis Test Suite
Tests KPI generation, chart data, and analysis metrics using HTTP requests (curl-like)
No direct imports from backend - only HTTP API calls
"""

import json
import requests
import logging
import os
import time
from datetime import datetime
import csv

# --- Configuration ---
BASE_URL = "http://localhost:8000/api"
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(CURRENT_DIR, "logs")
REPORTS_DIR = os.path.join(CURRENT_DIR, "reports")

# Create directories if they don't exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# Test file configuration
TEST_FILES = {
    "small": {
        "path": os.path.join(CURRENT_DIR, "test_small.csv"),
        "rows": 100,
        "cols": ["id", "name", "value", "category", "date", "amount"]
    },
    "medium": {
        "path": os.path.join(CURRENT_DIR, "test_medium.csv"),
        "rows": 1000,
        "cols": ["id", "product", "sales", "region", "date", "profit", "quantity"]
    },
    "large": {
        "path": os.path.join(CURRENT_DIR, "test_large.csv"),
        "rows": 5000,
        "cols": ["id", "name", "value", "category", "status", "amount", "date"]
    }
}

# Logger Setup
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = os.path.join(LOG_DIR, f"kpi_test_{timestamp}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class KPITestSuite:
    """KPI Chart and Analysis Test Suite"""
    
    def __init__(self):
        self.stats = {
            "files_uploaded": 0,
            "kpi_generated": 0,
            "kpi_failed": 0,
            "chart_validations_passed": 0,
            "chart_validations_failed": 0
        }
        self.uploaded_files = {}
        self.test_results = []
        
    def create_test_file(self, file_config):
        """Create a test CSV file"""
        path = file_config["path"]
        rows = file_config["rows"]
        cols = file_config["cols"]
        
        try:
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                
                for i in range(rows):
                    row = [
                        i,
                        f"item_{i}",
                        i * 10 + (i % 100),
                        f"category_{i % 5}",
                        f"2025-01-{(i % 28) + 1:02d}",
                        i * 50 + (i % 300),
                        i % 10
                    ]
                    writer.writerow(row)
            
            file_size_mb = os.path.getsize(path) / (1024 * 1024)
            logger.info(f"✅ Created test file: {os.path.basename(path)} ({file_size_mb:.2f}MB, {rows} rows)")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create test file {path}: {e}")
            return False
    
    def upload_file(self, file_key):
        """Upload a test file and return file_id"""
        file_config = TEST_FILES.get(file_key)
        if not file_config:
            logger.error(f"❌ Unknown file key: {file_key}")
            return None
        
        file_path = file_config["path"]
        
        if not os.path.exists(file_path):
            logger.warning(f"⚠️ Test file not found, creating: {file_key}")
            self.create_test_file(file_config)
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(
                    f"{BASE_URL}/files/upload",
                    files=files,
                    timeout=60
                )
                response.raise_for_status()
                data = response.json()
                file_id = data.get('id')
                
                if file_id:
                    self.uploaded_files[file_key] = {
                        'id': file_id,
                        'filename': data.get('original_filename'),
                        'rows': data.get('row_count'),
                        'size': os.path.getsize(file_path) / (1024 * 1024)
                    }
                    self.stats["files_uploaded"] += 1
                    logger.info(f"✅ Uploaded {file_key}: file_id={file_id}, rows={data.get('row_count')}")
                    return file_id
                else:
                    logger.error(f"❌ No file_id in response: {data}")
                    return None
                    
        except requests.exceptions.Timeout:
            logger.error(f"❌ Upload timeout for {file_key}")
            return None
        except Exception as e:
            logger.error(f"❌ Upload failed for {file_key}: {e}")
            return None
    
    def get_kpi_data(self, file_id):
        """Get KPI analysis for a file"""
        try:
            start_time = time.time()
            response = requests.get(
                f"{BASE_URL}/files/{file_id}/kpis",
                timeout=120
            )
            response.raise_for_status()
            duration = time.time() - start_time
            
            data = response.json()
            
            # Validate response structure
            required_keys = ['summary', 'metrics', 'visual_recommendations']
            missing_keys = [k for k in required_keys if k not in data]
            
            if missing_keys:
                logger.warning(f"⚠️ KPI response missing keys: {missing_keys}")
            
            self.stats["kpi_generated"] += 1
            logger.info(f"✅ KPI generated in {duration:.2f}s for file_id={file_id}")
            return data, duration
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ KPI request timeout for file_id={file_id}")
            self.stats["kpi_failed"] += 1
            return None, 0
        except Exception as e:
            logger.error(f"❌ Failed to get KPI for file_id={file_id}: {e}")
            self.stats["kpi_failed"] += 1
            return None, 0
    
    def validate_kpi_summary(self, summary):
        """Validate KPI summary structure"""
        validations = {
            "has_rows": 'rows' in summary,
            "has_columns": 'columns' in summary,
            "has_numeric_columns": 'numeric_columns' in summary,
            "has_categorical_columns": 'categorical_columns' in summary,
            "has_missing_values": 'missing_values' in summary,
            "rows_is_positive": summary.get('rows', 0) > 0,
            "columns_is_positive": summary.get('columns', 0) > 0
        }
        
        passed = sum(1 for v in validations.values() if v)
        total = len(validations)
        
        if passed == total:
            logger.info(f"✅ Summary validation passed ({passed}/{total})")
            self.stats["chart_validations_passed"] += 1
            return True
        else:
            logger.warning(f"⚠️ Summary validation: {passed}/{total} checks passed")
            failed_checks = [k for k, v in validations.items() if not v]
            logger.warning(f"   Failed: {failed_checks}")
            self.stats["chart_validations_failed"] += 1
            return False
    
    def validate_kpi_metrics(self, metrics):
        """Validate KPI metrics"""
        if not isinstance(metrics, list):
            logger.warning("❌ Metrics is not a list")
            self.stats["chart_validations_failed"] += 1
            return False
        
        if len(metrics) == 0:
            logger.warning("⚠️ Metrics list is empty")
            self.stats["chart_validations_failed"] += 1
            return False
        
        # Check metric structure
        valid_metrics = 0
        for metric in metrics:
            if isinstance(metric, dict) and 'label' in metric and 'value' in metric:
                valid_metrics += 1
        
        pass_rate = valid_metrics / len(metrics) if metrics else 0
        
        if pass_rate >= 0.8:
            logger.info(f"✅ Metrics validation passed ({valid_metrics}/{len(metrics)} valid)")
            self.stats["chart_validations_passed"] += 1
            return True
        else:
            logger.warning(f"⚠️ Metrics validation: {valid_metrics}/{len(metrics)} valid ({pass_rate*100:.0f}%)")
            self.stats["chart_validations_failed"] += 1
            return False
    
    def validate_visual_recommendations(self, visuals):
        """Validate visual recommendations and charts"""
        if not isinstance(visuals, list):
            logger.warning("❌ Visual recommendations is not a list")
            self.stats["chart_validations_failed"] += 1
            return False
        
        if len(visuals) == 0:
            logger.warning("⚠️ No visual recommendations generated")
            self.stats["chart_validations_failed"] += 1
            return False
        
        chart_count = 0
        for i, visual in enumerate(visuals, 1):
            if not isinstance(visual, dict):
                logger.warning(f"   Visual {i}: Not a dict")
                continue
            
            has_title = 'title' in visual
            has_description = 'description' in visual
            has_query = 'suggested_query' in visual
            has_chart = 'chart_data' in visual
            
            if has_title and has_description and has_query:
                logger.info(f"✅ Visual {i}: {visual.get('title')} (chart: {'yes' if has_chart else 'no'})")
                chart_count += 1
            else:
                logger.warning(f"   Visual {i}: Missing required fields (title={has_title}, desc={has_description}, query={has_query})")
        
        if chart_count > 0:
            logger.info(f"✅ Visual recommendations validated ({chart_count}/{len(visuals)} complete)")
            self.stats["chart_validations_passed"] += 1
            return True
        else:
            logger.warning(f"❌ No valid visualizations in response")
            self.stats["chart_validations_failed"] += 1
            return False
    
    def validate_ai_insights(self, kpi_data):
        """Validate AI-generated insights if available"""
        ai_summary = kpi_data.get('ai_summary')
        analysis_insights = kpi_data.get('analysis_insights')
        data_quality = kpi_data.get('data_quality')
        
        validations = {
            "ai_summary": bool(ai_summary),
            "analysis_insights": bool(analysis_insights) or analysis_insights is None,
            "data_quality": bool(data_quality) or data_quality is None
        }
        
        passed = sum(1 for v in validations.values() if v)
        
        logger.info(f"✅ AI Insights validation: {passed}/{len(validations)} checks passed")
        if ai_summary:
            logger.info(f"   AI Summary: {ai_summary[:100]}...")
        
        return passed == len(validations)
    
    def run_file_test(self, file_key):
        """Run complete test for a file"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing KPI for {file_key} file")
        logger.info(f"{'='*60}")
        
        # 1. Upload file
        file_id = self.upload_file(file_key)
        if not file_id:
            logger.error(f"❌ Skipping {file_key} test due to upload failure")
            return False
        
        # 2. Get KPI data
        kpi_data, duration = self.get_kpi_data(file_id)
        if not kpi_data:
            logger.error(f"❌ Failed to get KPI data for {file_key}")
            return False
        
        # 3. Validate components
        summary_valid = self.validate_kpi_summary(kpi_data.get('summary', {}))
        metrics_valid = self.validate_kpi_metrics(kpi_data.get('metrics', []))
        visuals_valid = self.validate_visual_recommendations(kpi_data.get('visual_recommendations', []))
        insights_valid = self.validate_ai_insights(kpi_data)
        
        # 4. Store results
        test_result = {
            "file_key": file_key,
            "file_id": file_id,
            "duration_seconds": duration,
            "summary_valid": summary_valid,
            "metrics_valid": metrics_valid,
            "visuals_valid": visuals_valid,
            "insights_valid": insights_valid,
            "overall_pass": all([summary_valid, metrics_valid, visuals_valid, insights_valid])
        }
        
        self.test_results.append(test_result)
        
        status = "✅ PASS" if test_result["overall_pass"] else "❌ FAIL"
        logger.info(f"\n{status}: KPI test for {file_key} file")
        logger.info(f"  Duration: {duration:.2f}s")
        logger.info(f"  Summary: {summary_valid} | Metrics: {metrics_valid} | Visuals: {visuals_valid} | AI: {insights_valid}")
        
        return test_result["overall_pass"]
    
    def generate_report(self):
        """Generate test report"""
        report_path = os.path.join(REPORTS_DIR, f"kpi_test_report_{timestamp}.json")
        
        report = {
            "timestamp": timestamp,
            "statistics": self.stats,
            "uploaded_files": self.uploaded_files,
            "test_results": self.test_results,
            "summary": {
                "total_tests": len(self.test_results),
                "passed": sum(1 for r in self.test_results if r["overall_pass"]),
                "failed": sum(1 for r in self.test_results if not r["overall_pass"]),
                "success_rate": f"{(sum(1 for r in self.test_results if r['overall_pass']) / len(self.test_results) * 100):.1f}%" if self.test_results else "0%"
            }
        }
        
        try:
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"✅ Report saved to {report_path}")
        except Exception as e:
            logger.error(f"❌ Failed to save report: {e}")
        
        return report
    
    def print_summary(self):
        """Print test summary"""
        logger.info(f"\n{'='*60}")
        logger.info("KPI Test Suite Summary")
        logger.info(f"{'='*60}")
        logger.info(f"Files Uploaded: {self.stats['files_uploaded']}")
        logger.info(f"KPI Generated: {self.stats['kpi_generated']}")
        logger.info(f"KPI Failed: {self.stats['kpi_failed']}")
        logger.info(f"Chart Validations Passed: {self.stats['chart_validations_passed']}")
        logger.info(f"Chart Validations Failed: {self.stats['chart_validations_failed']}")
        
        if self.test_results:
            passed = sum(1 for r in self.test_results if r["overall_pass"])
            total = len(self.test_results)
            success_rate = (passed / total * 100) if total > 0 else 0
            
            logger.info(f"\nTest Results: {passed}/{total} passed ({success_rate:.1f}%)")
            
            avg_duration = sum(r["duration_seconds"] for r in self.test_results) / len(self.test_results)
            logger.info(f"Average Duration: {avg_duration:.2f}s")
        
        logger.info(f"{'='*60}\n")


def main():
    """Run the KPI test suite"""
    logger.info("🚀 Starting KPI Chart & Analysis Test Suite")
    logger.info(f"Base URL: {BASE_URL}")
    
    suite = KPITestSuite()
    
    try:
        # Run tests for different file sizes
        for file_key in ["small", "medium"]:
            suite.run_file_test(file_key)
            time.sleep(2)  # Brief pause between tests
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Test suite interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}", exc_info=True)
    finally:
        # Generate report and summary
        report = suite.generate_report()
        suite.print_summary()
        
        logger.info("✅ KPI Test Suite Completed")


if __name__ == "__main__":
    main()
