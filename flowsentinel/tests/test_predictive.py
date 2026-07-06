import asyncio
import pytest
from flowsentinel.models import PoolState, AnomalyCandidate
from flowsentinel.detection.predictive import LiquidityPredictiveModel

@pytest.mark.asyncio
async def test_predictive_liquidity_depletion():
    anomalies = []
    async def on_anomaly(candidate: AnomalyCandidate):
        anomalies.append(candidate)

    # Instantiate model with depletion time threshold of 60 seconds
    model = LiquidityPredictiveModel(lambda_decay=0.9, depletion_time_threshold_seconds=60.0, on_anomaly=on_anomaly)
    pool = "0xPredictivePool"

    # Feed sequence of states with decreasing reserves to simulate depletion
    # Initial reserve = 100
    # Reserve decrements by 5 units per step. After 10 steps (elapsed time = 10s), reserve is 50.
    # Linear projection: reserve = 100 - 5 * t
    # Slope is -5.0. 10% reserve threshold = 10.
    # Projected depletion time: 10 = 100 - 5 * t_target => 5 * t_target = 90 => t_target = 18.
    # Time to depletion at t = 10 is 18 - 10 = 8 seconds. This is < 60s threshold, so it should trigger anomaly!
    
    # We simulate a tight loop with small sleeps (or fake elapsed times by mocking time)
    # To keep it simple without mocking time.time directly, we can just feed states with a small real sleep
    # Or feed them quickly. But since the code uses time.time(), a small real sleep of 0.01s is fine,
    # or we can mock time.time in the test! Let's mock time.time to make it completely deterministic and super fast.
    
    import time
    from unittest.mock import patch
    
    start_time = 1000.0
    mock_times = [start_time + i * 1.0 for i in range(15)] # 1s intervals
    
    # Let's feed states corresponding to reserves: 100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40...
    reserves = [100.0 - 5.0 * i for i in range(15)]
    
    with patch("time.time") as mock_time:
        for idx, (m_time, m_res) in enumerate(zip(mock_times, reserves)):
            mock_time.return_value = m_time
            state = PoolState(
                pool_address=pool,
                exchange_name="Uniswap",
                reserve0=m_res,
                reserve1=10000.0,
                token0="WETH",
                token1="USDT",
                timestamp=m_time
            )
            await model.process_pool_state(state)
            
    # We should have triggered an anomaly candidate because slope is negative and depletion time is short
    assert len(anomalies) > 0
    last_anomaly = anomalies[-1]
    assert last_anomaly.pool_address == pool
    assert last_anomaly.pattern_type == "liquidity_depletion_prediction"
    assert last_anomaly.metadata["slope"] < 0
    assert last_anomaly.metadata["time_to_depletion"] > 0
