import pytest
from flowsentinel.feeds.simulated import SimulatedMempoolFeed, SimulatedLiquidityFeed
from flowsentinel.models import TxIntent, PoolState, OrderBookSnapshot

@pytest.mark.asyncio
async def test_simulated_mempool_feed():
    feed = SimulatedMempoolFeed(interval=0.01, include_sandwich=False)
    events = []
    
    # Read first 5 events from stream
    async for event in feed.stream():
        events.append(event)
        if len(events) >= 5:
            break
            
    assert len(events) == 5
    for event in events:
        assert isinstance(event, TxIntent)
        assert event.chain_id == 1
    
    feed.stop()

@pytest.mark.asyncio
async def test_simulated_liquidity_feed():
    feed = SimulatedLiquidityFeed(interval=0.01)
    events = []
    
    async for event in feed.stream():
        events.append(event)
        if len(events) >= 5:
            break
            
    assert len(events) == 5
    for event in events:
        assert isinstance(event, (PoolState, OrderBookSnapshot))
        
    feed.stop()
