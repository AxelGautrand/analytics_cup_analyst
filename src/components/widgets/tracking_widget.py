"""
Tracking Data Widget - Visualizes player tracking and shot data.
"""
import logging
from typing import Any, Dict, List, Optional

import plotly.graph_objects as go
from dash import dcc, html

from src.components.widgets.base import BaseWidget, WidgetConfig
from src.core.visualizations.factory import VisualizationFactory

logger = logging.getLogger(__name__)


class TrackingWidget(BaseWidget):
    """
    Widget that displays tracking data visualizations.

    Features:
    - Heatmap of player positions
    - Shot positions visualization with xG-based sizing
    - Player movement tracking
    - Filter by player only (TODO: team, period, time_range)
    """

    def __init__(self, config: WidgetConfig, aggregator=None, **kwargs):
        """
        Initialize the tracking widget.

        Args:
            config: Widget configuration
            aggregator: Data aggregator instance
            **kwargs: Additional parameters including filters, visualization options, etc.
        """
        super().__init__(config)
        self.aggregator = aggregator

        # Get visualization type from options
        self.viz_type = kwargs.get("visualization_type", "heatmap")

        # Generate unique component IDs
        self.graph_id = f"{config.id}-graph"
        self.viz_type_selector_id = f"{config.id}-viz-type-selector"

        # Store filter configuration
        self.filter_config = kwargs.get("filter_config", {})

        # Store default player information
        self.default_player_id = kwargs.get("default_player_id")
        self.default_player_label = kwargs.get("default_player_label")

        # Visualization options
        self.viz_options = kwargs.get("viz_options", {})

        # Store filters for initialization
        self.initial_filters = kwargs.get("filters", {})

        self._current_figure = None

        # Initialize visualization instance
        self.viz_instance = None
        if aggregator:
            try:
                # Apply default player filter if provided
                filters = self.initial_filters.copy()
                if self.default_player_id and self.default_player_id != "all":
                    filters["player_id"] = self.default_player_id
                elif self.default_player_label and self.default_player_label != "all":
                    filters["player_label"] = self.default_player_label

                self.viz_instance = VisualizationFactory.create(
                    viz_type="tracking",
                    aggregator=aggregator,
                    filters=filters,
                    visualization_type=self.viz_type,
                    aggregation_context="tracking_analysis",
                    **self.viz_options,
                )
            except Exception as e:
                logger.error(f"Failed to create tracking visualization instance: {e}")

        logger.info(
            f"[TrackingWidget] Initialized '{config.id}' with viz_type: {self.viz_type}"
        )

    def get_current_figure(self) -> Optional[go.Figure]:
        """Get the currently displayed tracking figure."""
        return self._current_figure

    def render(self) -> html.Div:
        """
        Render the widget with tracking visualization.

        Returns:
            html.Div: Complete widget structure
        """
        # Get figure from visualization
        figure = None
        if self.viz_instance:
            try:
                self.viz_instance.prepare_data()
                figure = self.viz_instance.create_figure()
            except Exception as e:
                logger.error(f"Failed to generate tracking visualization: {e}")

        self._current_figure = figure

        # Build widget layout
        return html.Div(
            [
                html.Div(
                    [
                        # Main content area
                        html.Div(
                            dcc.Graph(
                                id=self.graph_id,
                                figure=figure or self._create_empty_figure(),
                                config={
                                    "displayModeBar": False,
                                    "displaylogo": False,
                                    "scrollZoom": False,
                                    "responsive": True,
                                },
                            ),
                            className="widget-content",
                            style={
                                "height": "100%",
                            },
                        )
                    ],
                    className="tile",
                )
            ],
            id=self.config.id,
            className="grid-stack-item",
            style=self.config.styles,
            **{"data-widget-type": "tracking", "data-viz-type": self.viz_type},
        )

    def _create_viz_type_selector(self) -> html.Div:
        """
        Create visualization type selector dropdown.

        Returns:
            html.Div: Dropdown component for visualization type selection
        """
        viz_types = [
            {"label": "Heatmap", "value": "heatmap"},
            {"label": "Shot Positions", "value": "shots"},
            {"label": "Combined View", "value": "combined"},
        ]

        return html.Div(
            [
                html.Label(
                    "View:",
                    style={
                        "color": "rgba(255,255,255,0.8)",
                        "marginRight": "8px",
                        "fontSize": "12px",
                    },
                ),
                dcc.Dropdown(
                    id=self.viz_type_selector_id,
                    options=viz_types,  # type: ignore
                    value=self.viz_type,
                    clearable=False,
                    searchable=False,
                    style={
                        "width": "140px",
                        "backgroundColor": "rgba(30, 35, 40, 0.8)",
                        "border": "1px solid rgba(72, 156, 203, 0.3)",
                        "color": "white",
                    },
                    className="custom-dropdown",
                ),
            ],
            style={"display": "flex", "alignItems": "center"},
        )

    def update_from_filters(self, filter_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update widget content based on filter data.

        Args:
            filter_data: Dictionary containing filter values

        Returns:
            Dict[str, Any]: Update instructions for the widget
        """
        try:
            if not self.viz_instance:
                logger.warning(
                    f"[{self.config.id}] No visualization instance available"
                )
                return {"error": "Visualization instance not available"}

            # Extract player information from filters
            # FIXME : Confusion between player_id and player_label
            player_id = filter_data.get("player_id")
            player_label = filter_data.get("player_label")

            # Update visualization filters
            new_filters = {}

            # if player_id and player_id != "all":
            # new_filters["player_id"] = player_id
            # logger.debug(f"[{self.config.id}] Updating for player ID: {player_id}")
            if player_label and player_label != "all":
                # Try to extract player ID from label if possible
                # TODO: Implement player name to ID mapping if needed
                new_filters["player_label"] = player_label
                logger.info(
                    f"[{self.config.id}] Updating for player label: {player_label}"
                )

            # Apply new filters
            if new_filters:
                self.viz_instance.update_filters(new_filters)

            # Update visualization type if changed
            viz_type = filter_data.get("viz_type")
            if viz_type and viz_type != self.viz_type:
                self.viz_type = viz_type
                self.viz_instance.viz_type = viz_type
                logger.info(
                    f"[{self.config.id}] Visualization type changed to: {viz_type}"
                )

            # Prepare data with new filters
            self.viz_instance.prepare_data()

            # Create updated figure
            figure = self.viz_instance.create_figure()

            self._current_figure = figure

            # Prepare update data
            update_data = {"figure": figure, "viz_type": self.viz_type}

            # Add metadata for logging
            if hasattr(self.viz_instance, "data") and self.viz_instance.data:
                tracking_len = len(self.viz_instance.data.get("tracking", []))
                shots_len = (
                    len(self.viz_instance.data.get("shots", []))
                    if self.viz_instance.data.get("shots") is not None
                    else 0
                )
                update_data["metadata"] = {
                    "tracking_frames": tracking_len,
                    "shots_count": shots_len,
                    "filters": new_filters,
                }

            logger.info(
                f"[{self.config.id}] Updated successfully with {update_data.get('metadata', {})}"
            )
            return update_data

        except Exception as e:
            logger.error(
                f"[{self.config.id}] Error updating from filters: {e}", exc_info=True
            )
            return {"error": str(e)}

    def _create_empty_figure(
        self, message: str = "Select a player to view tracking data"
    ) -> go.Figure:
        """
        Create an empty placeholder figure.

        Args:
            message: Message to display in the placeholder

        Returns:
            go.Figure: Empty Plotly figure
        """
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=14, color="rgba(255,255,255,0.7)", family="Arial"),
            align="center",
            bgcolor="rgba(0,0,0,0.5)",
            bordercolor="rgba(72, 156, 203, 0.3)",
            borderwidth=1,
            borderpad=10,
        )

        # Add pitch background for context even in empty state
        try:
            # Create minimal pitch outline
            pitch_length = 105
            pitch_width = 68

            fig.add_shape(
                type="rect",
                x0=0,
                y0=0,
                x1=pitch_width,
                y1=pitch_length,
                line=dict(color="rgba(255,255,255,0.1)", width=1),
                fillcolor="rgba(11, 56, 30, 0.1)",
                layer="below",
            )

            # Update layout with pitch dimensions
            fig.update_layout(
                xaxis=dict(
                    range=[-5, pitch_width + 5],
                    showgrid=False,
                    zeroline=False,
                    showticklabels=False,
                    scaleanchor="y",
                    scaleratio=1,
                ),
                yaxis=dict(
                    range=[-5, pitch_length + 5],
                    showgrid=False,
                    zeroline=False,
                    showticklabels=False,
                ),
            )
        except:
            pass

        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=10),
            height=400,
        )
        return fig

    def get_client_config(self) -> Dict[str, Any]:
        """
        Get configuration for client-side JavaScript.

        Returns:
            Dict[str, Any]: Configuration dictionary
        """
        config = {
            "widgetType": "tracking",
            "id": self.config.id,
            "vizType": self.viz_type,
            "layout": self.config.to_gridstack_dict(),
            "graphId": self.graph_id,
            "vizTypeSelectorId": self.viz_type_selector_id,
            "defaultPlayerId": self.default_player_id,
            "defaultPlayerLabel": self.default_player_label,
        }

        # Add filter configuration
        if self.filter_config:
            config["filterConfig"] = self.filter_config

        return config

    def get_callback_inputs(self) -> List:
        """
        Get callback inputs for this widget.

        Returns:
            List: List of Dash Input objects
        """
        from dash import Input

        return [Input(self.viz_type_selector_id, "value")]

    def get_callback_outputs(self) -> List:
        """
        Get callback outputs for this widget.

        Returns:
            List: List of Dash Output objects
        """
        from dash import Output

        return [Output(self.graph_id, "figure")]

    def register_callbacks(self, app):
        """
        Register callbacks for this widget.

        Args:
            app: Dash application instance
        """
        from dash import callback_context
        from dash.exceptions import PreventUpdate

        @app.callback(self.get_callback_outputs(), self.get_callback_inputs())
        def update_viz_type(selected_viz_type):
            """
            Update visualization type when dropdown changes.
            """
            if not callback_context.triggered:
                raise PreventUpdate

            if selected_viz_type != self.viz_type:
                self.viz_type = selected_viz_type
                if self.viz_instance:
                    self.viz_instance.viz_type = selected_viz_type
                    self.viz_instance.prepare_data()
                    figure = self.viz_instance.create_figure()
                    return [figure]

            raise PreventUpdate

    @classmethod
    def from_config(
        cls, config_dict: Dict[str, Any], aggregator, page_prefix: str = "tracking"
    ) -> "TrackingWidget":
        """
        Create a TrackingWidget from a configuration dictionary.

        Args:
            config_dict: Configuration dictionary with widget specs
            aggregator: Data aggregator instance
            page_prefix: Prefix for filter IDs

        Returns:
            TrackingWidget: Configured widget instance

        Raises:
            ValueError: If required configuration is missing
        """
        required_keys = ["id", "title", "visualization", "position"]
        for key in required_keys:
            if key not in config_dict:
                raise ValueError(f"Missing required key '{key}' in widget config")

        # Extract visualization type from options
        viz_options = config_dict.get("options", {})
        visualization_type = viz_options.get("type", "heatmap")

        # Extract filter configuration
        filter_types = config_dict.get("filters", [])
        filter_config = {}
        for filter_type in filter_types:
            filter_config[filter_type] = f"{page_prefix}-{filter_type}"

        # Extract filters from configuration
        filters = config_dict.get("initial_filters", {})

        # Create WidgetConfig
        widget_config = WidgetConfig(
            id=config_dict["id"],
            title=config_dict["title"],
            widget_type="chart",
            position=config_dict["position"],
            data_source=config_dict.get("data_source", "tracking"),
            styles=config_dict.get("styles", {}),
            properties=config_dict.get("properties", {}),
        )

        return cls(
            config=widget_config,
            aggregator=aggregator,
            viz_options=viz_options,
            filter_config=filter_config,
            filters=filters,
            default_player_id=config_dict.get("default_player_id"),
            default_player_label=config_dict.get("default_player_label"),
            visualization_type=visualization_type,
        )
