import requests
import pytest, time

BASE_URL = "http://localhost:8000/api"
FILE_PATH = "/Users/rwk3030/Downloads/products-100.csv"

# --- Define all 20 Test Cases ---
test_cases = [
    # Level 1: Basic Retrieval & Distribution
    {"id": 1, "query": "What is the exact median price of all products in the dataset?", "expected_snippet": ".median()", "expected_val": 470.50},
    {"id": 2, "query": "What is the name and price of the single most expensive product?", "expected_snippet": ".max()", "expected_val": 999},
    # {"id": 3, "query": "How many unique brands are represented in this dataset?", "expected_snippet": ".nunique()", "expected_val": 100},
    # {"id": 4, "query": "Give me the exact count of products for each availability status.", "expected_snippet": "value_counts", "expected_val": 25}, # Checking pre_order count
    # {"id": 5, "query": "How many products contain the word 'Smart' anywhere in their name?", "expected_snippet": ".str.contains", "expected_val": 10},

    # # Level 2: Aggregation & Grouping
    # {"id": 6, "query": "Which 3 categories have the highest total stock available?", "expected_snippet": "groupby", "expected_val": 3314},
    # {"id": 7, "query": "What is the average price of items broken down by their availability status?", "expected_snippet": "mean", "expected_val": 606.60},
    # {"id": 8, "query": "What is the total combined stock for all items in the 'Kitchen Appliances' category?", "expected_snippet": "sum", "expected_val": 2572},
    # {"id": 9, "query": "What is the most common color specifically among products that are on 'pre_order'?", "expected_snippet": "mode", "expected_val": "LimeGreen"},
    # {"id": 10, "query": "Which 3 brands have the absolute lowest total stock across all their products?", "expected_snippet": "nsmallest", "expected_val": 10},

    # # Level 3: Multi-Condition Filtering & Calculations
    # {"id": 11, "query": "If we define 'Inventory Value' as Price multiplied by Stock, what is the total inventory value of the entire dataset?", "expected_snippet": "*", "expected_val": 24452583},
    # {"id": 12, "query": "What is the total inventory value (Price * Stock) for only the items that are currently 'in_stock'?", "expected_snippet": "==", "expected_val": 5719031},
    # {"id": 13, "query": "Exactly what percentage of the total products in this dataset have an availability of 'discontinued'?", "expected_snippet": "/", "expected_val": 12.0},
    # {"id": 14, "query": "How many products have a color of 'Black' AND a stock level greater than 50?", "expected_snippet": "&", "expected_val": 2},
    # {"id": 15, "query": "How many products are priced over $200 but have less than 20 items in stock?", "expected_snippet": "<", "expected_val": 2},

    # # Level 4: Advanced Logic & Data Manipulation
    # {"id": 16, "query": "Is there a correlation between the Price of a product and its Stock level? Give me the exact correlation coefficient.", "expected_snippet": ".corr()", "expected_val": -0.0227},
    # {"id": 17, "query": "Which product Category has the widest price range?", "expected_snippet": "max", "expected_val": "Automotive"},
    # {"id": 18, "query": "If we group the data by 'Size', which specific size has the highest average price?", "expected_snippet": "mean", "expected_val": "XL"},
    # {"id": 19, "query": "What is the average character length of the 'Description' field?", "expected_snippet": ".str.len()", "expected_val": 35.47},
    # {"id": 20, "query": "Which specific Brand has the highest average product price?", "expected_snippet": "mean", "expected_val": "Zimmerman"}
]

def run_automated_tests():
    print(f"\n🚀 Starting Automated Test Suite: {len(test_cases)} cases found.")
    print("-" * 60)

    # 1. Setup: Upload File
    try:
        with open(FILE_PATH, "rb") as f:
            file_resp = requests.post(f"{BASE_URL}/files/upload", files={"file": f})
            file_resp.raise_for_status()
            file_id = file_resp.json()["id"]
    except Exception as e:
        print(f"❌ Critical Error: Could not upload file. {e}")
        return

    passed_count = 0
    failed_count = 0

    # 2. Execution Loop
    for case in test_cases:
        print(f"Testing Case #{case['id']}: {case['query'][:50]}...")
        
        try:
            chat_payload = {
                "session_id": f"test_session_{case['id']}",
                "message": case["query"],
                "file_id": file_id
            }
            response = requests.post(f"{BASE_URL}/chat/message", json=chat_payload)
            response.raise_for_status()
            data = response.json()

            # Logic Check: Code snippet exists
            code_passed = case["expected_snippet"].lower() in data.get("generated_code", "").lower()
            
            # Note: For real-world use, you'd add numeric parsing here 
            # to check data.get("answer_value") against case["expected_val"]
            
            if code_passed:
                print(f"  ✅ PASSED")
                passed_count += 1
            else:
                print(f"  ❌ FAILED: Snippet '{case['expected_snippet']}' not found in code.")
                failed_count += 1

        except Exception as e:
            print(f"  ❌ FAILED: API Error - {e}")
            failed_count += 1

    # 3. Final Report
    print("-" * 60)
    print(f"TOTAL TEST CASES: {len(test_cases)}")
    print(f"✅ PASSED: {passed_count}")
    print(f"❌ FAILED: {failed_count}")
    print("-" * 60)

if __name__ == "__main__":
    start_time = time.time()
    run_automated_tests()
    end_time = time.time()
    print(f"Test suite completed in {end_time - start_time:.2f} seconds.")