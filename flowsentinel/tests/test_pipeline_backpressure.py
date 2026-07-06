import asyncio
import pytest
from typing import AsyncIterator, Union
from flowsentinel.feeds.base import Feed
from flowsentinel.models import TxIntent, PoolState, OrderBookSnapshot
from flowsentinel.pipeline import PipelineOrchestrator

class QuickDummyFeed(Feed):
    def __init__(self):
        self.count = 0

    async def stream(self) -> AsyncIterator[Union[TxIntent, PoolState, OrderBookSnapshot]]:
        while True:
            yield TxIntent(
                tx_hash=f"0x{self.count}",
                gas_price=50.0,
                gas_limit=21000,
                target_address="0xpool",
                value=1.0,
                input_data="0x",
                chain_id=1,
                timestamp=1000.0 + self.count,
                nonce=10 + self.count
            )
            self.count += 1
            await asyncio.sleep(0.001)

@pytest.mark.asyncio
async def test_pipeline_backpressure():
    # Setup mocks
    class MockClient:
        async def is_duplicate(self, *args): return False
        async def execute(self, *args): pass
    
    # Instantiate pipeline with a backpressure limit of 2
    orchestrator = PipelineOrchestrator(
        redis_client=MockClient(),
        timescale_client=MockClient(),
        sandwich_detector=None,
        liquidity_scorer=None,
        predictive_model=None,
        risk_classifier=None,
        narrative_generator=None,
        backpressure_limit=2
    )

    feed = QuickDummyFeed()
    orchestrator.register_feed(feed, semaphore_limit=5)
    orchestrator.running = True

    # Manual ingest loop start (without consumer loop!)
    # This will fill the queue up to 2 and then block
    ingest_task = asyncio.create_task(orchestrator._ingest_loop(feed, orchestrator.feeds[0][1]))
    
    # Wait a bit for the ingest loop to block
    await asyncio.sleep(0.1)

    # Queue size should be exactly 2
    assert orchestrator.queue.qsize() == 2
    # The feed should have generated more than 2 but only 2 are in the queue
    # The 3rd one is blocked waiting to put into the queue
    assert feed.count >= 2

    # Clean up
    ingest_task.cancel()
    try:
        await ingest_task
    except asyncio.CancelledError:
        pass
