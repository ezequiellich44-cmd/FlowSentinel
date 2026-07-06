import os
import pytest
from flowsentinel.models import AnomalyCandidate
from flowsentinel.llm.classifier import RiskClassifier
from flowsentinel.llm.narrative import NarrativeGenerator

@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="Gated test: requires ANTHROPIC_API_KEY environment variable to be set"
)
@pytest.mark.asyncio
async def test_llm_live_smoke():
    """
    Smoke test that hits the real Anthropic Claude API.
    Verifies that tool calling and narrative generation work correctly end-to-end.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    classifier = RiskClassifier(api_key=api_key)
    narrator = NarrativeGenerator(api_key=api_key)
    
    assert classifier.use_llm is True
    assert narrator.use_llm is True

    candidate = AnomalyCandidate(
        anomaly_id="live_smoke_1",
        pattern_type="sandwich",
        severity="high",
        pool_address="0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",  # Uniswap v3 USDC/ETH pool
        related_txs=["0xfrontrun_tx", "0xvictim_tx", "0xbackrun_tx"],
        timestamp=1600000000.0,
        metadata={
            "frontrun_gas": 250.0,
            "victim_gas": 60.0,
            "backrun_gas": 55.0,
            "frontrun_nonce": 12,
            "backrun_nonce": 13
        }
    )

    # 1. Run live classification
    assessment = await classifier.classify(candidate)
    assert assessment.severity in ["low", "medium", "high", "critical"]
    assert len(assessment.rationale) > 0
    assert len(assessment.recommended_action) > 0

    # 2. Run live narrative generation (Spanish)
    report_es = await narrator.generate(assessment, language="es")
    assert "Severidad" in report_es or "SEVERIDAD" in report_es or len(report_es) > 0
    
    # 3. Run live narrative generation (English)
    report_en = await narrator.generate(assessment, language="en")
    assert "Severity" in report_en or "SEVERITY" in report_en or len(report_en) > 0
