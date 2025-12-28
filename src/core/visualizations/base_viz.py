"""
Base class for all data visualizations.
Connects aggregators to Plotly figures.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


class BaseVisualization(ABC):
    """Abstract base class for creating Plotly visualizations from aggregated data."""

    def __init__(
        self,
        aggregator,
        filters: Optional[Dict[str, Any]] = None,
        visualization_type: str = "bar",
        aggregation_context: Optional[str] = None,
        **other_options
    ):
        """
        Initialize visualization with an aggregator instance.

        Args:
            aggregator: Instance of an aggregator class (DynamicEventsAggregator, etc.)
            filters: Dictionary of filters to apply (team, match, time_range, etc.)
            visualization_type: Type of visualization (bar, scatter, etc.)
            aggregation_context: Context name for aggregation configuration
            **other_options: Additional visualization-specific options
        """
        self.aggregator = aggregator
        # Avoid mutable default argument by using None in the signature
        self.filters = filters or {}
        self.data = None

        # Explicits attributes
        self.visualization_type = visualization_type
        self.aggregation_context = aggregation_context

        # Supp options
        self.other_options = other_options

    @abstractmethod
    def prepare_data(self):
        """Prepare data for visualization using the aggregator."""
        pass

    @abstractmethod
    def create_figure(self) -> go.Figure:
        """Create Plotly figure from prepared data."""
        pass

    def apply_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply common filters to dataframe."""
        filtered_df = df.copy()

        # Apply team filter
        if "team" in self.filters and self.filters["team"] != "all":
            filtered_df = filtered_df[
                filtered_df["team_shortname"] == self.filters["team"]
            ]

        # Apply match filter
        if "match" in self.filters and self.filters["match"] != "all":
            filtered_df = filtered_df[filtered_df["match_id"] == self.filters["match"]]

        # Apply time range filter
        if "time_range" in self.filters:
            start, end = self.filters["time_range"]
            filtered_df = filtered_df[
                (filtered_df["minute"] >= start) & (filtered_df["minute"] <= end)
            ]

        return filtered_df

    def get_figure(self) -> go.Figure:
        """Get the complete Plotly figure with data preparation."""
        self.prepare_data()
        return self.create_figure()

    def update_filters(self, new_filters: Dict[str, Any]):
        """Update filters and refresh data."""
        self.filters.update(new_filters)
        self.data = None  # Force data refresh
