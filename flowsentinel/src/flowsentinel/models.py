from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class TxIntent(BaseModel):
    tx_hash: str
    gas_price: float  # In Gwei
    gas_limit: int
    target_address: str  # e.g., the target pool or router contract
    value: float  # In ETH/native token
    input_data: str  # Hex data representing swap details
    chain_id: int
    timestamp: float
    nonce: int

class PoolState(BaseModel):
    pool_address: str
    exchange_name: str  # e.g., "UniswapV3" or "Sushiswap"
    reserve0: float
    reserve1: float
    token0: str
    token1: str
    slot0: Optional[Dict[str, Any]] = None  # Holds sqrtPriceX96, tick, etc.
    timestamp: float

class OrderBookSnapshot(BaseModel):
    pair: str  # e.g. "WETH/USDT"
    bids: List[List[float]]  # List of [price, size]
    asks: List[List[float]]  # List of [price, size]
    timestamp: float

class AnomalyCandidate(BaseModel):
    anomaly_id: str
    pattern_type: str  # e.g. "sandwich", "liquidity_drop", "arbitrage"
    severity: str  # "low", "medium", "high", "critical"
    pool_address: str
    related_txs: List[str]
    timestamp: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
