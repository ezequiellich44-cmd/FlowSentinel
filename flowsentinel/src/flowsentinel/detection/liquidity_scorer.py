import time
import logging
from typing import Dict, List, Optional, Callable, Awaitable
from flowsentinel.models import PoolState, AnomalyCandidate

logger = logging.getLogger(__name__)

class LiquidityScorer:
    def __init__(self,
                 test_swap_size: float = 10.0,  # Hypothetical trade size in token0 units
                 impact_threshold: float = 0.05,  # 5% price impact threshold
                 on_anomaly: Optional[Callable[[AnomalyCandidate], Awaitable[None]]] = None):
        self.test_swap_size = test_swap_size
        self.impact_threshold = impact_threshold
        self.on_anomaly = on_anomaly
        self.latest_states: Dict[str, PoolState] = {}  # pool_address -> PoolState

    async def process_pool_state(self, state: PoolState) -> None:
        """
        Receives reserve updates, updates internal state, calculates price impact,
        and triggers anomaly candidate if impact exceeds threshold.
        """
        pool = state.pool_address
        self.latest_states[pool] = state

        # Calculate price impact on this pool for a constant product market maker (xy=k)
        # Price impact = delta_x / (reserve0 + delta_x)
        # where delta_x is our test swap size
        r0 = state.reserve0
        r1 = state.reserve1

        if r0 <= 0 or r1 <= 0:
            logger.warning("Invalid reserves for pool %s: r0=%s, r1=%s", pool, r0, r1)
            return

        # Price impact of buying token1 with test_swap_size of token0
        impact = self.test_swap_size / (r0 + self.test_swap_size)

        # Cross-venue analysis: if we have multiple pools for the same pair, we compare
        pair_key = f"{state.token0}/{state.token1}"
        
        # Log calculated impact
        logger.info("Liquidity pool %s (%s) | Pair: %s | Reserves: [%.2f, %.2f] | Test Swap Impact: %.4f", 
                    pool, state.exchange_name, pair_key, r0, r1, impact)

        if impact > self.impact_threshold:
            logger.warning("HIGH PRICE IMPACT DETECTED on pool %s: %.4f > %.4f", pool, impact, self.impact_threshold)
            
            anomaly = AnomalyCandidate(
                anomaly_id=f"liq_{int(time.time())}_{pool[:6]}",
                pattern_type="liquidity_drop",
                severity="medium" if impact < 0.15 else "high",
                pool_address=pool,
                related_txs=[],
                timestamp=time.time(),
                metadata={
                    "exchange_name": state.exchange_name,
                    "reserve0": r0,
                    "reserve1": r1,
                    "price_impact": impact,
                    "test_swap_size": self.test_swap_size,
                    "threshold": self.impact_threshold,
                    "pair": pair_key
                }
            )
            
            if self.on_anomaly:
                await self.on_anomaly(anomaly)
