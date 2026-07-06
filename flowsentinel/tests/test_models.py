import pytest
from pydantic import ValidationError
from flowsentinel.models import TxIntent, PoolState, OrderBookSnapshot, AnomalyCandidate

def test_tx_intent_validation():
    # Valid TxIntent
    tx = TxIntent(
        tx_hash="0x123",
        gas_price=50.0,
        gas_limit=21000,
        target_address="0xpool",
        value=1.0,
        input_data="0x",
        chain_id=1,
        timestamp=1000.0,
        nonce=10
    )
    assert tx.tx_hash == "0x123"
    assert tx.nonce == 10

    # Invalid TxIntent (missing field)
    with pytest.raises(ValidationError):
        TxIntent(tx_hash="0x123")

def test_pool_state_validation():
    state = PoolState(
        pool_address="0xpool",
        exchange_name="Uniswap",
        reserve0=10.0,
        reserve1=100.0,
        token0="WETH",
        token1="USDT",
        timestamp=1000.0
    )
    assert state.reserve0 == 10.0
    assert state.token0 == "WETH"

def test_orderbook_snapshot_validation():
    obs = OrderBookSnapshot(
        pair="WETH/USDT",
        bids=[[3000.0, 10.0]],
        asks=[[3005.0, 5.0]],
        timestamp=1000.0
    )
    assert obs.pair == "WETH/USDT"
    assert obs.bids[0][0] == 3000.0

def test_anomaly_candidate_validation():
    cand = AnomalyCandidate(
        anomaly_id="anomaly_1",
        pattern_type="sandwich",
        severity="high",
        pool_address="0xpool",
        related_txs=["0x1", "0x2"],
        timestamp=1000.0,
        metadata={"impact": 0.05}
    )
    assert cand.pattern_type == "sandwich"
    assert cand.metadata["impact"] == 0.05
