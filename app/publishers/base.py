from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class BasePublisher(ABC):
    """
    Abstract Publisher Adapter interface inspired by Postiz IntegrationManager.
    Each social platform provider defines independent validation, token checking, and publish workflows.
    """
    platform_name: str = "base"

    @abstractmethod
    def validate_content(self, post_data: Dict[str, Any]) -> List[str]:
        """Validates caption length, image aspect ratios and limits for the provider."""
        pass

    @abstractmethod
    def check_connection(self) -> Dict[str, Any]:
        """Checks if the access token is valid and active."""
        pass

    @abstractmethod
    def publish(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Publishes content and returns standardized result dictionary."""
        pass
