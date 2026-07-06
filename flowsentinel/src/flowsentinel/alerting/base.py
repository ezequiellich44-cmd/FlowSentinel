from abc import ABC, abstractmethod
from flowsentinel.llm.schemas import AnomalyRiskAssessment

class AlertSink(ABC):
    @abstractmethod
    async def send(self, assessment: AnomalyRiskAssessment, narrative: str) -> None:
        """
        Send the classification assessment and explanation narrative to the target alert system.
        """
        pass
