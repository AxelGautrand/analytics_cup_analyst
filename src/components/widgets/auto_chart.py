"""
Auto-configurable Chart Widget for plug-and-play dashboard integration.

This widget extends the base ChartWidget with automatic configuration
capabilities, making it easy to create chart widgets from configuration
files without manual coding.
"""
import logging
from typing import Any, Dict, List, Optional, Union

import plotly.graph_objects as go
from dash import Output

from .base import WidgetConfig
from .charts import ChartWidget

# Get module logger
logger = logging.getLogger(__name__)


class AutoChartWidget(ChartWidget):
    """
    Auto-configurable chart widget that can be created from configuration.

    This widget extends ChartWidget with:
    - Automatic filter ID generation
    - Configuration-based initialization
    - Automatic callback registration
    """

    def __init__(
        self,
        config: WidgetConfig,
        visualization_type: str,
        aggregator=None,
        data_source: Optional[str] = None,
        viz_options: Optional[Dict[str, Any]] = None,
        filter_config: Optional[Dict[str, str]] = None,
        page_prefix: str = "teams",
    ):
        """
        Initialize an auto-configurable chart widget.

        Args:
            config: Widget configuration
            visualization_type: Type of visualization (e.g., 'off_ball_runs')
            aggregator: Data aggregator instance
            data_source: Optional data source identifier
            viz_options: Additional visualization options
            filter_config: Dictionary mapping filter types to filter IDs
            page_prefix: Prefix for filter IDs (e.g., 'teams', 'players')
        """
        super().__init__(
            config=config,
            visualization_type=visualization_type,
            aggregator=aggregator,
            data_source=data_source,
            viz_options=viz_options,
        )

        self.page_prefix = page_prefix
        self.filter_config = filter_config or {}
        self.filter_ids = self._generate_filter_ids()

        # Store aggregation context
        self.aggregation_context = (
            viz_options.get("aggregation_context") if viz_options else None
        )

        logger.info(
            f"[AutoChartWidget] Initialized '{config.id}' with "
            f"filters: {list(self.filter_ids.keys())}"
        )

    @classmethod
    def from_config(
        cls, config_dict: Dict[str, Any], aggregator, page_prefix: str = "teams"
    ) -> "AutoChartWidget":
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

        # Create widget instance
        return cls(
            config=widget_config,
            visualization_type=config_dict["visualization"],
            aggregator=aggregator,
            viz_options=config_dict.get("options", {}),
            filter_config=filter_config,
            page_prefix=page_prefix,
        )

    def _generate_filter_ids(self) -> Dict[str, str]:
        """
        Generate filter IDs based on filter configuration.

        Returns:
            Dict[str, str]: Mapping of filter types to their IDs
        """
        filter_ids = {}
        for filter_type, filter_id in self.filter_config.items():
            # If filter_id is just a type name, prepend page prefix
            if "-" not in filter_id:
                filter_ids[filter_type] = f"{self.page_prefix}-{filter_id}"
            else:
                filter_ids[filter_type] = filter_id

        return filter_ids

    def get_callback_inputs(self) -> List:
        """
        Get callback inputs based on filter configuration.

        Returns:
            List: List of Dash Input objects for configured filters
        """
        from dash import Input

        inputs = []
        for filter_type, filter_id in self.filter_ids.items():
            inputs.append(Input(filter_id, "value"))

        logger.debug(
            f"[AutoChartWidget] Generated {len(inputs)} callback inputs "
            f"for widget '{self.config.id}'"
        )
        return inputs

    def update_from_filters(self, **filter_values) -> Union[go.Figure, Dict[str, Any]]:
        """
        Update widget with filter values.

        Args:
            **filter_values: Keyword arguments with filter values

        Returns:
            Dict[str, Any]: Updated figure

        Note:
            This is a convenience method for use in auto-generated callbacks
        """
        filters = {}
        for filter_type in self.filter_ids.keys():
            if filter_type in filter_values:
                filters[filter_type] = filter_values[filter_type]

        logger.debug(
            f"[AutoChartWidget] Updating '{self.config.id}' with filters: {filters}"
        )
        return self.update_figure(filters)

    def update_figure(self, filters: Dict[str, Any] = {}):
        """Override pour passer le contexte d'agrégation."""
        if not self.viz_instance:
            return self._create_empty_figure()

        try:
            # Pass the aggragation context if possible
            if self.aggregation_context and hasattr(
                self.viz_instance, "aggregation_context"
            ):
                self.viz_instance.aggregation_context = self.aggregation_context

            # Apply filters
            if filters:
                self.viz_instance.update_filters(filters)

            # Generate figures
            return self.viz_instance.get_figure()

        except Exception as e:
            logger.error(f"Error updating figure: {e}")
            return self._create_simple_error_figure(str(e))

    def get_update_callback_spec(self) -> Dict[str, Any]:
        """
        Get specification for auto-generated callback.

        Returns:
            Dict[str, Any]: Dictionary with callback specification
        """
        return {
            "widget_id": self.config.id,
            "output": Output(f"{self.config.id}-graph", "figure"),
            "inputs": self.get_callback_inputs(),
            "function_name": f"update_{self.config.id}",
        }
