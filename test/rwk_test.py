import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
import yaml

# --- Configuration ---
BASE_URL = "http://localhost:8000/api"
FILE_PATH = "/Users/rwk3030/Downloads/products-100.csv"
JSON_FILE = "test_suites.json"
# Get the absolute path of the directory containing this script (the 'test' folder)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Construct the absolute path to the YAML file
YML_FILE = os.path.join(CURRENT_DIR, "test_suites.yml")
MAX_RETRIES = 5
LOG_DIR = "logs"
MAX_FAILED_ALLOWED = 5
MAX_CONCURRENT_QUERIES = 5

# Logger Setup
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = os.path.join(LOG_DIR, f"suite_run_{timestamp}.log")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", 
                    handlers=[logging.FileHandler(log_filename), logging.StreamHandler()])
logger = logging.getLogger(__name__)


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value).strip()).lower()


def extract_alnum_tokens(value):
    return re.findall(r"[a-z0-9]+", normalize_text(value))


def extract_number_tokens(value):
    tokens = []
    for match in re.findall(r"-?\d+(?:,\d{3})*(?:\.\d+)?", str(value)):
        compact = match.replace(",", "")
        tokens.append(compact)
        if "." in compact:
            tokens.append(compact.rstrip("0").rstrip("."))
    return {token for token in tokens if token}


def answer_matches_expected(expected_value, answer):
    expected_normalized = normalize_text(expected_value)
    answer_normalized = normalize_text(answer)
    if expected_normalized in answer_normalized:
        return True

    expected_tokens = extract_alnum_tokens(expected_value)
    if not expected_tokens:
        return False

    answer_token_set = set(extract_alnum_tokens(answer))
    if all(token in answer_token_set for token in expected_tokens):
        return True

    expected_numbers = extract_number_tokens(expected_value)
    if expected_numbers:
        answer_numbers = extract_number_tokens(answer)
        non_numeric_tokens = [token for token in expected_tokens if not token.isdigit()]
        return expected_numbers.issubset(answer_numbers) and all(
            token in answer_token_set for token in non_numeric_tokens
        )

    return False

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


def process_test_case(case, file_id):
    logger.info(f"\n--- [ID {case['id']}] Starting ---")
    session_id = f"suite_{timestamp}_{case['id']}"
    current_msg = case['query']
    start_time = time.time()

    for n in range(1, MAX_RETRIES + 1):
        logger.info(f"[ID {case['id']}] Attempt {n}: Sending query...")
        data = call_rag_api(current_msg, session_id, file_id)
        logger.info(f"[ID {case['id']}] Response payload: {data}")
        answer = str(data.get("response", ""))
        code = str(data.get("generated_code", ""))
        message_id = data.get("message_id")

        if answer_matches_expected(case["expected_val"], answer):
            logger.info(f"[ID {case['id']}] ✅ Success on attempt {n}")
            if message_id:
                send_feedback(message_id, is_positive=True)
            else:
                logger.warning(f"[ID {case['id']}] ⚠️ Success, but no message_id returned to send feedback.")

            return {
                "case": case,
                "passed": True,
                "elapsed_time": time.time() - start_time,
                "final_message": current_msg,
            }

        logger.warning(
            f"[ID {case['id']}] ⚠️ Attempt {n} incorrect. Retrying...\n"
            f" Query: {case['query']}\nAnswer: {answer}\nCode: {code} \nExpected Value: {case['expected_val']}"
        )
        current_msg = (
            "Your answer was wrong. Please re-read the question and provide a correct response.\n"
            f"Query: {case['query']}\n"
            f"Answer: {answer} \n"
            f"Expected Value: {case['expected_val']}"
        )

    return {
        "case": case,
        "passed": False,
        "elapsed_time": time.time() - start_time,
        "final_message": current_msg,
    }




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
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_QUERIES) as executor:
        future_to_case = {
            executor.submit(process_test_case, case, file_id): case for case in test_cases
        }

        for future in as_completed(future_to_case):
            case = future_to_case[future]

            try:
                result = future.result()
            except Exception as exc:
                logger.exception(f"[ID {case['id']}] ❌ Worker failed with unexpected error: {exc}")
                result = {
                    "case": case,
                    "passed": False,
                    "elapsed_time": 0.0,
                    "final_message": case["query"],
                }

            logger.info(
                f"⏱️ execution time for task \'{result['final_message']}\' : {result['elapsed_time']:.2f} seconds"
            )

            if result["passed"]:
                stats["passed"] += 1
                continue

            logger.error(f"[ID {case['id']}] ❌ FAILED after {MAX_RETRIES} attempts.")
            stats["failed"] += 1
            list_faided_cases.append(case)

            if stats["failed"] > MAX_FAILED_ALLOWED:
                logger.error("❌ Failure limit reached. Finishing in-flight tasks and stopping further scheduling.")
                break
        

    logger.info(f"\nFINISH: Passed {stats['passed']} | Failed {stats['failed']}")
    logger.info(f"\nFailed Cases: {[case['id'] for case in list_faided_cases]}")


if __name__ == "__main__":
    start_time = time.time()
    run_automated_suite()
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(f"⏱️ Total execution time: {elapsed_time:.2f} seconds")