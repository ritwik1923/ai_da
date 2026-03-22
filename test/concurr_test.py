import json
import requests
import logging
import os
import time
import yaml
import argparse
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Configuration & Defaults ---
BASE_URL = "http://localhost:8000/api"
FILE_PATH = "/Users/rwk3030/Downloads/products-100.csv"
YML_FILE = "test_suites.yml"
LOG_DIR = "logs"
MAX_RETRIES = 2
MAX_FAILED_ALLOWED = 5
DEFAULT_CONCURRENT_TASKS = 5

# --- Logger Setup ---
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = os.path.join(LOG_DIR, f"suite_run_{timestamp}.log")

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(threadName)s: %(message)s", 
    handlers=[logging.FileHandler(log_filename), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def load_test_cases(file_path):
    """Loads cases from YAML file safely"""
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            cases = data.get("test_cases", [])
            logger.info(f"📦 Loaded {len(cases)} test cases from {file_path}")
            return cases
    except Exception as e:
        logger.error(f"❌ Failed to load YAML: {e}")
        return []

def call_rag_api(message, session_id, file_id):
    """Sends request to the backend API"""
    payload = {"session_id": session_id, "message": message, "file_id": file_id}
    try:
        # Timeout is higher to account for model contention during parallel runs
        response = requests.post(f"{BASE_URL}/chat/message", json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"API Error for {session_id}: {e}")
        return {}

def process_single_case(case, file_id):
    """Worker function to process one test case (with retries)"""
    session_id = f"suite_{timestamp}_{case['id']}"
    current_msg = case['query']
    
    for n in range(1, MAX_RETRIES + 1):
        logger.info(f"--- [ID {case['id']}] Attempt {n} ---")
        data = call_rag_api(current_msg, session_id, file_id)
        
        answer = str(data.get("response", ""))
        # You can also check data.get("generated_code") if needed
        
        # Validation Logic
        if case["expected_val"].lower() in answer.lower():
            logger.info(f"✅ [ID {case['id']}] PASSED on attempt {n}")
            return {"id": case['id'], "passed": True}
        else:
            logger.warning(f"⚠️ [ID {case['id']}] Incorrect. Retrying with feedback...")
            current_msg = (
                f"Your previous answer was incorrect.\n"
                f"Query: {case['query']}\n"
                f"Expected searching for: {case['expected_val']}\n"
                f"Actual Answer received: {answer}\n"
                f"Please fix your logic and try again."
            )

    logger.error(f"❌ [ID {case['id']}] FAILED after {MAX_RETRIES} attempts.")
    return {"id": case['id'], "passed": False}

def run_automated_suite(concurrent_limit):
    # 1. Load Data
    test_cases = load_test_cases(YML_FILE)
    if not test_cases:
        return

    # 2. Upload File Once (Serial execution)
    try:
        with open(FILE_PATH, "rb") as f:
            resp = requests.post(f"{BASE_URL}/files/upload", files={"file": f})
            resp.raise_for_status()
            file_id = resp.json()["id"]
            logger.info(f"✅ Data uploaded successfully. ID: {file_id}")
    except Exception as e:
        logger.error(f"❌ Initial upload failed. Aborting suite: {e}")
        return

    stats = {"passed": 0, "failed": 0}
    failed_cases = []

    # 3. Parallel Execution
    logger.info(f"🚀 Starting execution with {concurrent_limit} concurrent tasks...")
    
    with ThreadPoolExecutor(max_workers=concurrent_limit, thread_name_prefix="Worker") as executor:
        # Submit all tasks
        future_to_case = {executor.submit(process_single_case, case, file_id): case for case in test_cases}
        
        try:
            for future in as_completed(future_to_case):
                result = future.result()
                
                if result["passed"]:
                    stats["passed"] += 1
                else:
                    stats["failed"] += 1
                    failed_cases.append(result["id"])

                # Early exit if too many failures
                if stats["failed"] >= MAX_FAILED_ALLOWED:
                    logger.error("🛑 Failure threshold reached. Cancelling remaining tasks...")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
        except KeyboardInterrupt:
            logger.warning("⌨️ Interrupted by user. Shutting down...")
            executor.shutdown(wait=False, cancel_futures=True)

    # 4. Final Report
    logger.info("\n" + "="*30)
    logger.info(f"FINAL RESULTS: Passed: {stats['passed']} | Failed: {stats['failed']}")
    if failed_cases:
        logger.info(f"Failed Case IDs: {failed_cases}")
    logger.info("="*30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI DA Parallel Test Suite Runner")
    parser.add_argument(
        "--tasks", 
        type=int, 
        default=DEFAULT_CONCURRENT_TASKS,
        help=f"Number of concurrent requests (default: {DEFAULT_CONCURRENT_TASKS})"
    )
    
    args = parser.parse_args()
    
    start_time = time.time()
    run_automated_suite(args.tasks)
    elapsed = time.time() - start_time
    logger.info(f"⏱️ Total execution time: {elapsed:.2f} seconds")