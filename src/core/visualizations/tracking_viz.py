"""
Tracking Data Visualization - Heatmap and shot positions.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .base_viz import BaseVisualization

logger = logging.getLogger(__name__)


class TrackingVisualization(BaseVisualization):
    """Visualization for tracking data with heatmaps and shot positions."""

    def __init__(
        self,
        aggregator,
        filters: Dict[str, Any] = {},
        visualization_type: str = "heatmap",
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
        self.viz_type = visualization_type

        # Pitch dimensions (standard FIFA pitch)
        self.pitch_length = 105
        self.pitch_width = 68

        # Original coordinate ranges
        self.original_x_range = (-52.5, 52.5)
        self.original_y_range = (-34, 34)

        # Colors
        self.heatmap_colorscale = [
            [0, "rgba(0, 0, 0, 0)"],
            [0.1, "rgba(30, 60, 120, 0.3)"],
            [0.5, "rgba(60, 120, 200, 0.6)"],
            [0.8, "rgba(100, 200, 255, 0.8)"],
            [1, "rgba(255, 255, 255, 1)"],
        ]

        # Shot colors
        self.shot_colors = {
            True: "#4aff7c",  # Green for goals
            False: "#ff6384",  # Red for non-goals
        }

    def prepare_data(self):
        """Prepare tracking and event data for visualization."""
        logger.info("📊 [TrackingViz] Preparing tracking data...")

        try:
            from core.data_manager import data_manager

            # Get tracking data
            tracking_data = data_manager.tracking_data

            if tracking_data is None or tracking_data.empty:
                logger.warning("No tracking data available")
                self.data = None
                return

            # Get metadata
            # self.metadata = data_manager.matches_df

            # Get event data for shots
            self.event_data = data_manager.events_df
            shots_data = (
                self._extract_shots_data(self.event_data)
                if self.event_data is not None
                else None
            )

            # Apply player filter if specified
            if "player_id" in self.filters and self.filters["player_id"] != "all":
                player_id = str(self.filters["player_id"])
                # Filter tracking data for specific player
                filtered_tracking = self._filter_tracking_by_player(
                    tracking_data, player_id
                )
                logger.info(
                    f"Filtered tracking data for player {player_id}: {len(filtered_tracking)} frames"
                )
                filtered_shots = self._filter_shots_by_player(shots_data, player_id=player_id)  # type: ignore
            elif (
                "player_label" in self.filters and self.filters["player_label"] != "all"
            ):
                player_label = self.filters["player_label"]
                filtered_tracking = self._filter_tracking_by_player(
                    tracking_data, player_label=player_label
                )
                filtered_shots = self._filter_shots_by_player(shots_data, player_label=player_label)  # type: ignore
            else:
                # TODO: Add other filters (team, period, time_range)
                filtered_tracking = tracking_data
                filtered_shots = shots_data

            # Prepare data structure
            self.data = {
                "tracking": filtered_tracking,
                "shots": filtered_shots,
                "filters": self.filters.copy(),
            }

            logger.info(
                f"✅ [TrackingViz] Data prepared: {len(filtered_tracking)} tracking frames"
            )
            if shots_data is not None:
                logger.info(f"✅ [TrackingViz] Shots data: {len(shots_data)} shots")

        except Exception as e:
            logger.exception(f"❌ [TrackingViz] Error preparing data: {e}")
            self.data = None

    def _filter_tracking_by_player(
        self,
        tracking_data: pd.DataFrame,
        player_id: Optional[str] = None,
        player_label: Optional[str] = None,
    ) -> pd.DataFrame:
        """Filter tracking data for a specific player."""
        try:
            if player_label and not player_id:
                # handle cases where label is specified
                player_id = self.event_data[
                    self.event_data["player_name"] == player_label
                ]["player_id"].iloc[0]

            # Check if player columns exist
            x_col = f"{player_id}_x"
            y_col = f"{player_id}_y"

            if x_col not in tracking_data.columns or y_col not in tracking_data.columns:
                logger.warning(f"Player {player_id} not found in tracking data")
                return pd.DataFrame()

            # Get essential columns plus the player's columns
            essential_cols = ["period_id", "timestamp", "frame_id"]

            # Make sure we only include columns that exist
            available_cols = [
                col for col in essential_cols if col in tracking_data.columns
            ]
            player_cols = [x_col, y_col]

            # Return filtered dataframe
            return tracking_data[available_cols + player_cols].copy()

        except Exception as e:
            logger.error(
                f"Error filtering tracking data for player {player_id}, {player_label}: {e}"
            )
            return pd.DataFrame()

    def _filter_shots_by_player(
        self,
        shots_data: pd.DataFrame,
        player_id: Optional[str] = None,
        player_label: Optional[str] = None,
    ) -> pd.DataFrame:
        """Filter shots data for a specific player."""
        try:
            if player_label and not player_id:
                # handle cases where label is specified
                player_id = self.event_data[
                    self.event_data["player_name"] == player_label
                ]["player_id"].iloc[0]

            filtered_shots = shots_data[shots_data["player_id"] == player_id]

            return filtered_shots
        except Exception as e:
            logger.error(
                f"Error filtering shot data for player {player_id}, {player_label}: {e}"
            )
            return pd.DataFrame()

    def _extract_shots_data(self, event_data: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Extract shot events from event data."""
        try:
            # Filter for shot events
            shot_mask = event_data["end_type"] == "shot"

            shots = event_data[shot_mask].copy()

            if shots.empty:
                logger.warning("No shot events found in event data")
                return None

            # Extract shot outcome and coordinates
            shots_data = []

            for _, shot in shots.iterrows():
                try:
                    # Get coordinates
                    x = shot.get("x_end", None)
                    y = shot.get("y_end", None)

                    if pd.isna(x) or pd.isna(y):
                        continue

                    # Get player info
                    player_id = shot.get("player_id", None)
                    player_name = shot.get(
                        "player_name", f"Player {player_id}" if player_id else "Unknown"
                    )

                    # Get shot outcome
                    outcome = shot.get("lead_to_goal", False)

                    # Get xG value
                    xG = shot.get("xG", shot.get("xg", 0))

                    # Get additional shot info
                    is_header = shot.get("is_header", False)
                    if isinstance(is_header, str):
                        is_header = is_header.lower() in ["true", "1", "yes"]

                    shot_distance = shot.get("shot_distance_to_goal", 0)

                    # Get shot type details
                    shot_info = {
                        "player_id": player_id,
                        "player_name": player_name,
                        "x": float(x),
                        "y": float(y),
                        "outcome": outcome,
                        "xG": float(xG),
                        "is_header": is_header,
                        "shot_distance": float(shot_distance),
                        "timestamp": shot.get("time_end", shot.get("timestamp", 0)),
                        "period_id": shot.get("period", 1),
                    }

                    shots_data.append(shot_info)

                except Exception as e:
                    logger.debug(f"Error processing shot: {e}")
                    continue

            logger.info(f"Extracted {len(shots_data)} valid shots")
            return pd.DataFrame(shots_data) if shots_data else None

        except Exception as e:
            logger.error(f"Error extracting shots data: {e}")
            return None

    def _normalize_coordinates(self, x: float, y: float) -> Tuple[float, float]:
        """
        Normalize coordinates from original range to pitch dimensions.

        Original: x ∈ [-52.5, 52.5] (length), y ∈ [-34, 34] (width)
        Transformed: y becomes X axis [0, 68] (left to right)
                     x becomes Y axis [0, 105] (bottom to top)

        Football pitch orientation:
        - Bottom goal (y=0): Team defending (usually their own goal)
        - Top goal (y=105): Team attacking (opponent's goal)

        For standard tracking data where:
        - x = -52.5 is one goal line, x = 52.5 is the other goal line
        - y = -34 is left touchline, y = 34 is right touchline
        """
        # Original Y (width coordinate) [-34, 34] becomes X axis [0, 68]
        # Left touchline (-34) → x=0, right touchline (34) → x=68
        x_normalized = (
            (y - self.original_y_range[0])
            / (self.original_y_range[1] - self.original_y_range[0])
        ) * self.pitch_width

        # Original X (length coordinate) [-52.5, 52.5] becomes Y axis [0, 105]
        # We need to decide which goal is at the bottom
        # Assuming -52.5 is defending goal (bottom) and 52.5 is attacking goal (top)
        # So -52.5 → y=0 (bottom), 52.5 → y=105 (top)
        y_normalized = (
            (x - self.original_x_range[0])
            / (self.original_x_range[1] - self.original_x_range[0])
        ) * self.pitch_length

        return x_normalized, y_normalized

    def _create_pitch_background(self) -> go.Figure:
        """Create soccer pitch background with vertical orientation."""
        fig = go.Figure()

        # Pitch outline
        fig.add_shape(
            type="rect",
            x0=0,
            y0=0,
            x1=self.pitch_width,
            y1=self.pitch_length,
            line=dict(color="white", width=2),
            fillcolor="rgba(11, 56, 30, 0.7)",  # Dark green pitch
            layer="below",
        )

        # Center circle
        center_x = self.pitch_width / 2
        center_y = self.pitch_length / 2
        circle_radius = 9.15

        fig.add_shape(
            type="circle",
            xref="x",
            yref="y",
            x0=center_x - circle_radius,
            y0=center_y - circle_radius,
            x1=center_x + circle_radius,
            y1=center_y + circle_radius,
            line_color="white",
            line_width=2,
            layer="below",
        )

        # Center spot
        fig.add_trace(
            go.Scatter(
                x=[center_x],
                y=[center_y],
                mode="markers",
                marker=dict(size=4, color="white"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

        # Halfway line
        fig.add_shape(
            type="line",
            x0=0,
            y0=center_y,
            x1=self.pitch_width,
            y1=center_y,
            line=dict(color="white", width=2),
            layer="below",
        )

        # Penalty areas
        penalty_area_width = 40.3
        penalty_area_depth = 16.5

        # Bottom penalty area
        fig.add_shape(
            type="rect",
            x0=(self.pitch_width - penalty_area_width) / 2,
            y0=0,
            x1=(self.pitch_width + penalty_area_width) / 2,
            y1=penalty_area_depth,
            line=dict(color="white", width=2),
            fillcolor="rgba(0,0,0,0)",
            layer="below",
        )

        # Top penalty area
        fig.add_shape(
            type="rect",
            x0=(self.pitch_width - penalty_area_width) / 2,
            y0=self.pitch_length - penalty_area_depth,
            x1=(self.pitch_width + penalty_area_width) / 2,
            y1=self.pitch_length,
            line=dict(color="white", width=2),
            fillcolor="rgba(0,0,0,0)",
            layer="below",
        )

        # Goals
        goal_width = 7.32
        goal_depth = 2

        # Bottom goal
        fig.add_shape(
            type="rect",
            x0=(self.pitch_width - goal_width) / 2,
            y0=-goal_depth,
            x1=(self.pitch_width + goal_width) / 2,
            y1=0,
            line=dict(color="white", width=2),
            fillcolor="rgba(255,255,255,0.1)",
            layer="below",
        )

        # Top goal
        fig.add_shape(
            type="rect",
            x0=(self.pitch_width - goal_width) / 2,
            y0=self.pitch_length,
            x1=(self.pitch_width + goal_width) / 2,
            y1=self.pitch_length + goal_depth,
            line=dict(color="white", width=2),
            fillcolor="rgba(255,255,255,0.1)",
            layer="below",
        )

        return fig

    def create_figure(self) -> go.Figure:
        """Create visualization figure based on viz_type."""
        if self.data is None:
            return self._create_empty_figure("No tracking data available")

        if self.viz_type == "heatmap":
            return self._create_heatmap_figure()
        elif self.viz_type == "shots":
            return self._create_shots_figure()
        elif self.viz_type == "combined":
            return self._create_combined_figure()
        else:
            logger.warning(f"Unknown visualization type: {self.viz_type}")
            return self._create_empty_figure(f"Unknown viz type: {self.viz_type}")

    def _create_heatmap_figure(self) -> go.Figure:
        """Create heatmap figure of player positions (single player)."""
        try:
            if self.data is None or "tracking" not in self.data:
                return self._create_empty_figure("No tracking data available")

            tracking_data = self.data["tracking"]

            # Find player position columns
            x_cols = [
                col
                for col in tracking_data.columns
                if col.endswith("_x") and not col.startswith("ball")
            ]

            if not x_cols:
                return self._create_empty_figure("No player position data available")

            # Extract positions for all players found
            all_positions = []
            player_ids = []

            for x_col in x_cols:
                player_id = x_col.replace("_x", "")
                y_col = f"{player_id}_y"

                if y_col in tracking_data.columns:
                    player_ids.append(player_id)
                    # Get positions for this player
                    player_x = tracking_data[x_col].dropna()
                    player_y = tracking_data[y_col].dropna()

                    # Normalize coordinates and add to positions
                    for x, y in zip(player_x, player_y):
                        try:
                            x_norm, y_norm = self._normalize_coordinates(x, y)
                            all_positions.append([x_norm, y_norm])
                        except Exception as e:
                            logger.debug(
                                f"Error normalizing coordinates ({x}, {y}): {e}"
                            )
                            continue

            if not all_positions:
                return self._create_empty_figure("No valid player position data")

            # Convert to numpy array
            positions = np.array(all_positions)

            # Create 2D histogram (heatmap) with normalized coordinates
            hist, x_edges, y_edges = np.histogram2d(
                positions[:, 0],
                positions[:, 1],
                bins=[30, 50],  # More bins in Y for vertical orientation
                range=[[0, self.pitch_width], [0, self.pitch_length]],
            )

            # Normalize histogram
            hist_normalized = hist / hist.max() if hist.max() > 0 else hist

            # Start with pitch background
            fig = self._create_pitch_background()

            # Add heatmap trace
            fig.add_trace(
                go.Heatmap(
                    z=hist_normalized.T,
                    x=x_edges,
                    y=y_edges,
                    colorscale=self.heatmap_colorscale,
                    showscale=True,
                    colorbar=dict(
                        title="Density",
                        tickfont=dict(color="white", size=10),
                        x=1.02,  # Moved slightly further right
                        xanchor="left",
                        len=0.7,  # Reduced length
                        y=0.5,
                        yanchor="middle",
                    ),
                    hoverinfo="skip",
                )
            )

            # Add shots if available
            if self.data.get("shots") is not None:
                fig = self._add_shots_to_figure(fig, self.data["shots"])

            # Update layout with optimized display
            fig.update_layout(
                template="plotly_dark",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    showticklabels=False,
                    showline=False,
                ),
                yaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    showticklabels=False,
                    showline=False,
                ),
                margin=dict(
                    l=0, r=10, t=0, b=0
                ),  # Minimal margins, extra space on right for colorbar
                showlegend=True,
                legend=dict(
                    bgcolor="rgba(0,0,0,0.7)",
                    font=dict(color="white", size=11),
                    x=1.08,  # Position legend further right, after colorbar
                    xanchor="left",
                    y=0.95,
                    yanchor="top",
                ),
                autosize=True,
            )

            # Desactivate plotly toolbar
            # config = {'displayModeBar': False,'scrollZoom': False,'responsive': True}
            # fig.update_layout(config=config)

            logger.info(
                f"✅ [TrackingViz] Heatmap created for {len(player_ids)} player(s)"
            )
            return fig

        except Exception as e:
            logger.error(f"❌ [TrackingViz] Error creating heatmap: {e}", exc_info=True)
            return self._create_empty_figure(f"Error creating heatmap: {str(e)}")

    def _create_shots_figure(self) -> go.Figure:
        """Create figure showing shot positions with xG-based sizing."""
        try:
            if self.data is None or self.data.get("shots") is None:
                return self._create_empty_figure("No shot data available")

            shots_data = self.data["shots"]

            # Filter by player if specified
            if "player_id" in self.filters and self.filters["player_id"] != "all":
                player_id = str(self.filters["player_id"])
                shots_data = shots_data[shots_data["player_id"] == player_id].copy()
                logger.info(
                    f"Filtered shots for player {player_id}: {len(shots_data)} shots"
                )

            if shots_data.empty:
                return self._create_empty_figure(
                    "No shot data for selected player/filters"
                )

            # Start with pitch background
            fig = self._create_pitch_background()

            # Group shots by outcome
            for outcome, color in self.shot_colors.items():
                outcome_shots = shots_data[shots_data["outcome"] == outcome]

                if len(outcome_shots) > 0:
                    # Calculate marker sizes based on xG (min 8, max 30)
                    min_size = 8
                    max_size = 30

                    # Normalize xG values for sizing
                    xg_values = outcome_shots["xG"].fillna(0).values
                    if len(xg_values) > 0 and max(xg_values) > 0:
                        # Scale xG values to marker size range
                        scaled_sizes = min_size + (xg_values / max(xg_values)) * (
                            max_size - min_size
                        )
                    else:
                        scaled_sizes = [min_size] * len(outcome_shots)

                    # Prepare normalized coordinates
                    x_coords = []
                    y_coords = []

                    for _, shot in outcome_shots.iterrows():
                        try:
                            x_norm, y_norm = self._normalize_coordinates(
                                shot["x"], shot["y"]
                            )
                            x_coords.append(x_norm)
                            y_coords.append(y_norm)
                        except Exception as e:
                            logger.debug(f"Error normalizing shot coordinates: {e}")
                            continue

                    if not x_coords:  # Skip if no valid coordinates
                        continue

                    # Add scatter trace for this outcome
                    fig.add_trace(
                        go.Scatter(
                            x=x_coords,
                            y=y_coords,
                            mode="markers",
                            name="Goal" if outcome else "No Goal",
                            marker=dict(
                                size=scaled_sizes,
                                color=color,
                                opacity=0.8,
                                line=dict(width=1, color="white"),
                                symbol="circle",
                            ),
                            hovertemplate=(
                                "<b>%{customdata[0]}</b><br>"
                                + "Position: %{x:.1f}m × %{y:.1f}m<br>"
                                + "Outcome: %{customdata[1]}<br>"
                                + "xG: %{customdata[2]:.3f}<br>"
                                + "Type: %{customdata[3]}<br>"
                                + "Distance: %{customdata[4]:.1f}m<extra></extra>"
                            ),
                            customdata=np.column_stack(
                                [
                                    outcome_shots["player_name"].iloc[: len(x_coords)],
                                    [
                                        "Goal" if o else "No Goal"
                                        for o in outcome_shots["outcome"].iloc[
                                            : len(x_coords)
                                        ]
                                    ],
                                    outcome_shots["xG"].iloc[: len(x_coords)],
                                    [
                                        "Header" if h else "Foot"
                                        for h in outcome_shots["is_header"].iloc[
                                            : len(x_coords)
                                        ]
                                    ],
                                    outcome_shots["shot_distance"].iloc[
                                        : len(x_coords)
                                    ],
                                ]
                            ),
                            hoverlabel=dict(
                                bgcolor="rgba(20, 25, 30, 0.95)",
                                font=dict(color="white", size=10),
                            ),
                        )
                    )

            # Update layout with optimized display
            fig.update_layout(
                template="plotly_dark",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(
                    range=[-1, self.pitch_width + 1],
                    showgrid=False,
                    zeroline=False,
                    showticklabels=False,
                    showline=False,
                ),
                yaxis=dict(
                    range=[-1, self.pitch_length + 1],
                    showgrid=False,
                    zeroline=False,
                    showticklabels=False,
                    showline=False,
                ),
                margin=dict(l=0, r=0, t=0, b=0),  # Minimal margins
                showlegend=True,
                legend=dict(
                    bgcolor="rgba(0,0,0,0.7)",
                    font=dict(color="white", size=11),
                    x=1.02,  # Position legend to the right
                    xanchor="left",
                    y=0.95,
                    yanchor="top",
                ),
                autosize=True,
            )

            # Desactivate plotly toolbar
            # config = {'displayModeBar': False,'scrollZoom': False,'responsive': True}
            # fig.update_layout(config=config)

            logger.info(
                f"✅ [TrackingViz] Shots figure created with {len(shots_data)} shots"
            )
            return fig

        except Exception as e:
            logger.error(
                f"❌ [TrackingViz] Error creating shots figure: {e}", exc_info=True
            )
            return self._create_empty_figure(f"Error creating shots figure: {str(e)}")

    def _create_combined_figure(self) -> go.Figure:
        """Create combined figure with heatmap and shots."""
        try:
            # Create subplots
            fig = make_subplots(
                rows=1,
                cols=2,
                subplot_titles=("Player Heatmap", "Shot Locations"),
                horizontal_spacing=0.1,
            )

            # Heatmap subplot
            heatmap_fig = self._create_heatmap_figure()
            if heatmap_fig.data:
                for trace in heatmap_fig.data:
                    fig.add_trace(trace, row=1, col=1)

            # Shots subplot
            shots_fig = self._create_shots_figure()
            if shots_fig.data:
                for trace in shots_fig.data:
                    fig.add_trace(trace, row=1, col=2)

            # Update layout for combined figure
            fig.update_layout(
                template="plotly_dark",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=10, b=0),
                showlegend=True,
                autosize=True,
            )

            # Update axes for both subplots
            for col in [1, 2]:
                fig.update_xaxes(
                    range=[-1, self.pitch_width + 1],
                    row=1,
                    col=col,
                    showgrid=False,
                    showticklabels=False,
                    showline=False,
                    scaleanchor="y",
                    scaleratio=1,
                    fixedrange=True,
                )
                fig.update_yaxes(
                    range=[-1, self.pitch_length + 1],
                    row=1,
                    col=col,
                    showgrid=False,
                    showticklabels=False,
                    showline=False,
                    fixedrange=True,
                )

            logger.info("✅ [TrackingViz] Combined figure created successfully")
            return fig

        except Exception as e:
            logger.error(f"❌ [TrackingViz] Error creating combined figure: {e}")
            return self._create_empty_figure(
                f"Error creating combined figure: {str(e)}"
            )

    def _add_pitch_to_subplot(self, fig: go.Figure, row: int, col: int):
        """Add pitch background to a specific subplot."""
        # Pitch outline
        fig.add_shape(
            type="rect",
            x0=0,
            y0=0,
            x1=self.pitch_width,
            y1=self.pitch_length,
            line=dict(color="white", width=2),
            fillcolor="rgba(11, 56, 30, 0.7)",
            layer="below",
            row=row,
            col=col,
        )

    def _add_shots_to_figure(
        self, fig: go.Figure, shots_data: pd.DataFrame
    ) -> go.Figure:
        """Add shot markers to an existing figure with xG-based sizing."""
        if shots_data is None or shots_data.empty:
            return fig

        # Filter by player if specified
        if "player_id" in self.filters and self.filters["player_id"] != "all":
            player_id = str(self.filters["player_id"])
            shots_data = shots_data[shots_data["player_id"] == player_id].copy()

        if shots_data.empty:
            return fig

        # Add shots as separate traces for each outcome
        for outcome, color in self.shot_colors.items():
            outcome_shots = shots_data[shots_data["outcome"] == outcome]

            if len(outcome_shots) > 0:
                # Calculate marker sizes based on xG
                min_size = 6
                max_size = 20
                xg_values = outcome_shots["xG"].fillna(0).values

                if len(xg_values) > 0 and max(xg_values) > 0:
                    scaled_sizes = min_size + (xg_values / max(xg_values)) * (
                        max_size - min_size
                    )
                else:
                    scaled_sizes = [min_size] * len(outcome_shots)

                # Prepare normalized coordinates
                x_coords = []
                y_coords = []

                for _, shot in outcome_shots.iterrows():
                    try:
                        x_norm, y_norm = self._normalize_coordinates(
                            shot["x"], shot["y"]
                        )
                        x_coords.append(x_norm)
                        y_coords.append(y_norm)
                    except Exception as e:
                        logger.debug(f"Error normalizing shot coordinates: {e}")
                        continue

                if not x_coords:
                    continue

                goal_value = "Goal" if outcome else "No Goal"

                fig.add_trace(
                    go.Scatter(
                        x=x_coords,
                        y=y_coords,
                        mode="markers",
                        name=f"Shot ({goal_value})",
                        marker=dict(
                            size=scaled_sizes,
                            color=color,
                            opacity=0.9,
                            line=dict(width=1.5, color="white"),
                            symbol="diamond",
                        ),
                        hovertemplate=(
                            "<b>%{customdata[0]}</b><br>"
                            + "Shot at: %{y:.1f}m × %{x:.1f}m<br>"
                            + "Outcome: %{customdata[1]}<br>"
                            + "xG: %{customdata[2]:.3f}<br>"
                            + "Type: %{customdata[3]}<br>"
                            + "Distance: %{customdata[4]:.1f}m<extra></extra>"
                        ),
                        customdata=np.column_stack(
                            [
                                outcome_shots["player_name"].iloc[: len(x_coords)],
                                [
                                    "Goal" if o else "No Goal"
                                    for o in outcome_shots["outcome"].iloc[
                                        : len(x_coords)
                                    ]
                                ],
                                outcome_shots["xG"].iloc[: len(x_coords)],
                                [
                                    "Header" if h else "Foot"
                                    for h in outcome_shots["is_header"].iloc[
                                        : len(x_coords)
                                    ]
                                ],
                                outcome_shots["shot_distance"].iloc[: len(x_coords)],
                            ]
                        ),
                        hoverlabel=dict(
                            bgcolor="rgba(20, 25, 30, 0.95)",
                            font=dict(color="white", size=10),
                        ),
                        showlegend=True,
                    )
                )

        return fig

    def _create_empty_figure(self, message: str = "Loading...") -> go.Figure:
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
            margin=dict(l=5, r=5, t=5, b=5),
        )
        return fig

    def update_filters(self, new_filters: Dict[str, Any]):
        """Update filters and refresh data."""
        super().update_filters(new_filters)
        self.data = None  # Force data refresh
