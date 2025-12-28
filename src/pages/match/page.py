"""
Match Analysis page using configuration-driven system.
"""
import logging

from src.pages.base import PageBase

# Get module logger
logger = logging.getLogger(__name__)


class MatchPage(PageBase):
    """
    Match Analysis dashboard page.
    """

    def __init__(self):
        """Initialize the Match page with configuration."""
        super().__init__(
            page_id="match",
            title="Match Analysis",
            page_prefix="match",
        )
        logger.info(f"[MatchPage] Match page initialized with configuration system")


def create_match_page() -> MatchPage:
    """
    Factory function to create a MatchPage instance.

    Returns:
        MatchPage: A new instance of the MatchPage class
    """
    return MatchPage()


# Export page instances for use in webapp.py
match_page_instance = create_match_page()
match_page = match_page_instance.build()
