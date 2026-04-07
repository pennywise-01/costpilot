"""Request deduplication and coalescing module.

This module provides functionality to coalesce identical concurrent requests
into a single backend call, reducing load on external APIs and databases.
"""

import asyncio
import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, ParamSpec, TypeVar
from functools import wraps

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


@dataclass
class PendingRequest(Generic[T]):
    """Represents a pending request that multiple callers are waiting for."""
    future: asyncio.Future[T] = field(default_factory=lambda: asyncio.get_event_loop().create_future())
    waiters: int = 0
    started_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class RequestCoalescer(Generic[P, T]):
    """Coalesces identical concurrent requests into a single execution.
    
    When multiple callers request the same data simultaneously, only one
    actual call is made to the backend. All callers receive the same result.
    
    This is particularly useful for:
    - Expensive cloud API calls (AWS Cost Explorer, Azure Resource Graph, etc.)
    - Database queries that are slow but return the same data
    - Cache stampede prevention (thundering herd)
    
    Example:
        coalescer = RequestCoalescer()
        
        # Multiple concurrent calls will result in a single API call
        result1 = await coalescer.coalesce("aws_costs", fetch_aws_costs, org_id, start, end)
        result2 = await coalescer.coalesce("aws_costs", fetch_aws_costs, org_id, start, end)
    """

    def __init__(self, max_wait_seconds: float = 30.0):
        """Initialize request coalescer.
        
        Args:
            max_wait_seconds: Maximum time to wait for a pending request before timing out
        """
        self._max_wait = max_wait_seconds
        self._pending: dict[str, PendingRequest[T]] = {}
        self._lock = asyncio.Lock()

    def _make_key(self, prefix: str, args: tuple, kwargs: dict) -> str:
        """Generate a unique key for the request."""
        key_data = f"{prefix}:{json.dumps(args, sort_keys=True, default=str)}:{json.dumps(kwargs, sort_keys=True, default=str)}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    async def coalesce(
        self,
        prefix: str,
        func: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs
    ) -> T:
        """Execute function with request coalescing.
        
        If an identical request is already in flight, wait for its result
        instead of making a duplicate call.
        
        Args:
            prefix: Prefix to identify this type of request
            func: Async function to execute
            *args: Positional arguments to pass to func
            **kwargs: Keyword arguments to pass to func
            
        Returns:
            Result from func execution (shared with all concurrent callers)
        """
        request_key = self._make_key(prefix, args, kwargs)
        
        async with self._lock:
            # Check if there's already a pending request
            if request_key in self._pending:
                pending = self._pending[request_key]
                pending.waiters += 1
                logger.debug(f"Coalescing into existing request: {prefix} ({pending.waiters} waiters)")
                
                # Wait for the existing request to complete
                future = pending.future
            else:
                # Create new pending request
                pending = PendingRequest[T]()
                pending.waiters = 1
                self._pending[request_key] = pending
                future = pending.future
                
                # Start the execution
                logger.debug(f"Starting new coalesced request: {prefix}")
                asyncio.create_task(self._execute(request_key, func, *args, **kwargs))
        
        # Wait for result (outside lock to allow concurrent waiting)
        try:
            return await asyncio.wait_for(future, timeout=self._max_wait)
        except asyncio.TimeoutError:
            logger.warning(f"Request coalescing timeout: {prefix}")
            raise

    async def _execute(
        self,
        request_key: str,
        func: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs
    ) -> None:
        """Execute the function and notify all waiters."""
        pending = self._pending.get(request_key)
        if not pending:
            return
        
        try:
            # Execute the actual function
            result = await func(*args, **kwargs)
            
            # Set the result on the future (wakes up all waiters)
            if not pending.future.done():
                pending.future.set_result(result)
                
        except Exception as e:
            logger.error(f"Coalesced request failed: {e}")
            # Set the exception on the future
            if not pending.future.done():
                pending.future.set_exception(e)
        finally:
            # Clean up
            async with self._lock:
                self._pending.pop(request_key, None)

    def get_stats(self) -> dict[str, Any]:
        """Get current coalescer statistics."""
        return {
            "pending_requests": len(self._pending),
            "requests": [
                {
                    "waiters": p.waiters,
                    "started_at": p.started_at,
                    "age_seconds": asyncio.get_event_loop().time() - p.started_at
                }
                for p in self._pending.values()
            ]
        }


# Global coalescer instances by prefix
_coalescers: dict[str, RequestCoalescer] = {}


def get_coalescer(prefix: str, max_wait_seconds: float = 30.0) -> RequestCoalescer:
    """Get or create a coalescer for a specific prefix.
    
    Args:
        prefix: Unique prefix for this coalescer type
        max_wait_seconds: Maximum wait time for pending requests
        
    Returns:
        RequestCoalescer instance
    """
    if prefix not in _coalescers:
        _coalescers[prefix] = RequestCoalescer(max_wait_seconds)
    return _coalescers[prefix]


def coalesced(
    prefix: str,
    max_wait_seconds: float = 30.0
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to enable request coalescing for a function.
    
    Usage:
        @coalesced("aws_costs", max_wait_seconds=30)
        async def fetch_aws_costs(org_id: str, start_date: str, end_date: str):
            # Expensive API call that should be coalesced
            return await aws_client.get_cost_and_usage(...)
    
    Args:
        prefix: Unique prefix to identify this type of request
        max_wait_seconds: Maximum time to wait for pending requests
        
    Returns:
        Decorated function with coalescing
    """
    coalescer = get_coalescer(prefix, max_wait_seconds)
    
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await coalescer.coalesce(prefix, func, *args, **kwargs)
        
        # Attach stats method
        wrapper.get_coalescer_stats = coalescer.get_stats
        
        return wrapper
    return decorator


class CoalescedBatchExecutor(Generic[T]):
    """Batches multiple requests and executes them together.
    
    Useful for APIs that support batch operations or when you want to
    reduce the number of individual API calls.
    
    Example:
        executor = CoalescedBatchExecutor(batch_size=10, max_wait_ms=50)
        
        # These will be batched into a single call
        result1 = await executor.submit("item1")
        result2 = await executor.submit("item2")
        # ... etc
    """

    def __init__(
        self,
        batch_processor: Callable[[list[str]], T],
        batch_size: int = 10,
        max_wait_ms: float = 50.0
    ):
        """Initialize batch executor.
        
        Args:
            batch_processor: Function to process a batch of items
            batch_size: Maximum number of items per batch
            max_wait_ms: Maximum time to wait before processing a partial batch
        """
        self._batch_processor = batch_processor
        self._batch_size = batch_size
        self._max_wait = max_wait_ms / 1000.0  # Convert to seconds
        
        self._pending: list[tuple[str, asyncio.Future[T]]] = []
        self._lock = asyncio.Lock()
        self._timer: asyncio.Task | None = None

    async def submit(self, item: str) -> T:
        """Submit an item to be processed in a batch.
        
        Args:
            item: Item identifier to process
            
        Returns:
            Result for this item
        """
        future = asyncio.get_event_loop().create_future()
        
        async with self._lock:
            self._pending.append((item, future))
            
            # Check if we should process immediately
            if len(self._pending) >= self._batch_size:
                await self._process_batch()
            elif self._timer is None:
                # Start timer for partial batch
                self._timer = asyncio.create_task(self._timer_callback())
        
        return await future

    async def _timer_callback(self) -> None:
        """Timer callback to process partial batches."""
        await asyncio.sleep(self._max_wait)
        async with self._lock:
            if self._pending:
                await self._process_batch()
            self._timer = None

    async def _process_batch(self) -> None:
        """Process the current batch of pending items."""
        if not self._pending:
            return
        
        batch = self._pending[:self._batch_size]
        self._pending = self._pending[self._batch_size:]
        
        items = [item for item, _ in batch]
        futures = [f for _, f in batch]
        
        try:
            results = await self._batch_processor(items)
            
            # Distribute results to futures
            for future, result in zip(futures, results):
                if not future.done():
                    future.set_result(result)
        except Exception as e:
            # Fail all futures
            for future in futures:
                if not future.done():
                    future.set_exception(e)


# Specific coalescers for common operations

# Cloud costs coalescer - combines identical cost queries
cloud_costs_coalescer = RequestCoalescer(max_wait_seconds=45.0)

# Resource discovery coalescer - combines identical resource queries  
resource_discovery_coalescer = RequestCoalescer(max_wait_seconds=60.0)

# Recommendations coalescer - combines identical recommendation queries
recommendations_coalescer = RequestCoalescer(max_wait_seconds=45.0)


async def coalesce_cloud_costs(
    func: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs
) -> T:
    """Coalesce cloud cost API calls.
    
    Args:
        func: Function to execute
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Function result (shared with concurrent callers)
    """
    return await cloud_costs_coalescer.coalesce("cloud_costs", func, *args, **kwargs)


async def coalesce_resource_discovery(
    func: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs
) -> T:
    """Coalesce resource discovery API calls.
    
    Args:
        func: Function to execute
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Function result (shared with concurrent callers)
    """
    return await resource_discovery_coalescer.coalesce("resource_discovery", func, *args, **kwargs)


async def coalesce_recommendations(
    func: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs
) -> T:
    """Coalesce recommendations API calls.
    
    Args:
        func: Function to execute
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Function result (shared with concurrent callers)
    """
    return await recommendations_coalescer.coalesce("recommendations", func, *args, **kwargs)
