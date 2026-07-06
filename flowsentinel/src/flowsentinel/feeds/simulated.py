import asyncio
import time
import random
from typing import AsyncIterator, Union
from flowsentinel.models import TxIntent, PoolState, OrderBookSnapshot
from flowsentinel.feeds.base import Feed

class SimulatedMempoolFeed(Feed):
    def __init__(self, interval: float = 0.5, include_sandwich: bool = True):
        self.interval = interval
        self.include_sandwich = include_sandwich
        self._running = True

    async def stream(self) -> AsyncIterator[Union[TxIntent, PoolState, OrderBookSnapshot]]:
        counter = 0
        pool_address = "0xPoolA"
        
        while self._running:
            # Occasionally generate a sandwich sequence if configured
            if self.include_sandwich and random.random() < 0.2:
                # Generate a sandwich sequence: Frontrun, Victim, Backrun
                now = time.time()
                attacker_nonce = random.randint(1000, 9000)
                victim_nonce = random.randint(10000, 90000)
                
                # 1. Frontrun Tx (Attacker buying X for Y, high gas price)
                frontrun = TxIntent(
                    tx_hash=f"0xfront_{counter}",
                    gas_price=150.0 + random.uniform(0, 10),
                    gas_limit=150000,
                    target_address=pool_address,
                    value=1.5,
                    input_data="0x123456_swap_X_for_Y",
                    chain_id=1,
                    timestamp=now,
                    nonce=attacker_nonce
                )
                yield frontrun
                await asyncio.sleep(0.05)
                
                # 2. Victim Tx (Victim buying X for Y, normal gas price)
                victim = TxIntent(
                    tx_hash=f"0xvictim_{counter}",
                    gas_price=50.0 + random.uniform(-2, 2),
                    gas_limit=150000,
                    target_address=pool_address,
                    value=5.0,
                    input_data="0x123456_swap_X_for_Y",
                    chain_id=1,
                    timestamp=now + 0.05,
                    nonce=victim_nonce
                )
                yield victim
                await asyncio.sleep(0.05)
                
                # 3. Backrun Tx (Attacker selling Y for X, low/normal gas price, consecutive nonce)
                backrun = TxIntent(
                    tx_hash=f"0xback_{counter}",
                    gas_price=45.0 + random.uniform(0, 2),
                    gas_limit=150000,
                    target_address=pool_address,
                    value=1.5,
                    input_data="0x654321_swap_Y_for_X",
                    chain_id=1,
                    timestamp=now + 0.1,
                    nonce=attacker_nonce + 1
                )
                yield backrun
                counter += 1
            else:
                # Generate normal transaction intents
                now = time.time()
                normal_tx = TxIntent(
                    tx_hash=f"0xnormal_{random.randint(100000, 999999)}",
                    gas_price=50.0 + random.uniform(-5, 5),
                    gas_limit=80000,
                    target_address=random.choice(["0xPoolA", "0xPoolB"]),
                    value=random.uniform(0.1, 2.0),
                    input_data="0xabcdef_transfer",
                    chain_id=1,
                    timestamp=now,
                    nonce=random.randint(10000, 50000)
                )
                yield normal_tx
            
            await asyncio.sleep(self.interval)

    def stop(self) -> None:
        self._running = False


class SimulatedLiquidityFeed(Feed):
    def __init__(self, interval: float = 0.8):
        self.interval = interval
        self._running = True

    async def stream(self) -> AsyncIterator[Union[TxIntent, PoolState, OrderBookSnapshot]]:
        pools = [
            ("0xPoolA", "UniswapV3", "WETH", "USDT", 100.0, 300000.0),
            ("0xPoolB", "Sushiswap", "WETH", "USDT", 80.0, 240000.0),
        ]
        
        while self._running:
            now = time.time()
            # Randomly select a pool and mutate its reserves
            pool_addr, exchange, t0, t1, r0, r1 = random.choice(pools)
            
            # Simulate a reserve fluctuation
            r0_mut = r0 * random.uniform(0.95, 1.05)
            r1_mut = r1 * random.uniform(0.95, 1.05)
            
            pool_state = PoolState(
                pool_address=pool_addr,
                exchange_name=exchange,
                reserve0=r0_mut,
                reserve1=r1_mut,
                token0=t0,
                token1=t1,
                slot0={"sqrtPriceX96": str(int(random.uniform(70000, 80000))), "tick": random.randint(-20000, 20000)},
                timestamp=now
            )
            yield pool_state
            
            # Occasionally emit an OrderBookSnapshot
            if random.random() < 0.5:
                # Generate matching orderbook depth
                mid_price = r1_mut / r0_mut
                bids = [[mid_price * (1 - 0.001 * i), random.uniform(1.0, 10.0)] for i in range(1, 6)]
                asks = [[mid_price * (1 + 0.001 * i), random.uniform(1.0, 10.0)] for i in range(1, 6)]
                
                obs = OrderBookSnapshot(
                    pair=f"{t0}/{t1}",
                    bids=bids,
                    asks=asks,
                    timestamp=now
                )
                yield obs
            
            await asyncio.sleep(self.interval)

    def stop(self) -> None:
        self._running = False
