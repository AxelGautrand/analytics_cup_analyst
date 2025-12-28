"""
Player Style Profile Widget - Combines Plotly chart with HTML components
"""
import logging
from typing import Any, Dict, Optional

import plotly.graph_objects as go
from dash import dcc, html

from src.components.widgets.base import BaseWidget, WidgetConfig
from src.core.visualizations.factory import VisualizationFactory

logger = logging.getLogger(__name__)


# FIXME : Handle players with multiple positions between matches


class PlayerStyleProfileWidget(BaseWidget):
    """Custom widget that properly combines Plotly with HTML."""

    def __init__(self, config: WidgetConfig, aggregator=None, **kwargs):
        super().__init__(config)
        self.aggregator = aggregator
        self.graph_id = f"{config.id}-graph"
        self.details_id = f"{config.id}-details"
        self.default_player_label = kwargs.get("default_player_label")
        self.default_player_id = kwargs.get("default_player_id")

        self._current_figure = None
        self._current_player_data = None
        self._current_strengths_html = None

        # Initialize visualization
        self.viz_instance = None
        if aggregator:
            try:
                self.viz_instance = VisualizationFactory.create(
                    viz_type="player_style_profile",
                    aggregator=aggregator,
                    filters=kwargs.get("filters", {}),
                    visualization_type=kwargs.get("viz_options", {}).get(
                        "visualization_type", "radar"
                    ),
                )
            except Exception as e:
                logger.error(f"Failed to create visualization: {e}")

    def render(self) -> html.Div:
        """Render widget with separate Plotly and HTML sections."""
        # Get figure from visualization
        figure = None
        player_data = None

        if self.viz_instance:
            try:
                self.viz_instance.prepare_data()
                if self.default_player_id:
                    # FIXME : Confusion with label and id within the code
                    player_data = self.viz_instance.get_player_data(
                        player_id=self.default_player_id
                    )
                    figure = self.viz_instance.create_figure(
                        player_id=self.default_player_id
                    )
                elif self.default_player_label:
                    player_data = self.viz_instance.get_player_data(
                        player_label=self.default_player_label
                    )
                    figure = self.viz_instance.create_figure(
                        player_label=self.default_player_label
                    )
                else:
                    figure = self.viz_instance.create_figure()
                    # Get player data for HTML
                    player_data = self.viz_instance.get_player_data()

            except Exception as e:
                logger.error(f"Failed to generate figure: {e}")

        self._current_figure = figure
        self._current_player_data = player_data
        self._current_strengths_html = self._create_strengths_html(player_data)

        return html.Div(
            [
                html.Div(
                    [
                        # Main content with two columns
                        html.Div(
                            [
                                # Left: Plotly chart
                                html.Div(
                                    dcc.Graph(
                                        id=self.graph_id,
                                        figure=figure or self._create_empty_figure(),
                                        config={
                                            "displayModeBar": False,
                                            "displaylogo": False,
                                            "responsive": True,
                                        },
                                    ),
                                    className="player-style-profile-chart-area",
                                ),
                            ],
                            className="player-style-profile-main-content",
                        ),
                        # Bottom: Strengths (always visible)
                        html.Div(
                            self._create_strengths_html(player_data),
                            className="player-style-profile-strengths-container",
                        ),
                    ],
                    className="tile",
                )
            ],
            id=self.config.id,
            className="grid-stack-item",
            style=self.config.styles,
        )

    def update_from_filters(self, filter_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update widget content based on filter data.

        Args:
            filter_data: Dictionary containing filter information (player_id, player_label, etc.)

        Returns:
            Dictionary with updated content for callback
        """
        try:
            # Extract player information from filters
            player_id = filter_data.get("player_id")
            player_label = filter_data.get("player_label")

            if (not player_id and not player_label) or not self.viz_instance:
                logger.warning(
                    f"[{self.config.id}] Missing player information or visualization instance"
                )
                return {"error": "Missing player information"}

            # Update visualization filters
            if player_id:
                self.viz_instance.filters["player_id"] = player_id

            # Get updated player data
            player_data = (
                self.viz_instance.get_player_data(
                    player_id=player_id, player_label=player_label
                )
                if hasattr(self.viz_instance, "get_player_data")
                else None
            )

            # Get updated figure with player info (ID or label)
            figure = self.viz_instance.create_figure(
                player_id=player_id, player_label=player_label
            )

            # Get strengths HTML
            strengths_html = self._create_strengths_html(player_data)

            self._current_figure = figure
            self._current_player_data = player_data
            self._current_strengths_html = strengths_html

            return {
                "figure": figure,
                "strengths_html": strengths_html,
                "player_data": player_data,
            }

        except Exception as e:
            logger.error(f"[{self.config.id}] Error updating from filters: {e}")
            return {"error": str(e)}

    def _create_roles_html(self, player_data: Optional[Dict[str, Any]]) -> html.Div:
        """Create HTML for roles list."""
        if not player_data or "roles" not in player_data:
            return html.Div("No role data", className="no-data")

        roles = player_data["roles"]
        sorted_roles = sorted(roles.items(), key=lambda x: x[1], reverse=True)

        role_items = []
        for role, percent in sorted_roles:
            # Get color based on percentage
            color = self._get_percent_color(percent)

            role_items.append(
                html.Div(
                    [
                        html.Span(
                            f"{percent:.1f}%",
                        ),
                        html.Span(
                            role,
                        ),
                    ],
                    className="player-style-profile-role-item",
                )
            )

        return html.Div(role_items, className="roles-list")

    def _create_strengths_html(self, player_data: Optional[Dict[str, Any]]) -> html.Div:
        """Create HTML for strengths."""
        if (
            not player_data
            or "strengths" not in player_data
            or not player_data["strengths"]
        ):
            return html.Div(
                [
                    html.Div(
                        "Select a player to view strengths", className="no-strengths"
                    )
                ]
            )

        strengths = player_data["strengths"]

        strength_items = []
        for strength in strengths:
            color = self._get_percent_color(strength["percentile"])

            strength_items.append(
                html.Div(
                    [
                        html.Div(
                            style={
                                "borderRadius": "50%",
                                "backgroundColor": color,
                                "flexShrink": "0",
                            }
                        ),
                        html.Span(
                            strength["label"],
                            style={"color": "var(--text-primary)"},
                            className="player-style-profile-strength-label",
                        ),
                        html.Span(
                            f"Top: {100-strength['percentile']}%",
                            style={
                                "color": color,
                            },
                            className="player-style-profile-strength-value",
                        ),
                    ],
                    className="player-style-profile-strength-item",
                )
            )

        return html.Div(
            [html.Div(strength_items, className="player-style-profile-strengths-list")]
        )

    def _get_percent_color(self, percent: float) -> str:
        """Get color based on percentage."""
        if percent >= 80:
            return "#4aff7c"  # High
        elif percent >= 60:
            return "#489ccb"  # Medium
        else:
            return "#e8e8e7"  # Low

    def get_current_figure(self) -> Optional[go.Figure]:
        """
        Get the currently displayed figure without recalculating.

        Returns:
            The cached figure or None if not available
        """
        return self._current_figure

    def get_current_html(self):
        """Get the currently displayed HTML content (strengths)."""
        return self._current_strengths_html

    def get_current_content(self):
        """Get the currently displayed content."""
        if self._current_figure is None and self._current_strengths_html is None:
            return None

        return {
            "figure": self._current_figure,
            "strengths_html": self._current_strengths_html,
            "player_data": self._current_player_data,
        }

    def _create_empty_figure(self) -> go.Figure:
        """Create empty figure."""
        fig = go.Figure()
        fig.add_annotation(
            text="Loading...",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=12, color="rgba(255,255,255,0.7)"),
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=10, r=10, t=10, b=10),
        )
        return fig

    def get_client_config(self) -> Dict[str, Any]:
        """Get configuration for JavaScript."""
        return {
            "widgetType": "player_style_profile",
            "id": self.config.id,
            "graphId": self.graph_id,
            "layout": self.config.to_gridstack_dict(),
        }

    @classmethod
    def from_config(
        cls, config_dict: Dict[str, Any], aggregator, page_prefix: str = "teams"
    ) -> "PlayerStyleProfileWidget":
        """
        Create an AutoChartWidget from a configuration dictionary.

        Args:
            config_dict: Configuration dictionary with widget specs
            aggregator: Data aggregator instance
            page_prefix: Prefix for filter IDs

        Returns:
            AutoChartWidget: Configured widget instance

        Raises:
            ValueError: If required configuration is missing
        """
        required_keys = ["id", "title", "visualization", "position"]
        for key in required_keys:
            if key not in config_dict:
                raise ValueError(f"Missing required key '{key}' in widget config")

        # Extract filter configuration
        filter_types = config_dict.get("filters", [])
        filter_config = {}
        for filter_type in filter_types:
            filter_config[filter_type] = f"{page_prefix}-{filter_type}"

        # Create WidgetConfig
        widget_config = WidgetConfig(
            id=config_dict["id"],
            title=config_dict["title"],
            widget_type="chart",
            position=config_dict["position"],
            data_source=config_dict.get("data_source", "dynamic_events"),
            styles=config_dict.get("styles", {}),
        )

        return cls(
            config=widget_config,
            visualization_type=config_dict["visualization"],
            aggregator=aggregator,
            viz_options=config_dict.get("options", {}),
            filter_config=filter_config,
            page_prefix=page_prefix,
            default_player_id=config_dict.get("default_player_id"),
            default_player_label=config_dict.get("default_player_label"),
        )
