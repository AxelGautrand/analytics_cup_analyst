"""
Widget components package for the PySport dashboard.

This package provides reusable widget components for building dashboard pages,
including chart widgets, filter widgets, and text widgets with a unified
interface for plug-and-play integration.
"""
import logging

from .auto_chart import AutoChartWidget
from .base import BaseWidget, WidgetConfig, WidgetFactory
from .charts import ChartWidget
from .filter import CompactFilterWidget
from .player_card import PlayerAttributesWidget
from .player_info import PlayerInfoWidget
from .registry import WidgetRegistry, register_widget, registry
from .text import TextWidget
from .tracking_widget import TrackingWidget

# Get module logger
logger = logging.getLogger("pysport.widgets")


# Define what's available when using "from components.widgets import *"
__all__ = [
    # Base classes
    "BaseWidget",
    "WidgetConfig",
    "WidgetFactory",
    # Widget implementations
    "ChartWidget",
    "TextWidget",
    "PlayerInfoWidget",
    "PlayerAttributesWidget",
    # plug-and-play system
    "WidgetRegistry",
    "registry",
    "register_widget",
    "AutoChartWidget",
    "CompactFilterWidget",
]

# Register new widget types with the registry
WidgetRegistry.register(
    widget_type="compact_filter",
    widget_class=CompactFilterWidget,
    default_config={"show_gear_icon": True, "gear_icon": "⚙️", "compact_filters": []},
)

WidgetRegistry.register(
    widget_type="player_info",
    widget_class=PlayerInfoWidget,
    default_config={
        "show_search": True,
        "show_stats": True,
        "show_photo_placeholder": True,
    },
)

WidgetRegistry.register(
    widget_type="player_attributes",
    widget_class=PlayerAttributesWidget,
    default_config={
        "widget_type": "chart",
        "data_source": "dynamic_events",
        "visualization": "player_attributes",
        "options": {"visualization_type": "radar"},
    },
)

WidgetRegistry.register(
    widget_type="player_heatmap",
    widget_class=TrackingWidget,
    default_config={
        "widget_type": "heatmap",
        "data_source": ["dynamic_events", "tracking"],
        "visualization": "player_heatmap",
        "options": {"visualization_type": "heatmap"},
    },
)


# Log initialization
logger.debug("Widget components package initialized")
logger.debug(f"Available classes: {__all__}")
