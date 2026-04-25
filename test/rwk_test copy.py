# scripts/run_val_suite.py
import httpx
import asyncio
import yaml
import logging
from datetime import datetime
# backend/test/rwk_test.py
import os
import sys

# backend/test/rwk_test.py
import os
import sys

# 1. Dynamically find the backend root
# This looks at the current file and goes up one level
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# 2. Now import using the absolute path from backend root
try:
    from app.utils.logger import get_production_logger
    logger = get_production_logger("ai_da.test_suite")
except ImportError as e:
    print(f"❌ Import failed. Ensure 'app' folder is in {BASE_DIR}")
    print(f"Error: {e}")
    sys.exit(1)

logger = get_production_logger("ai_da.test_suite")
# Configuration
BASE_URL = "http://localhost:8000/api"

# Get the absolute path of the directory containing this script (the 'test' folder)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Construct the absolute path to the YAML file
YML_FILE = os.path.join(CURRENT_DIR, "test_suites.yml")
logger = get_production_logger("ai_da.test_suite")

class AutomatedValidationSuite:
    def __init__(self):
        self.stats = {"passed": 0, "failed": 0}
        self.client = httpx.AsyncClient(timeout=120.0)

    async def upload_file(self, file_path):
        """Uploads the dataset once and returns file_id."""
        try:
            with open(file_path, "rb") as f:
                files = {"file": f}
                resp = await self.client.post(f"{BASE_URL}/files/upload", files=files)
                resp.raise_for_status()
                return resp.json()["id"]
        except Exception as e:
            logger.error("Data upload failed", extra={"error": str(e)})
            return None

    async def run_case(self, case, file_id):
        """Runs a single test case with retry logic."""
        session_id = f"suite_{datetime.now().strftime('%H%M%S')}_{case['id']}"
        query = case['query']
        
        for attempt in range(1, 4):  # Standardized 3 attempts
            payload = {"session_id": session_id, "message": query, "file_id": file_id}
            resp = await self.client.post(f"{BASE_URL}/chat/message", json=payload)
            data = resp.json()
            
            answer = str(data.get("response", ""))
            code = str(data.get("generated_code", ""))
            msg_id = data.get("message_id")

            # Deep Validation: Check value AND code snippet
            val_match = case["expected_val"].lower() in answer.lower()
            code_match = case["expected_snippet"] in code if "expected_snippet" in case else True

            if val_match and code_match:
                logger.info(f"✅ Case {case['id']} Passed", extra={"attempt": attempt})
                await self.send_feedback(msg_id, True)
                return True
            else:
                logger.warning(f"⚠️ Case {case['id']} Attempt {attempt} failed")
                # Update query for self-correction feedback
                query = f"Previous answer '{answer}' was incorrect. Required value: {case['expected_val']}. Query: {case['query']}"
        
        return False

    async def send_feedback(self, message_id, is_positive):
        """Triggers the learning mechanism in the backend."""
        if not message_id: return
        await self.client.post(f"{BASE_URL}/chat/feedback", json={
            "message_id": message_id,
            "is_positive": is_positive,
            "comments": "Automated Suite Learning"
        })

    async def execute(self, file_path):
        with open(YML_FILE, 'r') as f:
            suite = yaml.safe_load(f)
        
        file_id = await self.upload_file(file_path)
        if not file_id: return

        for case in suite['test_cases']:
            if await self.run_case(case, file_id):
                self.stats["passed"] += 1
            else:
                self.stats["failed"] += 1
        
        logger.info("Suite Finished", extra=self.stats)
        
if __name__ == "__main__":
    # Point this to your test dataset
    FILE_PATH = "/Users/rwk3030/Downloads/products-100.csv"
    
    logger.info("🎬 Starting Automated Test Suite...")
    
    suite = AutomatedValidationSuite()
    
    # Execute the async suite
    asyncio.run(suite.execute(FILE_PATH))