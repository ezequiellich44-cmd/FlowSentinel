import pytest
from flowsentinel.models import AnomalyCandidate
from flowsentinel.llm.classifier import RuleBasedClassifier

@pytest.mark.asyncio
async def test_rule_based_classifier():
    classifier = RuleBasedClassifier()

    # 1. Test sandwich classification
    sandwich_cand = AnomalyCandidate(
        anomaly_id="cand_1",
        pattern_type="sandwich",
        severity="high",
        pool_address="0xpool",
        related_txs=["0x1", "0x2", "0x3"],
        timestamp=1000.0,
        metadata={"frontrun_gas": 150.0, "backrun_nonce": 101}
    )
    assessment1 = await classifier.classify(sandwich_cand)
    assert assessment1.severity == "high"
    assert "Frontrun-Victim-Backrun" in assessment1.rationale
    assert "Flag searcher contract" in assessment1.recommended_action

    # 2. Test liquidity drop classification
    liq_cand = AnomalyCandidate(
        anomaly_id="cand_2",
        pattern_type="liquidity_drop",
        severity="medium",
        pool_address="0xpool",
        related_txs=[],
        timestamp=1000.0,
        metadata={"price_impact": 0.18, "test_swap_size": 10.0}
    )
    assessment2 = await classifier.classify(liq_cand)
    assert assessment2.severity == "high"  # because impact > 0.15
    assert "Pool price impact of 18.0000%" in assessment2.rationale
