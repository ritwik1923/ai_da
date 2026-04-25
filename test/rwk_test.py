import csv
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
MAX_RETRIES = 2
LOG_DIR = "logs"
REPORT_DIR = os.path.join(CURRENT_DIR, "reports")
MAX_FAILED_ALLOWED = 10
MAX_CONCURRENT_QUERIES = 5

os.makedirs(os.path.join(CURRENT_DIR, LOG_DIR), exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

# Logger Setup
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = os.path.join(CURRENT_DIR, LOG_DIR, f"suite_run_{timestamp}.log")
csv_report_filename = os.path.join(REPORT_DIR, f"suite_run_{timestamp}.csv")
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
    plan_markers = (
        "i will use the analysis tool",
        "to solve this question",
        "follow these steps",
        "thought process",
        "we need to use the analysis tool",
    )

    if any(marker in answer_normalized for marker in plan_markers):
        return False

    if expected_normalized in answer_normalized:
        return True

    expected_tokens = extract_alnum_tokens(expected_value)
    if not expected_tokens:
        return False

    expected_numbers = extract_number_tokens(expected_value)
    if expected_numbers and not re.search(r"[a-z]", expected_normalized):
        answer_numbers = extract_number_tokens(answer)
        return expected_numbers.issubset(answer_numbers)

    answer_token_set = set(extract_alnum_tokens(answer))
    if all(token in answer_token_set for token in expected_tokens):
        return True

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


def build_summary_metrics(case_results, total_elapsed_time):
    total_cases = len(case_results)
    total_attempts = sum(len(result["attempts"]) for result in case_results)
    passed_cases = sum(1 for result in case_results if result["passed"])
    failed_cases = total_cases - passed_cases
    successful_attempts = sum(
        1
        for result in case_results
        for attempt in result["attempts"]
        if attempt["matched_expected"]
    )
    attempt_latencies = [
        attempt["attempt_elapsed_time"]
        for result in case_results
        for attempt in result["attempts"]
        if attempt["attempt_elapsed_time"] is not None
    ]
    case_latencies = [result["elapsed_time"] for result in case_results]

    return {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "pass_rate_pct": round((passed_cases / total_cases) * 100, 2) if total_cases else 0.0,
        "total_attempts": total_attempts,
        "avg_attempts_per_case": round(total_attempts / total_cases, 2) if total_cases else 0.0,
        "successful_attempts": successful_attempts,
        "attempt_success_rate_pct": round((successful_attempts / total_attempts) * 100, 2) if total_attempts else 0.0,
        "avg_attempt_latency_sec": round(sum(attempt_latencies) / len(attempt_latencies), 2) if attempt_latencies else 0.0,
        "max_attempt_latency_sec": round(max(attempt_latencies), 2) if attempt_latencies else 0.0,
        "avg_case_latency_sec": round(sum(case_latencies) / len(case_latencies), 2) if case_latencies else 0.0,
        "max_case_latency_sec": round(max(case_latencies), 2) if case_latencies else 0.0,
        "total_suite_time_sec": round(total_elapsed_time, 2),
        "concurrency": MAX_CONCURRENT_QUERIES,
        "max_retries": MAX_RETRIES,
    }


def write_csv_report(case_results, total_elapsed_time, file_path):
    metrics = build_summary_metrics(case_results, total_elapsed_time)
    fieldnames = [
        "row_type",
        "run_timestamp",
        "case_id",
        "attempt_number",
        "session_id",
        "original_query",
        "sent_message",
        "expected_value",
        "response",
        "generated_code",
        "message_id",
        "matched_expected",
        "final_case_status",
        "case_elapsed_time_sec",
        "attempt_elapsed_time_sec",
        "feedback_sent",
        "error",
        "metric_name",
        "metric_value",
    ]

    with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for result in sorted(case_results, key=lambda item: item["case"]["id"]):
            for attempt in result["attempts"]:
                writer.writerow({
                    "row_type": "attempt",
                    "run_timestamp": timestamp,
                    "case_id": result["case"]["id"],
                    "attempt_number": attempt["attempt_number"],
                    "session_id": result["session_id"],
                    "original_query": result["case"]["query"],
                    "sent_message": attempt["sent_message"],
                    "expected_value": result["case"]["expected_val"],
                    "response": attempt["response"],
                    "generated_code": attempt["generated_code"],
                    "message_id": attempt["message_id"],
                    "matched_expected": attempt["matched_expected"],
                    "final_case_status": "passed" if result["passed"] else "failed",
                    "case_elapsed_time_sec": f"{result['elapsed_time']:.2f}",
                    "attempt_elapsed_time_sec": f"{attempt['attempt_elapsed_time']:.2f}",
                    "feedback_sent": attempt["feedback_sent"],
                    "error": attempt["error"],
                    "metric_name": "",
                    "metric_value": "",
                })

        for metric_name, metric_value in metrics.items():
            writer.writerow({
                "row_type": "summary",
                "run_timestamp": timestamp,
                "case_id": "",
                "attempt_number": "",
                "session_id": "",
                "original_query": "",
                "sent_message": "",
                "expected_value": "",
                "response": "",
                "generated_code": "",
                "message_id": "",
                "matched_expected": "",
                "final_case_status": "",
                "case_elapsed_time_sec": "",
                "attempt_elapsed_time_sec": "",
                "feedback_sent": "",
                "error": "",
                "metric_name": metric_name,
                "metric_value": metric_value,
            })

    return metrics


def process_test_case(case, file_id):
    logger.info(f"\n--- [ID {case['id']}] Starting ---")
    session_id = f"suite_{timestamp}_{case['id']}"
    current_msg = case['query']
    start_time = time.time()
    attempts = []

    for n in range(1, MAX_RETRIES + 1):
        logger.info(f"[ID {case['id']}] Attempt {n}: Sending query...")
        attempt_start_time = time.time()
        data = call_rag_api(current_msg, session_id, file_id)
        attempt_elapsed_time = time.time() - attempt_start_time
        logger.info(f"[ID {case['id']}] Response payload: {data}")
        answer = str(data.get("response", ""))
        code = str(data.get("generated_code", ""))
        message_id = data.get("message_id")
        matched_expected = answer_matches_expected(case["expected_val"], answer)

        attempts.append({
            "attempt_number": n,
            "sent_message": current_msg,
            "response": answer,
            "generated_code": code,
            "message_id": message_id,
            "matched_expected": matched_expected,
            "attempt_elapsed_time": attempt_elapsed_time,
            "feedback_sent": False,
            "error": data.get("detail", "") if isinstance(data, dict) else "",
        })

        if matched_expected:
            logger.info(f"[ID {case['id']}] ✅ Success on attempt {n}")
            if message_id:
                attempts[-1]["feedback_sent"] = send_feedback(message_id, is_positive=True)
            else:
                logger.warning(f"[ID {case['id']}] ⚠️ Success, but no message_id returned to send feedback.")

            return {
                "case": case,
                "session_id": session_id,
                "attempts": attempts,
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
        "session_id": session_id,
        "attempts": attempts,
        "passed": False,
        "elapsed_time": time.time() - start_time,
        "final_message": current_msg,
    }




def run_automated_suite():
    suite_start_time = time.time()
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
    case_results = []
    
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
                    "session_id": f"suite_{timestamp}_{case['id']}",
                    "attempts": [],
                    "passed": False,
                    "elapsed_time": 0.0,
                    "final_message": case["query"],
                }

            case_results.append(result)

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
                logger.error("❌ Failure limit reached. Continuing so the CSV still captures every test case.")

    total_elapsed_time = time.time() - suite_start_time
    metrics = write_csv_report(case_results, total_elapsed_time, csv_report_filename)

    logger.info(f"\nFINISH: Passed {stats['passed']} | Failed {stats['failed']}")
    logger.info(f"\nFailed Cases: {[case['id'] for case in list_faided_cases]}")
    logger.info(f"📄 CSV report written to {csv_report_filename}")
    logger.info(
        "📊 LLM metrics | pass_rate=%s%% | avg_attempt_latency=%.2fs | avg_case_latency=%.2fs | total_attempts=%s",
        metrics["pass_rate_pct"],
        metrics["avg_attempt_latency_sec"],
        metrics["avg_case_latency_sec"],
        metrics["total_attempts"],
    )


if __name__ == "__main__":
    start_time = time.time()
    run_automated_suite()
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(f"⏱️ Total execution time: {elapsed_time:.2f} seconds")