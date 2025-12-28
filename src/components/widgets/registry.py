"""
Widget Registry System for plug-and-play widget management.

This module provides a centralized registry system for registering,
discovering, and creating dashboard widgets dynamically.
"""
import logging
import threading
from typing import Any, Dict, List, Optional, Type

from .base import BaseWidget, WidgetConfig

# Get module logger
logger = logging.getLogger(__name__)


class WidgetRegistry:
    """
    Registry for managing widget types and their configurations.

    This class implements a singleton pattern to provide a centralized
    registry where widget types can be registered and later instantiated
    with automatic configuration.

    Attributes:
        _instance: Singleton instance
        _widget_types: Dictionary mapping widget type names to their classes
        _default_configs: Dictionary mapping widget type names to default configs
    """

    _instance = None
    _instances: Dict[str, BaseWidget] = {}
    _instances_lock = threading.RLock()
    _widget_types: Dict[str, Type[BaseWidget]] = {}
    _default_configs: Dict[str, Dict[str, Any]] = {}

    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super(WidgetRegistry, cls).__new__(cls)
            logger.debug("WidgetRegistry singleton created")
        return cls._instance

    @classmethod
    def register(
        cls,
        widget_type: str,
        widget_class: Type[BaseWidget],
        default_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Register a widget type in the registry.

        Args:
            widget_type: Unique identifier for the widget type
            widget_class: Widget class to register
            default_config: Default configuration for this widget type

        Raises:
            ValueError: If widget_type is already registered
        """
        # Check for duplicate registration
        if widget_type in cls._widget_types:
            raise ValueError(f"Widget type '{widget_type}' is already registered")

        # Register the widget
        cls._widget_types[widget_type] = widget_class
        cls._default_configs[widget_type] = default_config or {}

        logger.info(
            f"✅ Registered widget type: '{widget_type}' -> {widget_class.__name__}"
        )

    @classmethod
    def unregister(cls, widget_type: str):
        """
        Unregister a widget type from the registry.

        Args:
            widget_type: Widget type to unregister
        """
        if widget_type in cls._widget_types:
            del cls._widget_types[widget_type]
            if widget_type in cls._default_configs:
                del cls._default_configs[widget_type]
            logger.info(f"🗑️ Unregistered widget type: '{widget_type}'")

    @classmethod
    def create(
        cls, widget_type: str, widget_config: WidgetConfig, **kwargs
    ) -> BaseWidget:
        """
        Create a widget instance from the registry.

        Args:
            widget_type: Type of widget to create
            widget_id: Unique identifier for the widget instance
            **kwargs: Additional configuration parameters

        Returns:
            BaseWidget: Instance of the requested widget

        Raises:
            ValueError: If widget_type is not registered
        """
        if widget_type not in cls._widget_types:
            raise ValueError(
                f"Widget type '{widget_type}' is not registered. "
                f"Available types: {list(cls._widget_types.keys())}"
            )

        widget_class = cls._widget_types[widget_type]
        default_config = cls._default_configs.get(widget_type, {})

        # Merge defaults with provided kwargs
        config = {**default_config, **kwargs}

        logger.debug(f"Creating widget '{widget_config.id}' of type '{widget_type}'")
        return widget_class(widget_config, **config)

    @classmethod
    def get_available_types(cls) -> list:
        """
        Get list of available widget types.

        Returns:
            list: List of registered widget type names
        """
        return list(cls._widget_types.keys())

    @classmethod
    def has_widget_type(cls, widget_type: str) -> bool:
        """
        Check if a widget type is registered.

        Args:
            widget_type: Widget type to check

        Returns:
            bool: True if widget type is registered
        """
        return widget_type in cls._widget_types

    @classmethod
    def clear_registry(cls):
        """Clear all registered widget types (for testing)."""
        cls._widget_types.clear()
        cls._default_configs.clear()
        logger.debug("WidgetRegistry cleared")

    @classmethod
    def register_instance(cls, widget_id: str, widget_instance: BaseWidget):
        """
        Register a widget instance (not just type).

        Args:
            widget_id: Unique widget ID
            widget_instance: Widget instance to register
        """
        with cls._instances_lock:
            cls._instances[widget_id] = widget_instance
            logger.debug(f"[WidgetRegistry] Registered instance: '{widget_id}'")

    @classmethod
    def get_instance(cls, widget_id: str) -> Optional[BaseWidget]:
        """
        Get a widget instance by ID.

        Args:
            widget_id: Widget ID to look up

        Returns:
            BaseWidget or None: Widget instance if found
        """
        with cls._instances_lock:
            return cls._instances.get(widget_id)

    @classmethod
    def unregister_instance(cls, widget_id: str):
        """
        Unregister a widget instance.

        Args:
            widget_id: Widget ID to unregister
        """
        with cls._instances_lock:
            if widget_id in cls._instances:
                del cls._instances[widget_id]
                logger.debug(f"[WidgetRegistry] Unregistered instance: '{widget_id}'")

    @classmethod
    def list_instances(cls) -> List[str]:
        """
        List all registered widget instance IDs.

        Returns:
            List[str]: List of widget IDs
        """
        with cls._instances_lock:
            return list(cls._instances.keys())

    @classmethod
    def clear_instances(cls):
        """Clear all registered widget instances."""
        with cls._instances_lock:
            cls._instances.clear()
            logger.debug("[WidgetRegistry] Cleared all instances")


# Convenience decorator for registering widgets
def register_widget(widget_type: str, default_config: Optional[Dict[str, Any]] = None):
    """
    Decorator to register a widget class.

    Args:
        widget_type: Unique identifier for the widget type
        default_config: Default configuration for this widget type

    Returns:
        function: Decorator function
    """

    def decorator(widget_class):
        WidgetRegistry.register(widget_type, widget_class, default_config)
        return widget_class

    return decorator


# Singleton instance for easy import
registry = WidgetRegistry()
