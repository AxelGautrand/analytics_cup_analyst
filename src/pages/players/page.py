"""
Players Overview page using configuration-driven system.
"""
import logging

from pages.base import PageBase

# Get module logger
logger = logging.getLogger(__name__)


class PlayersPage(PageBase):
    """
    Players Overview dashboard page.
    """

    def __init__(self):
        """Initialize the Players page with configuration."""
        super().__init__(
            page_id="players",
            title="Players Overview",
            page_prefix="players",
        )
        logger.info(f"[PlayersPage] Players page initialized with configuration system")


def create_players_page() -> PlayersPage:
    """
    Factory function to create a PlayersPage instance.

    Returns:
        PlayersPage: A new instance of the PlayersPage class
    """
    return PlayersPage()


# Export page instances for use in webapp.py
players_page_instance = create_players_page()
players_page = players_page_instance.build()
