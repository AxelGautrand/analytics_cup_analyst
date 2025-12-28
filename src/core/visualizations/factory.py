"""
Factory for creating visualization instances.
"""
from typing import Any, Dict, Optional

from .off_ball_runs import OffBallRunsVisualization
from .player_card import PlayerAttributesVisualization
from .player_roles import PlayerStyleProfileVisualization
from .tracking_viz import TrackingVisualization


class VisualizationFactory:
    """Factory to create visualization instances based on type."""

    @staticmethod
    def create(
        viz_type: str,
        aggregator,
        filters: Optional[Dict[str, Any]] = None,
        visualization_type: str = "bar",
        aggregation_context: Optional[str] = None,
        **other_options,
    ):
        """
        Create a visualization instance with explicit parameters.

        Args:
            viz_type: Type of visualization ('off_ball_runs')
            aggregator: Aggregator instance
            filters: Filter dictionary
            visualization_type: Type of chart (bar, scatter, etc.)
            aggregation_context: Context for aggregation configuration
            **other_options: Additional visualization options

        Returns:
            BaseVisualization instance
        """
        viz_map = {
            "off_ball_runs": OffBallRunsVisualization,
            "player_style_profile": PlayerStyleProfileVisualization,
            "player_attributes": PlayerAttributesVisualization,
            "tracking": TrackingVisualization,
            # TODO : Add more as we create them:
            # 'line_breaking': LineBreakingVisualization,
            # 'pressing_engagements': PressingEngagementsVisualization,
        }

        viz_class = viz_map.get(viz_type)
        if not viz_class:
            raise ValueError(f"Unknown visualization type: {viz_type}")

        return viz_class(
            aggregator=aggregator,
            filters=filters or {},
            visualization_type=visualization_type,
            aggregation_context=aggregation_context,
            **other_options,
        )

    @staticmethod
    def get_available_types() -> list:
        """Get list of available visualization types."""
        return [
            "off_ball_runs",
            "player_style_profile",
            "player_attributes",
            "tracking",
            # 'line_breaking',
            # 'pressing_engagements',
        ]
