import asyncio
import httpx
import statistics
import time
from backend.app.utils.logger import get_production_logger

logger = get_production_logger("test.concurrency")
BASE_URL = "http://localhost:8000/api"
FILE_PATH = "/Users/rwk3030/Downloads/products-100.csv"

async def simulate_user(user_id: int, file_id: str, client: httpx.AsyncClient):
    """Simulates a single user asking a complex reasoning question."""
    query = "What is the average price of products containing 'Smart' in their name?"
    payload = {
        "session_id": f"stress_test_user_{user_id}",
        "message": query,
        "file_id": file_id
    }
    
    start = time.perf_counter()
    try:
        # This tests if ainvoke allows other requests to process while Llama is 'thinking'
        response = await client.post(f"{BASE_URL}/chat/message", json=payload, timeout=120)
        end = time.perf_counter()
        elapsed = end - start
        
        if response.status_code == 200:
            logger.info("👤 User %s finished in %.2fs", user_id, elapsed)
            return {
                "user_id": user_id,
                "ok": True,
                "status_code": response.status_code,
                "elapsed": elapsed,
            }
        else:
            logger.error("❌ User %s failed with status %s", user_id, response.status_code)
            return {
                "user_id": user_id,
                "ok": False,
                "status_code": response.status_code,
                "elapsed": elapsed,
            }
    except Exception as e:
        logger.error("🚨 User %s connection error: %s", user_id, e)
        return {
            "user_id": user_id,
            "ok": False,
            "status_code": None,
            "elapsed": None,
            "error": str(e),
        }

async def run_stress_test(num_users=15):
    async with httpx.AsyncClient() as client:
        # 1. Setup: Upload file
        with open(FILE_PATH, "rb") as f:
            resp = await client.post(f"{BASE_URL}/files/upload", files={"file": f})
            file_id = resp.json()["id"]

        logger.info("🔥 Starting stress test with %s concurrent users...", num_users)
        
        # 2. Execution: Launch users simultaneously
        tasks = [simulate_user(i, file_id, client) for i in range(num_users)]
        
        total_start = time.perf_counter()
        results = await asyncio.gather(*tasks)
        total_end = time.perf_counter()

        successes = [result for result in results if result["ok"]]
        failures = [result for result in results if not result["ok"]]
        latencies = [result["elapsed"] for result in successes if result["elapsed"] is not None]

        logger.info("✅ Stress test complete. Total time: %.2fs", total_end - total_start)
        logger.info("📈 Success: %s/%s | Failures: %s", len(successes), num_users, len(failures))

        if latencies:
            logger.info(
                "📊 Latency summary | min=%.2fs avg=%.2fs median=%.2fs max=%.2fs",
                min(latencies),
                statistics.mean(latencies),
                statistics.median(latencies),
                max(latencies),
            )

        if failures:
            logger.warning("⚠️ Failed user IDs: %s", [result["user_id"] for result in failures])

        return {
            "total_users": num_users,
            "successes": len(successes),
            "failures": len(failures),
            "total_time": total_end - total_start,
            "latencies": latencies,
        }

if __name__ == "__main__":
    asyncio.run(run_stress_test())