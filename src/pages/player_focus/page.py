"""
Player Focus page using configuration-driven system.
"""
import logging

from src.pages.base import PageBase

# Get module logger
logger = logging.getLogger(__name__)


class PlayerFocusPage(PageBase):
    """
    Player Focus dashboard page.

    This page shows detailed information and analysis for individual players.
    """

    def __init__(self):
        """Initialize the Player Focus page with configuration."""
        super().__init__(
            page_id="player_focus",
            title="Player Focus",
            page_prefix="player_focus",
        )
        logger.info(f"[PlayerFocusPage] Player focus page initialized")


def create_player_focus_page() -> PlayerFocusPage:
    """
    Factory function to create a PlayerFocusPage instance.

    Returns:
        PlayerFocusPage: A new instance of the PlayerFocusPage class
    """
    return PlayerFocusPage()


# Export page instances for use in webapp.py
player_focus_page_instance = create_player_focus_page()
player_focus_page = player_focus_page_instance.build()
