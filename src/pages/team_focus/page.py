"""
Team Focus page using configuration-driven system.
"""
import logging

from pages.base import PageBase

# Get module logger
logger = logging.getLogger(__name__)


class TeamFocusPage(PageBase):
    """
    Team focus dashboard page.
    """

    def __init__(self):
        """Initialize the Team Focus page with configuration."""
        super().__init__(
            page_id="team_focus",
            title="Team Focus",
            page_prefix="team_focus",
        )
        logger.info(
            f"[TeamFocusPage] Team Focus page initialized with configuration system"
        )


def create_team_focus_page() -> TeamFocusPage:
    """
    Factory function to create a TeamFocusPage instance.

    Returns:
        TeamFocusPage: A new instance of the TeamFocusPage class
    """
    return TeamFocusPage()


# Export page instances for use in webapp.py
team_focus_page_instance = create_team_focus_page()
team_focus_page = team_focus_page_instance.build()
