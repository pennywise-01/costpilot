"""Test script to verify the concurrent login performance fix."""

import asyncio
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockBoto3Client:
    """Mock boto3 client that simulates AWS API latency."""
    
    def __init__(self, service_name, region=None):
        self.service_name = service_name
        self.region = region or "us-east-1"
    
    def get_caller_identity(self):
        """Simulate STS get_caller_identity call."""
        time.sleep(0.5)  # Simulate 500ms network latency
        return {"Account": "123456789012"}
    
    def get_cost_and_usage(self, **kwargs):
        """Simulate Cost Explorer call."""
        time.sleep(1.0)  # Simulate 1s API latency
        return {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2024-01-01", "End": "2024-01-31"},
                    "Total": {"UnblendedCost": {"Amount": "100.00", "Unit": "USD"}}
                }
            ]
        }


class FixedAWSAdapter:
    """Fixed AWS adapter using asyncio.to_thread for all blocking calls."""
    
    def __init__(self, config: dict):
        self.access_key_id = config.get("access_key_id", "")
        self.secret_access_key = config.get("secret_access_key", "")
        self.region = config.get("region", "us-east-1")
        self.account_id = ""
    
    def _get_client(self, service: str, region: str | None = None):
        return MockBoto3Client(service, region or self.region)
    
    async def validate_credentials(self) -> bool:
        """FIXED: Non-blocking credential validation."""
        return await asyncio.to_thread(self._validate_credentials_sync)
    
    def _validate_credentials_sync(self) -> bool:
        sts = self._get_client("sts")
        identity = sts.get_caller_identity()
        self.account_id = identity.get("Account", "")
        return True
    
    async def get_monthly_cost_summary(self) -> dict[str, float]:
        """FIXED: Non-blocking cost fetching."""
        cost_data = await asyncio.to_thread(self._get_cost_and_usage_sync)
        
        total_cost = 0.0
        for result in cost_data.get("ResultsByTime", []):
            total_cost += float(result.get("Total", {}).get("UnblendedCost", {}).get("Amount", 0))
        
        return {
            "this_month": round(total_cost, 2),
            "last_month": round(total_cost * 0.9, 2),
            "forecast": round(total_cost * 1.1, 2),
        }
    
    def _get_cost_and_usage_sync(self) -> dict:
        ce = self._get_client("ce", region="us-east-1")
        return ce.get_cost_and_usage(
            TimePeriod={"Start": "2024-01-01", "End": "2024-01-31"},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
        )


async def simulate_session_login(session_id: str, adapter: FixedAWSAdapter) -> float:
    """Simulate a full login session flow."""
    start = time.monotonic()
    logger.info(f"[{session_id}] Starting login flow...")
    
    # Step 1: Validate credentials (0.5s simulated)
    await adapter.validate_credentials()
    logger.info(f"[{session_id}] Credentials validated")
    
    # Step 2: Fetch cost summary (1.0s simulated)
    summary = await adapter.get_monthly_cost_summary()
    logger.info(f"[{session_id}] Cost summary fetched: ${summary['this_month']}")
    
    elapsed = time.monotonic() - start
    logger.info(f"[{session_id}] Login flow complete in {elapsed:.2f}s")
    return elapsed


async def test_concurrent_logins():
    """Test that multiple logins can happen concurrently."""
    logger.info("=" * 70)
    logger.info("TEST: Concurrent Login Performance with Fixed AWS Adapter")
    logger.info("=" * 70)
    
    # Create adapters for 3 different sessions
    adapters = [
        FixedAWSAdapter({
            "access_key_id": f"AKIA{ i }EXAMPLE",
            "secret_access_key": "secret",
            "region": "us-east-1",
        })
        for i in range(3)
    ]
    
    start = time.monotonic()
    
    # Run all 3 sessions concurrently
    tasks = [
        simulate_session_login(f"Session-{i+1}", adapters[i])
        for i in range(3)
    ]
    
    results = await asyncio.gather(*tasks)
    total_time = time.monotonic() - start
    
    logger.info("")
    logger.info("RESULTS:")
    logger.info(f"  Individual session times: {[f'{r:.2f}s' for r in results]}")
    logger.info(f"  Total time for all 3 sessions: {total_time:.2f}s")
    logger.info("")
    
    # Validate results
    expected_sequential = sum(results)  # If blocking, would be ~4.5s each
    expected_concurrent = max(results)  # With fix, should be ~1.5s
    
    logger.info(f"  Expected if blocking (sequential): ~{expected_sequential:.2f}s")
    logger.info(f"  Expected if non-blocking (concurrent): ~{expected_concurrent:.2f}s")
    logger.info(f"  Actual: {total_time:.2f}s")
    logger.info("")
    
    # Determine if fix is working
    if total_time < expected_sequential * 0.7:  # At least 30% faster than sequential
        logger.info("✅ SUCCESS: Sessions are running concurrently!")
        logger.info(f"   Improvement: {((expected_sequential - total_time) / expected_sequential * 100):.0f}% faster")
        return True
    else:
        logger.info("❌ FAILURE: Sessions are still blocking each other")
        return False


async def test_event_loop_not_blocked():
    """Test that the event loop isn't blocked during AWS calls."""
    logger.info("=" * 70)
    logger.info("TEST: Event Loop Not Blocked")
    logger.info("=" * 70)
    
    adapter = FixedAWSAdapter({
        "access_key_id": "AKIAEXAMPLE",
        "secret_access_key": "secret",
        "region": "us-east-1",
    })
    
    heartbeat_count = [0]
    last_heartbeat = [time.monotonic()]
    
    async def heartbeat():
        """Background task that should continue running even during AWS calls."""
        while True:
            await asyncio.sleep(0.1)  # 100ms heartbeat
            heartbeat_count[0] += 1
            now = time.monotonic()
            gap = now - last_heartbeat[0]
            last_heartbeat[0] = now
            
            # If gap is > 0.2s, the event loop was blocked
            if gap > 0.2:
                logger.warning(f"⚠️  Event loop blocked for {gap:.2f}s!")
    
    # Start heartbeat
    heartbeat_task = asyncio.create_task(heartbeat())
    
    try:
        # Run AWS operations
        logger.info("Starting AWS operations with background heartbeat...")
        start_count = heartbeat_count[0]
        
        await adapter.validate_credentials()  # 0.5s
        await adapter.get_monthly_cost_summary()  # 1.0s
        
        await asyncio.sleep(0.1)  # Let heartbeat catch up
        
        end_count = heartbeat_count[0]
        heartbeats_during = end_count - start_count
        
        logger.info(f"Heartbeats during AWS operations: {heartbeats_during}")
        
        # Should have ~15 heartbeats (1.5s / 0.1s)
        if heartbeats_during >= 10:
            logger.info("✅ SUCCESS: Event loop stayed responsive!")
            return True
        else:
            logger.info(f"❌ FAILURE: Only {heartbeats_during} heartbeats (expected ~15)")
            return False
            
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass


async def main():
    """Run all tests."""
    logger.info("\n" + "=" * 70)
    logger.info("AWS Adapter Concurrent Login Fix - Verification Tests")
    logger.info("=" * 70 + "\n")
    
    # Test 1: Concurrent logins
    concurrent_pass = await test_concurrent_logins()
    logger.info("")
    
    # Test 2: Event loop not blocked
    heartbeat_pass = await test_event_loop_not_blocked()
    logger.info("")
    
    # Summary
    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Concurrent Logins Test: {'✅ PASS' if concurrent_pass else '❌ FAIL'}")
    logger.info(f"Event Loop Test: {'✅ PASS' if heartbeat_pass else '❌ FAIL'}")
    
    if concurrent_pass and heartbeat_pass:
        logger.info("\n🎉 All tests passed! The fix is working correctly.")
        logger.info("   Multiple sessions can now login concurrently without blocking.")
    else:
        logger.info("\n⚠️  Some tests failed. The fix may need adjustment.")
    
    return concurrent_pass and heartbeat_pass


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
