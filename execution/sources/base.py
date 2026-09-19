from abc import ABC, abstractmethod
from typing import List
from ..models import RawJobListing


class JobSource(ABC):
    """Abstract base class for all job discovery sources."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the source provider."""
        pass

    @abstractmethod
    def fetch_jobs(self, query: str = "", limit: int = 20) -> List[RawJobListing]:
        """Fetches raw job listings from the source."""
        pass
