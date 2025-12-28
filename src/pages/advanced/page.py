"""
Match Analysis page using configuration-driven system.
"""
import logging

from src.pages.base import PageBase

# Get module logger
logger = logging.getLogger(__name__)


class AdvancedPage(PageBase):
    """
    Advanced dashboard page.
    """

    def __init__(self):
        """Initialize the Advanced page with configuration."""
        super().__init__(
            page_id="advanced",
            title="Advanced",
            page_prefix="advanced",
        )
        logger.info(
            f"[AdvancedPage] Advanced Page initialized with configuration system"
        )


def advanced_match_page() -> AdvancedPage:
    """
    Factory function to create a MatchPage instance.

    Returns:
        MatchPage: A new instance of the MatchPage class
    """
    return AdvancedPage()


# Export page instances for use in webapp.py
advanced_page_instance = advanced_match_page()
advanced_page = advanced_page_instance.build()
