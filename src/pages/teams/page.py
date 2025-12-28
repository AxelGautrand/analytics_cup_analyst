"""
Team Focus page using configuration-driven system.
"""
import logging

from src.pages.base import PageBase

# Get module logger
logger = logging.getLogger(__name__)


class TeamsPage(PageBase):
    """
    Team focus dashboard page.
    """

    def __init__(self):
        """Initialize the Team Focus page with configuration."""
        super().__init__(
            page_id="teams",
            title="Team Focus",
            page_prefix="teams",
        )
        logger.info(
            f"[TeamsPage] Team Focus page initialized with configuration system"
        )


def create_teams_page() -> TeamsPage:
    """
    Factory function to create a TeamsPage instance.

    Returns:
        TeamsPage: A new instance of the TeamsPage class
    """
    return TeamsPage()


# Export page instances for use in webapp.py
teams_page_instance = create_teams_page()
teams_page = teams_page_instance.build()
