import json
import os
import logging
from typing import List, Optional
from pydantic import ValidationError
from flowsentinel.models import AnomalyCandidate
from flowsentinel.llm.schemas import AnomalyRiskAssessment
from flowsentinel.config import settings

logger = logging.getLogger(__name__)

class RuleBasedClassifier:
    """
    Fallback classifier that uses deterministic heuristics.
    Used when ANTHROPIC_API_KEY is not configured or in local test environments.
    """
    async def classify(self, candidate: AnomalyCandidate) -> AnomalyRiskAssessment:
        pattern = candidate.pattern_type.lower()
        metadata = candidate.metadata
        
        if "sandwich" in pattern:
            return AnomalyRiskAssessment(
                severity="high",
                rationale=(
                    "Rule-based classification: Detected a structured Frontrun-Victim-Backrun sequence. "
                    f"Frontrun transaction ({candidate.related_txs[0] if candidate.related_txs else 'unknown'}) used high gas price "
                    f"({metadata.get('frontrun_gas', 'N/A')} Gwei) and backrun transaction used consecutive nonce "
                    f"({metadata.get('backrun_nonce', 'N/A')}) to capture slippage."
                ),
                recommended_action="Flag searcher contract and monitor target pool for recurrent sandwich signatures."
            )
        elif "liquidity_drop" in pattern:
            impact = metadata.get("price_impact", 0.0)
            severity = "high" if impact > 0.15 else "medium"
            return AnomalyRiskAssessment(
                severity=severity,
                rationale=(
                    f"Rule-based classification: Pool price impact of {impact:.4%}"
                    f" exceeds threshold for a test swap of size {metadata.get('test_swap_size', 'N/A')}."
                ),
                recommended_action="Investigate if liquidity fragmentation is transient or represents a permanent withdrawal."
            )
        elif "depletion" in pattern:
            time_left = metadata.get("time_to_depletion", 0.0)
            severity = "critical" if time_left < 20 else "high"
            return AnomalyRiskAssessment(
                severity=severity,
                rationale=(
                    f"Rule-based classification: Online exponential regression projects pool liquidity "
                    f"exhaustion in {time_left:.2f} seconds based on recent volume slope ({metadata.get('slope', 0.0):.4f})."
                ),
                recommended_action="Verify pool health and alert downstream smart routing routers of impending liquidity exhaustion."
            )
        else:
            return AnomalyRiskAssessment(
                severity="low",
                rationale="Rule-based classification: General anomaly candidate did not trigger heuristic triggers.",
                recommended_action="Review anomalies collection for noise."
            )

    async def classify_batch(self, candidates: List[AnomalyCandidate]) -> List[AnomalyRiskAssessment]:
        return [await self.classify(c) for c in candidates]


class RiskClassifier:
    """
    Risk Classifier using Anthropic Claude with Tool Use to enforce output structure.
    Automatically falls back to RuleBasedClassifier if ANTHROPIC_API_KEY is missing.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            logger.warning("No ANTHROPIC_API_KEY provided. Falling back to RuleBasedClassifier.")
            self.delegate = RuleBasedClassifier()
            self.use_llm = False
        else:
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(api_key=self.api_key)
            self.delegate = None
            self.use_llm = True

        # Load system prompt
        current_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_path = os.path.join(current_dir, "prompts", "classification_system.md")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
        except FileNotFoundError:
            self.system_prompt = "You are FlowSentinel Risk Analysis AI."

    async def classify(self, candidate: AnomalyCandidate) -> AnomalyRiskAssessment:
        if not self.use_llm:
            return await self.delegate.classify(candidate)

        tool_schema = {
            "name": "AnomalyRiskAssessment",
            "description": "Output the risk assessment for the anomaly.",
            "input_schema": AnomalyRiskAssessment.model_json_schema()
        }

        # Build prompt
        candidate_json = json.dumps(candidate.model_dump(), indent=2)
        user_message = f"Please classify the following anomaly candidate:\n\n{candidate_json}"

        messages = [
            {"role": "user", "content": user_message}
        ]

        retries = 2
        for attempt in range(retries + 1):
            try:
                response = await self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1000,
                    system=self.system_prompt,
                    messages=messages,
                    tools=[tool_schema],
                    tool_choice={"type": "tool", "name": "AnomalyRiskAssessment"}
                )

                # Extract tool call
                tool_use = None
                for content in response.content:
                    if content.type == "tool_use" and content.name == "AnomalyRiskAssessment":
                        tool_use = content
                        break

                if not tool_use:
                    raise ValueError("Claude did not call the forced AnomalyRiskAssessment tool.")

                # Validate against schema
                assessment = AnomalyRiskAssessment.model_validate(tool_use.input)
                return assessment

            except (ValidationError, ValueError, Exception) as e:
                logger.warning("Attempt %d classification failed: %s", attempt + 1, str(e))
                if attempt == retries:
                    # Final attempt failed, use rule-based fallback
                    logger.error("All LLM attempts failed. Falling back to RuleBasedClassifier.")
                    fallback = RuleBasedClassifier()
                    return await fallback.classify(candidate)

                # Append assistant response (or placeholder) and validation error for retry
                validation_error_msg = f"Validation Error on previous attempt: {str(e)}. Please correct the schema fields and try again."
                
                # We need to construct conversation messages properly for Anthropic
                # If we have a tool_use block, we should append it
                assistant_content = []
                if 'response' in locals() and hasattr(response, 'content'):
                    assistant_content = response.content
                else:
                    assistant_content = [{"type": "text", "text": "Failed to parse tool use."}]
                    
                messages.append({"role": "assistant", "content": assistant_content})
                
                # Create corresponding tool result error message
                tool_use_id = getattr(tool_use, 'id', 'dummy_id') if tool_use else 'dummy_id'
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": validation_error_msg,
                            "is_error": True
                        }
                    ]
                })

    async def classify_batch(self, candidates: List[AnomalyCandidate]) -> List[AnomalyRiskAssessment]:
        import asyncio
        tasks = [self.classify(c) for c in candidates]
        return list(await asyncio.gather(*tasks))

import os
