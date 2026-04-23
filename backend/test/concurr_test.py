import asyncio
import httpx
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
        
        if response.status_code == 200:
            logger.info(f"👤 User {user_id} finished in {end - start:.2f}s")
        else:
            logger.error(f"❌ User {user_id} failed with status {response.status_code}")
    except Exception as e:
        logger.error(f"🚨 User {user_id} connection error: {e}")

async def run_stress_test(num_users=5):
    async with httpx.AsyncClient() as client:
        # 1. Setup: Upload file
        with open(FILE_PATH, "rb") as f:
            resp = await client.post(f"{BASE_URL}/files/upload", files={"file": f})
            file_id = resp.json()["id"]

        logger.info(f"🔥 Starting stress test with {num_users} concurrent users...")
        
        # 2. Execution: Launch users simultaneously
        tasks = [simulate_user(i, file_id, client) for i in range(num_users)]
        
        total_start = time.perf_counter()
        await asyncio.gather(*tasks)
        total_end = time.perf_counter()
        
        logger.info(f"✅ Stress test complete. Total time: {total_end - total_start:.2f}s")

if __name__ == "__main__":
    asyncio.run(run_stress_test())