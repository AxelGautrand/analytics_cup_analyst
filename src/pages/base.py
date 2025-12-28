"""
Base class for all configuration-driven pages.

This module provides a reusable base class for creating dashboard pages
from YAML configuration files, with automatic widget creation, layout
generation, and callback registration.
"""
import json
import logging
import os
import time
from typing import Any, Dict, Optional

import yaml
from dash import Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate

from src.components.widgets.auto_chart import AutoChartWidget
from src.components.widgets.filter import CompactFilterWidget
from src.components.widgets.player_card import PlayerAttributesWidget
from src.components.widgets.player_info import PlayerInfoWidget
from src.components.widgets.player_roles import PlayerStyleProfileWidget
from src.components.widgets.registry import WidgetConfig, WidgetRegistry
from src.components.widgets.tracking_widget import TrackingWidget
from src.core.data_manager import data_manager

# Get module logger
logger = logging.getLogger(__name__)


class PageBase:
    """
    Base class for configuration-driven dashboard pages.

    This class handles:
    - Loading configuration from YAML files
    - Creating widgets from configuration
    - Generating GridStack layouts
    - Registering auto-generated callbacks
    - Managing page lifecycle

    Subclasses should define:
    - page_id: Unique page identifier
    - title: Page display title
    - page_prefix: Prefix for widget IDs (e.g., 'teams', 'players')
    """

    def __init__(
        self,
        page_id: str,
        title: str,
        page_prefix: Optional[str] = None,
        config_path: Optional[str] = None,
    ):
        """
        Initialize a configuration-driven page.

        Args:
            page_id: Unique identifier for the page
            title: Display title for the page
            page_prefix: Prefix for widget IDs (defaults to page_id)
            config_path: Path to configuration file (defaults to pages/{page_id}/config.yaml)
        """
        self.page_id = page_id
        self.title = title
        self.page_prefix = page_prefix or page_id
        self.config_path = config_path or self._get_default_config_path()
        self.widgets: Dict[str, Any] = {}
        self._callbacks_registered = False
        self._config = None

        logger.info(
            f"[PageBase:{self.page_id}] Initialized page '{title}' with prefix '{self.page_prefix}'"
        )

    def _get_default_config_path(self) -> str:
        """
        Get default configuration file path.

        Returns:
            str: Path to configuration file
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(current_dir, self.page_id)
        config_path = os.path.join(config_dir, "config.yaml")

        if not os.path.exists(config_path):
            # Fallback: look for config in pages directory
            config_path = os.path.join(current_dir, f"{self.page_id}", "config.yaml")

        return config_path

    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load page configuration from YAML file.

        Args:
            config_path: Path to configuration file

        Returns:
            Dict[str, Any]: Page configuration dictionary

        Raises:
            FileNotFoundError: If configuration file doesn't exist
            ValueError: If configuration is invalid
        """
        path = config_path or self.config_path

        logger.info(f"[PageBase:{self.page_id}] Loading configuration from: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # Validate basic structure
            if "page" not in config:
                raise ValueError("Configuration missing 'page' section")
            if "widgets" not in config:
                raise ValueError("Configuration missing 'widgets' section")

            # Override page config from YAML if present
            if "id" in config["page"]:
                self.page_id = config["page"]["id"]
            if "title" in config["page"]:
                self.title = config["page"]["title"]
            if "prefix" in config["page"]:
                self.page_prefix = config["page"]["prefix"]

            self._config = config
            logger.info(f"[PageBase:{self.page_id}] Configuration loaded successfully")

            return config

        except FileNotFoundError:
            logger.error(
                f"[PageBase:{self.page_id}] Configuration file not found: {path}"
            )
            raise
        except yaml.YAMLError as e:
            logger.error(
                f"[PageBase:{self.page_id}] Invalid YAML in configuration: {e}"
            )
            raise
        except Exception as e:
            logger.error(f"[PageBase:{self.page_id}] Error loading configuration: {e}")
            raise

    def _create_widgets_from_config(self):
        """Create widget instances from configuration."""
        if not self._config:
            raise RuntimeError("Configuration not loaded. Call _load_config() first.")

        logger.info(f"[PageBase:{self.page_id}] Creating widgets from configuration...")

        for widget_config in self._config["widgets"]:
            try:
                widget = self._create_single_widget(widget_config)
                if widget:
                    self.widgets[widget_config["id"]] = widget
                    logger.debug(
                        f"[PageBase:{self.page_id}] Created widget: {widget_config['id']}"
                    )
            except Exception as e:
                logger.error(
                    f"[PageBase:{self.page_id}] Failed to create widget '{widget_config.get('id', 'unknown')}': {e}"
                )
                continue

        logger.info(
            f"[PageBase:{self.page_id}] Created {len(self.widgets)} widgets successfully"
        )

    def _create_single_widget(self, widget_config: Dict[str, Any]):
        """
        Create a single widget instance from configuration.

        Args:
            widget_config: Widget configuration dictionary

        Returns:
            BaseWidget: Widget instance or None if creation failed
        """
        widget_type = widget_config.get("type")
        widget_id = widget_config.get("id")

        if not widget_type:
            logger.error(
                f"[PageBase:{self.page_id}] Widget config missing 'type': {widget_config}"
            )
            return None

        if not widget_id:
            logger.error(
                f"[PageBase:{self.page_id}] Widget config missing 'id': {widget_config}"
            )
            return None

        try:
            if widget_type == "chart":
                widget = AutoChartWidget.from_config(
                    config_dict=widget_config,
                    aggregator=data_manager.aggregator_manager,
                    page_prefix=self.page_prefix,
                )
            elif widget_type == "compact_filter":
                widget = CompactFilterWidget.from_config(
                    config_dict=widget_config,
                    page_prefix=self.page_prefix,
                    data_manager=data_manager,
                )
            elif widget_type == "player_info":
                widget = PlayerInfoWidget.from_config(
                    config_dict=widget_config,
                    page_prefix=self.page_prefix,
                    data_manager=data_manager,
                )
            elif widget_type == "player_style_profile":
                widget = PlayerStyleProfileWidget.from_config(
                    config_dict=widget_config,
                    aggregator=data_manager.aggregator_manager,
                    page_prefix=self.page_prefix,
                )
            elif widget_type == "player_attributes":
                widget = PlayerAttributesWidget.from_config(
                    config_dict=widget_config,
                    aggregator=data_manager.aggregator_manager,
                    page_prefix=self.page_prefix,
                )
            elif widget_type == "player_tracking":
                widget = TrackingWidget.from_config(
                    config_dict=widget_config,
                    aggregator=data_manager.aggregator_manager,
                    page_prefix=self.page_prefix,
                )
            else:
                # Try to create from registry
                if WidgetRegistry.has_widget_type(widget_type):
                    config_obj = WidgetConfig(
                        id=widget_id,
                        title=widget_config.get("title", widget_id),
                        widget_type=widget_type,
                        position=widget_config.get(
                            "position", {"x": 0, "y": 0, "w": 4, "h": 3}
                        ),
                        data_source=widget_config.get("data_source"),
                        styles=widget_config.get("styles", {}),
                        properties=widget_config.get("properties", {}),
                    )

                    widget = WidgetRegistry.create(
                        widget_type=widget_type,
                        widget_config=config_obj,
                        **widget_config,
                    )
                else:
                    logger.error(
                        f"[PageBase:{self.page_id}] Unknown widget type: {widget_type}"
                    )
                    return None

            # Register the widget instance in the registry
            WidgetRegistry.register_instance(widget_id, widget)
            logger.debug(
                f"[PageBase:{self.page_id}] Registered widget instance '{widget_id}'"
            )

            return widget

        except Exception as e:
            logger.error(
                f"[PageBase:{self.page_id}] Error creating widget '{widget_id}': {e}"
            )
            return None

    def _generate_layout_from_config(self) -> html.Div:
        """
        Generate page layout from configuration.

        Returns:
            html.Div: Complete page layout
        """
        if not self.widgets:
            raise RuntimeError(
                "No widgets created. Call _create_widgets_from_config() first."
            )

        if not self._config:
            raise RuntimeError("Configuration not loaded. Call _load_config() first.")

        logger.info(
            f"[PageBase:{self.page_id}] Generating layout from configuration..."
        )

        # Render all widgets
        rendered_widgets = []
        for widget_id, widget in self.widgets.items():
            try:
                rendered_widget = widget.render()
                rendered_widgets.append(rendered_widget)
                logger.debug(f"[PageBase:{self.page_id}] Rendered widget: {widget_id}")
            except Exception as e:
                logger.error(
                    f"[PageBase:{self.page_id}] Failed to render widget '{widget_id}': {e}"
                )

        # Create widgets configuration for JavaScript GridStack
        widgets_config = []
        for widget_config in self._config["widgets"]:
            widget_id = widget_config.get("id")
            if widget_id in self.widgets:
                widget_obj = self.widgets[widget_id]
                gs_config = widget_obj.config.to_gridstack_dict()
                widgets_config.append(gs_config)

        logger.info(
            f"[PageBase:{self.page_id}] Generated layout with {len(rendered_widgets)} widgets"
        )

        # Generate page layout with dynamic IDs
        return html.Div(
            [
                # Page header with title
                html.Div(
                    [html.H2(self.title, className="page-title")],
                    className="page-title-bar",
                ),
                # Main content area with GridStack container
                html.Div(
                    className="grid-wrapper",
                    children=[
                        html.Div(
                            id={
                                "type": "grid-container",
                                "page": self.page_prefix,  # Pattern matching ID
                            },
                            className="grid-stack page-grid-stack",
                            children=[
                                # JSON configuration for JavaScript GridStack
                                html.Script(
                                    json.dumps(widgets_config),
                                    id=f"{self.page_prefix}-layout-json",
                                    type="application/json",
                                ),
                                # Widgets container (initially hidden)
                                html.Div(
                                    rendered_widgets,
                                    id=f"{self.page_prefix}-widgets-container",
                                    style={"display": "none"},
                                ),
                            ],
                        ),
                    ],
                ),
                # Script to initialize GridStack after page load
                dcc.Interval(
                    id={
                        "type": "grid-init-interval",
                        "page": self.page_prefix,  # Pattern matching ID
                    },
                    interval=1000,
                    n_intervals=0,
                    max_intervals=1,
                ),
            ],
            className="page",
        )

    def _generate_auto_callbacks(self):
        """
        Generate and register callbacks automatically based on widget configurations.

        This method analyzes widget dependencies and creates appropriate
        callbacks for chart widgets that depend on filter widgets.
        """
        if not self.widgets:
            logger.warning(
                f"[PageBase:{self.page_id}] No widgets to generate callbacks for"
            )
            return

        logger.info(f"[PageBase:{self.page_id}] Generating automatic callbacks...")

        # Register callbacks for all widgets that have callback methods
        for _, widget in self.widgets.items():
            self._register_widget_callbacks(widget)

    def _register_widget_callbacks(self, widget):
        """
        Register callbacks for any widget that supports them.

        Args:
            widget: Widget instance
        """
        try:
            # Check if widget has callback methods
            has_callback_methods = (
                hasattr(widget, "get_callback_function")
                and hasattr(widget, "get_callback_inputs")
                and hasattr(widget, "get_callback_outputs")
            )

            if has_callback_methods:
                callback_func = widget.get_callback_function()
                callback_inputs = widget.get_callback_inputs()
                callback_outputs = widget.get_callback_outputs()

                if callback_inputs and callback_outputs:
                    # Register the callback
                    self._register_dash_callback(
                        output=callback_outputs,
                        inputs=callback_inputs,
                        function=callback_func,
                        widget_id=widget.config.id,
                    )

                    logger.debug(
                        f"[PageBase:{self.page_id}] Registered callbacks for widget '{widget.config.id}'"
                    )

        except Exception as e:
            logger.error(
                f"[PageBase:{self.page_id}] Failed to register callbacks for widget '{widget.config.id}': {e}"
            )

    def _create_callback_function(self, chart_widget: AutoChartWidget):
        """
        Create a callback function for a chart widget.

        Args:
            chart_widget: Chart widget to create callback for

        Returns:
            function: Callback function
        """

        def callback_wrapper(*args):
            """
            Auto-generated callback wrapper.

            This function extracts filter values from callback arguments
            and passes them to the chart widget's update method.
            """
            callback_start = time.time()
            widget_id = chart_widget.config.id

            try:
                # Extract filter values from args
                filter_values = {}
                for i, filter_type in enumerate(chart_widget.filter_ids.keys()):
                    if i < len(args):
                        filter_values[filter_type] = args[i]

                logger.debug(
                    f"[PageBase:{self.page_id}] Callback triggered for '{widget_id}' "
                    f"with filters: {filter_values}"
                )

                # Update the chart widget
                figure = chart_widget.update_from_filters(**filter_values)

                elapsed = time.time() - callback_start
                logger.info(
                    f"[PageBase:{self.page_id}] Callback for '{widget_id}' completed in {elapsed:.2f}s"
                )

                return figure

            except Exception as e:
                elapsed = time.time() - callback_start
                logger.error(
                    f"[PageBase:{self.page_id}] Callback for '{widget_id}' failed after {elapsed:.2f}s: {e}",
                    exc_info=True,
                )
                # Return empty figure on error
                return chart_widget._create_empty_figure()

        # Set a useful name for debugging
        callback_wrapper.__name__ = (
            f"{self.page_prefix}_update_{chart_widget.config.id}"
        )

        return callback_wrapper

    def _register_dash_callback(self, output, inputs, function, widget_id: str):
        """
        Register a callback with Dash app.

        Args:
            output: Callback output
            inputs: List of callback inputs
            function: Callback function
            widget_id: Widget ID for logging
        """
        try:
            # Use the global app from webapp
            from analytics_cup_analyst.main import app

            # Create the callback
            @app.callback(output, inputs)
            def dynamic_callback(*args):
                return function(*args)

            # Set a useful name for debugging
            dynamic_callback.__name__ = f"{self.page_prefix}_callback_{widget_id}"

            logger.debug(
                f"[PageBase:{self.page_id}] Registered Dash callback for '{widget_id}'"
            )

        except Exception as e:
            logger.error(
                f"[PageBase:{self.page_id}] Failed to register Dash callback for '{widget_id}': {e}"
            )
            raise

    def build(self) -> html.Div:
        """
        Build the page layout using configuration-driven approach.

        Returns:
            html.Div: The complete Dash layout for the page.
        """
        logger.info(
            f"[PageBase:{self.page_id}] Building page with plug-and-play system"
        )

        try:
            # 1. Load configuration
            self._load_config()

            # 2. Create widgets from configuration
            self._create_widgets_from_config()

            # 3. Generate layout
            layout = self._generate_layout_from_config()

            logger.info(
                f"[PageBase:{self.page_id}] Page built successfully with configuration-driven approach"
            )

            return layout

        except Exception as e:
            logger.error(
                f"[PageBase:{self.page_id}] Failed to build page: {e}", exc_info=True
            )

            # Fallback to error layout
            return self._build_error_layout(str(e))

    def _build_error_layout(self, error_message: str) -> html.Div:
        """
        Build an error layout when configuration fails.

        Args:
            error_message: Error message to display

        Returns:
            html.Div: Error layout
        """
        logger.error(
            f"[PageBase:{self.page_id}] Building error layout: {error_message}"
        )

        return html.Div(
            [
                html.Div(
                    [html.H2(self.title, className="page-title")],
                    className="page-title-bar",
                ),
                html.Div(
                    [
                        html.H3("Configuration Error", style={"color": "#ff6b6b"}),
                        html.P(
                            "Failed to load page configuration. "
                            "Please check the configuration file.",
                            style={"margin": "20px 0"},
                        ),
                        html.Pre(
                            error_message,
                            style={
                                "background": "#2d2d2d",
                                "padding": "15px",
                                "borderRadius": "5px",
                                "overflow": "auto",
                                "color": "#ff6b6b",
                            },
                        ),
                        html.P(
                            "Using default layout as fallback...",
                            style={"marginTop": "20px", "color": "#aaa"},
                        ),
                    ],
                    className="grid-wrapper",
                    style={"padding": "40px", "textAlign": "center"},
                ),
            ],
            className="page",
        )

    def register_callbacks(self, app):
        """
        Register all Dash callbacks for the page.

        Args:
            app: The Dash application instance
        """
        if self._callbacks_registered:
            logger.warning(
                f"[PageBase:{self.page_id}] Page callbacks already registered"
            )
            return

        logger.info(
            f"[PageBase:{self.page_id}] Registering page callbacks with auto-generation"
        )
        start_time = time.time()

        try:
            # Ensure widgets are created
            if not self.widgets:
                logger.warning(
                    f"[PageBase:{self.page_id}] No widgets found, creating them from config..."
                )
                self._load_config()
                self._create_widgets_from_config()

            # Generate and register auto callbacks
            self._generate_auto_callbacks()

            # Register the standard page callbacks
            self._register_page_callbacks(app)

            # Mark callbacks as registered
            self._callbacks_registered = True
            total_time = time.time() - start_time

            logger.info(
                f"[PageBase:{self.page_id}] Page callbacks registered in {total_time:.2f}s"
            )

        except Exception as e:
            logger.error(
                f"[PageBase:{self.page_id}] Failed to register callbacks: {e}",
                exc_info=True,
            )
            raise

    def _register_page_callbacks(self, app):
        """
        Register standard page-level callbacks.

        Args:
            app: Dash application instance
        """
        logger.debug(f"[PageBase:{self.page_id}] Registering standard page callbacks")

        # ===========================================================================
        # Callback 1: GridStack initialization
        # ===========================================================================
        @app.callback(
            Output(f"{self.page_prefix}-grid-container", "children"),
            Input(f"{self.page_prefix}-grid-init-interval", "n_intervals"),
            State(f"{self.page_prefix}-grid-container", "children"),
        )
        def init_gridstack(n_intervals, current_children):
            """
            Initialize GridStack after page load.

            This callback is triggered by the interval and returns the current children
            unchanged, which allows the JavaScript to initialize GridStack.
            """
            if n_intervals == 0:
                # Don't trigger on first interval
                raise PreventUpdate

            logger.info(f"[PageBase:{self.page_id}] Initializing GridStack integration")

            # Simply return the current children unchanged
            # The JavaScript will handle GridStack initialization when the interval fires
            return current_children or []

        # ===========================================================================
        # Callback 2: Show widgets after GridStack init
        # ===========================================================================
        @app.callback(
            Output(f"{self.page_prefix}-widgets-container", "style"),
            Input(f"{self.page_prefix}-grid-init-interval", "n_intervals"),
        )
        def show_widgets_after_init(n_intervals):
            """
            Show widgets after GridStack initialization.
            """
            if n_intervals > 0:
                logger.debug(f"[PageBase:{self.page_id}] Showing widgets container")
                return {"display": "block"}
            return {"display": "none"}


def create_page_from_config(
    page_id: str,
    title: str,
    page_prefix: Optional[str] = None,
    config_path: Optional[str] = None,
) -> PageBase:
    """
    Factory function to create a PageBase instance.

    Args:
        page_id: Unique identifier for the page
        title: Display title for the page
        page_prefix: Prefix for widget IDs
        config_path: Path to configuration file

    Returns:
        PageBase: A new instance of the PageBase class
    """
    return PageBase(
        page_id=page_id,
        title=title,
        page_prefix=page_prefix,
        config_path=config_path,
    )
