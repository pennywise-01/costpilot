"""Debug script to test concurrent login performance and identify blocking calls."""

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


async def simulate_login_request(session_name: str, delay_seconds: float = 0):
    """Simulate a login request with timing."""
    start = time.monotonic()
    logger.info(f"[{session_name}] Login request START at {datetime.now().isoformat()}")
    
    # Simulate the actual login flow timing
    await asyncio.sleep(delay_seconds)
    
    elapsed = time.monotonic() - start
    logger.info(f"[{session_name}] Login request END - took {elapsed:.2f}s")
    return elapsed


async def simulate_blocking_aws_call(session_name: str, block_duration: float = 3.0):
    """Simulate a blocking boto3 call (synchronous)."""
    start = time.monotonic()
    logger.info(f"[{session_name}] AWS API call START (blocking for {block_duration}s)")
    
    # This simulates the blocking boto3 call - uses time.sleep which blocks the thread
    time.sleep(block_duration)
    
    elapsed = time.monotonic() - start
    logger.info(f"[{session_name}] AWS API call END - took {elapsed:.2f}s")
    return elapsed


async def simulate_non_blocking_aws_call(session_name: str, block_duration: float = 3.0):
    """Simulate a non-blocking boto3 call using asyncio.to_thread."""
    start = time.monotonic()
    logger.info(f"[{session_name}] AWS API call START (non-blocking for {block_duration}s)")
    
    # This is the proper way - runs sync code in thread pool
    await asyncio.to_thread(time.sleep, block_duration)
    
    elapsed = time.monotonic() - start
    logger.info(f"[{session_name}] AWS API call END - took {elapsed:.2f}s")
    return elapsed


async def test_blocking_behavior():
    """Test the current blocking behavior (what's happening now)."""
    logger.info("=" * 60)
    logger.info("TEST 1: Current Blocking Behavior (BUG)")
    logger.info("=" * 60)
    
    start = time.monotonic()
    
    # Simulate Session A logging in and making AWS calls (blocking)
    # Then Session B trying to login while Session A is blocked
    
    # Fire both tasks concurrently
    task_a = asyncio.create_task(simulate_blocking_aws_call("Session-A", 3.0))
    await asyncio.sleep(0.1)  # Small delay to ensure A starts first
    task_b = asyncio.create_task(simulate_login_request("Session-B", 0.5))
    
    await task_a
    await task_b
    
    total = time.monotonic() - start
    logger.info(f"TOTAL TIME (blocking): {total:.2f}s")
    logger.info("Expected with blocking: ~3.5s (Session B waits for Session A's AWS call)")
    logger.info("")


async def test_non_blocking_behavior():
    """Test the fixed non-blocking behavior."""
    logger.info("=" * 60)
    logger.info("TEST 2: Fixed Non-Blocking Behavior")
    logger.info("=" * 60)
    
    start = time.monotonic()
    
    # Fire both tasks concurrently with proper async handling
    task_a = asyncio.create_task(simulate_non_blocking_aws_call("Session-A", 3.0))
    await asyncio.sleep(0.1)  # Small delay to ensure A starts first
    task_b = asyncio.create_task(simulate_login_request("Session-B", 0.5))
    
    await task_a
    await task_b
    
    total = time.monotonic() - start
    logger.info(f"TOTAL TIME (non-blocking): {total:.2f}s")
    logger.info("Expected with non-blocking: ~3.1s (concurrent execution)")
    logger.info("")


async def test_login_flow_with_expensive_calls():
    """Simulate the full login -> dashboard flow with expensive cloud calls."""
    logger.info("=" * 60)
    logger.info("TEST 3: Full Dashboard Load (Multiple Expensive Calls)")
    logger.info("=" * 60)
    
    async def session_flow(session_name: str, use_blocking: bool):
        """Full session flow: login -> org select -> dashboard data."""
        flow_start = time.monotonic()
        
        # 1. Login (fast)
        await simulate_login_request(session_name, 0.1)
        
        # 2. Organization list (fast)
        logger.info(f"[{session_name}] Fetching organizations...")
        await asyncio.sleep(0.05)
        
        # 3. Dashboard data (expensive - multiple cloud calls)
        logger.info(f"[{session_name}] Fetching dashboard data...")
        
        # Simulate 5 parallel expensive cloud calls
        calls = []
        for i in range(5):
            if use_blocking:
                calls.append(simulate_blocking_aws_call(f"{session_name}/call-{i}", 2.0))
            else:
                calls.append(simulate_non_blocking_aws_call(f"{session_name}/call-{i}", 2.0))
        
        await asyncio.gather(*calls)
        
        flow_elapsed = time.monotonic() - flow_start
        logger.info(f"[{session_name}] COMPLETE - Total flow time: {flow_elapsed:.2f}s")
        return flow_elapsed
    
    # Test with blocking (current bug)
    logger.info("--- With BLOCKING calls (BUG) ---")
    start = time.monotonic()
    await asyncio.gather(
        session_flow("Session-A", use_blocking=True),
        session_flow("Session-B", use_blocking=True),
    )
    blocking_total = time.monotonic() - start
    logger.info(f"Both sessions complete in {blocking_total:.2f}s")
    logger.info("")
    
    # Test with non-blocking (fixed)
    logger.info("--- With NON-BLOCKING calls (FIXED) ---")
    start = time.monotonic()
    await asyncio.gather(
        session_flow("Session-A", use_blocking=False),
        session_flow("Session-B", use_blocking=False),
    )
    non_blocking_total = time.monotonic() - start
    logger.info(f"Both sessions complete in {non_blocking_total:.2f}s")


async def main():
    """Run all diagnostic tests."""
    logger.info("Concurrent Login Performance Diagnostic")
    logger.info("This demonstrates why login is slow with multiple sessions\n")
    
    await test_blocking_behavior()
    await asyncio.sleep(0.5)
    
    await test_non_blocking_behavior()
    await asyncio.sleep(0.5)
    
    await test_login_flow_with_expensive_calls()
    
    logger.info("\n" + "=" * 60)
    logger.info("CONCLUSION:")
    logger.info("=" * 60)
    logger.info("The blocking boto3 calls in AWSAdapter prevent concurrent execution.")
    logger.info("Fix: Wrap all boto3 calls in asyncio.to_thread()")


if __name__ == "__main__":
    asyncio.run(main())
