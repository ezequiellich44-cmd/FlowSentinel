import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError
from flowsentinel.models import AnomalyCandidate
from flowsentinel.llm.classifier import RiskClassifier
from flowsentinel.llm.schemas import AnomalyRiskAssessment

@pytest.mark.asyncio
async def test_llm_classifier_retry_on_invalid_schema():
    """
    Verifies that the RiskClassifier retries when Claude returns an invalid tool schema response,
    and successfully validates when a correct response is returned on the second attempt.
    """
    # 1. Setup RiskClassifier with dummy key to force LLM mode
    classifier = RiskClassifier(api_key="mock_key")
    assert classifier.use_llm is True

    # 2. Mock responses
    mock_messages = AsyncMock()
    classifier.client.messages = mock_messages

    # First mock response content: missing "recommended_action" (triggers Pydantic ValidationError)
    mock_content_invalid = MagicMock()
    mock_content_invalid.type = "tool_use"
    mock_content_invalid.name = "AnomalyRiskAssessment"
    mock_content_invalid.input = {
        "severity": "high",
        "rationale": "Missing recommended_action field"
    }

    response_invalid = MagicMock()
    response_invalid.content = [mock_content_invalid]

    # Second mock response content: fully valid
    mock_content_valid = MagicMock()
    mock_content_valid.type = "tool_use"
    mock_content_valid.name = "AnomalyRiskAssessment"
    mock_content_valid.input = {
        "severity": "critical",
        "rationale": "Valid assessment",
        "recommended_action": "Pause trading"
    }

    response_valid = MagicMock()
    response_valid.content = [mock_content_valid]

    # Side effect: first return invalid response, then valid response
    mock_messages.create.side_effect = [response_invalid, response_valid]

    candidate = AnomalyCandidate(
        anomaly_id="cand_test",
        pattern_type="sandwich",
        severity="high",
        pool_address="0xpool",
        related_txs=[],
        timestamp=1000.0,
        metadata={}
    )

    assessment = await classifier.classify(candidate)

    # 3. Assertions
    # Verify mock was called exactly twice (first call failed validation, second succeeded)
    assert mock_messages.create.call_count == 2
    assert assessment.severity == "critical"
    assert assessment.rationale == "Valid assessment"
    assert assessment.recommended_action == "Pause trading"
