"""
Compact Filter Widget with modal for advanced filters.

This widget displays 1-2 primary filters in a compact tile with a gear icon.
Clicking the gear icon opens a modal with all available filters.
"""
import logging
from typing import Any, Dict, List, Optional

from dash import dcc, html
from dash.dependencies import Input

from .base import BaseWidget, WidgetConfig

# Get module logger
logger = logging.getLogger(__name__)


class CompactFilterWidget(BaseWidget):
    """
    Compact filter widget with primary filters in tile and modal for advanced filters.

    Features:
    - 1-2 primary filters shown in the tile
    - Gear icon to open modal with all filters
    - Real data from DataManager for filter options
    - Hierarchical filter configuration from YAML
    """

    # Default filter definitions with real data placeholders
    DEFAULT_FILTERS = {
        "match": {
            "type": "dropdown",
            "label": "Match",
            "value": "all",
            "clearable": False,
            "searchable": True,
            "placeholder": "Select match...",
            "category": "primary",  # Can be primary or secondary
        },
        "team": {
            "type": "dropdown",
            "label": "Team",
            "value": "all",
            "clearable": False,
            "searchable": True,
            "placeholder": "Select team...",
            "category": "primary",
        },
        "time_range": {
            "type": "range_slider",
            "label": "Time Range",
            "min": 0,
            "max": 90,
            "step": 5,
            "value": [0, 90],
            "marks": {0: "0", 45: "45", 90: "90"},
            "tooltip": {"placement": "bottom", "always_visible": False},
            "category": "secondary",
        },
        "player": {
            "type": "dropdown",
            "label": "Player",
            "value": "all",
            "clearable": False,
            "searchable": True,
            "placeholder": "Select a player...",
            "category": "primary",
            "allow_all": True,
        },
        "position": {
            "type": "dropdown",
            "label": "Position",
            "value": "all",
            "clearable": True,
            "searchable": False,
            "placeholder": "All positions...",
            "category": "secondary",
        },
    }

    def __init__(
        self,
        config: WidgetConfig,
        filter_types: Optional[List[str]] = None,
        compact_filters: Optional[List[str]] = None,
        page_prefix: str = "teams",
        modal_title: Optional[str] = None,
        show_gear_icon: bool = True,
        gear_icon: str = "⚙️",
        data_manager=None,
        filter_options: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """
        Initialize a compact filter widget.

        Args:
            config: Widget configuration
            filter_types: All filter types to include (primary + secondary)
            compact_filters: Filter types to show in compact tile (max 2)
            page_prefix: Prefix for filter IDs
            modal_title: Title for the advanced filters modal
            show_gear_icon: Whether to show gear icon
            gear_icon: Icon/emoji for the gear button
            data_manager: DataManager instance for real data
            filter_options: Custom options for specific filters
        """
        super().__init__(config)
        self.page_prefix = page_prefix
        self.filter_types = filter_types or []
        self.compact_filters = compact_filters or []
        self.modal_title = modal_title or f"{page_prefix.title()} Filters"
        self.show_gear_icon = show_gear_icon
        self.gear_icon = gear_icon
        self.data_manager = data_manager
        self.custom_filter_options = filter_options or {}

        # Validate compact_filters (max 2)
        if len(self.compact_filters) > 2:
            logger.warning(
                f"[CompactFilterWidget] Too many compact filters ({len(self.compact_filters)}). "
                f"Showing only first 2: {self.compact_filters[:2]}"
            )
            self.compact_filters = self.compact_filters[:2]

        # Initialize filter definitions with real data
        self.filter_definitions = self._initialize_filter_definitions()

        logger.info(
            f"[CompactFilterWidget] Initialized '{config.id}' with "
            f"{len(self.compact_filters)} compact filters and "
            f"{len(self.filter_types)} total filters"
        )

    def _initialize_filter_definitions(self) -> Dict[str, Dict[str, Any]]:
        """
        Initialize filter definitions with real data from DataManager.

        Returns:
            Dict: Updated filter definitions with real options
        """
        definitions = {**self.DEFAULT_FILTERS}

        # Apply custom filter options from constructor BEFORE adding data options
        for filter_type, custom_options in self.custom_filter_options.items():
            if filter_type in definitions:
                definitions[filter_type].update(custom_options)
            else:
                logger.warning(
                    f"[CompactFilterWidget] Unknown filter type '{filter_type}' "
                    f"in custom options"
                )

        # If we have a data_manager, populate real options
        if self.data_manager:
            try:
                # Populate match options
                if "match" in definitions:
                    match_options = [{"label": "All Matches", "value": "all"}]
                    available_matches = self.data_manager.get_available_matches()

                    for match_id in available_matches:
                        match_info = self.data_manager.get_match_info(match_id)
                        label = f"{match_info.get('home_team', 'Team A')} vs {match_info.get('away_team', 'Team B')}"
                        match_options.append({"label": label, "value": match_id})

                    definitions["match"]["options"] = match_options

                # Populate team options
                if "team" in definitions:
                    team_options = [{"label": "All Teams", "value": "all"}]
                    available_teams = self.data_manager.get_available_teams()

                    for team in available_teams:
                        team_options.append({"label": team, "value": team})

                    definitions["team"]["options"] = team_options

                # Populate player options (with alphabetical sorting)
                if "player" in definitions:
                    player_options = []

                    # Add "All Players" option based on allow_all setting
                    allow_all = definitions["player"].get("allow_all", True)
                    if allow_all:
                        player_options.append({"label": "All Players", "value": "all"})

                    players_data = self.data_manager.load_player_data()

                    # Create list of players for sorting
                    players_list = []
                    for player_id, player_info in list(players_data.items()):
                        display_name = player_info.get("short_name") or player_info.get(
                            "full_name", f"Player {player_id}"
                        )
                        players_list.append(
                            {
                                "label": display_name,
                                "value": player_id,
                                "sort_key": display_name.lower(),  # For case-insensitive sorting
                            }
                        )

                    # Sort alphabetically by display name
                    players_list.sort(key=lambda x: x["sort_key"])

                    # Add sorted players to options
                    for player in players_list:
                        player_options.append(
                            {"label": player["label"], "value": player["value"]}
                        )

                    definitions["player"]["options"] = player_options

                logger.debug(
                    "[CompactFilterWidget] Populated filter options with real data"
                )

            except Exception as e:
                logger.error(f"[CompactFilterWidget] Error loading real data: {e}")

        # Apply custom category assignments
        for filter_type in self.filter_types:
            if filter_type in definitions:
                if filter_type in self.compact_filters:
                    definitions[filter_type]["category"] = "primary"
                else:
                    definitions[filter_type]["category"] = "secondary"

        return definitions

    def render(self) -> html.Div:
        """
        Render compact filter widget with primary filters and gear icon.

        Returns:
            html.Div: Complete widget structure
        """
        # Create primary filter elements (shown in tile)
        primary_elements = []
        for filter_type in self.compact_filters:
            if filter_type in self.filter_definitions:
                element = self._create_compact_filter_element(filter_type)
                if element:
                    primary_elements.append(element)

        # Create gear icon button if enabled
        gear_button = None
        if self.show_gear_icon and self.filter_types:
            gear_button = html.Button(
                self.gear_icon,
                id=f"{self.config.id}-gear-btn",
                className="filters-gear-btn",
                title=f"Open {self.modal_title}",
                n_clicks=0,
            )

        # Combine elements
        children = primary_elements
        if gear_button:
            children.append(gear_button)

        return html.Div(
            children,
            className="tile filter-tile compact-filter-tile",
            id=self.config.id,
            style=self.config.styles,
        )

    def _create_compact_filter_element(self, filter_type: str) -> html.Div | None:
        """
        Create a compact filter element for the tile.

        Args:
            filter_type: Type of filter to create

        Returns:
            html.Div: Compact filter element
        """
        filter_def = self.filter_definitions.get(filter_type)
        if not filter_def:
            return None

        filter_id = f"{self.page_prefix}-{filter_type}"
        control_type = filter_def.get("type", "dropdown")

        # Create compact version of the control
        if control_type == "dropdown":
            # Check if multi-select is allowed (use custom option or default)
            multi = filter_def.get("multi", False)

            control = dcc.Dropdown(
                id=filter_id,
                options=filter_def.get("options", []),
                value=filter_def.get("value", "all"),
                clearable=filter_def.get("clearable", True),
                searchable=filter_def.get("searchable", True),
                multi=multi,
                placeholder=filter_def.get("placeholder", "Select..."),
                className="compact-filter-dropdown",
            )

        elif control_type == "range_slider":
            # For compact view, show a simplified version
            control = html.Div(
                [
                    html.Span(
                        f"{filter_def.get('value', [0, 90])[0]}-{filter_def.get('value', [0, 90])[1]}min",
                        className="compact-slider-value",
                        style={
                            "fontSize": "11px",
                            "color": "var(--text-secondary)",
                            "padding": "4px 8px",
                            "background": "rgba(255,255,255,0.05)",
                            "borderRadius": "4px",
                        },
                    )
                ]
            )
        else:
            return None

        return html.Div(
            control,
            className="compact-filter-item",
            style={"display": "inline-block", "verticalAlign": "middle"},
        )

    def create_modal_content(self) -> html.Div:
        """
        Create content for the advanced filters modal.

        Returns:
            html.Div: Modal content with all filters
        """
        modal_elements = []

        for filter_type in self.filter_types:
            if filter_type in self.filter_definitions:
                element = self._create_full_filter_element(filter_type)
                if element:
                    modal_elements.append(element)

        return html.Div(
            modal_elements,
            className="filter-modal-content",
        )

    def _create_full_filter_element(self, filter_type: str) -> html.Div | None:
        """
        Create a full filter element for the modal.

        Args:
            filter_type: Type of filter to create

        Returns:
            html.Div: Complete filter element with label
        """
        filter_def = self.filter_definitions.get(filter_type)
        if not filter_def:
            return None

        filter_id = f"{self.page_prefix}-{filter_type}"
        control_type = filter_def.get("type", "dropdown")

        # Create label
        label = html.Label(
            filter_def.get("label", filter_type.title()),
            htmlFor=filter_id,
            className="filter-modal-label",
            style={
                "display": "block",
                "marginBottom": "8px",
                "fontWeight": "500",
                "color": "var(--text-primary)",
            },
        )

        # Create control
        if control_type == "dropdown":
            # Use multi option from custom filter options
            multi = filter_def.get("multi", False)

            control = dcc.Dropdown(
                id=filter_id,
                options=filter_def.get("options", []),
                value=filter_def.get("value", "all"),
                clearable=filter_def.get("clearable", True),
                searchable=filter_def.get("searchable", True),
                multi=multi,  # Apply multi-select option
                placeholder=filter_def.get("placeholder", "Select..."),
                className="filter-modal-dropdown",
            )
        elif control_type == "range_slider":
            control = html.Div(
                [
                    label,
                    dcc.RangeSlider(
                        id=filter_id,
                        min=filter_def.get("min", 0),
                        max=filter_def.get("max", 100),
                        step=filter_def.get("step", 1),
                        value=filter_def.get("value", [0, 100]),
                        marks=filter_def.get("marks", {}),
                        tooltip=filter_def.get("tooltip", {"placement": "bottom"}),
                        className="filter-modal-slider",
                    ),
                ]
            )
            return control  # Return early since label is included
        else:
            control = html.Div(f"Unsupported filter type: {control_type}")

        return html.Div([label, control], className="filter-modal-item")

    def get_callback_inputs(self) -> List[Input]:
        """
        Get callback inputs from all filters.

        Returns:
            List[Input]: List of Input objects for all filters
        """
        inputs = []
        for filter_type in self.filter_types:
            filter_id = f"{self.page_prefix}-{filter_type}"
            inputs.append(Input(filter_id, "value"))

        logger.debug(
            f"[CompactFilterWidget] Generated {len(inputs)} callback inputs "
            f"for widget '{self.config.id}'"
        )
        return inputs

    def get_gear_button_id(self) -> str:
        """
        Get the ID of the gear button.

        Returns:
            str: Gear button ID
        """
        return f"{self.config.id}-gear-btn"

    def get_client_config(self) -> Dict[str, Any]:
        """
        Get configuration for JavaScript.

        Returns:
            Dict[str, Any]: Configuration dictionary
        """
        return {
            "widgetType": "compact_filter",
            "id": self.config.id,
            "filterTypes": self.filter_types,
            "compactFilters": self.compact_filters,
            "pagePrefix": self.page_prefix,
            "modalTitle": self.modal_title,
            "showGearIcon": self.show_gear_icon,
            "layout": self.config.to_gridstack_dict(),
        }

    @classmethod
    def from_config(
        cls, config_dict: Dict[str, Any], page_prefix: str = "teams", data_manager=None
    ) -> "CompactFilterWidget":
        """
        Create a CompactFilterWidget from a configuration dictionary.

        Args:
            config_dict: Configuration dictionary with widget specs
            page_prefix: Prefix for filter IDs
            data_manager: DataManager instance for real data

        Returns:
            CompactFilterWidget: Configured widget instance
        """
        required_keys = ["id", "position"]
        for key in required_keys:
            if key not in config_dict:
                raise ValueError(
                    f"Missing required key '{key}' in filter widget config"
                )

        # Create WidgetConfig
        widget_config = WidgetConfig(
            id=config_dict["id"],
            title=config_dict.get("title", ""),
            widget_type="compact_filter",
            position=config_dict["position"],
            styles=config_dict.get("styles", {}),
            properties=config_dict.get("properties", {}),
        )

        # Create widget instance
        return cls(
            config=widget_config,
            filter_types=config_dict.get("filter_types", []),
            compact_filters=config_dict.get("compact_filters", []),
            page_prefix=page_prefix,
            modal_title=config_dict.get("modal_title"),
            show_gear_icon=config_dict.get("show_gear_icon", True),
            gear_icon=config_dict.get("gear_icon", "⚙️"),
            data_manager=data_manager,
            filter_options=config_dict.get("filter_options", {}),
        )
