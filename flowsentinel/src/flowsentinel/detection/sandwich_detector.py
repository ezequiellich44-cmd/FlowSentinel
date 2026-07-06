import asyncio
import time
import logging
from typing import Dict, List, Set, Union, Callable, Awaitable, Optional
from flowsentinel.models import TxIntent, AnomalyCandidate

logger = logging.getLogger(__name__)

class SandwichDetector:
    def __init__(self, 
                 window_seconds: float = 5.0, 
                 gas_percentile_threshold: float = 80.0,
                 on_anomaly: Optional[Callable[[AnomalyCandidate], Awaitable[None]]] = None):
        self.window_seconds = window_seconds
        self.gas_percentile_threshold = gas_percentile_threshold
        self.on_anomaly = on_anomaly
        self.pool_queues: Dict[str, asyncio.Queue] = {}
        self.pool_tasks: Dict[str, asyncio.Task] = {}
        self.detected_triples: Set[str] = set()  # Store hashes of detected sandwich triples to avoid duplicate alerts

    async def process_intent(self, intent: TxIntent) -> None:
        """
        Pushes the TxIntent into the queue for its target pool.
        Spawns a watcher task for the pool if it doesn't exist yet.
        """
        pool = intent.target_address
        if pool not in self.pool_queues:
            queue = asyncio.Queue()
            self.pool_queues[pool] = queue
            task = asyncio.create_task(self._watch_pool(pool, queue))
            self.pool_tasks[pool] = task
            logger.info("Spawned sandwich watch task for pool %s", pool)
            
        await self.pool_queues[pool].put(intent)

    async def _watch_pool(self, pool: str, queue: asyncio.Queue) -> None:
        """
        Monitors a single pool for sandwich attack patterns.
        """
        history: List[TxIntent] = []
        
        try:
            while True:
                # Wait for next intent or check window periodically
                try:
                    # Non-blocking check for new items or timeout to clean up window
                    intent = await asyncio.wait_for(queue.get(), timeout=1.0)
                    history.append(intent)
                except asyncio.TimeoutError:
                    pass

                # Clean up expired items in history based on the latest transaction timestamp
                latest_time = max(tx.timestamp for tx in history)
                history = [tx for tx in history if latest_time - tx.timestamp <= self.window_seconds]
                if not history:
                    continue

                # Sort by timestamp
                history.sort(key=lambda tx: tx.timestamp)

                # Need at least 3 transactions to search for a sandwich
                if len(history) < 3:
                    continue

                # Analyze all triples
                for i in range(len(history)):
                    for j in range(i + 1, len(history)):
                        for k in range(j + 1, len(history)):
                            tx1 = history[i]  # potential frontrun
                            tx2 = history[j]  # potential victim
                            tx3 = history[k]  # potential backrun

                            # Create unique identifier for this triple to prevent duplicate detection
                            triple_id = f"{tx1.tx_hash}:{tx2.tx_hash}:{tx3.tx_hash}"
                            if triple_id in self.detected_triples:
                                continue

                            # Check conditions for a sandwich attack:
                            # 1. Attacker nonce proximity: backrun nonce must be consecutive to frontrun nonce
                            # (usually from the same account, so backrun.nonce == frontrun.nonce + 1)
                            # 2. Gas price rule: Frontrun gas price must be higher than victim,
                            # and backrun gas price should be lower/normal (less than frontrun)
                            # 3. Target addresses must match (already guaranteed since they are in the same pool queue)
                            # 4. Temporal proximity (all within the sliding window, e.g. 5 seconds)
                            
                            is_nonce_consecutive = (tx3.nonce == tx1.nonce + 1)
                            is_gas_sandwich = (tx1.gas_price > tx2.gas_price) and (tx1.gas_price > tx3.gas_price)
                            
                            # Additional checks on direction:
                            # Typically frontrun & victim swap in the same direction, backrun in the opposite direction.
                            # We can check input data containing tokens/swap directions
                            is_direction_valid = ("swap_X_for_Y" in tx1.input_data and 
                                                  "swap_X_for_Y" in tx2.input_data and 
                                                  "swap_Y_for_X" in tx3.input_data) or \
                                                 ("swap_Y_for_X" in tx1.input_data and 
                                                  "swap_Y_for_X" in tx2.input_data and 
                                                  "swap_X_for_Y" in tx3.input_data)
                            
                            # For simulated feeds, or general match
                            if is_nonce_consecutive and is_gas_sandwich and is_direction_valid:
                                # We found a sandwich!
                                self.detected_triples.add(triple_id)
                                logger.warning("SANDWICH DETECTED on pool %s: Frontrun=%s (Gas=%s), Victim=%s (Gas=%s), Backrun=%s (Gas=%s)", 
                                               pool, tx1.tx_hash, tx1.gas_price, tx2.tx_hash, tx2.gas_price, tx3.tx_hash, tx3.gas_price)

                                candidate = AnomalyCandidate(
                                    anomaly_id=f"sand_{int(time.time())}_{random_id()}",
                                    pattern_type="sandwich",
                                    severity="high",
                                    pool_address=pool,
                                    related_txs=[tx1.tx_hash, tx2.tx_hash, tx3.tx_hash],
                                    timestamp=tx2.timestamp,
                                    metadata={
                                        "frontrun_gas": tx1.gas_price,
                                        "victim_gas": tx2.gas_price,
                                        "backrun_gas": tx3.gas_price,
                                        "frontrun_nonce": tx1.nonce,
                                        "backrun_nonce": tx3.nonce,
                                        "victim_nonce": tx2.nonce,
                                        "pool_address": pool
                                    }
                                )
                                if self.on_anomaly:
                                    await self.on_anomaly(candidate)

        except asyncio.CancelledError:
            logger.info("Sandwich watch task for pool %s cancelled", pool)
            raise

    async def stop(self) -> None:
        """
        Cancels all active pool watching tasks.
        """
        for pool, task in self.pool_tasks.items():
            task.cancel()
        await asyncio.gather(*self.pool_tasks.values(), return_exceptions=True)
        self.pool_tasks.clear()
        self.pool_queues.clear()

def random_id() -> str:
    import random
    return f"{random.randint(1000, 9999)}"
