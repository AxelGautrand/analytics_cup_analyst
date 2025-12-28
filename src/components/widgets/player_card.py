"""
Player Attributes Widget - Combines radar chart visualization with attribute scores.
"""
import logging
from typing import Any, Dict, List, Optional

import plotly.graph_objects as go
from dash import dcc, html

from components.widgets.base import BaseWidget, WidgetConfig
from core.visualizations.factory import VisualizationFactory

logger = logging.getLogger(__name__)


class PlayerAttributesWidget(BaseWidget):
    """
    Widget that displays player attributes with a radar chart and attribute scores.

    Features:
    - Radar chart showing category averages
    - Attribute scores display
    - Reactive to player filter changes
    - Clean layout optimized for dashboard tiles
    """

    def __init__(self, config: WidgetConfig, aggregator=None, **kwargs):
        """
        Initialize the player attributes widget.

        Args:
            config: Widget configuration
            aggregator: Data aggregator instance
            **kwargs: Additional parameters including filters, visualization options, etc.
        """
        super().__init__(config)
        self.aggregator = aggregator

        # Get visualization type from options
        self.viz_type = kwargs.get("visualization_type", "radar")

        # Generate unique component IDs
        self.graph_id = f"{config.id}-graph"
        self.scores_id = f"{config.id}-scores"
        self.strengths_id = f"{config.id}-strengths"
        self.table_id = f"{config.id}-table"

        self._current_figure = None
        self._current_player_data = None
        self._current_scores_html = None

        # Store default player information
        self.default_player_label = kwargs.get("default_player_label")
        self.default_player_id = kwargs.get("default_player_id")

        # Store visualization options
        self.viz_options = kwargs.get("viz_options", {})
        self.aggregation_context = kwargs.get(
            "aggregation_context", "player_attributes"
        )

        # Initialize visualization instance
        self.viz_instance = None
        if aggregator:
            try:
                self.viz_instance = VisualizationFactory.create(
                    viz_type="player_attributes",
                    aggregator=aggregator,
                    filters=kwargs.get("filters", {}),
                    visualization_type=self.viz_type,  # Use the visualization type
                    aggregation_context=self.aggregation_context,
                )
            except Exception as e:
                logger.error(f"Failed to create visualization instance: {e}")

        logger.info(
            f"[PlayerAttributesWidget] Initialized '{config.id}' with viz_type: {self.viz_type}"
        )

    def render(self) -> html.Div:
        """
        Render the widget with radar chart and attribute scores.

        Returns:
            html.Div: Complete widget structure
        """
        # Get figure and player data from visualization
        figure = None
        player_data = None

        if self.viz_instance:
            try:
                self.viz_instance.prepare_data()

                # Get data for specific player if provided
                if self.default_player_id:
                    player_data = self.viz_instance.get_player_data()
                    figure = self.viz_instance.create_figure()
                elif self.default_player_label:
                    player_data = self.viz_instance.get_player_data()
                    figure = self.viz_instance.create_figure()
                else:
                    # Get data for first available player
                    player_data = self.viz_instance.get_player_data()
                    figure = self.viz_instance.create_figure()

            except Exception as e:
                logger.error(f"Failed to generate visualization: {e}")

        self._current_figure = figure
        self._current_player_data = player_data
        self._current_scores_html = self._create_scores_html(player_data)

        # Build different layouts based on visualization type
        if self.viz_type == "table":
            # For table view: full-width table
            return html.Div(
                [
                    html.Div(
                        [
                            # Table view (full width)
                            html.Div(
                                dcc.Graph(
                                    id=self.table_id,
                                    figure=figure or self._create_empty_figure(),
                                    config={
                                        "displayModeBar": False,
                                        "displaylogo": False,
                                        "responsive": True,
                                        "scrollZoom": False,
                                    },
                                    style={"height": "600px"},
                                ),
                                className="player-attributes-table-area",
                            ),
                        ],
                        className="tile",
                    )
                ],
                id=self.config.id,
                className="grid-stack-item",
                style=self.config.styles,
            )
        else:
            # For radar view: split layout with chart and scores
            return html.Div(
                [
                    html.Div(
                        [
                            # Main content area
                            html.Div(
                                [
                                    # Left column: Radar chart
                                    html.Div(
                                        dcc.Graph(
                                            id=self.graph_id,
                                            figure=figure
                                            or self._create_empty_figure(),
                                            config={
                                                "displayModeBar": False,
                                                "displaylogo": False,
                                                "responsive": True,
                                            },
                                        ),
                                        className="player-attributes-chart-area",
                                    ),
                                    # Right column: Attribute scores
                                    html.Div(
                                        self._create_scores_html(player_data),
                                        id=self.scores_id,
                                        className="player-attributes-scores-area",
                                    ),
                                ],
                                className="player-attributes-main-content",
                            ),
                        ],
                        className="tile",
                    )
                ],
                id=self.config.id,
                className="grid-stack-item",
                style=self.config.styles,
            )

    def get_current_html(self):
        """Get the currently displayed HTML content (scores)."""
        return self._current_scores_html if self.viz_type != "table" else None

    def get_current_content(self):
        """Get the currently displayed content."""
        if self.viz_type == "table":
            return {"figure": self._current_figure}
        else:
            return {
                "figure": self._current_figure,
                "scores_html": self._current_scores_html,
                "player_data": self._current_player_data,
            }

    def update_from_filters(self, filter_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update widget content based on filter data.
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

            # Update visualization filters if needed
            current_filter_hash = self.viz_instance._get_filter_hash()

            # Check if we need to recalculate all players data
            if (
                self.viz_instance._all_players_cache is None
                or self.viz_instance._last_filter_hash != current_filter_hash
            ):
                self.viz_instance.prepare_data()

            # Get updated player data (optimized - uses cache)
            player_data = self.viz_instance.get_player_data(player_id, player_label)

            # Get updated figure (optimized - uses cached player data)
            figure = self.viz_instance.create_figure(player_id, player_label)

            self._current_figure = figure
            self._current_player_data = player_data
            self._current_scores_html = self._create_scores_html(player_data)

            if self.viz_type == "table":
                # For table view, return only the figure
                return {
                    "figure": figure,
                    "player_data": player_data,
                }
            else:  # For radar view, return figure and scores HTML
                scores_html = self._create_scores_html(player_data)
                return {
                    "figure": figure,
                    "scores_html": scores_html,
                    "player_data": player_data,
                }

        except Exception as e:
            logger.error(f"[{self.config.id}] Error updating from filters: {e}")
            return {"error": str(e)}

    def _create_scores_html(
        self, player_data: Optional[Dict[str, Any]]
    ) -> List[html.Div]:
        """Create HTML for attribute scores display in 2-column grid, original style."""
        if not player_data or "category_averages" not in player_data:
            return [
                html.Div(
                    html.P(
                        "Select a player to view attribute scores",
                        className="no-data-message",
                    ),
                    className="player-attributes-scores-placeholder",
                )
            ]

        category_averages = player_data["category_averages"]
        attributes_data = player_data.get("attributes", {})

        # Display names with full category names
        display_names = {
            "physical": "Physical",
            "mental": "Mental",
            "technical_creation": "Creation",
            "technical_defense": "Defense",
            "technical_attack": "Attack",
        }

        # Build overall score item (no border, special styling)
        overall_avg = player_data.get("overall_average", 0)
        overall_color = self._get_score_color(overall_avg)

        # Get attributes for overall hover (all categories)
        overall_attributes = []
        for category_key, category_info in CATEGORIES_CONFIG.items():
            for attr_key in category_info["attributes"].keys():
                if attr_key in attributes_data:
                    attr = attributes_data[attr_key]
                    overall_attributes.append(
                        {
                            "label": attr["label"],
                            "score": attr["score_rounded"],
                            "color": attr["color"],
                            "category": display_names.get(category_key, category_key),
                        }
                    )

        # Take top 6 attributes for overall hover
        overall_attributes = sorted(
            overall_attributes, key=lambda x: x["score"], reverse=True
        )[:6]

        overall_hover_content = [
            html.Div(
                "Overall Score",
                style={
                    "color": overall_color,
                    "fontWeight": "bold",
                    "fontSize": "14px",
                    "marginBottom": "8px",
                    "textAlign": "center",
                },
            ),
            html.Div(
                f"Average of all categories",
                style={
                    "color": "rgba(255,255,255,0.8)",
                    "fontSize": "12px",
                    "marginBottom": "12px",
                    "textAlign": "center",
                },
            ),
        ]

        if overall_attributes:
            overall_hover_content.append(
                html.Div(
                    "Top Attributes:",
                    style={
                        "color": "rgba(255,255,255,0.7)",
                        "fontSize": "12px",
                        "fontWeight": "bold",
                        "marginBottom": "8px",
                    },
                )
            )

            for attr in overall_attributes:
                overall_hover_content.append(
                    html.Div(
                        [
                            html.Span(
                                "• ",
                                style={"color": attr["color"], "marginRight": "6px"},
                            ),
                            html.Span(
                                f"{attr['label']}: ",
                                style={"color": "rgba(255,255,255,0.9)"},
                            ),
                            html.Span(
                                f"{attr['score']}/20",
                                style={"color": attr["color"], "fontWeight": "bold"},
                            ),
                            html.Span(
                                f" ({attr['category']})",
                                style={
                                    "color": "rgba(255,255,255,0.6)",
                                    "fontSize": "10px",
                                },
                            ),
                        ],
                        style={
                            "fontSize": "11px",
                            "marginBottom": "4px",
                            "display": "flex",
                            "alignItems": "center",
                            "flexWrap": "wrap",
                        },
                    )
                )

        overall_item = html.Div(
            [
                html.Div(
                    "Overall",
                    className="player-attributes-overall-label",
                    style={"color": overall_color},
                ),
                html.Div(
                    [
                        html.Span(
                            str(overall_avg),
                            className="player-attributes-overall-value",
                            style={"color": overall_color},
                        ),
                        html.Span("/20", className="player-attributes-overall-max"),
                    ],
                    className="player-attributes-overall-container",
                ),
                # No score bar for overall
                html.Div(
                    overall_hover_content, className="player-attributes-hover-tooltip"
                ),
            ],
            className="player-attributes-overall-item",
            **{
                "data-category": "overall",
                "data-score": overall_avg,
                "data-color": overall_color,
            },
        )

        # Build regular score items for each category
        score_items = []

        # Define the order for the grid (2 columns, 3 rows including overall)
        category_order = [
            "technical_attack",
            "mental",
            "technical_creation",
            "physical",
            "technical_defense",
        ]

        for category_key in category_order:
            if category_key in category_averages:
                avg_data = category_averages[category_key]
                category_info = CATEGORIES_CONFIG[category_key]

                # Get individual attributes for this category for hover
                category_attributes = []
                for attr_key in category_info["attributes"].keys():
                    if attr_key in attributes_data:
                        attr = attributes_data[attr_key]
                        category_attributes.append(
                            {
                                "label": attr["label"],
                                "score": attr["score_rounded"],
                                "color": attr["color"],
                            }
                        )

                # Create hover content
                hover_content = [
                    html.Div(
                        display_names[category_key],
                        style={
                            "color": category_info["color"],
                            "fontWeight": "bold",
                            "fontSize": "13px",
                            "marginBottom": "8px",
                            "textAlign": "center",
                        },
                    ),
                    html.Div(
                        f"Score: {avg_data['rounded']}/20",
                        style={
                            "color": "white",
                            "fontSize": "12px",
                            "marginBottom": "10px",
                            "textAlign": "center",
                        },
                    ),
                ]

                # Add individual attributes to hover
                if category_attributes:
                    hover_content.append(
                        html.Div(
                            "Attributes:",
                            style={
                                "color": "rgba(255,255,255,0.7)",
                                "fontSize": "11px",
                                "fontWeight": "bold",
                                "marginBottom": "6px",
                            },
                        )
                    )

                    for attr in category_attributes:
                        hover_content.append(
                            html.Div(
                                [
                                    html.Span(
                                        "• ",
                                        style={
                                            "color": attr["color"],
                                            "marginRight": "4px",
                                        },
                                    ),
                                    html.Span(
                                        f"{attr['label']}: ",
                                        style={"color": "rgba(255,255,255,0.9)"},
                                    ),
                                    html.Span(
                                        f"{attr['score']}/20",
                                        style={
                                            "color": attr["color"],
                                            "fontWeight": "bold",
                                        },
                                    ),
                                ],
                                style={
                                    "fontSize": "11px",
                                    "marginBottom": "3px",
                                    "display": "flex",
                                    "alignItems": "center",
                                },
                            )
                        )

                # Create the score item (with border)
                score_item = html.Div(
                    [
                        # Category label
                        html.Div(
                            display_names[category_key],
                            className="player-attributes-category-label",
                            style={"color": category_info["color"]},
                        ),
                        # Score value
                        html.Div(
                            [
                                html.Span(
                                    str(avg_data["rounded"]),
                                    className="player-attributes-score-value",
                                    style={"color": avg_data["color"]},
                                ),
                                html.Span(
                                    "/20", className="player-attributes-score-max"
                                ),
                            ],
                            className="player-attributes-score-container",
                        ),
                        # Score bar
                        html.Div(
                            html.Div(
                                style={
                                    "width": f"{avg_data['average'] / 20 * 100}%",
                                    "backgroundColor": avg_data["color"],
                                }
                            ),
                            className="player-attributes-score-bar",
                        ),
                        # Hidden hover tooltip
                        html.Div(
                            hover_content, className="player-attributes-hover-tooltip"
                        ),
                    ],
                    className="player-attributes-score-item",
                    **{
                        "data-category": category_key,
                        "data-score": avg_data["rounded"],
                        "data-color": category_info["color"],
                    },
                )

                score_items.append(score_item)

        # Create grid with overall first, then other categories
        grid_content = [overall_item] + score_items

        return [html.Div(grid_content, className="player-attributes-scores-grid")]

    def _get_score_color(self, score: float) -> str:
        """
        Get color based on score value.

        Args:
            score: Score out of 20

        Returns:
            str: Color code
        """
        if score >= 16:
            return "#4aff7c"  # Excellent
        elif score >= 13:
            return "#6cbfcf"  # Good
        elif score >= 10:
            return "#489ccb"  # Average
        else:
            return "#e8e8e7"  # Weak

    def _get_percent_color(self, percentile: float) -> str:
        """
        Get color based on percentile.

        Args:
            percentile: Percentile value (0-100)

        Returns:
            str: Color code
        """
        if percentile >= 80:
            return "#4aff7c"  # High
        elif percentile >= 60:
            return "#489ccb"  # Medium
        else:
            return "#e8e8e7"  # Low

    def _create_empty_figure(self) -> go.Figure:
        """
        Create an empty placeholder figure.

        Returns:
            go.Figure: Empty Plotly figure
        """
        fig = go.Figure()
        fig.add_annotation(
            text="Loading player attributes...",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=14, color="rgba(255,255,255,0.7)"),
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
        """
        Get configuration for client-side JavaScript.

        Returns:
            Dict[str, Any]: Configuration dictionary
        """
        config = {
            "widgetType": "player_attributes",
            "id": self.config.id,
            "vizType": self.viz_type,
            "layout": self.config.to_gridstack_dict(),
        }

        # Add different IDs based on visualization type
        if self.viz_type == "table":
            config["tableId"] = self.table_id
        else:
            config["graphId"] = self.graph_id
            config["scoresId"] = self.scores_id
            config["strengthsId"] = self.strengths_id

        return config

    @classmethod
    def from_config(
        cls, config_dict: Dict[str, Any], aggregator, page_prefix: str = "player_focus"
    ) -> "PlayerAttributesWidget":
        """
        Create a PlayerAttributesWidget from a configuration dictionary.

        Args:
            config_dict: Configuration dictionary with widget specs
            aggregator: Data aggregator instance
            page_prefix: Prefix for filter IDs

        Returns:
            PlayerAttributesWidget: Configured widget instance

        Raises:
            ValueError: If required configuration is missing
        """
        required_keys = ["id", "title", "visualization", "position"]
        for key in required_keys:
            if key not in config_dict:
                raise ValueError(f"Missing required key '{key}' in widget config")

        # Extract visualization type from options
        viz_options = config_dict.get("options", {})
        visualization_type = viz_options.get("visualization_type", "radar")

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
            aggregator=aggregator,
            viz_options=viz_options,
            filter_config=filter_config,
            page_prefix=page_prefix,
            default_player_id=config_dict.get("default_player_id"),
            default_player_label=config_dict.get("default_player_label"),
            aggregation_context=config_dict.get(
                "aggregation_context", "player_attributes"
            ),
            visualization_type=visualization_type,  # Pass visualization type
        )


# Categories configuration (should match visualization)
CATEGORIES_CONFIG = {
    "physical": {
        "label": "Physical",
        "attributes": {
            "speed": "Max Speed",
            "acceleration": "Sprints / 90",
            "stamina": "Distance Covered / 90",
            "activity": "Sprint Distance / 90",
        },
        "color": "#ff6384",
    },
    "mental": {
        "label": "Mental",
        "attributes": {
            "off_ball": "Off-Ball Movement",
            "positioning": "Positioning",
            "decision_making": "Decision Making",
        },
        "color": "#489ccb",
    },
    "technical_creation": {
        "label": "Technical - Creation",
        "attributes": {
            "ball_retention": "Ball Retention",
            "passing": "Passing",
            "crossing": "Crossing",
            # "dribbling": "Dribbling",
        },
        "color": "#ff9f43",
    },
    "technical_defense": {
        "label": "Technical - Defense",
        "attributes": {
            "aerial_ability": "Aerial Ability",
            "pressing": "Pressing",
            "tackling": "Tackling",
            "marking": "Marking",
        },
        "color": "#4aff7c",
    },
    "technical_attack": {
        "label": "Technical - Attack",
        "attributes": {"finishing": "Finishing", "long_shots": "Long Shots"},
        "color": "#c56cf0",
    },
}
