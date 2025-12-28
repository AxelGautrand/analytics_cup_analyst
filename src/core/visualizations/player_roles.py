"""
Player Style Profile Visualization - Complete with data processing
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .base_viz import BaseVisualization

logger = logging.getLogger(__name__)

# -----------------------------
# Configuration
# -----------------------------
COLOR_GRADIENT = [
    "#236883",  # Deep blue
    "#489ccb",  # Blue
    "#6cbfcf",  # Cyan
    "#90c4b1",  # Mint
    "#4aff7c",  # Bright green
]

STRENGTH_COLORS = {
    "high": "#4aff7c",  # > 80%
    "medium": "#489ccb",  # 60-80%
    "low": "#e8e8e7",  # < 60%
}

AXES_DEFINITION: Dict[str, Dict[str, float]] = {
    "depth": {
        "depth_runs_ratio": 0.7,
        "open_space_reception_ratio": 0.3,
    },
    "association": {
        "association_run_ratio": 0.45,
        "quick_pass_ratio": 0.2,
        "tight_space_reception_ratio": 0.35,
    },
    "width": {
        "width_ratio": 1.0,
    },
    "progression": {
        "progressive_pass_ratio": 0.5,
        "line_break_pass_ratio": 0.5,
    },
    "creativity": {
        "last_line_break_ratio": 0.4,
        "opponents_bypassed_ratio": 0.3,
        "defensive_line_movement_ratio": 0.3,
    },
    "pressing": {
        "defensive_activity_rate": 1.0,
    },
    "danger": {
        "shot_frequency": 0.6,
        "dangerous_action_ratio": 0.4,
    },
    "aerial": {
        "aerial_involvement_ratio": 1.0,
    },
}

POSITION_FAMILY_MAP = {
    "GK": "GK",
    "LB": "FB",
    "RB": "FB",
    "LWB": "FB",
    "RWB": "FB",
    "RCB": "CB",
    "LCB": "CB",
    "CB": "CB",
    "DM": "CM",
    "LDM": "CM",
    "RDM": "CM",
    "AM": "CM",
    "LM": "W",
    "RM": "W",
    "LW": "W",
    "RW": "W",
    "LF": "F",
    "RF": "F",
    "CF": "F",
    "SUB": "SUB",
}

ROLE_PROFILES = {
    "F": {
        "Deep Forward": {
            "depth": 1.0,
            "danger": 1.0,
            "width": 0.2,
            "creativity": 0.2,
            "progression": 0.1,
            "aerial": 0.0,
            "pressing": -0.8,
            "association": -0.7,
        },
        "False 9": {
            "association": 1.0,
            "creativity": 0.8,
            "progression": 0.6,
            "danger": 0.3,
            "pressing": 0.0,
            "width": -0.4,
            "aerial": -0.5,
            "depth": -0.8,
        },
        "Target Man": {
            "aerial": 1.0,
            "association": 0.8,
            "pressing": 0.4,
            "danger": 0.4,
            "depth": -0.4,
            "creativity": -0.3,
            "width": -0.6,
            "progression": -0.3,
        },
        "Pressing Forward": {
            "pressing": 1.0,
            "depth": 0.2,
            "aerial": 0.2,
            "danger": 0.1,
            "width": 0.1,
            "association": -0.2,
            "creativity": -0.2,
            "progression": -0.2,
        },
        "Complete Forward": {
            "depth": 0.2,
            "association": 0.2,
            "creativity": 0.2,
            "danger": 0.2,
            "pressing": 0.0,
            "aerial": 0.1,
            "progression": 0.1,
            "width": 0.0,
        },
    },
    "W": {
        "Wide Winger": {
            "width": 1.0,
            "depth": 0.5,
            "danger": 0.4,
            "creativity": 0.2,
            "progression": 0.2,
            "aerial": -0.4,
            "pressing": -0.4,
            "association": -0.5,
        },
        "Inverted Winger": {
            "danger": 0.7,
            "creativity": 0.6,
            "association": 0.3,
            "progression": 0.4,
            "width": -1.0,
            "depth": 0.0,
            "pressing": 0.0,
            "aerial": 0.0,
        },
        "Playmaking Winger": {
            "creativity": 0.8,
            "association": 0.7,
            "progression": 0.6,
            "danger": 0.1,
            "width": 0.0,
            "depth": -0.5,
            "pressing": -0.3,
            "aerial": -0.4,
        },
        "Defensive Winger": {
            "pressing": 1.0,
            "aerial": 0.6,
            "width": 0.2,
            "association": 0.3,
            "depth": 0.1,
            "danger": -0.5,
            "creativity": -0.4,
            "progression": -0.3,
        },
        "Complete Winger": {
            "danger": 0.3,
            "creativity": 0.3,
            "pressing": 0.0,
            "depth": 0.2,
            "association": 0.1,
            "progression": 0.2,
            "aerial": 0.0,
            "width": 0.1,
        },
    },
    "CM": {
        "Defensive Midfielder": {
            "pressing": 1.0,
            "progression": 0.6,
            "association": 0.4,
            "aerial": 0.7,
            "danger": -0.5,
            "creativity": -0.4,
            "depth": -0.5,
            "width": -0.3,
        },
        "Box-to-box": {
            "progression": 0.4,
            "pressing": 0.4,
            "association": 0.3,
            "creativity": 0.0,
            "danger": 0.1,
            "depth": 0.0,
            "width": 0.0,
            "aerial": -0.2,
        },
        "Playmaker": {
            "creativity": 0.8,
            "association": 0.6,
            "progression": 0.6,
            "danger": 0.2,
            "pressing": -0.4,
            "aerial": -0.4,
            "depth": -0.3,
            "width": -0.1,
        },
        "Attacking Midfielder": {
            "creativity": 0.7,
            "danger": 0.7,
            "association": 0.3,
            "progression": 0.2,
            "depth": 0.2,
            "width": 0.0,
            "pressing": -0.8,
            "aerial": -0.4,
        },
        "Complete Midfielder": {
            "progression": 0.2,
            "association": 0.2,
            "creativity": 0.2,
            "pressing": 0.2,
            "danger": 0.1,
            "aerial": 0.1,
            "depth": 0.0,
            "width": 0.0,
        },
    },
    "CB": {
        "Ball-playing Defender": {
            "progression": 0.6,
            "creativity": 0.4,
            "association": 0.5,
            "width": 0.3,
            "depth": 0.2,
            "aerial": -0.5,
            "danger": 0.1,
            "pressing": -0.6,
        },
        "Aggressive Defender": {
            "pressing": 1.0,
            "aerial": 0.7,
            "association": 0.3,
            "danger": 0.3,
            "creativity": -0.3,
            "progression": -0.4,
            "width": -0.2,
            "depth": -0.4,
        },
        "Cover Defender": {
            "aerial": 0.7,
            "pressing": 0.3,
            "association": 0.6,
            "creativity": 0.2,
            "danger": -0.3,
            "progression": -0.2,
            "depth": -0.5,
            "width": 0.0,
        },
        "Aerial Dominator": {
            "aerial": 1.0,
            "danger": 0.9,
            "pressing": 0.5,
            "progression": 0.1,
            "creativity": -0.4,
            "association": -0.2,
            "width": -0.5,
            "depth": -0.4,
        },
        "Complete Defender": {
            "aerial": 0.2,
            "pressing": 0.2,
            "progression": 0.2,
            "association": 0.2,
            "creativity": 0.1,
            "danger": 0.1,
            "width": 0.0,
            "depth": 0.0,
        },
    },
    "FB": {
        "Attacking Fullback": {
            "depth": 0.6,
            "width": 0.4,
            "progression": 0.5,
            "creativity": 0.3,
            "association": 0.2,
            "danger": 0.3,
            "pressing": -0.7,
            "aerial": -0.6,
        },
        "Defensive Fullback": {
            "pressing": 1.0,
            "aerial": 0.8,
            "association": 0.4,
            "width": 0.5,
            "depth": -0.3,
            "danger": -0.8,
            "creativity": -0.3,
            "progression": -0.3,
        },
        "Wing-back": {
            "width": 1.0,
            "progression": 0.4,
            "depth": 0.0,
            "pressing": 0.1,
            "creativity": 0.0,
            "association": 0.0,
            "danger": 0.0,
            "aerial": -0.5,
        },
        "Inverted Fullback": {
            "progression": 0.6,
            "creativity": 0.5,
            "association": 0.5,
            "pressing": 0.5,
            "depth": 0.0,
            "width": -1.0,
            "danger": -0.1,
            "aerial": 0.0,
        },
        "Complete Fullback": {
            "width": 0.2,
            "pressing": 0.2,
            "progression": 0.2,
            "association": 0.2,
            "depth": 0.0,
            "creativity": 0.1,
            "aerial": 0.1,
            "danger": 0.0,
        },
    },
    "GK": {
        "Goalkeeper": {
            "depth": 0.125,
            "width": 0.125,
            "progression": 0.125,
            "creativity": 0.125,
            "association": 0.125,
            "danger": 0.125,
            "pressing": 0.125,
            "aerial": 0.125,
        }
    },
    "SUB": {
        "SUB": {
            "depth": 0.125,
            "width": 0.125,
            "progression": 0.125,
            "creativity": 0.125,
            "association": 0.125,
            "danger": 0.125,
            "pressing": 0.125,
            "aerial": 0.125,
        }
    },
}

# FIXME : Handle subsitute players


# -----------------------------
# UTILITY FUNCTIONS
# -----------------------------
def compute_quantiles(
    df: pd.DataFrame, group_col: str, metrics: List[str]
) -> pd.DataFrame:
    """Compute per-group quantile-normalized values."""
    df_q = df.copy()
    for metric in metrics:
        if metric in df_q.columns:
            df_q[metric + "_q"] = (
                df_q.groupby(group_col)[metric].rank(pct=True).clip(0, 1)
            )
        else:
            df_q[metric + "_q"] = 0.0
    return df_q


def compute_axes_scores(
    df: pd.DataFrame, axes_definition: Dict[str, Dict[str, float]]
) -> pd.DataFrame:
    """Compute axis scores as weighted sum of metrics."""
    df_axes = df.copy()
    for axis, metrics in axes_definition.items():
        score = 0.0
        for metric, weight in metrics.items():
            metric_q = metric + "_q"
            if metric_q in df_axes.columns:
                score += weight * df_axes[metric_q]
        df_axes["axis_" + axis] = score.clip(0, 1)  # type: ignore
    return df_axes


def compute_style_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all style ratios from raw count columns.
    Assumes only count_* columns are available.
    """
    df = df.copy()

    # --------------------
    # DEPTH
    # --------------------
    df["depth_runs_ratio"] = (
        df["count_runs_in_behind"] + df["count_runs_ahead_of_ball"]
    ) / df["count_off_ball_runs"].replace(0, np.nan)

    df["open_space_reception_ratio"] = df["count_received_in_open_space"] / df[
        "count_pass_receptions"
    ].replace(0, np.nan)

    # --------------------
    # ASSOCIATION
    # --------------------
    df["association_run_ratio"] = df["count_associations_runs"] / df[
        "count_off_ball_runs"
    ].replace(0, np.nan)

    df["quick_pass_ratio"] = df["count_quick_passes"] / df["count_passes"].replace(
        0, np.nan
    )

    df["tight_space_reception_ratio"] = df["count_received_in_tight_space"] / df[
        "count_pass_receptions"
    ].replace(0, np.nan)

    # --------------------
    # WIDTH
    # --------------------
    df["width_ratio"] = df["count_wide_actions"] / (
        df["count_wide_actions"] + df["count_interior_actions"]
    ).replace(0, np.nan)

    # --------------------
    # PROGRESSION
    # --------------------
    df["progressive_pass_ratio"] = df["count_progressive_pass"] / df[
        "count_passes"
    ].replace(0, np.nan)

    df["line_break_pass_ratio"] = df["count_line_break_pass"] / df[
        "count_passes"
    ].replace(0, np.nan)

    # --------------------
    # CREATIVITY
    # --------------------
    df["last_line_break_ratio"] = df["count_last_line_break"] / df[
        "count_passes"
    ].replace(0, np.nan)

    df["opponents_bypassed_ratio"] = df["count_player_bypassed_possessions"] / df[
        "count_player_possessions"
    ].replace(0, np.nan)

    df["defensive_line_movement_ratio"] = df[
        "count_moving_defensive_line_possessions"
    ] / df["count_player_possessions"].replace(0, np.nan)

    # --------------------
    # PRESSING
    # --------------------
    df["defensive_activity_rate"] = df["count_pressing"] / df[
        "count_all_events"
    ].replace(0, np.nan)

    # --------------------
    # DANGER
    # --------------------
    df["shot_frequency"] = df["count_shot"] / df["count_player_possessions"].replace(
        0, np.nan
    )

    df["dangerous_action_ratio"] = df["count_dangerous_movement"] / df[
        "count_all_events"
    ].replace(0, np.nan)

    # --------------------
    # AERIAL
    # --------------------
    df["aerial_involvement_ratio"] = (
        df["count_aerial_duel"] + df["count_aerial_target"]
    ) / df["count_aerial_events"].replace(0, np.nan)

    return df.fillna(0)


def calculate_role_affinity(
    player_axes: Dict[str, float], role_profile: Dict[str, float]
) -> float:
    """
    Calculate affinity score for a role with exponential amplification.

    Args:
        player_axes: Dict of player's axis scores (0-1)
        role_profile: Dict of role coefficients (+ for good, - for bad)

    Returns:
        float: Affinity score between 0 and 1
    """
    # Calculate raw dot product
    raw_score = 0.0
    for axis, coefficient in role_profile.items():
        player_value = player_axes.get(axis, 0.5)  # Default to neutral 0.5
        raw_score += player_value * coefficient

    # Apply sigmoid function to get smooth 0-1 score
    # The sigmoid helps with discrimination while keeping it smooth
    sigmoid_score = 1 / (1 + np.exp(-raw_score))

    return sigmoid_score


def amplify_differences(
    scores: Dict[str, float], power: float = 3.0, min_percentage: float = 5.0
) -> Dict[str, float]:
    """
    Amplify differences between scores while keeping distribution fluid.

    Args:
        scores: Dict of role affinity scores
        power: Amplification factor (higher = more discrimination)
        min_percentage: Minimum percentage to include in final distribution

    Returns:
        Dict of role percentages
    """
    if not scores:
        return {}

    # Convert to arrays
    roles = list(scores.keys())
    values = np.array(list(scores.values()))

    # Step 1: Apply power function to amplify differences
    amplified = np.power(values, power)

    # Step 2: Normalize to percentages
    total = np.sum(amplified)
    if total == 0:
        return {}

    percentages = (amplified / total) * 100

    # Step 3: Filter by minimum percentage
    result = {}
    for role, percentage in zip(roles, percentages):
        if percentage >= min_percentage:
            result[role] = round(float(percentage), 1)

    # Step 4: Ensure at least 2 roles if possible
    if len(result) < 2 and len(scores) >= 2:
        # Keep top 2 roles
        top_indices = np.argsort(values)[-2:]
        result = {}
        top_values = values[top_indices]
        top_total = np.sum(top_values)

        for idx in top_indices:
            role = roles[idx]
            percentage = (values[idx] / top_total) * 100
            result[role] = round(float(percentage), 1)

    return result


def compute_role_distribution(
    row: pd.Series,
    role_profiles: Dict[str, Dict[str, Dict[str, float]]],
    amplification_power: float = 3.0,
) -> Dict[str, float]:
    """
    Compute role percentage distribution with improved discrimination.

    Args:
        row: Player data row
        role_profiles: Role profiles dictionary
        amplification_power: Power for amplifying differences

    Returns:
        Dict of role percentages
    """
    position = row.get("player_position_family", "SUB")
    if position not in role_profiles:
        return {}

    # Extract player axis scores
    player_axes = {}
    for col in row.index:
        if col.startswith("axis_"):
            axis_name = col.replace("axis_", "")
            player_axes[axis_name] = row[col]

    # Calculate raw affinity scores for each role
    raw_affinities = {}
    for role_name, role_profile in role_profiles[position].items():
        affinity = calculate_role_affinity(player_axes, role_profile)
        raw_affinities[role_name] = affinity

    # Amplify differences to get better discrimination
    distribution = amplify_differences(raw_affinities, power=amplification_power)

    return distribution


def get_role_contributions(
    role: str, player_axes: Dict[str, float], role_profile: Dict[str, float]
) -> List[Tuple[str, float]]:
    """Calculate how much each axis contributes to this role assignment."""
    contributions = []

    for axis, role_weight in role_profile.items():
        if axis in player_axes:
            # Calculate contribution (positive or negative)
            contribution = player_axes[axis] * role_weight
            contributions.append((axis.title(), contribution))

    # Sort by absolute contribution
    contributions.sort(key=lambda x: abs(x[1]), reverse=True)

    # Take top 3 contributions for display
    top_contributions = contributions[:3]

    # Calculate percentages for top contributions
    total_abs = sum(abs(c[1]) for c in top_contributions)
    if total_abs > 0:
        return [
            (axis, round((abs(score) / total_abs) * 100, 1))
            for axis, score in top_contributions
        ]

    return []


def get_top_strengths(player_row: pd.Series) -> List[Dict[str, Any]]:
    """Extract top strengths from player data."""
    strengths = []

    axis_cols = [col for col in player_row.index if col.startswith("axis_")]
    for col in axis_cols:
        score = player_row[col]
        if score > 0:
            axis_name = col.replace("axis_", "").title()
            percentile = int(score * 100)

            # Get color based on percentile
            if percentile >= 80:
                color = STRENGTH_COLORS["high"]
            elif percentile >= 60:
                color = STRENGTH_COLORS["medium"]
            else:
                color = STRENGTH_COLORS["low"]

            strengths.append(
                {
                    "label": axis_name,
                    "score": float(score),
                    "percentile": percentile,
                    "color": color,
                }
            )

    strengths.sort(key=lambda x: x["score"], reverse=True)
    return strengths


def get_color_from_gradient(value: float, max_value: float) -> str:
    """Get color from gradient based on value."""
    if max_value == 0:
        return COLOR_GRADIENT[0]

    normalized = value / max_value
    idx = int(normalized * (len(COLOR_GRADIENT) - 1))
    idx = min(max(idx, 0), len(COLOR_GRADIENT) - 1)

    return COLOR_GRADIENT[idx]


# -----------------------------
# Main Visualization Class
# -----------------------------
class PlayerStyleProfileVisualization(BaseVisualization):
    """Player style profile with improved role distribution."""

    def __init__(
        self,
        aggregator,
        filters: Dict[str, Any] = {},
        visualization_type: str = "radar",
        aggregation_context: Optional[str] = None,
        amplification_power: float = 10.0,  # parameter for discrimination
    ):
        super().__init__(aggregator, filters)
        self.viz_type = visualization_type
        self.aggregation_context = aggregation_context
        self.amplification_power = amplification_power
        self.data = None
        self.player_data = None

    def prepare_data(self):
        """Prepare ALL data with axes, roles, and strengths."""
        logger.info(
            "📊 [PlayerStyleProfileViz] Preparing data with improved role distribution"
        )
        try:
            from core.data_manager import data_manager

            # Get aggregated data
            config_name = self.aggregation_context or "player_style_profile"
            self.data = data_manager.get_aggregated_data(
                config_name=config_name,
                group_by=["player_id", "player_name", "player_position"],
                filters=self.filters,
            )

            # Apply position family
            self.data["player_position_family"] = (
                self.data["player_position"].map(POSITION_FAMILY_MAP).fillna("SUB")
            )

            if self.data.empty:
                logger.warning(
                    "⚠️ No data returned from aggregation context '%s'", config_name
                )
                return

            logger.debug(f"Raw data shape: {self.data.shape}")
            logger.debug(f"Columns: {list(self.data.columns)}")

            # Compute style ratios from raw counts
            self.data = compute_style_ratios(self.data)

            # Metrics needed are now the computed ratios
            metrics_needed = list(
                {m for axis in AXES_DEFINITION.values() for m in axis.keys()}
            )
            logger.debug(f"Metrics needed: {metrics_needed}")

            # Check which metrics we actually have
            available_metrics = [m for m in metrics_needed if m in self.data.columns]
            logger.debug(f"Available metrics: {available_metrics}")

            if not available_metrics:
                logger.error("❌ None of the required metrics found in data")
                return

            # 1. Compute quantiles
            self.data = compute_quantiles(
                self.data, group_col="player_position_family", metrics=available_metrics
            )
            logger.debug(f"After quantiles - columns: {list(self.data.columns)}")

            # 2. Compute axis scores
            self.data = compute_axes_scores(self.data, AXES_DEFINITION)
            logger.debug(f"After axes scores - columns: {list(self.data.columns)}")

            # 3. Compute role distributions with improved logic
            self.data["role_distribution"] = self.data.apply(
                lambda row: compute_role_distribution(
                    row, ROLE_PROFILES, self.amplification_power
                ),
                axis=1,
            )
            logger.debug(f"Role distribution computed for {len(self.data)} players")

            # 4. Create role columns
            role_counts = {}
            for idx, row in self.data.iterrows():
                if isinstance(row["role_distribution"], dict):
                    for role, pct in row["role_distribution"].items():
                        self.data.at[idx, "role_" + role] = pct  # type: ignore
                        role_counts[role] = role_counts.get(role, 0) + 1

            logger.debug(f"Roles created: {role_counts}")

            # 5. Calculate strengths
            self.data["strengths"] = self.data.apply(get_top_strengths, axis=1)
            logger.debug(f"Strengths calculated for {len(self.data)} players")

            # 6. DO NOT extract player data here - wait until we know which player
            # Just log that data is ready
            logger.info(
                f"✅ [PlayerStyleProfileViz] Data prepared with {len(self.data)} players"
            )

        except Exception as e:
            logger.exception("❌ [PlayerStyleProfileViz] Error preparing data: %s", e)
            self.data = pd.DataFrame()
            self.player_data = None

    def _extract_player_data(
        self,
        row: Optional[pd.Series] = None,
        player_id: Optional[str] = None,
        player_label: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract player data for external widget use.

        Args:
            row: Direct row data (optional)
            player_id: Player ID to search (optional)
            player_label: Player name/label to search (optional)
        """
        # If no row provided, try to find player by ID or label
        if row is None and self.data is not None:
            if player_id is not None and "player_id" in self.data.columns:
                # Search by ID first
                player_row = self.data[self.data["player_id"] == player_id]
                if not player_row.empty:
                    row = player_row.iloc[0]
                    logger.info(
                        f"[PlayerStyleProfileViz] Found player by ID: {player_id}"
                    )
                elif player_label is not None:
                    # If ID not found, try by label
                    row = self._find_player_by_name(player_label, player_id)
            elif player_label is not None:
                # Search by label only
                row = self._find_player_by_name(player_label, player_id)

        # Fallback to first player if still no row
        if row is None and self.data is not None and not self.data.empty:
            row = self.data.iloc[0]
            logger.info(
                f"[PlayerStyleProfileViz] Using first player as fallback for {player_label or player_id}"
            )

        if row is None:
            return {
                "player_name": "Select a player",
                "roles": {},
                "strengths": [],
                "dominant_role": ("", 0),
            }

        player_data = {
            "player_name": row.get("player_name", "Player"),
            "roles": {},
            "strengths": [],
            "dominant_role": ("", 0),
        }

        try:
            # Extract roles from computed columns
            roles = {}
            if self.data is not None:
                for col in self.data.columns:
                    if col.startswith("role_") and not pd.isna(row[col]):
                        try:
                            role_name = col.replace("role_", "")
                            role_value = float(row[col])
                            if role_value > 0:  # Only include roles with > 0%
                                roles[role_name] = role_value
                        except (ValueError, TypeError) as e:
                            logger.debug(f"Could not parse role {col} for figure: {e}")
                            continue

            player_data["roles"] = roles

            # Extract strengths
            if "strengths" in row and isinstance(row["strengths"], list):
                player_data["strengths"] = row["strengths"]
            else:
                # Fallback: compute strengths directly
                strengths = get_top_strengths(row)
                player_data["strengths"] = strengths

            # Find dominant role
            if roles:
                dominant_role = max(roles.items(), key=lambda x: x[1])
                player_data["dominant_role"] = dominant_role

            logger.info(
                f"[PlayerStyleProfileViz] Extracted data for {player_data['player_name']}: {len(roles)} roles, {len(player_data['strengths'])} strengths"
            )

        except Exception as e:
            logger.error(f"Error extracting player data: {e}")

        return player_data

    def get_player_data(
        self, player_id: Optional[str] = None, player_label: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get player data for external widget.

        Args:
            player_id: Player ID to search
            player_label: Player name/label to search
        """
        return self._extract_player_data(player_id=player_id, player_label=player_label)

    def create_figure(
        self,
        player_id: Optional[str] = None,
        player_label: Optional[str] = None,
        show_contributions=False,
    ) -> go.Figure:
        """Create clean half-circle pie chart for specific player."""
        if self.data is None or self.data.empty:
            logger.warning("No data for figure")
            return self._create_empty_figure("No player data")

        # Find the right player row
        row = None

        # First try by ID
        if player_id is not None and "player_id" in self.data.columns:
            player_row = self.data[self.data["player_id"] == player_id]
            if not player_row.empty:
                row = player_row.iloc[0]
                logger.info(
                    f"[PlayerStyleProfileViz] Creating figure for player ID: {player_id}"
                )

        # If not found by ID, try by label
        if row is None and player_label is not None:
            row = self._find_player_by_name(player_label, player_id)
            if row is not None:
                logger.info(
                    f"[PlayerStyleProfileViz] Creating figure for player label: {player_label}"
                )

        # Fallback to first player
        if row is None and not self.data.empty:
            row = self.data.iloc[0]
            logger.info("[PlayerStyleProfileViz] Using first player for figure")

        if row is None:
            return self._create_empty_figure("No player selected")

        # Extract player axes for hover information
        player_axes = {}
        axis_cols = [col for col in row.index if col.startswith("axis_")]
        for col in axis_cols:
            axis_name = col.replace("axis_", "")
            player_axes[axis_name] = row[col]

        # Extract roles for the pie chart
        roles = {}
        for col in self.data.columns:
            if col.startswith("role_") and not pd.isna(row[col]):
                try:
                    role_name = col.replace("role_", "")
                    role_value = float(row[col])
                    if role_value > 0:  # Only include roles with > 0%
                        roles[role_name] = role_value
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not parse role {col} for figure: {e}")
                    continue

        if not roles:
            logger.warning("No role data for figure")
            return self._create_empty_figure("No role data available")

        # Sort and prepare data
        sorted_roles = sorted(roles.items(), key=lambda x: x[1], reverse=True)
        labels = [role for role, _ in sorted_roles]
        values = [float(value) for _, value in sorted_roles]

        # Get role profile for hover info
        position = row.get("player_position", "SUB")
        role_profile = ROLE_PROFILES.get(position, {})

        logger.debug(f"Figure data - Labels: {labels}, Values: {values}")

        # Calculate colors
        max_value = values[0] if values else 0
        colors = []
        hover_texts = []  # Store custom hover text for each slice

        for i, (role, value) in enumerate(sorted_roles):
            colors.append(get_color_from_gradient(value, max_value))
            # Build hover text with contributions
            hover_lines = [f"<b>{role}</b>", f"<b>{value:.1f}%</b>"]

            if show_contributions:
                # Calculate contributions for this role
                contributions = []
                if role in role_profile:
                    contributions = get_role_contributions(
                        role, player_axes, role_profile[role]
                    )

                if contributions:
                    hover_lines.append("<b>Key Factors:</b>")
                    for axis_name, contribution in contributions:
                        # Determine if factor is positive or negative for this role
                        role_coefficient = role_profile[role].get(axis_name.lower(), 0)
                        sign = (
                            "+"
                            if role_coefficient > 0
                            else "-"
                            if role_coefficient < 0
                            else "~"
                        )
                        hover_lines.append(f"• {axis_name}: {sign}{contribution:.1f}%")

            hover_texts.append("<br>".join(hover_lines))

        # Create clean pie chart
        fig = go.Figure()

        fig.add_trace(
            go.Pie(
                labels=labels,
                values=values,
                hole=0.85,
                marker=dict(
                    colors=colors, line=dict(color="rgba(255,255,255,0.15)", width=1)
                ),
                textinfo="none",
                textposition="outside",
                textfont=dict(size=9, color="white"),
                hoverinfo="text",
                hovertext=hover_texts,
                domain=dict(x=[0.1, 0.9], y=[0.1, 0.9]),
                sort=False,
                direction="clockwise",
                rotation=270,
                pull=[0.10 for i in range(len(labels))],
                showlegend=False,
            )
        )

        # Add only dominant role in center
        if labels and values:
            dominant_color = colors[0]
            fig.add_annotation(
                text=f"<b>{labels[0]}</b>",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=12, color=dominant_color),
                align="center",
            )

        # Clean layout
        fig.update_layout(
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=False,
            autosize=True,
            uniformtext=dict(mode="hide", minsize=8),
        )

        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)

        logger.info(
            "✅ [PlayerStyleProfileViz] Figure created successfully with improved role distribution"
        )
        return fig

    def _create_empty_figure(self, message: str = "Loading...") -> go.Figure:
        """Create empty placeholder."""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=12, color="rgba(255,255,255,0.7)"),
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=0, r=0, t=0, b=0),
        )
        return fig

    def _find_player_by_name(
        self, player_label: str, fallback_id: Optional[str] = None
    ) -> Optional[pd.Series]:
        """
        Try to find player by name (label) if ID lookup fails.

        Args:
            player_label: Player display name
            fallback_id: Original player ID to fall back to

        Returns:
            Player data row or None
        """
        if self.data is None or self.data.empty:
            return None

        try:
            # Search for player by name in the dataset
            # Check exact matches first
            for idx, row in self.data.iterrows():
                player_name = row.get("player_name", "")
                if player_label == player_name:
                    logger.info(
                        f"[PlayerStyleProfileViz] Found player by exact name: {player_label}"
                    )
                    return row

            # Then check partial matches
            for idx, row in self.data.iterrows():
                player_name = row.get("player_name", "")
                if player_label in player_name or player_name in player_label:
                    logger.info(
                        f"[PlayerStyleProfileViz] Found player by partial name: {player_label} -> {player_name}"
                    )
                    return row

            # If not found, return row for fallback ID
            if fallback_id is not None and "player_id" in self.data.columns:
                player_row = self.data[self.data["player_id"] == fallback_id]
                if not player_row.empty:
                    logger.info(
                        f"[PlayerStyleProfileViz] Using fallback ID: {fallback_id}"
                    )
                    return player_row.iloc[0]

        except Exception as e:
            logger.warning(
                f"[PlayerStyleProfileViz] Error searching player by name: {e}"
            )

        # If everything fails, return first player
        if not self.data.empty:
            logger.info(f"[PlayerStyleProfileViz] Using first player as fallback")
            return self.data.iloc[0]

        return None
