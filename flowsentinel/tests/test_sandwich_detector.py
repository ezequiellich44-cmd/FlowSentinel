import asyncio
import time
import pytest
from flowsentinel.models import TxIntent, AnomalyCandidate
from flowsentinel.detection.sandwich_detector import SandwichDetector

@pytest.mark.asyncio
async def test_sandwich_detector_accuracy():
    detected_anomalies = []
    
    async def on_anomaly(candidate: AnomalyCandidate):
        detected_anomalies.append(candidate)

    # Use window of 2.0 seconds
    detector = SandwichDetector(window_seconds=2.0, on_anomaly=on_anomaly)
    
    pool = "0xPoolA"
    now = time.time()

    # --- 5 VALID SANDWICH SEQUENCES (spaced out by 10 seconds each) ---
    
    # Sandwich 1: Basic valid sandwich (T=now + 0)
    t1 = now + 0.0
    s1_front = TxIntent(tx_hash="s1_front", gas_price=100.0, gas_limit=150000, target_address=pool, value=1.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t1, nonce=100)
    s1_victim = TxIntent(tx_hash="s1_victim", gas_price=50.0, gas_limit=150000, target_address=pool, value=2.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t1 + 0.1, nonce=500)
    s1_back = TxIntent(tx_hash="s1_back", gas_price=40.0, gas_limit=150000, target_address=pool, value=1.0, input_data="swap_Y_for_X", chain_id=1, timestamp=t1 + 0.2, nonce=101)

    # Sandwich 2: Different gas values, consecutive nonces 200/201 (T=now + 10)
    t2 = now + 10.0
    s2_front = TxIntent(tx_hash="s2_front", gas_price=120.0, gas_limit=150000, target_address=pool, value=1.5, input_data="swap_X_for_Y", chain_id=1, timestamp=t2, nonce=200)
    s2_victim = TxIntent(tx_hash="s2_victim", gas_price=80.0, gas_limit=150000, target_address=pool, value=3.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t2 + 0.1, nonce=600)
    s2_back = TxIntent(tx_hash="s2_back", gas_price=45.0, gas_limit=150000, target_address=pool, value=1.5, input_data="swap_Y_for_X", chain_id=1, timestamp=t2 + 0.2, nonce=201)

    # Sandwich 3: Swap direction Y->X for frontrun & victim, X->Y for backrun (T=now + 20)
    t3 = now + 20.0
    s3_front = TxIntent(tx_hash="s3_front", gas_price=150.0, gas_limit=150000, target_address=pool, value=0.5, input_data="swap_Y_for_X", chain_id=1, timestamp=t3, nonce=300)
    s3_victim = TxIntent(tx_hash="s3_victim", gas_price=50.0, gas_limit=150000, target_address=pool, value=1.0, input_data="swap_Y_for_X", chain_id=1, timestamp=t3 + 0.1, nonce=700)
    s3_back = TxIntent(tx_hash="s3_back", gas_price=49.0, gas_limit=150000, target_address=pool, value=0.5, input_data="swap_X_for_Y", chain_id=1, timestamp=t3 + 0.2, nonce=301)

    # Sandwich 4: Valid sandwich with victim having high but lower than frontrun gas price (T=now + 30)
    t4 = now + 30.0
    s4_front = TxIntent(tx_hash="s4_front", gas_price=200.0, gas_limit=150000, target_address=pool, value=2.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t4, nonce=400)
    s4_victim = TxIntent(tx_hash="s4_victim", gas_price=120.0, gas_limit=150000, target_address=pool, value=8.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t4 + 0.1, nonce=800)
    s4_back = TxIntent(tx_hash="s4_back", gas_price=110.0, gas_limit=150000, target_address=pool, value=2.0, input_data="swap_Y_for_X", chain_id=1, timestamp=t4 + 0.2, nonce=401)

    # Sandwich 5: Valid sandwich with very tight timestamps (T=now + 40)
    t5 = now + 40.0
    s5_front = TxIntent(tx_hash="s5_front", gas_price=90.0, gas_limit=150000, target_address=pool, value=0.2, input_data="swap_X_for_Y", chain_id=1, timestamp=t5, nonce=500)
    s5_victim = TxIntent(tx_hash="s5_victim", gas_price=60.0, gas_limit=150000, target_address=pool, value=0.5, input_data="swap_X_for_Y", chain_id=1, timestamp=t5 + 0.02, nonce=900)
    s5_back = TxIntent(tx_hash="s5_back", gas_price=30.0, gas_limit=150000, target_address=pool, value=0.2, input_data="swap_Y_for_X", chain_id=1, timestamp=t5 + 0.04, nonce=501)

    # --- 5 INVALID SEQUENCES (spaced out, should not trigger) ---

    # Invalid 1: Non-consecutive attacker nonces (1000 and 1002) (T=now + 50)
    t6 = now + 50.0
    i1_front = TxIntent(tx_hash="i1_front", gas_price=100.0, gas_limit=150000, target_address=pool, value=1.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t6, nonce=1000)
    i1_victim = TxIntent(tx_hash="i1_victim", gas_price=50.0, gas_limit=150000, target_address=pool, value=2.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t6 + 0.1, nonce=5000)
    i1_back = TxIntent(tx_hash="i1_back", gas_price=40.0, gas_limit=150000, target_address=pool, value=1.0, input_data="swap_Y_for_X", chain_id=1, timestamp=t6 + 0.2, nonce=1002)

    # Invalid 2: Backrun gas higher than frontrun gas (T=now + 60)
    t7 = now + 60.0
    i2_front = TxIntent(tx_hash="i2_front", gas_price=100.0, gas_limit=150000, target_address=pool, value=1.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t7, nonce=2000)
    i2_victim = TxIntent(tx_hash="i2_victim", gas_price=50.0, gas_limit=150000, target_address=pool, value=2.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t7 + 0.1, nonce=6000)
    i2_back = TxIntent(tx_hash="i2_back", gas_price=110.0, gas_limit=150000, target_address=pool, value=1.0, input_data="swap_Y_for_X", chain_id=1, timestamp=t7 + 0.2, nonce=2001)

    # Invalid 3: Mismatching swap directions (backrun swaps in same direction X->Y) (T=now + 70)
    t8 = now + 70.0
    i3_front = TxIntent(tx_hash="i3_front", gas_price=100.0, gas_limit=150000, target_address=pool, value=1.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t8, nonce=3000)
    i3_victim = TxIntent(tx_hash="i3_victim", gas_price=50.0, gas_limit=150000, target_address=pool, value=2.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t8 + 0.1, nonce=7000)
    i3_back = TxIntent(tx_hash="i3_back", gas_price=40.0, gas_limit=150000, target_address=pool, value=1.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t8 + 0.2, nonce=3001)

    # Invalid 4: Different pools (frontrun on pool B, victim and backrun on pool A) (T=now + 80)
    t9 = now + 80.0
    i4_front = TxIntent(tx_hash="i4_front", gas_price=100.0, gas_limit=150000, target_address="0xPoolB", value=1.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t9, nonce=4000)
    i4_victim = TxIntent(tx_hash="i4_victim", gas_price=50.0, gas_limit=150000, target_address=pool, value=2.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t9 + 0.1, nonce=8000)
    i4_back = TxIntent(tx_hash="i4_back", gas_price=40.0, gas_limit=150000, target_address=pool, value=1.0, input_data="swap_Y_for_X", chain_id=1, timestamp=t9 + 0.2, nonce=4001)

    # Invalid 5: Time gap too large (T=now + 90, backrun is 5.0s later) (T=now + 90)
    t10 = now + 90.0
    i5_front = TxIntent(tx_hash="i5_front", gas_price=100.0, gas_limit=150000, target_address=pool, value=1.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t10, nonce=5000)
    i5_victim = TxIntent(tx_hash="i5_victim", gas_price=50.0, gas_limit=150000, target_address=pool, value=2.0, input_data="swap_X_for_Y", chain_id=1, timestamp=t10 + 0.1, nonce=9000)
    i5_back = TxIntent(tx_hash="i5_back", gas_price=40.0, gas_limit=150000, target_address=pool, value=1.0, input_data="swap_Y_for_X", chain_id=1, timestamp=t10 + 5.0, nonce=5001)

    # Feed sequences sequentially, allow processing
    
    # Process Sandwich 1
    await detector.process_intent(s1_front)
    await detector.process_intent(s1_victim)
    await detector.process_intent(s1_back)
    
    # Process Sandwich 2
    await detector.process_intent(s2_front)
    await detector.process_intent(s2_victim)
    await detector.process_intent(s2_back)

    # Process Sandwich 3
    await detector.process_intent(s3_front)
    await detector.process_intent(s3_victim)
    await detector.process_intent(s3_back)

    # Process Sandwich 4
    await detector.process_intent(s4_front)
    await detector.process_intent(s4_victim)
    await detector.process_intent(s4_back)

    # Process Sandwich 5
    await detector.process_intent(s5_front)
    await detector.process_intent(s5_victim)
    await detector.process_intent(s5_back)

    # Process all Invalids
    await detector.process_intent(i1_front)
    await detector.process_intent(i1_victim)
    await detector.process_intent(i1_back)

    await detector.process_intent(i2_front)
    await detector.process_intent(i2_victim)
    await detector.process_intent(i2_back)

    await detector.process_intent(i3_front)
    await detector.process_intent(i3_victim)
    await detector.process_intent(i3_back)

    await detector.process_intent(i4_front)
    await detector.process_intent(i4_victim)
    await detector.process_intent(i4_back)

    await detector.process_intent(i5_front)
    await detector.process_intent(i5_victim)
    await detector.process_intent(i5_back)

    # Wait for processing
    await asyncio.sleep(0.5)
    await detector.stop()

    # Verify exactly 5 anomalies detected
    assert len(detected_anomalies) == 5, f"Expected 5 sandwiches but detected {len(detected_anomalies)}"
    
    detected_hashes = set()
    for candidate in detected_anomalies:
        detected_hashes.update(candidate.related_txs)
        
    assert "s1_front" in detected_hashes
    assert "s2_front" in detected_hashes
    assert "s3_front" in detected_hashes
    assert "s4_front" in detected_hashes
    assert "s5_front" in detected_hashes
    
    assert "i1_front" not in detected_hashes
    assert "i2_front" not in detected_hashes
    assert "i3_front" not in detected_hashes
    assert "i4_front" not in detected_hashes
    assert "i5_front" not in detected_hashes
