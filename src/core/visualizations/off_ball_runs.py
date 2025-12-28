"""
Visualization for off-ball runs data.
"""
import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .base_viz import BaseVisualization

logger = logging.getLogger(__name__)


class OffBallRunsVisualization(BaseVisualization):
    """Create visualizations for off-ball runs metrics."""

    def __init__(
        self,
        aggregator,
        filters: Dict[str, Any] = {},
        visualization_type: str = "bar",
        aggregation_context: Optional[str] = None,
        **other_options,
    ):
        super().__init__(
            aggregator=aggregator,
            filters=filters or {},
            visualization_type=visualization_type,
            aggregation_context=aggregation_context,
            **other_options,
        )
        self.viz_type = self.visualization_type
        self._raw_data = pd.DataFrame()
        self._aggregated_data = pd.DataFrame()

    def prepare_data(self):
        """Prepare off-ball runs data using the aggregator.

        This method applies filters (match, team, time_range) to the
        aggregator's dataframe, creates a temporary aggregator from the
        filtered rows and asks it to produce the off-ball runs aggregates.
        Any exceptions are caught and result in empty DataFrames."""
        logger.info("📊 [OffBallRunsViz] Data Preparation...")

        try:
            from src.core.data_manager import data_manager

            # Use explicit context name
            config_name = self.aggregation_context or "off_ball_runs"

            logger.info(f"[OffBallRunsViz] Using aggregation context: {config_name}")

            # Obtain aggregated data
            self._raw_data = data_manager.get_aggregated_data(
                config_name=config_name,
                group_by=["player_id", "player_name"],
                filters=self.filters,
            )

            # Extract metrics
            self._extract_metrics_from_aggregation()

            logger.info(
                f"✅ [OffBallRunsViz] Data prepared: {len(self._raw_data)} players"
            )

        except Exception as e:
            logger.exception("❌ [OffBallRunsViz] Error preparing data: %s", e)
            self._raw_data = pd.DataFrame()
            self._aggregated_data = pd.DataFrame()

    def _extract_basic_metrics(self):
        """Extract basic metrics from prefixed columns."""
        if self._raw_data.empty:
            self._aggregated_data = pd.DataFrame()
            return

        logger.debug("🔍 [OffBallRunsViz] Extracting base metrics...")

        # Build a mapping for base metrics found in the aggregated table
        base_metrics = {}
        target_metrics = ["count", "count_targeted", "count_received", "xthreat"]

        for metric in target_metrics:
            # Find columns that start with the metric name and include a suffix
            matching_cols = [
                col
                for col in self._raw_data.columns
                if col.startswith(metric) and "_" in col
            ]

            if matching_cols:
                # Use the first matching column (could be adjusted to sum multiple)
                base_metrics[metric] = self._raw_data[matching_cols[0]].fillna(0)
                logger.debug("[OffBallRunsViz]  ✓ %s -> %s", metric, matching_cols[0])
            else:
                base_metrics[metric] = pd.Series(0, index=self._raw_data.index)
                logger.debug("[OffBallRunsViz]  ✗ %s -> not found", metric)

        # Create a simplified DataFrame for visualization
        self._aggregated_data = self._raw_data[["player_id", "player_name"]].copy()

        # Add team column if present in the aggregated data
        team_cols = [
            c
            for c in self._raw_data.columns
            if "team" in c.lower() and "name" in c.lower()
        ]
        if team_cols:
            self._aggregated_data["team"] = self._raw_data[team_cols[0]]

        # Attach the base metrics to the simplified frame
        for metric, series in base_metrics.items():
            self._aggregated_data[metric] = series

        # Compute efficiency (received / targeted) safely
        if "count_targeted" in self._aggregated_data.columns:
            self._aggregated_data["efficiency"] = (
                self._aggregated_data["count_received"]
                / self._aggregated_data["count_targeted"].replace(0, 1)
            ).fillna(0)

        logger.info(
            "✅ [OffBallRunsViz] Metrics extracted: %d players",
            len(self._aggregated_data),
        )

    def _extract_metrics_from_aggregation(self):
        """Extract metrics from aggregated data."""
        if self._raw_data.empty:
            self._aggregated_data = pd.DataFrame()
            return

        # Create basic dataframe
        self._aggregated_data = self._raw_data[["player_id", "player_name"]].copy()

        # Map aggregated columns to basic name
        column_mapping = {
            "count_off_ball_runs_all": "count",
            "count_off_ball_runs_targeted": "count_targeted",
            "count_off_ball_runs_received": "count_received",
            "xthreat_sum_off_ball_runs_all": "xthreat",
        }

        for agg_col, simple_col in column_mapping.items():
            if agg_col in self._raw_data.columns:
                self._aggregated_data[simple_col] = self._raw_data[agg_col]
            else:
                self._aggregated_data[simple_col] = 0
        # Compute efficiency
        if "count_targeted" in self._aggregated_data.columns:
            self._aggregated_data["efficiency"] = (
                self._aggregated_data["count_received"]
                / self._aggregated_data["count_targeted"].replace(0, 1)
            ).fillna(0)

        logger.info(
            "✅ [OffBallRunsViz] Metrics extracted: %d players",
            len(self._aggregated_data),
        )

    def create_figure(self) -> go.Figure:
        """Create Plotly figure based on visualization type."""
        logger.debug("🎨 [OffBallRunsViz] Creating figure...")

        if self._aggregated_data is None or self._aggregated_data.empty:
            logger.info("⚠️ [OffBallRunsViz] No data available for visualization.")
            return self._create_empty_figure("No data available")

        try:
            if self.viz_type == "bar":
                return self._create_bar_chart()
            elif self.viz_type == "heatmap":
                return self._create_heatmap()
            elif self.viz_type == "scatter":
                return self._create_scatter_plot()
            else:
                return self._create_bar_chart()
        except Exception as e:
            logger.error(f"❌ [OffBallRunsViz] Error creation figure: {e}")
            return self._create_empty_figure(f"Error: {str(e)}")

    def _create_bar_chart(self) -> go.Figure:
        """Create bar chart of off-ball runs metrics."""
        logger.debug("📊 [OffBallRunsViz] Creating bar chart...")

        # Limite to n top players by total runs for clarity
        display_data = self._aggregated_data.sort_values("count", ascending=False).head(
            5
        )

        if display_data.empty:
            return self._create_empty_figure("Not enough Data")

        fig = go.Figure()

        # Bar for total runs
        fig.add_trace(
            go.Bar(
                name="Courses totales",
                x=display_data["player_name"],
                y=display_data["count"],
                marker_color="#489ccb",
                hovertemplate="<b>%{x}</b><br>Courses totales: %{y}<extra></extra>",
            )
        )

        # Bar for targeted runs (if available)
        if "count_targeted" in display_data.columns:
            fig.add_trace(
                go.Bar(
                    name="Courses ciblées",
                    x=display_data["player_name"],
                    y=display_data["count_targeted"],
                    marker_color="#4aff7c",
                    hovertemplate="<b>%{x}</b><br>Courses ciblées: %{y}<extra></extra>",
                )
            )

        # Bar for received runs (if available)
        if "count_received" in display_data.columns:
            fig.add_trace(
                go.Bar(
                    name="Courses reçues",
                    x=display_data["player_name"],
                    y=display_data["count_received"],
                    marker_color="#75ff9c",
                    hovertemplate="<b>%{x}</b><br>Courses reçues: %{y}<extra></extra>",
                )
            )

        # Optimised Layout
        fig.update_layout(
            barmode="group",
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            hovermode="closest",
            # IMPORTANT: Keep legend for bar chart
            showlegend=True,
            legend=dict(
                orientation="h",  # Horizontal
                yanchor="bottom",
                y=-0.3,  # Place below the chart
                xanchor="center",
                x=0.5,
                font=dict(size=10),
                bgcolor="rgba(0,0,0,0.5)",
                bordercolor="rgba(255,255,255,0.2)",
            ),
            # Adjusted margins
            margin=dict(l=40, r=10, t=10, b=60, pad=0),
            # Layout compact
            bargap=0.2,
            bargroupgap=0.1,
            # AXE X
            xaxis=dict(
                title=None,
                showgrid=False,
                zeroline=False,
                tickangle=45,
                tickfont=dict(size=10),
                ticks="outside",
                ticklen=3,
                automargin=True,
                tickmode="auto",
            ),
            # AXE Y
            yaxis=dict(
                title=None,
                showgrid=True,
                gridcolor="rgba(255,255,255,0.1)",
                zeroline=False,
                tickfont=dict(size=10),
                ticks="outside",
                ticklen=3,
                automargin=True,
                rangemode="tozero",
            ),
            # Responsive
            autosize=True,
        )

        logger.info(
            "✅ [OffBallRunsViz] Bar chart created with %d players", len(display_data)
        )
        return fig

    def _create_scatter_plot(self) -> go.Figure:
        """Create scatter plot of efficiency vs xthreat."""
        logger.debug("📊 [OffBallRunsViz] Creating scatter plot...")

        if (
            self._aggregated_data.empty
            or "efficiency" not in self._aggregated_data.columns
        ):
            return self._create_empty_figure("Insufficient data for scatter plot")

        # Filter to valid efficiency values
        scatter_data = self._aggregated_data[
            (self._aggregated_data["efficiency"].notna())
            & (self._aggregated_data["efficiency"] <= 1)
            & (self._aggregated_data["count"] > 0)
        ].copy()

        if scatter_data.empty:
            return self._create_empty_figure("No valid data for efficiency")

        # Determine if team column exists for coloring
        team_col = "team" if "team" in scatter_data.columns else None

        fig = px.scatter(
            scatter_data,
            x="count",
            y="efficiency",
            size="count",
            color=team_col,
            hover_name="player_name",
            hover_data=["count_targeted", "count_received"]
            if all(
                x in scatter_data.columns for x in ["count_targeted", "count_received"]
            )
            else [],
            # NOTE : We delete titles
            # title="Efficiency of off-ball runs",
            labels={
                "count": "Nombre total de courses",
                "efficiency": "Efficacité (reçues/ciblées)",
                "team": "Équipe",
            },
            template="plotly_dark",
        )

        # Optimised layout for small tiles
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            hovermode="closest",
            # Delete legend
            showlegend=False,
            margin=dict(l=30, r=10, t=10, b=30),
            xaxis=dict(
                title=None,  # Delete X axis title
                showgrid=True,
                gridcolor="rgba(255,255,255,0.1)",
                tickfont=dict(size=9),
            ),
            yaxis=dict(
                title=None,  # Delete Y axis title
                showgrid=True,
                gridcolor="rgba(255,255,255,0.1)",
                tickfont=dict(size=9),
            ),
            # Responsive
            autosize=True,
        )

        logger.info(
            "✅ [OffBallRunsViz] Scatter plot created with %d players", len(scatter_data)
        )
        return fig

    def _create_empty_figure(self, message: str = "Chargement...") -> go.Figure:
        """Create empty placeholder figure."""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=14, color="white"),
            align="center",
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=20, r=20, t=40, b=20),
        )
        return fig

    def _create_heatmap(self) -> go.Figure:
        """Create heatmap of off-ball runs by field position."""
        # Use raw event coordinates if present to draw a density heatmap.
        # Note: some aggregators put coordinates on the raw events frame,
        # so we check `_raw_data` for 'x'/'y'. If absent, return an empty
        # placeholder figure.
        if "x" not in self._raw_data.columns or "y" not in self._raw_data.columns:
            return self._create_empty_figure()

        fig = px.density_heatmap(
            self._raw_data,
            x="x",
            y="y",
            nbinsx=30,
            nbinsy=20,
            title="Off-Ball Runs Heatmap",
            template="plotly_dark",
            color_continuous_scale="Viridis",
        )

        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
        )

        return fig
