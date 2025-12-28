"""
Chart widgets with Plotly integration and data visualization support.
"""
import logging
from typing import Any, Dict, List, Optional

from dash import dcc, html

from src.core.visualizations.factory import VisualizationFactory

from .base import BaseWidget, WidgetConfig

# Get module logger
logger = logging.getLogger(__name__)


class ChartWidget(BaseWidget):
    """
    Plotly chart widget with data visualization integration.

    This widget integrates with the visualization system to create
    interactive charts from aggregated data, with support for real-time
    filtering and updates.
    """

    def __init__(
        self,
        config: WidgetConfig,
        visualization_type: str,  # e.g., 'off_ball_runs'
        aggregator=None,
        data_source: Optional[str] = None,
        viz_options: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a chart widget.

        Args:
            config: Widget configuration
            visualization_type: Type of visualization (e.g., 'off_ball_runs')
            aggregator: Data aggregator instance
            data_source: Optional data source identifier
            viz_options: Additional visualization options
        """
        super().__init__(config)
        self.visualization_type = visualization_type
        self.aggregator = aggregator
        self.data_source = data_source or config.data_source
        self.viz_options = viz_options or {}
        self.viz_instance = None
        self._current_figure = None

        # Generate unique IDs - must match callback expectations
        self.graph_id = f"{self.config.id}-graph"
        self.loading_id = f"{self.config.id}-loading"

        logger.info(
            "[ChartWidget] "
            f"Initialized ChartWidget: id='{config.id}', "
            f"graph_id='{self.graph_id}', "
            f"viz_type='{visualization_type}'"
        )

        # Initialize visualization if aggregator is provided
        if self.aggregator:
            self._init_visualization()
        else:
            logger.warning(
                f"[ChartWidget] No aggregator provided for widget '{config.id}'"
            )

    def _init_visualization(self):
        """Initialize the visualization instance with explicit parameters."""
        try:
            logger.debug(
                f"[ChartWidget] Creating visualization instance: {self.visualization_type}"
            )

            # Extract viz_options parameters
            viz_options = self.viz_options.copy() if self.viz_options else {}

            visualization_type = viz_options.pop("visualization_type", "bar")
            aggregation_context = viz_options.pop("aggregation_context", None)

            # Create viz with explicit parameters
            self.viz_instance = VisualizationFactory.create(
                viz_type=self.visualization_type,
                aggregator=self.aggregator,
                filters={},  # Empty initialy
                visualization_type=visualization_type,
                aggregation_context=aggregation_context,
                **viz_options,  # allow other options
            )

            logger.debug(
                f"[ChartWidget] Visualization created successfully for '{self.config.id}'"
            )
        except ValueError as e:
            logger.error(
                f"[ChartWidget] Unknown visualization type '{self.visualization_type}': {e}"
            )
            self.viz_instance = None
        except Exception as e:
            logger.error(
                f"[ChartWidget] Error creating visualization for '{self.config.id}': {e}",
                exc_info=True,
            )
            self.viz_instance = None

    def render(self) -> html.Div:
        """
        Render chart widget as a complete tile with header and graph.

        Returns:
            html.Div: Complete tile structure containing the chart
        """
        logger.debug(f"[ChartWidget] Rendering chart widget: {self.config.id}")

        return html.Div(
            [
                html.Div(
                    [
                        html.Div(self.config.title, className="tile-header"),
                        html.Div(
                            self._render_graph(),
                            className="tile-body",
                            id=self.loading_id,
                        ),
                    ],
                    className="tile",
                )
            ],
            id=self.config.id,
            className="grid-stack-item",
        )

    def _render_graph(self) -> dcc.Graph:
        """
        Render the Plotly graph component.

        Returns:
            dcc.Graph: Plotly Graph component with initial figure
        """
        # Get initial figure
        initial_figure = self._get_initial_figure()

        logger.debug(
            f"[ChartWidget] Creating Graph component with id='{self.graph_id}'"
        )

        return dcc.Graph(
            id=self.graph_id,
            figure=initial_figure,
            config={
                "displayModeBar": True,
                "displaylogo": False,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                "responsive": True,
                "fillFrame": False,
                # IMPORTANT: Disable problematic features
                "staticPlot": False,
                "doubleClick": "reset",  # Reset on double-click
                "scrollZoom": False,  # Disable scroll zoom
            },
            style={
                "width": "100%",
                "height": "100%",
                "minHeight": "150px",  # Reasonable minimum
                "display": "flex",
                "flex": "1 1 auto",
                "margin": "0",
                "padding": "0",
                "overflow": "hidden",
                "position": "relative",
            },
        )

    def _get_initial_figure(self):
        """Get initial Plotly figure for the chart."""
        if self.viz_instance:
            try:
                logger.debug(
                    f"[ChartWidget] Generating initial figure for '{self.config.id}'"
                )
                figure = self.viz_instance.get_figure()
                self._current_figure = figure
                logger.debug(
                    f"[ChartWidget] Initial figure generated for '{self.config.id}'"
                )
                return figure
            except Exception as e:
                logger.error(
                    f"[ChartWidget] Error generating initial figure for '{self.config.id}': {e}",
                    exc_info=True,
                )

        # Fallback to empty figure
        logger.warning(
            f"[ChartWidget] Using empty placeholder figure for '{self.config.id}'"
        )
        return self._create_empty_figure()

    def _create_empty_figure(self):
        """
        Create empty placeholder figure.

        Returns:
            go.Figure: Empty Plotly figure with loading message
        """
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_annotation(
            text=f"{self.config.title}\n(Loading...)",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color="white", size=14),
            align="center",
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=20, r=20, t=40, b=20),
            transition={"duration": 300},
        )
        return fig

    def update_figure(self, filters: Dict[str, Any] = {}):
        """
        Update the chart figure with new filter values.
        Args:
        filters: Dictionary of filter values (match, team, time_range)

        Returns:
            go.Figure: Updated Plotly figure or error placeholder"""
        logger.info(
            "[ChartWidget] Updating figure for '%s' with filters: %s",
            self.config.id,
            filters,
        )

        if not self.viz_instance:
            logger.error(
                f"[ChartWidget] No visualization instance for '{self.config.id}'"
            )
            return self._create_empty_figure()

        try:
            # Apply new filters if provided
            if filters:
                logger.debug(
                    "[ChartWidget] Applying filters to visualization: %s", filters
                )
                self.viz_instance.update_filters(filters)

            # Generate updated figure
            figure = self.viz_instance.get_figure()
            self._current_figure = figure  # NEW: Met à jour le cache

            logger.debug(
                "[ChartWidget] Figure updated successfully for '%s'", self.config.id
            )
            return figure

        except Exception as e:
            logger.error(
                "[ChartWidget] Error updating figure for '%s': %s",
                self.config.id,
                e,
                exc_info=True,
            )
            return self._create_simple_error_figure(str(e))

    def _create_simple_error_figure(self, error_msg: str = ""):
        """Create a simple error figure without transitions."""
        import plotly.graph_objects as go

        # Shorten message for display
        short_msg = error_msg[:50] + "..." if len(error_msg) > 50 else error_msg

        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {short_msg}",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=12, color="white"),
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=20, r=20, t=40, b=20),
        )
        return fig

    def get_client_config(self) -> Dict[str, Any]:
        """
        Get configuration for client-side JavaScript.

        Returns:
            Dict[str, Any]: Configuration dictionary for the client
        """
        return {
            "widgetType": "chart",
            "id": self.config.id,
            "graphId": self.graph_id,
            "visualizationType": self.visualization_type,
            "dataSource": self.data_source,
            "layout": self.config.to_gridstack_dict(),
        }

    def get_callback_outputs(self) -> List:
        """
        Get callback outputs for this widget.

        Returns:
            List: List of Dash Output objects for this widget's callbacks
        """
        from dash import Output

        return [Output(self.graph_id, "figure")]

    def get_callback_inputs(self) -> List:
        """
        Get callback inputs for this widget.

        Returns:
            List: List of Dash Input objects for this widget's callbacks
        """
        from dash import Input

        # Default inputs for teams page filters
        # Can be overridden by specific page implementations
        return [
            Input("teams-match", "value"),
            Input("teams-team", "value"),
            Input("teams-time-range", "value"),
        ]

    def get_current_figure(self):
        """Get the current cached figure without regenerating it."""
        if self._current_figure is not None:
            # Clone the figure to avoid side effects and reload issues
            import plotly.graph_objects as go

            fig_dict = self._current_figure.to_dict()
            return go.Figure(fig_dict)
        return None
