import json
import requests
import logging
import os
import time
from datetime import datetime
import yaml

# --- Configuration ---
BASE_URL = "http://localhost:8000/kpi"
FILE_PATH = "/Users/rwk3030/Downloads/products-100.csv"
JSON_FILE = "test_suites.json"
# Get the absolute path of the directory containing this script (the 'test' folder)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Construct the absolute path to the YAML file
YML_FILE = os.path.join(CURRENT_DIR, "test_suites.yml")
MAX_RETRIES = 5
LOG_DIR = "logs"
MAX_FAILED_ALLOWED = 5

# Logger Setup
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = os.path.join(LOG_DIR, f"suite_run_{timestamp}.log")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", 
                    handlers=[logging.FileHandler(log_filename), logging.StreamHandler()])
logger = logging.getLogger(__name__)

def load_test_cases_json(file_path):
    """Loads cases from JSON file"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            return data.get("test_cases", [])
    except FileNotFoundError:
        logger.error(f"❌ JSON file not found at {file_path}")
        return []
    except json.JSONDecodeError:
        logger.error(f"❌ Failed to decode JSON. Check syntax in {file_path}")
        return []

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
    payload = {"session_id": session_id, "message": message, "file_id": file_id}
    try:
        response = requests.post(f"{BASE_URL}/chat/message", json=payload, timeout=90)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"API Error: {e}")
        return {}

def send_feedback(message_id, is_positive):
    """Sends feedback to trigger continuous learning in the backend."""
    payload = {
        "message_id": message_id,
        "is_positive": is_positive,
        "comments": "Automated test suite validation"
    }
    try:
        response = requests.post(f"{BASE_URL}/chat/feedback", json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"🎓 Feedback submitted for message ID {message_id} -> AI learned successfully!")
        return True
    except Exception as e:
        logger.error(f"⚠️ Failed to submit feedback for message ID {message_id}: {e}")
        return False

def run_automated_suite():
    # 1. Load Data
    test_cases = load_test_cases(YML_FILE)
    if not test_cases:
        return

    logger.info(f"🚀 Loaded {len(test_cases)} test cases from {YML_FILE}")

    # 2. Upload File Once
    try:
        with open(FILE_PATH, "rb") as f:
            resp = requests.post(f"{BASE_URL}/files/upload", files={"file": f})
            file_id = resp.json()["id"]
            logger.info(f"✅ Data uploaded. ID: {file_id}")
    except Exception as e:
        logger.error(f"❌ Upload failed: {e}")
        return

    stats = {"passed": 0, "failed": 0}
    list_faided_cases = []
    
    # 3. Process Cases
    for case in test_cases:
        logger.info(f"\n--- [ID {case['id']}] Starting ---")
        session_id = f"suite_{timestamp}_{case['id']}"
        current_msg = case['query']
        case_passed = False
        start_time = time.time()
        for n in range(1, MAX_RETRIES + 1):
            logger.info(f"Attempt {n}: Sending query...")
            data = call_rag_api(current_msg, session_id, file_id)
            print(f"data\t\t\n{data}\n")
            answer = str(data.get("response", ""))
            code = str(data.get("generated_code", ""))
            message_id = data.get("message_id")  # Extract the newly added message_id

            # Validation logic
            value_match = case["expected_val"].lower() in answer.lower()

            if value_match:
                logger.info(f"✅ Success on attempt {n}")
                stats["passed"] += 1
                case_passed = True
                
                # TRIGGER LEARNING: Send positive feedback to the backend
                if message_id:
                    send_feedback(message_id, is_positive=True)
                else:
                    logger.warning("⚠️ Success, but no message_id returned to send feedback.")
                break
            else:
                logger.warning(f"⚠️ Attempt {n} incorrect. Retrying...\n Query: {case['query']}\nAnswer: {answer}\nCode: {code} \nExpected Value: {case['expected_val']}")
                
                current_msg = f"Your answer was wrong. Please re-read the question and provide a correct response.\nQuery: {case['query']}\nAnswer: {answer} \nExpected Value: {case['expected_val']}"

        end_time = time.time()
        elapsed_time = end_time - start_time
        logger.info(f"⏱️ execution time for task \'{current_msg}\' : {elapsed_time:.2f} seconds")
        
        if not case_passed:
            logger.error(f"❌ FAILED after {MAX_RETRIES} attempts.")
            stats["failed"] += 1
            list_faided_cases.append(case)

        if stats["failed"] > MAX_FAILED_ALLOWED:
            logger.error(f"❌ Stopping suite due to failure limit.")
            break
        

    logger.info(f"\nFINISH: Passed {stats['passed']} | Failed {stats['failed']}")
    logger.info(f"\nFailed Cases: {[case['id'] for case in list_faided_cases]}")


if __name__ == "__main__":
    start_time = time.time()
    run_automated_suite()
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(f"⏱️ Total execution time: {elapsed_time:.2f} seconds")