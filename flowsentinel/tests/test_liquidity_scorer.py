import pytest
from flowsentinel.models import PoolState, AnomalyCandidate
from flowsentinel.detection.liquidity_scorer import LiquidityScorer

@pytest.mark.asyncio
async def test_liquidity_scorer_anomalies():
    anomalies = []
    async def on_anomaly(candidate: AnomalyCandidate):
        anomalies.append(candidate)

    # Threshold of 5% (0.05). Swap size 10.
    # Impact = swap_size / (reserve0 + swap_size)
    # If reserve0 = 100, impact = 10 / (100 + 10) = 10 / 110 = 9.09% (triggers anomaly!)
    # If reserve0 = 1000, impact = 10 / 1010 = 0.99% (does NOT trigger)
    scorer = LiquidityScorer(test_swap_size=10.0, impact_threshold=0.05, on_anomaly=on_anomaly)

    # 1. Normal pool state (high depth)
    state_normal = PoolState(
        pool_address="0xNormalPool",
        exchange_name="UniswapV3",
        reserve0=1000.0,
        reserve1=3000000.0,
        token0="WETH",
        token1="USDT",
        timestamp=1000.0
    )
    await scorer.process_pool_state(state_normal)
    assert len(anomalies) == 0

    # 2. Low depth pool state (triggers anomaly)
    state_low = PoolState(
        pool_address="0xLowPool",
        exchange_name="Sushiswap",
        reserve0=100.0,
        reserve1=300000.0,
        token0="WETH",
        token1="USDT",
        timestamp=1001.0
    )
    await scorer.process_pool_state(state_low)
    
    assert len(anomalies) == 1
    assert anomalies[0].pool_address == "0xLowPool"
    assert anomalies[0].pattern_type == "liquidity_drop"
    assert anomalies[0].metadata["price_impact"] > 0.05
