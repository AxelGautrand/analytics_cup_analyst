"""
Player Attributes Visualization - Optimized version with caching
"""
import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import scipy.stats as stats

from .base_viz import BaseVisualization

logger = logging.getLogger(__name__)

# -----------------------------
# Configuration
# -----------------------------
CATEGORIES_CONFIG = {
    "physical": {
        "label": "Physical",
        "attributes": {
            "speed": "Speed",
            "acceleration": "Acceleration",
            "stamina": "Stamina",
            "activity": "Activity",
        },
        "color": "#ff6384",  # Red
    },
    "mental": {
        "label": "Mental",
        "attributes": {
            "off_ball": "Off-Ball",
            "positioning": "Positioning",
            "decision_making": "Decision Making",
        },
        "color": "#489ccb",  # Blue
    },
    "technical_creation": {
        "label": "Technical - Creation",
        "attributes": {
            "ball_retention": "Ball Retention",
            "passing": "Passing",
            "crossing": "Crossing",
        },
        "color": "#ff9f43",  # Orange
    },
    "technical_defense": {
        "label": "Technical - Defense",
        "attributes": {
            "aerial_ability": "Aerial",
            "pressing": "Pressing",
            "tackling": "Tackling",
            "marking": "Marking",
        },
        "color": "#4aff7c",  # Green
    },
    "technical_attack": {
        "label": "Technical - Attack",
        "attributes": {"finishing": "Finishing", "long_shots": "Long Shots"},
        "color": "#c56cf0",  # Purple
    },
}

# Score colors for external display
SCORE_COLORS = {
    "excellent": "#4aff7c",  # > 16
    "good": "#6cbfcf",  # 13-16
    "average": "#489ccb",  # 10-13
    "weak": "#e8e8e7",  # < 10
}

# Comparison colors (for table)
COMPARISON_COLORS = {
    "above_median": "rgba(74, 255, 124, 0.3)",
    "at_median": "rgba(72, 156, 203, 0.3)",
    "below_median": "rgba(255, 99, 132, 0.3)",
    "border": "rgba(255, 255, 255, 0.1)",
    "text_above": "#4aff7c",
    "text_below": "#ff6384",
    "text_median": "#489ccb",
}

METRIC_EXPLANATIONS = {
    "finishing": "ΔxG on close-range shots",
    "long_shots": "ΔxG on long-range shots",
    "ball_retention": "ΔxLoss under pressure",
    "passing": "ΔxPass value",
    "crossing": "ΔxCross value",
    "aerial_ability": "Aerial duel win rate (Gaussian smoothing)",
    "pressing": "Pressures per 90min",
    "tackling": "Ball recoveries per 90min",
    "marking": "Avg distance to ball carrier when defending",
    "off_ball": "Average Off-ball movement score per 90min",
    "positioning": "Average Positioning score per 90min",
    "decision_making": "Mean diff in pass score vs optimal pass",
    "speed": "Top speed (PSV99 scale)",
    "acceleration": "Time to reach sprint speed",
    "stamina": "Total distance per 90min",
    "activity": "Sprint distance per 90min",
}


# -----------------------------
# Utility Functions
# -----------------------------
def convert_to_score_20(p: float, mu=10, sigma=4) -> float:
    """
    Convert percentile to score using a normal distribution.
    """
    p = min(max(p, 1e-6), 1 - 1e-6)
    z = stats.norm.ppf(p)
    score = mu + sigma * z
    return min(max(score, 0.0), 20.0)  # type: ignore


def get_score_color(score: float) -> str:
    """Get color corresponding to score level."""
    if score >= 16:
        return SCORE_COLORS["excellent"]
    elif score >= 13:
        return SCORE_COLORS["good"]
    elif score >= 10:
        return SCORE_COLORS["average"]
    else:
        return SCORE_COLORS["weak"]


def get_comparison_color(percentile: float) -> Dict[str, str]:
    """Get color for median comparison based on percentile."""
    if percentile > 0.5:
        return {
            "fill": COMPARISON_COLORS["above_median"],
            "text": COMPARISON_COLORS["text_above"],
            "symbol": "▲",
            "status": "above",
        }
    elif percentile == 0.5:
        return {
            "fill": COMPARISON_COLORS["at_median"],
            "text": COMPARISON_COLORS["text_median"],
            "symbol": "●",
            "status": "median",
        }
    else:
        return {
            "fill": COMPARISON_COLORS["below_median"],
            "text": COMPARISON_COLORS["text_below"],
            "symbol": "▼",
            "status": "below",
        }


def compute_percentiles(player_value: float, all_values: List[float]) -> float:
    """Compute percentile of a value within a distribution."""
    if not all_values:
        return 0.5

    # Handle NaN values
    valid_values = [v for v in all_values if pd.notna(v)]
    if not valid_values:
        return 0.5

    # Sort values and find rank
    sorted_values = sorted(valid_values)
    rank = sum(1 for v in sorted_values if v < player_value)

    # Calculate percentile
    percentile = rank / len(sorted_values)

    return percentile


def calculate_attributes_from_data(
    aggregated_df: pd.DataFrame,
    physical_aggregates_df: pd.DataFrame,
    player_id: str,
    min_minutes: float = 30.0,
) -> Dict[str, float]:
    """
    Calculate football player attributes with consistent per90 normalization.
    """
    attributes: Dict[str, float] = {}

    # Retrieve player data
    player_data = aggregated_df[aggregated_df["player_id"] == player_id]
    player_physical = physical_aggregates_df[
        physical_aggregates_df["player_id"] == player_id
    ]

    if player_data.empty:
        return {
            attr: 0.0
            for category in CATEGORIES_CONFIG.values()
            for attr in category["attributes"]
        }

    # Minutes played
    if (
        not player_physical.empty
        and "minutes_full_all" in player_physical.columns
        and pd.notna(player_physical["minutes_full_all"].iloc[0])
    ):
        minutes_played = float(player_physical["minutes_full_all"].iloc[0])
    else:
        minutes_played = 90.0

    minutes_played = max(minutes_played, min_minutes)

    # Helper functions
    def get_agg_value(context: str, metric: str, default: float = 0.0) -> float:
        col = f"{metric}_{context}"
        if col in player_data.columns:
            val = player_data[col].iloc[0]
            if pd.notna(val):
                return float(val)
        return default

    def per90(value: float) -> float:
        return value * 90.0 / minutes_played

    # PHYSICAL
    attributes["speed"] = float(
        player_physical["psv99_top5"].iloc[0]
        if "psv99_top5" in player_physical.columns
        else 0.0
    )

    attributes["acceleration"] = float(
        player_physical["timetosprint_top3"].iloc[0]
        if "timetosprint_top3" in player_physical.columns
        else 0.0
    )

    attributes["stamina"] = per90(
        float(player_physical["total_distance_full_all"].iloc[0])
        if "total_distance_full_all" in player_physical.columns
        else 0.0
    )

    attributes["activity"] = per90(
        float(player_physical["sprint_distance_full_all"].iloc[0])
        if "sprint_distance_full_all" in player_physical.columns
        else 0.0
    )

    # MENTAL
    # Note: using off_ball (not off_ball_calls) to match CATEGORIES_CONFIG
    attributes["off_ball"] = per90(
        get_agg_value("off_ball_runs", "sum_passing_option_score")
    )

    attributes["positioning"] = per90(
        get_agg_value("passing_options", "sum_passing_option_score")
    )

    attributes["decision_making"] = get_agg_value(
        "player_possession", "mean_passing_decision_delta"
    )

    # TECHNICAL - CREATION
    attributes["ball_retention"] = get_agg_value(
        "player_possession", "mean_xloss_delta_under_pressure"
    )

    attributes["passing"] = get_agg_value("player_possession", "mean_xpass_delta")

    attributes["crossing"] = get_agg_value("player_possession", "mean_xcross_delta")

    # TECHNICAL - DEFENSE
    headers_won = get_agg_value("header_successful", "count")
    headers_lost = get_agg_value("header_unsuccessful", "count")
    total_headers = headers_won + headers_lost

    ALPHA = 5
    BETA = 5
    attributes["aerial_ability"] = (headers_won + ALPHA) / (
        total_headers + ALPHA + BETA
    )

    attributes["pressing"] = per90(get_agg_value("pressing_successful", "count"))

    attributes["tackling"] = per90(get_agg_value("ball_recovery", "count"))

    attributes["marking"] = get_agg_value(
        "on_ball_engagement", "mean_defender_distance_to_ball_carrier"
    )

    # TECHNICAL - ATTACK
    attributes["finishing"] = get_agg_value("shot_close", "mean_shot_xg_delta")

    attributes["long_shots"] = get_agg_value("shot_long", "mean_shot_xg_delta")

    return attributes


def prepare_attribute_data_for_player(
    player_data: Dict[str, Any], all_players_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Prepare attribute data for a specific player using pre-calculated all players data.
    """
    if not player_data or "attributes" not in player_data:
        return {
            "player_info": {
                "name": "Unknown Player",
                "team": "",
                "position": "",
            },
            "attributes": {},
            "category_averages": {},
            "strengths": [],
            "overall_average": 0,
            "comparison_data": [],
        }

    # Extract all values for each attribute from the population
    all_attributes = {}
    attribute_medians = {}

    for category in CATEGORIES_CONFIG.values():
        for attr in category["attributes"].keys():
            values = [
                player.get("attributes", {}).get(attr, 0.0)
                for player in all_players_data
            ]
            all_attributes[attr] = values

            # Calculate median for each attribute
            if values:
                valid_values = [v for v in values if pd.notna(v)]
                if valid_values:
                    attribute_medians[attr] = np.median(valid_values)
                else:
                    attribute_medians[attr] = 0.0
            else:
                attribute_medians[attr] = 0.0

    # Calculate percentiles and scores for the target player
    attributes_data = {}
    category_scores = {}
    comparison_data = []

    for category_key, category_info in CATEGORIES_CONFIG.items():
        category_scores[category_key] = []

        for attr_key, attr_label in category_info["attributes"].items():
            player_value = player_data["attributes"].get(attr_key, 0.0)
            all_values = all_attributes.get(attr_key, [])

            # Calculate percentile within population
            percentile = compute_percentiles(player_value, all_values)

            # Convert to score out of 20
            score = convert_to_score_20(percentile)
            score_rounded = round(score, 1)

            # Get comparison info (above/below median)
            median_value = attribute_medians.get(attr_key, 0.0)
            comparison_info = get_comparison_color(percentile)

            # Calculate comparison percentage
            if median_value != 0:
                comparison_pct = (
                    (player_value - median_value) / abs(median_value)
                ) * 100
            else:
                comparison_pct = 0.0 if player_value == 0 else 100.0

            # Store attribute data
            attributes_data[attr_key] = {
                "label": attr_label,
                "value": player_value,
                "percentile": percentile,
                "score": score,
                "score_rounded": score_rounded,
                "category": category_key,
                "color": get_score_color(score),
                "median": median_value,
                "comparison_pct": comparison_pct,
                "comparison_color": comparison_info,
                "symbol": comparison_info["symbol"],
                "comparison_status": comparison_info["status"],
            }

            # Add to category scores for radar
            category_scores[category_key].append(score)

            # Add to comparison data for table
            comparison_data.append(
                {
                    "attribute_key": attr_key,
                    "category": category_info["label"],
                    "attribute": attr_label,
                    "score": score_rounded,
                    "percentile": int(percentile * 100),
                    "comparison": comparison_info["status"],
                    "symbol": comparison_info["symbol"],
                    "color": comparison_info["text"],
                    "fill_color": comparison_info["fill"],
                    "value": player_value,
                    "median": median_value,
                    "difference": player_value - median_value,
                }
            )

    # Calculate average scores per category (for radar chart)
    category_averages = {}
    for category_key, scores in category_scores.items():
        if scores:
            valid_scores = [s for s in scores if pd.notna(s)]
            if valid_scores:
                avg_score = sum(valid_scores) / len(valid_scores)
                category_averages[category_key] = {
                    "average": avg_score,
                    "rounded": round(avg_score, 1),
                    "color": get_score_color(avg_score),
                }

    # Sort strengths by score (descending) for widget display
    strengths_list = [
        {
            "label": data["label"],
            "score": float(data["score"]),
            "percentile": int(data["percentile"] * 100),
            "color": data["color"],
        }
        for data in attributes_data.values()
    ]
    strengths_list.sort(key=lambda x: x["score"], reverse=True)
    top_strengths = strengths_list[:6]

    # Sort comparison data by category for table
    comparison_data.sort(key=lambda x: (x["category"], x["attribute"]))

    return {
        "player_info": {
            "name": player_data.get("player_name", "Player"),
            "team": player_data.get("team", ""),
            "position": player_data.get("position", ""),
        },
        "attributes": attributes_data,
        "category_averages": category_averages,
        "strengths": top_strengths,
        "comparison_data": comparison_data,
        "overall_average": round(
            sum(avg["average"] for avg in category_averages.values())
            / len(category_averages),
            1,
        )
        if category_averages
        else 0,
    }


# -----------------------------
# Main Visualization Class
# -----------------------------
class PlayerAttributesVisualization(BaseVisualization):
    """Optimized player attributes visualization with caching."""

    def __init__(
        self,
        aggregator,
        filters: Dict[str, Any] = {},
        visualization_type: str = "radar",
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

        # Cache for all players data
        self._all_players_cache = None
        self._all_players_data = None
        self._last_filter_hash = None

        # Cache for current player
        self._current_player_id = None
        self._current_player_data = None
        self._current_attributes_data = None

    def _get_filter_hash(self) -> str:
        """Create a hash of the current filters for caching."""
        import hashlib

        filter_str = str(sorted(self.filters.items()))
        return hashlib.md5(filter_str.encode()).hexdigest()

    def prepare_data(self):
        """Prepare data for ALL players once and cache it."""
        logger.info("📊 [PlayerAttributesViz] Preparing data for all players...")

        # Check if we need to recalculate
        current_filter_hash = self._get_filter_hash()
        if (
            self._all_players_cache is not None
            and self._last_filter_hash == current_filter_hash
        ):
            logger.debug("Using cached data for all players")
            return

        try:
            from core.data_manager import data_manager

            # Get aggregated data for all players
            config_name = self.aggregation_context or "player_attributes"
            aggregated_data = data_manager.get_aggregated_data(
                config_name=config_name,
                group_by=["player_id", "player_name"],
                filters=self.filters,
            )

            if aggregated_data is None or aggregated_data.empty:
                logger.warning("No aggregated data available")
                self._all_players_cache = {}
                self._all_players_data = []
                self._last_filter_hash = current_filter_hash
                return

            # Get physical aggregates
            physical_aggregates = data_manager.physical_aggregates
            if physical_aggregates is None or physical_aggregates.empty:
                logger.warning("No physical aggregates data available")
                self._all_players_cache = {}
                self._all_players_data = []
                self._last_filter_hash = current_filter_hash
                return

            # Find intersection of players with both data sources
            dynamic_player_ids = aggregated_data["player_id"].unique()
            physical_player_ids = physical_aggregates["player_id"].unique()
            all_player_ids = list(set(dynamic_player_ids) & set(physical_player_ids))

            if not all_player_ids:
                logger.warning("No players found with both data sources")
                self._all_players_cache = {}
                self._all_players_data = []
                self._last_filter_hash = current_filter_hash
                return

            # Calculate attributes for all players and cache them
            all_players_data = []
            players_cache = {}

            for player_id in all_player_ids:
                try:
                    # Get player info
                    player_row = aggregated_data[
                        aggregated_data["player_id"] == player_id
                    ]
                    if player_row.empty:
                        continue

                    player_name = player_row["player_name"].iloc[0]

                    # Calculate attributes
                    attributes = calculate_attributes_from_data(
                        aggregated_df=aggregated_data,
                        physical_aggregates_df=physical_aggregates,
                        player_id=player_id,
                    )

                    player_data = {
                        "player_id": player_id,
                        "player_name": player_name,
                        "team": "",
                        "position": "",
                        "attributes": attributes,
                    }

                    all_players_data.append(player_data)
                    players_cache[player_id] = player_data
                    players_cache[player_name] = player_data

                except Exception as e:
                    logger.debug(f"Error processing player {player_id}: {e}")
                    continue

            # Store in cache
            self._all_players_cache = players_cache
            self._all_players_data = all_players_data
            self._last_filter_hash = current_filter_hash

            logger.info(
                f"✅ [PlayerAttributesViz] Cached data for {len(all_players_data)} players"
            )

        except Exception as e:
            logger.exception(f"❌ [PlayerAttributesViz] Error preparing data: {e}")
            self._all_players_cache = {}
            self._all_players_data = []
            self._last_filter_hash = current_filter_hash

    def get_player_data(
        self, player_id: Optional[str] = None, player_label: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get prepared player attribute data for a specific player.
        """
        # Ensure we have cached data
        if self._all_players_cache is None:
            self.prepare_data()

        if not self._all_players_cache:
            return None

        # Find player in cache
        player_data = None

        if player_id and player_id in self._all_players_cache:
            player_data = self._all_players_cache[player_id]
        elif player_label and player_label in self._all_players_cache:
            player_data = self._all_players_cache[player_label]
        else:
            # Try to find by name (partial match)
            if player_label:
                for key, data in self._all_players_cache.items():
                    if isinstance(key, str) and player_label in key:
                        player_data = data
                        break

        if player_data is None and self._all_players_data:
            # Return first player as fallback
            player_data = self._all_players_data[0]

        if player_data:
            # Check if we need to update cache for this specific player
            current_player_key = (
                f"{player_data.get('player_id')}_{player_data.get('player_name')}"
            )
            if (
                self._current_player_id != current_player_key
                or self._current_attributes_data is None
            ):
                # Prepare attribute data for this player
                self._current_player_id = current_player_key
                self._current_player_data = player_data
                self._current_attributes_data = prepare_attribute_data_for_player(
                    player_data, self._all_players_data  # type: ignore
                )

            return self._current_attributes_data

        return None

    def create_figure(
        self, player_id: Optional[str] = None, player_label: Optional[str] = None
    ) -> go.Figure:
        """Create visualization figure based on viz_type."""
        logger.debug(f"🎨 [PlayerAttributesViz] Creating {self.viz_type} chart...")

        # Get player data
        player_data = self.get_player_data(player_id, player_label)

        if not player_data:
            logger.warning(f"No attribute data available for {self.viz_type} chart")
            return self._create_empty_figure("No attribute data available")

        if self.viz_type == "radar":
            return self._create_radar_chart(player_data)
        elif self.viz_type == "table":
            return self._create_comparison_table(player_data)
        else:
            logger.warning(f"Unknown visualization type: {self.viz_type}")
            return self._create_empty_figure(f"Unknown viz type: {self.viz_type}")

    def _create_radar_chart(self, player_data: Dict[str, Any]) -> go.Figure:
        """Create radar chart figure for specific player."""
        try:
            # Prepare data for radar chart
            categories = []
            scores = []
            colors = []
            hover_texts = []

            category_averages = player_data["category_averages"]
            attributes_data = player_data["attributes"]

            # Define the order for the radar chart
            radar_order = [
                "technical_attack",
                "technical_creation",
                "technical_defense",
                "physical",
                "mental",
            ]

            for category_key in radar_order:
                if category_key in category_averages:
                    avg_data = category_averages[category_key]
                    category_info = CATEGORIES_CONFIG[category_key]

                    categories.append(category_info["label"])
                    normalized_score = avg_data["average"] / 20
                    scores.append(normalized_score)
                    colors.append(category_info["color"])

                    # Get individual attributes for hover
                    category_attributes = []
                    for attr_key in category_info["attributes"].keys():
                        if attr_key in attributes_data:
                            attr = attributes_data[attr_key]
                            category_attributes.append(
                                f"{attr['label']}: {attr['score_rounded']}/20"
                            )

                    # Prepare hover text
                    hover_text = (
                        f"<span style='color:{category_info['color']};font-weight:bold'>"
                        f"{category_info['label']}</span><br>"
                        f"Score: {avg_data['rounded']}/20<br><br>"
                        f"<b>Attributes:</b><br>"
                    )
                    hover_text += "<br>".join(category_attributes)
                    hover_text += "<extra></extra>"
                    hover_texts.append(hover_text)

            # Duplicate first point to close the radar chart
            if categories and scores:
                categories = categories + [categories[0]]
                scores = scores + [scores[0]]
                colors = colors + [colors[0]]
                hover_texts = hover_texts + [hover_texts[0]]

            # Create radar chart
            fig = go.Figure()
            fig.add_trace(
                go.Scatterpolar(
                    r=scores,
                    theta=categories,
                    fill="toself",
                    fillcolor="rgba(72, 156, 203, 0.1)",
                    line=dict(color="#489ccb", width=2),
                    marker=dict(
                        size=10, color=colors, line=dict(width=2, color="white")
                    ),
                    hovertemplate="%{hovertext}",
                    hovertext=hover_texts,
                    hoverlabel=dict(
                        bgcolor="rgba(20, 25, 30, 0.95)",
                        bordercolor="#489ccb",
                        font=dict(color="white", size=12),
                    ),
                )
            )

            # Optimize layout
            fig.update_layout(
                polar=dict(
                    bgcolor="rgba(0,0,0,0)",
                    radialaxis=dict(
                        visible=True,
                        range=[0, 1],
                        tickvals=[0, 0.25, 0.5, 0.75, 1],
                        ticktext=["", "", "", "", ""],
                        gridcolor="rgba(255,255,255,0.1)",
                        linecolor="rgba(255,255,255,0.15)",
                        angle=90,
                        showticklabels=False,
                    ),
                    angularaxis=dict(
                        gridcolor="rgba(255,255,255,0.05)",
                        linecolor="rgba(255,255,255,0.1)",
                        rotation=90,
                        direction="clockwise",
                        tickfont=dict(size=1),
                        showticklabels=False,
                    ),
                ),
                template="plotly_dark",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white", size=11),
                showlegend=False,
                margin=dict(l=0, r=0, t=0, b=0),
                autosize=True,
            )

            logger.info("✅ [PlayerAttributesViz] Radar chart created successfully")
            return fig

        except Exception as e:
            logger.error(f"❌ [PlayerAttributesViz] Error creating radar chart: {e}")
            return self._create_empty_figure(f"Error creating radar: {str(e)}")

    def _create_comparison_table(self, player_data: Dict[str, Any]) -> go.Figure:
        """Create comparison table showing actual statistics relative to median."""
        try:
            comparison_data = player_data.get("comparison_data", [])

            if not comparison_data:
                return self._create_empty_figure("No comparison data available")

            # Define metric display formatting with ORDER
            METRIC_ORDER = [
                "finishing",  # 1. Finishing Δ
                "long_shots",  # 2. Long Shot Δ
                "ball_retention",  # 3. Ball Retention Δ
                "passing",  # 4. Passing Δ
                "crossing",  # 5. Crossing Δ
                "aerial_ability",  # 6. Aerial Duels Δ
                "pressing",  # 7. Presses / 90
                "tackling",  # 8. Engagements / 90
                "marking",  # 9. Avg Distance to Ball
                "off_ball",  # 10. Off-Ball Score / 90
                "positioning",  # 11. Positioning Score / 90
                "decision_making",  # 12. Pass Decision Δ
                "speed",  # 13. Top Speed (PSV99)
                "acceleration",  # 14. Time to Sprint (s)
                "stamina",  # 15. Distance / 90min
                "activity",  # 16. Sprint Distance / 90min
            ]

            METRIC_FORMATS = {
                "finishing": "{:.3f}",
                "long_shots": "{:.3f}",
                "ball_retention": "{:.3f}",
                "passing": "{:.3f}",
                "crossing": "{:.3f}",
                "aerial_ability": "{:.1%}",
                "pressing": "{:.2f}",
                "tackling": "{:.2f}",
                "marking": "{:.1f}m",
                "off_ball": "{:.2f}",
                "positioning": "{:.2f}",
                "decision_making": "{:.3f}",
                "speed": "{:.1f}",
                "acceleration": "{:.2f}s",
                "stamina": "{:.0f}m",
                "activity": "{:.0f}m",
            }

            # Category colors for cell backgrounds
            CATEGORY_COLORS = {
                "Physical": "rgba(255, 99, 132, 0.1)",
                "Mental": "rgba(72, 156, 203, 0.1)",
                "Technical - Creation": "rgba(255, 159, 67, 0.1)",
                "Technical - Defense": "rgba(74, 255, 124, 0.1)",
                "Technical - Attack": "rgba(197, 108, 240, 0.1)",
            }

            # Create a dictionary for quick lookup of comparison data
            comparison_dict = {item["attribute_key"]: item for item in comparison_data}

            # Prepare data for table IN THE SPECIFIED ORDER
            display_names = []
            metric_values = []
            percentiles = []
            comparisons = []

            metric_colors = []
            value_colors = []
            percentile_colors = []
            comparison_colors = []

            for attr_key in METRIC_ORDER:
                if attr_key not in comparison_dict:
                    logger.debug(f"Skipping missing metric: {attr_key}")
                    continue

                item = comparison_dict[attr_key]
                category = item["category"]

                # Get explanation for this metric
                explanation = METRIC_EXPLANATIONS.get(attr_key, "")

                # Create combined display name with explanation
                display_name = f"{item['attribute']}<br><sub style='font-size: 10px; opacity: 0.7;'>{explanation}</sub>"

                # Format the value
                format_str = METRIC_FORMATS.get(attr_key, "{:.2f}")
                formatted_value = format_str.format(item["value"])

                # Determine comparison symbol and value
                diff_value = item["difference"]
                symbol = item["symbol"]

                if diff_value > 0:
                    comparison_display = f"{symbol} +{abs(diff_value):.3f}"
                elif diff_value < 0:
                    comparison_display = f"{symbol} -{abs(diff_value):.3f}"
                else:
                    comparison_display = f"{symbol} 0.000"

                # Get category color for cell background
                cell_bg_color = CATEGORY_COLORS.get(
                    category, "rgba(255, 255, 255, 0.05)"
                )

                # Append data IN ORDER
                display_names.append(display_name)
                metric_values.append(formatted_value)
                percentiles.append(f"{item['percentile']}%")
                comparisons.append(comparison_display)

                # Apply colors
                metric_colors.append(cell_bg_color)
                value_colors.append(cell_bg_color)
                percentile_colors.append(cell_bg_color)
                comparison_colors.append(cell_bg_color)

            if not display_names:
                return self._create_empty_figure("No valid metrics to display")

            # Create table trace with updated column widths
            fig = go.Figure(
                data=[
                    go.Table(
                        columnwidth=[
                            220,
                            100,
                            80,
                            120,
                        ],  # Première colonne légèrement plus large
                        header=dict(
                            values=["Metric", "Value", "Percentile", "vs Median"],
                            fill_color="rgba(20, 25, 30, 0.95)",
                            align=["left", "center", "center", "center"],
                            font=dict(
                                color="white", size=12, family="Arial", weight="bold"
                            ),
                            line=dict(color=COMPARISON_COLORS["border"], width=1.5),
                        ),
                        cells=dict(
                            values=[
                                display_names,
                                metric_values,
                                percentiles,
                                comparisons,
                            ],
                            fill_color=[
                                metric_colors,
                                value_colors,
                                percentile_colors,
                                comparison_colors,
                            ],
                            align=["left", "center", "center", "center"],
                            font=dict(
                                color=["white"] * len(display_names),
                            ),
                            height=40,
                            line=dict(color=COMPARISON_COLORS["border"], width=0.5),
                        ),
                    )
                ]
            )

            # Customize layout
            fig.update_layout(
                template="plotly_dark",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white", size=11),
                margin=dict(l=0, r=0, t=0, b=0),
                height=650,  # Hauteur légèrement augmentée
            )

            logger.info("✅ [PlayerAttributesViz] Comparison table created successfully")
            return fig

        except Exception as e:
            logger.error(
                f"❌ [PlayerAttributesViz] Error creating comparison table: {e}"
            )
            return self._create_empty_figure(f"Error creating table: {str(e)}")

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
            margin=dict(l=20, r=20, t=40, b=20),
        )
        return fig
