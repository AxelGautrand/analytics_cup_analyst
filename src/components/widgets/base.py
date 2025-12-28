"""
Base widget classes and configuration models.
"""
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash import dcc, html

# Get module logger
logger = logging.getLogger(__name__)


@dataclass
class WidgetConfig:
    """
    Configuration model for a dashboard widget.

    Attributes:
        id: Unique identifier for the widget
        title: Display title for the widget
        widget_type: Type of widget ('filter', 'chart', 'text', etc.)
        position: Grid position dictionary with x, y, w, h keys
        styles: CSS styles to apply to the widget
        data_source: Optional data source identifier
        properties: Additional widget properties
    """

    id: str
    title: str
    widget_type: str
    position: Dict[str, int]
    styles: Dict[str, Any] = field(default_factory=dict)
    data_source: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize default values."""
        if not self.styles:
            self.styles = {}
        if not self.properties:
            self.properties = {}

    def to_gridstack_dict(self) -> Dict[str, Any]:
        """
        Convert to GridStack-compatible dictionary.

        Returns:
            Dict[str, Any]: Dictionary compatible with GridStack layout
        """
        return {
            "id": self.id,
            "title": self.title,
            "type": self.widget_type,
            "x": self.position.get("x", 0),
            "y": self.position.get("y", 0),
            "w": self.position.get("w", 4),
            "h": self.position.get("h", 3),
        }

    def to_json(self) -> str:
        """
        Serialize to JSON string.

        Returns:
            str: JSON representation of the configuration
        """
        return json.dumps(self.to_gridstack_dict(), indent=2)


class BaseWidget(ABC):
    """
    Abstract base class for all dashboard widgets.

    This class defines the interface that all widgets must implement,
    including rendering, configuration, and callback management.
    """

    def __init__(self, config: WidgetConfig):
        """
        Initialize the widget with configuration.

        Args:
            config: Widget configuration object
        """
        self.config = config
        self._components: List = []
        logger.debug(f"Initialized BaseWidget: id='{config.id}'")

    @abstractmethod
    def render(self) -> html.Div:
        """
        Render widget as Dash components.

        Returns:
            html.Div: Complete widget structure as Dash components

        Note:
            This method should return a complete tile structure including
            header and body, ready to be placed in a GridStack container.
        """
        pass

    @abstractmethod
    def get_client_config(self) -> Dict[str, Any]:
        """
        Get configuration for client-side JavaScript.

        Returns:
            Dict[str, Any]: Configuration dictionary for the client
        """
        pass

    def get_callback_inputs(self) -> List:
        """
        Get callback inputs for this widget.

        Returns:
            List: List of Dash Input objects for this widget's callbacks
        """
        return []

    def get_callback_outputs(self) -> List:
        """
        Get callback outputs for this widget.

        Returns:
            List: List of Dash Output objects for this widget's callbacks
        """
        return []

    def register_callbacks(self, app):
        """
        Register callbacks for this widget.

        Args:
            app: Dash application instance

        Note:
            This method can be overridden by widgets that need to
            register their own callbacks. By default, it does nothing.
        """
        pass


class WidgetFactory:
    """
    Factory for creating widget instances from configuration.

    This factory provides a centralized way to create widget instances
    based on their type, promoting loose coupling and easier testing.
    """

    @staticmethod
    def create(config: WidgetConfig, **kwargs) -> BaseWidget:
        """
        Create a widget instance based on its type.

        Args:
            config: Widget configuration
            **kwargs: Additional keyword arguments passed to widget constructor

        Returns:
            BaseWidget: Instance of the appropriate widget class

        Raises:
            ValueError: If the widget type is not recognized
        """
        # Import here to avoid circular imports
        from .charts import ChartWidget
        from .text import TextWidget

        widget_map = {
            "chart": ChartWidget,
            "text": TextWidget,
            # Add more widget types as they are implemented
        }

        widget_class = widget_map.get(config.widget_type)
        if not widget_class:
            logger.error(f"[WidgetFactory] Unknown widget type: {config.widget_type}")
            raise ValueError(
                f"[WidgetFactory] Unknown widget type: {config.widget_type}"
            )

        logger.info(
            "[WidgetFactory] "
            f"Creating widget: type='{config.widget_type}', "
            f"id='{config.id}', class='{widget_class.__name__}'"
        )

        try:
            widget = widget_class(config, **kwargs)
            logger.debug(f"[WidgetFactory] Widget created successfully: {config.id}")
            return widget
        except Exception as e:
            logger.error(
                f"[WidgetFactory] Error creating widget '{config.id}': {e}",
                exc_info=True,
            )
            raise
