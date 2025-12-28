"""
Utility to load JSON configurations for fast aggregations.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def load_fast_config(config_type: str, name: str) -> Dict[str, Any]:
    """
    Load fast aggregation configuration from JSON.

    Args:
        config_type: 'contexts' or 'metrics'
        name: Configuration name (e.g., 'off_ball_runs_fast')

    Returns:
        Dict[str, Any]: Configuration dictionary
    """
    config_dir = Path(__file__).parent / config_type
    config_path = config_dir / f"{name}.json"

    if not config_path.exists():
        logger.warning(f"Fast config not found: {config_path}")
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading fast config {config_path}: {e}")
        return {}


def convert_json_to_aggregator_params(json_config: Dict[str, Any]) -> tuple:
    """
    Convert JSON configuration to aggregator parameters.

    Returns:
        tuple: (custom_context_groups, custom_metric_groups)
    """
    # TODO : This is a stub - need to adapt based on your aggregator's actual API
    # The aggregator might expect different format
    return json_config, {}
