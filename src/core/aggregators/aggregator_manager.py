"""
Aggregator Manager for handling multiple aggregation configurations.
"""
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class AggregatorManager:
    """
    Manages aggregation configurations and executes aggregations efficiently.

    This class loads context and metric configurations from JSON files,
    and provides methods to execute aggregations, potentially in parallel.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._initialized = True
        self.contexts: Dict[str, Dict[str, str]] = {}
        self.metrics: Dict[str, Dict[str, str]] = {}
        self._executor = ThreadPoolExecutor(max_workers=4)  # Configurable

        # Load configurations
        self._load_configurations()

        logger.info(
            f"✅ AggregatorManager initialized with {len(self.contexts)} contexts"
        )

    def _load_configurations(self):
        """Load context and metric configurations from JSON files."""
        try:
            # Load contexts
            contexts_path = Path(__file__).parent / "contexts.json"
            with open(contexts_path, "r", encoding="utf-8") as f:
                self.contexts = json.load(f)

            # Load metrics
            metrics_path = Path(__file__).parent / "metrics.json"
            with open(metrics_path, "r", encoding="utf-8") as f:
                self.metrics = json.load(f)

            logger.info(
                f"📁 Loaded {len(self.contexts)} context groups and {len(self.metrics)} metric groups"
            )

        except Exception as e:
            logger.error(f"❌ Failed to load aggregator configurations: {e}")
            self.contexts = {}
            self.metrics = {}

    def get_contexts_for(self, config_name: str) -> Dict[str, str]:
        """
        Get contexts for a specific configuration.

        Args:
            config_name: Name of the configuration (e.g., 'off_ball_runs')

        Returns:
            Dict[str, str]: Context name -> condition string
        """
        return self.contexts.get(config_name, {})

    def get_metrics_for(self, config_name: str) -> Dict[str, str]:
        """
        Get metrics for a specific configuration.

        Args:
            config_name: Name of the configuration

        Returns:
            Dict[str, str]: Metric name -> function string
        """
        return self.metrics.get(config_name, {})

    def execute_aggregation(
        self,
        df: pd.DataFrame,
        config_name: str,
        group_by: List[str],
        filters: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        logger.debug(f"[AggregatorManager] Executing aggregation: {config_name}")

        import os

        import psutil

        process = psutil.Process(os.getpid())
        logger.info(f"Memory before :{process.memory_info().rss / 1024 / 1024}")

        # Apply filters if provided
        filtered_df = self._apply_filters(df, filters) if filters else df

        # Get contexts and metrics for this configuration
        contexts = self.get_contexts_for(config_name)
        metrics_defs = self.get_metrics_for(config_name)

        if not contexts:
            logger.warning(f"No contexts found for configuration: {config_name}")
            return pd.DataFrame()

        if not metrics_defs:
            logger.warning(f"No metrics found for configuration: {config_name}")
            return pd.DataFrame()

        # Parse metrics into functions
        metrics = self._parse_metrics(metrics_defs)

        # Create an empty dataframe
        all_results = pd.DataFrame()

        for context_name, condition_str in contexts.items():
            try:
                # Apply context condition
                context_condition = self._evaluate_condition(filtered_df, condition_str)
                context_df = filtered_df[context_condition]

                if context_df.empty:
                    logger.debug(
                        f"Context '{context_name}' has no data after filtering"
                    )
                    continue

                # Initialize DataFrame for this context
                context_results = context_df[group_by].drop_duplicates().copy()

                # Apply each metric
                for metric_name, metric_func in metrics.items():
                    try:
                        if metric_name == "count":
                            # Optimize count
                            grouped = context_df.groupby(group_by)
                            counts = grouped.size().reset_index(
                                name=f"{metric_name}_{context_name}"
                            )
                            context_results = pd.merge(
                                context_results, counts, on=group_by, how="left"
                            )
                        else:
                            # Apply other metrics
                            grouped = context_df.groupby(group_by)
                            metric_result = metric_func(grouped).reset_index(
                                name=f"{metric_name}_{context_name}"
                            )
                            context_results = pd.merge(
                                context_results, metric_result, on=group_by, how="left"
                            )

                    except Exception as e:
                        logger.warning(
                            f"Error applying metric '{metric_name}' to context '{context_name}': {e}"
                        )

                # Merge with global results
                if all_results.empty:
                    all_results = context_results
                else:
                    all_results = pd.merge(
                        all_results, context_results, on=group_by, how="outer"
                    )

            except Exception as e:
                logger.error(f"Error processing context '{context_name}': {e}")
                continue

        # Fill NaN with 0
        all_results = all_results.fillna(0)

        # all_results.to_csv("all_results.csv") # FIXME : Remove this

        logger.debug(
            f"[AggregatorManager] Aggregation completed: {config_name} → {len(all_results)} rows"
        )
        logger.debug(f"[AggregatorManager] Columns: {list(all_results.columns)}")

        process = psutil.Process(os.getpid())
        logger.info(f"Memory after :{process.memory_info().rss / 1024 / 1024}")

        return all_results

    def execute_multiple_aggregations(
        self,
        df: pd.DataFrame,
        configs: List[Dict[str, Any]],
        group_by: List[str],
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        Execute multiple aggregations in parallel.

        Args:
            df: DataFrame to aggregate
            configs: List of config dictionaries with 'name' key
            group_by: Columns to group by
            filters: Optional filters to apply

        Returns:
            Dict[str, pd.DataFrame]: Map of config name to results
        """
        results = {}

        # Prepare tasks
        tasks = []
        for config in configs:
            config_name = config.get("name")
            if not config_name:
                continue

            task = (config_name, df, config_name, group_by, filters)
            tasks.append(task)

        # Execute in parallel
        if len(tasks) > 1:
            logger.info(f"Executing {len(tasks)} aggregations in parallel")

            futures = {}
            for config_name, df, config_name, group_by, filters in tasks:
                future = self._executor.submit(
                    self.execute_aggregation, df, config_name, group_by, filters
                )
                futures[future] = config_name

            # Collect results
            for future in futures:
                config_name = futures[future]
                try:
                    results[config_name] = future.result(timeout=30)  # 30s timeout
                except Exception as e:
                    logger.error(
                        f"Failed to execute aggregation for {config_name}: {e}"
                    )
                    results[config_name] = pd.DataFrame()
        else:
            # Single task, execute directly
            for config_name, df, config_name, group_by, filters in tasks:
                results[config_name] = self.execute_aggregation(
                    df, config_name, group_by, filters
                )

        return results

    def _apply_filters(self, df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
        """Apply common filters to dataframe."""
        filtered_df = df.copy()

        # Apply match filter
        if filters.get("match") and filters["match"] != "all":
            filtered_df = filtered_df[filtered_df["match_id"] == str(filters["match"])]

        # Apply team filter
        if filters.get("team") and filters["team"] != "all":
            team_cols = [
                c for c in filtered_df.columns if "team_shortname" in c.lower()
            ]
            if team_cols:
                filtered_df = filtered_df[filtered_df[team_cols[0]] == filters["team"]]

        # Apply time range filter
        if filters.get("time_range"):
            start, end = filters["time_range"]
            if "minute" in filtered_df.columns:
                filtered_df = filtered_df[
                    (filtered_df["minute"] >= start) & (filtered_df["minute"] <= end)
                ]

        logger.debug(f"Applied filters: {len(filtered_df)} rows remaining")
        return filtered_df

    def _evaluate_condition(self, df: pd.DataFrame, condition_str: str) -> pd.Series:
        """Evaluate a condition string on a DataFrame."""
        try:
            # Use pandas eval for simple conditions
            return pd.Series(df.eval(condition_str))
        except Exception:
            # Fallback to manual parsing for complex conditions
            return self._parse_condition_manual(df, condition_str)

    def _parse_condition_manual(
        self, df: pd.DataFrame, condition_str: str
    ) -> pd.Series:
        """Manual parsing of condition strings."""
        # Start with all True
        result = pd.Series(True, index=df.index)

        # Split by 'and'
        conditions = condition_str.split(" and ")

        for cond in conditions:
            cond = cond.strip()

            # Handle column == value
            if "==" in cond:
                parts = cond.split("==")
                if len(parts) == 2:
                    col = parts[0].strip()
                    val = parts[1].strip().strip("'\"")
                    if col in df.columns:
                        result &= df[col] == val

            # Handle column != value
            elif "!=" in cond:
                parts = cond.split("!=")
                if len(parts) == 2:
                    col = parts[0].strip()
                    val = parts[1].strip().strip("'\"")
                    if col in df.columns:
                        result &= df[col] != val

            # Handle column in list
            elif " in " in cond:
                # Simple implementation - can be extended
                pass

        return result

    def _parse_metrics(self, metrics_defs: Dict[str, Any]) -> Dict[str, Callable]:
        """Parse metric definitions into callable functions."""
        metrics = {}

        for metric_name, metric_def in metrics_defs.items():
            # Support both string and dict formats
            if isinstance(metric_def, str):
                func_str = metric_def
            elif isinstance(metric_def, dict) and "function" in metric_def:
                func_str = metric_def["function"]
            else:
                logger.warning(
                    f"Invalid metric definition for '{metric_name}': {metric_def}"
                )
                func_str = "len"  # Default

            metrics[metric_name] = self._create_metric_function(func_str)

        return metrics

    def _create_metric_function(self, func_str: str) -> Callable:
        """Create a metric function from a string definition."""
        if not isinstance(func_str, str):
            logger.error(
                f"Expected string for function, got: {type(func_str)} - {func_str}"
            )
            return self._count_func

        # Function mapping
        if func_str == "len":
            return self._count_func
        elif func_str == "sum":
            return lambda g: g.sum(numeric_only=True)
        elif func_str == "mean":
            return lambda g: g.mean(numeric_only=True)
        elif func_str.endswith(".sum"):
            col = func_str.replace(".sum", "")
            return (
                lambda g: g[col].sum()
                if col in g.obj.columns
                else pd.Series([0] * len(g))
            )
        elif func_str.endswith(".mean"):
            col = func_str.replace(".mean", "")
            return (
                lambda g: g[col].mean()
                if col in g.obj.columns
                else pd.Series([0] * len(g))
            )
        elif func_str.endswith(".count"):
            col = func_str.replace(".count", "")
            return (
                lambda g: g[col].count()
                if col in g.obj.columns
                else pd.Series([0] * len(g))
            )
        else:
            # Default to count
            logger.warning(f"Unknown function string: {func_str}, defaulting to count")
            return self._count_func

    def _count_func(self, grouped):
        """Optimized count function."""
        return grouped.size()

    def shutdown(self):
        """Shutdown the thread pool executor."""
        self._executor.shutdown(wait=True)
        logger.info("AggregatorManager thread pool shutdown")


# Singleton instance
aggregator_manager = AggregatorManager()
