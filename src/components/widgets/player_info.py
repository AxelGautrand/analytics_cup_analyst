"""
Player Info Widget for displaying detailed player information.

This widget shows player details (name, age, position, team, etc.)
based on the selected player from page filters.
"""
import logging
import random
from typing import Any, Dict, List, Optional

from dash import html

from .base import BaseWidget, WidgetConfig

# Get module logger
logger = logging.getLogger(__name__)

# TODO : More player infos such as playing time etc


class PlayerInfoWidget(BaseWidget):
    """
    Widget for displaying player information.

    Features:
    - Displays player info from DataManager
    - Photo placeholder
    - Basic player details
    - Compact layout that fits within defined space
    - Reactive to player filter changes
    """

    def __init__(
        self,
        config: WidgetConfig,
        data_manager=None,
        page_prefix: str = "player_focus",
        show_photo_placeholder: bool = True,
        default_player_id: Optional[str] = None,
    ):
        """
        Initialize a player info widget.

        Args:
            config: Widget configuration
            data_manager: DataManager instance
            page_prefix: Prefix for component IDs
            show_photo_placeholder: Whether to show photo placeholder
            default_player_id: Default player ID to display (fallback)
        """
        super().__init__(config)
        self.data_manager = data_manager
        self.page_prefix = page_prefix
        self.show_photo_placeholder = show_photo_placeholder
        self.default_player_id = default_player_id
        self._current_html = None

        # Generate unique IDs
        self.player_info_id = f"{self.config.id}-player-info"
        self.player_photo_id = f"{self.config.id}-player-photo"

        # Store ID for connecting to the player filter store
        self.player_filter_store_id = "player-filter-store"

        logger.info(
            f"[PlayerInfoWidget] Initialized '{config.id}' with "
            f"photo_placeholder={show_photo_placeholder}"
        )

    def render(self) -> html.Div:
        """
        Render player info widget with compact layout.

        Returns:
            html.Div: Complete widget structure
        """
        # Build widget components
        components = []

        # Photo placeholder
        if self.show_photo_placeholder:
            components.append(
                html.Div(
                    html.Div(
                        "👤",
                        id=self.player_photo_id,
                        className="player-photo-placeholder",
                    ),
                    className="player-photo-container",
                )
            )

        # Player info details - initial state will show placeholder
        components.append(
            html.Div(
                self._get_initial_player_info(),
                id=self.player_info_id,
                className="player-info-details",
            )
        )

        rendered_div = html.Div(
            components,
            className="player-info-tile",
            id=self.config.id,
        )

        self._current_html = rendered_div

        return html.Div(
            [
                html.Div(
                    [rendered_div],
                    className="tile",
                )
            ],
            id=self.config.id,
            className="grid-stack-item",
        )

    def get_current_html(self):
        """Get the currently displayed HTML content."""
        return self._current_html

    def get_current_content(self):
        """Get the currently displayed content."""
        return {"html": self._current_html} if self._current_html else None

    def update_from_filters(self, filter_data: Dict[str, Any]) -> List:
        """
        Update widget content based on filter data.
        """
        try:
            # Extract player information
            player_label = filter_data.get("player_label")
            player_id = filter_data.get("player_id")

            if not player_id or not self.data_manager:
                logger.warning(f"[{self.config.id}] Missing player_id or data_manager")
                return self._get_error_player_info("Missing player information")

            logger.info(
                f"[{self.config.id}] Updating with player: {player_label} (ID: {player_id})"
            )

            # Get player info from data manager
            player_info = self.data_manager.get_player_info(player_id)

            if not player_info:
                # Try to find player by name
                player_info = self._find_player_by_name(player_label, player_id)

            if not player_info:
                return self._get_error_player_info(f"Player not found: {player_label}")

            return self.get_player_info_content(filter_data)  # Reuse existing method

        except Exception as e:
            logger.error(f"[{self.config.id}] Error updating from filters: {e}")
            return self._get_error_player_info(f"Error: {str(e)}")

    def _get_initial_player_info(self) -> List:
        """
        Get initial player info (placeholder or default player).

        Returns:
            List of Dash components
        """
        # Get a fallback player ID for initial display
        player_id = self._get_fallback_player_id()

        if not player_id or not self.data_manager:
            return self._get_empty_player_info("Select a player to view details")

        try:
            player_info = self.data_manager.get_player_info(player_id)
            if not player_info:
                return self._get_empty_player_info("Select a player to view details")

            return self._build_player_info_components(player_info, player_id)

        except Exception as e:
            logger.error(f"[PlayerInfoWidget] Error getting initial player info: {e}")
            return self._get_empty_player_info("Select a player to view details")

    def _get_fallback_player_id(self) -> str:
        """
        Get a fallback player ID.

        Returns:
            str: Player ID to display
        """
        # Priority 1: Use default_player_id from config
        if self.default_player_id:
            return self.default_player_id

        # Priority 2: Get random player from DataManager
        if self.data_manager:
            try:
                players_data = self.data_manager.load_player_data()
                if players_data:
                    player_ids = list(players_data.keys())
                    if player_ids:
                        return random.choice(player_ids[:20])  # Pick from first 20
            except Exception as e:
                logger.warning(f"[PlayerInfoWidget] Could not load players: {e}")

        # Priority 3: Fallback to a known player ID
        return "38673"  # Guillermo Luis May Bartesaghi

    def get_player_info_content(self, player_data: Optional[Dict] = None) -> List:
        """
        Generate player information content from store data.

        Returns:
            List of Dash components with player info INCLUDING photo placeholder
        """
        if not player_data:
            return self._get_empty_player_info("No player data received")

        try:
            # Extract player information from store data
            player_label = player_data.get("player_label")
            player_id = player_data.get("player_id")

            if not player_id or not self.data_manager:
                logger.warning(f"[PlayerInfoWidget] Missing player_id or data_manager")
                return self._get_error_player_info("Missing player information")

            logger.info(
                f"[PlayerInfoWidget] Loading info for player: {player_label} (ID: {player_id})"
            )

            # Get player info from data manager
            player_info = self.data_manager.get_player_info(player_id)

            if not player_info:
                # Try to find player by name if ID lookup fails
                player_info = self._find_player_by_name(player_label, player_id)

            if not player_info:
                logger.warning(
                    f"[PlayerInfoWidget] Player not found: {player_label} (ID: {player_id})"
                )
                return self._get_error_player_info(f"Player not found: {player_label}")

            # Build the complete structure with photo placeholder
            components = []

            # Photo placeholder (if enabled)
            if self.show_photo_placeholder:
                components.append(
                    html.Div(
                        html.Div(
                            "👤",
                            id=self.player_photo_id,
                            className="player-photo-placeholder",
                        ),
                        className="player-photo-container",
                    )
                )

            # Player info details
            info_content = self._build_player_info_components(
                player_info, player_id, player_label
            )
            components.append(
                html.Div(
                    info_content,
                    id=self.player_info_id,
                    className="player-info-details",
                )
            )

            self._current_html = components

            return components

        except Exception as e:
            logger.error(f"[PlayerInfoWidget] Error getting player info: {e}")
            return self._get_error_player_info(f"Error: {str(e)}")

    def _find_player_by_name(
        self, player_label: Optional[str] = None, fallback_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Try to find player by name if ID lookup fails.

        Args:
            player_label: Player display name
            fallback_id: Original player ID to fall back to

        Returns:
            Player info dict or None
        """
        try:
            if not self.data_manager or not player_label:
                return None

            players_data = self.data_manager.load_player_data()
            if not players_data:
                return None

            # Search for player by name
            for player_id, player_info in players_data.items():
                full_name = player_info.get("full_name", "")
                short_name = player_info.get("short_name", "")

                if (
                    player_label == full_name
                    or player_label == short_name
                    or player_label in full_name
                    or player_label in short_name
                ):
                    logger.info(
                        f"[PlayerInfoWidget] Found player by name: {player_label} -> ID: {player_id}"
                    )
                    return player_info

            # If not found, return info for fallback ID
            if fallback_id and fallback_id in players_data:
                return players_data[fallback_id]

        except Exception as e:
            logger.warning(f"[PlayerInfoWidget] Error searching player by name: {e}")

        return None

    def _build_player_info_components(
        self, player_info: Dict, player_id: str, display_name: Optional[str] = None
    ) -> List:
        """
        Build player info components from player info dictionary.

        Args:
            player_info: Player information dictionary
            player_id: Player ID
            display_name: Optional custom display name

        Returns:
            List of Dash components
        """
        components = []

        # Player name
        if display_name:
            player_name = display_name
        else:
            full_name = player_info.get("full_name", "")
            short_name = player_info.get("short_name", "")
            player_name = short_name or full_name or f"Player {player_id}"

        components.append(
            html.H4(
                player_name,
                className="player-name",
            )
        )

        # Compact info grid
        info_grid = self._build_info_grid(player_info)

        if info_grid:
            components.append(
                html.Div(
                    info_grid,
                    className="player-info-grid",
                )
            )

        return components

    def _build_info_grid(self, player_info: Dict) -> List:
        """
        Build the information grid from player info.

        Args:
            player_info: Player information dictionary

        Returns:
            List of info grid items
        """
        info_grid = []

        # Age
        age = player_info.get("age")
        if age:
            info_grid.append(
                html.Div(
                    [
                        html.Span("Age: ", className="info-label"),
                        html.Span(str(age), className="info-value"),
                    ],
                    className="info-item",
                )
            )

        # Gender
        gender = player_info.get("gender", "").title()
        if gender:
            gender_icon = (
                "♂"
                if gender.lower() == "male"
                else "♀"
                if gender.lower() == "female"
                else "👤"
            )
            info_grid.append(
                html.Div(
                    [
                        html.Span("Gender: ", className="info-label"),
                        html.Span(f"{gender} {gender_icon}", className="info-value"),
                    ],
                    className="info-item",
                )
            )

        # Position
        positions = player_info.get("positions", [])
        if positions:
            position_str = ", ".join(positions[:2])  # Show up to 2 positions
            info_grid.append(
                html.Div(
                    [
                        html.Span("Position: ", className="info-label"),
                        html.Span(position_str, className="info-value"),
                    ],
                    className="info-item",
                )
            )

        # Player number
        number = player_info.get("number")
        if number:
            info_grid.append(
                html.Div(
                    [
                        html.Span("Number: ", className="info-label"),
                        html.Span(f"#{number}", className="info-value"),
                    ],
                    className="info-item",
                )
            )

        # Teams
        teams = player_info.get("team_names", player_info.get("teams", []))
        if teams:
            if (
                isinstance(teams, list)
                and teams
                and isinstance(teams[0], str)
                and not teams[0].isdigit()
            ):
                # Show first 2 team names
                team_str = ", ".join(teams[:2])
                if len(teams) > 2:
                    team_str += f" (+{len(teams) - 2})"
            else:
                # Show team count if names not available
                team_str = f"{len(teams)} team{'s' if len(teams) > 1 else ''}"

            info_grid.append(
                html.Div(
                    [
                        html.Span("Teams: ", className="info-label"),
                        html.Span(team_str, className="info-value"),
                    ],
                    className="info-item",
                )
            )

        # Matches played
        matches = player_info.get("matches", [])
        if matches:
            info_grid.append(
                html.Div(
                    [
                        html.Span("Matches: ", className="info-label"),
                        html.Span(str(len(matches)), className="info-value"),
                    ],
                    className="info-item",
                )
            )

        return info_grid

    def _get_empty_player_info(
        self, message: str = "Select a player to view details"
    ) -> List:
        """Get empty player info placeholder."""
        return [
            html.H4(
                "Player Information",
                className="player-name",
            ),
            html.P(
                message,
                style={
                    "color": "var(--text-secondary)",
                    "fontStyle": "italic",
                    "textAlign": "center",
                    "marginTop": "10px",
                },
            ),
        ]

    def _get_error_player_info(self, error_msg: str) -> List:
        """Get error player info placeholder."""
        return [
            html.H4(
                "Error Loading Player",
                className="player-name",
                style={
                    "color": "#ff6b6b",
                    "textAlign": "center",
                    "marginBottom": "10px",
                },
            ),
            html.P(
                error_msg,
                style={
                    "color": "var(--text-secondary)",
                    "fontStyle": "italic",
                    "textAlign": "center",
                    "fontSize": "12px",
                },
            ),
        ]

    def get_client_config(self) -> Dict[str, Any]:
        """
        Get configuration for client-side JavaScript.

        Returns:
            Dict[str, Any]: Configuration dictionary
        """
        return {
            "widgetType": "player_info",
            "id": self.config.id,
            "pagePrefix": self.page_prefix,
            "showPhotoPlaceholder": self.show_photo_placeholder,
            "layout": self.config.to_gridstack_dict(),
            "playerFilterStoreId": self.player_filter_store_id,
        }

    @classmethod
    def from_config(
        cls,
        config_dict: Dict[str, Any],
        page_prefix: str = "player_focus",
        data_manager=None,
    ) -> "PlayerInfoWidget":
        """
        Create a PlayerInfoWidget from a configuration dictionary.

        Args:
            config_dict: Configuration dictionary with widget specs
            page_prefix: Prefix for component IDs
            data_manager: DataManager instance

        Returns:
            PlayerInfoWidget: Configured widget instance
        """
        required_keys = ["id", "position"]
        for key in required_keys:
            if key not in config_dict:
                raise ValueError(
                    f"Missing required key '{key}' in player info widget config"
                )

        # Create WidgetConfig
        widget_config = WidgetConfig(
            id=config_dict["id"],
            title=config_dict.get("title", "Player Information"),
            widget_type="player_info",
            position=config_dict["position"],
            styles=config_dict.get("styles", {}),
            properties=config_dict.get("properties", {}),
        )

        # Create widget instance
        return cls(
            config=widget_config,
            data_manager=data_manager,
            page_prefix=page_prefix,
            show_photo_placeholder=config_dict.get("show_photo_placeholder", True),
            default_player_id=config_dict.get("default_player_id"),
        )
