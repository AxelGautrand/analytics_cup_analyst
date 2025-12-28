"""Data manager singleton for loading and caching data.

This module exposes a `DataManager` singleton that loads dynamic event
CSV files, provides accessors for events and matches metadata and
offers helper methods to list available matches and teams.
"""
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd
import requests
from joblib import load
from kloppy import skillcorner

logger = logging.getLogger(__name__)

AggFunc = str | Callable[[pd.Series], object]


class DataManager:
    """Singleton to manage data loading and caching.

    The class lazily loads event and match data and caches an
    aggregator instance built from the events DataFrame.
    """

    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.__initialized = False
                cls._instance._xg_model_path = kwargs.get("xg_model_path")
            return cls._instance

    def __init__(self, xg_model_path: Optional[str] = None):
        """Initialize only once."""
        if self.__initialized:
            return

        if "RENDER" in os.environ:
            self.data_path = Path("/opt/render/project/src/data")
        else:
            self.data_path = Path(__file__).parent.parent.parent / "data"

        logger.info(f"📁 Data path: {self.data_path}")

        logger.info("🔄 [DataManager] Initializing DataManager...")
        self.ensure_data_downloaded()
        self._events_df = None
        self._aggregator_manager = None
        self._matches_df = None  # DataFrame for matches metadata
        self._players_data = None  # Cache for player data
        self._tracking_cache = {}
        self._physical_aggregates = None
        self._players_cache = {}
        self.__initialized = True

        # Store xG model path
        self._xg_model_path = xg_model_path
        self.xg_model = None
        if xg_model_path:
            self.load_xg_model(xg_model_path)

        logger.info("✅ [DataManager] DataManager initialized")

    @property
    def tracking_data(self) -> pd.DataFrame:
        """Get all combined tracking data for open-sources games"""
        # Load all data
        if not self._tracking_cache:
            self.load_all_tracking_data()

        # Combine dataframes
        if self._tracking_cache:
            combined = pd.concat(list(self._tracking_cache.values()), ignore_index=True)
            logger.info(f"📊 [Tracking] Data Combined : {len(combined)} frames total")
            return combined
        else:
            logger.warning("⚠️ [Tracking] No tracking data available")
            return pd.DataFrame()

    @property
    def events_df(self) -> pd.DataFrame:
        """Get events DataFrame (load if not already loaded)."""
        if self._events_df is None:
            logger.info("📂 [DataManager] Loading event data from disk...")
            self._events_df = self._load_dynamic_events_data()
        return self._events_df

    @property
    def matches_df(self) -> pd.DataFrame:
        """Get matches metadata DataFrame (load if not already loaded)."""
        if self._matches_df is None:
            logger.info("📂 [DataManager] Loading matches metadata...")
            self._matches_df = self._load_matches_data()
        return self._matches_df

    @property
    def aggregator_manager(self):
        """Get the aggregator manager instance."""
        if self._aggregator_manager is None:
            logger.info("🧮 [DataManager] Creating AggregatorManager...")
            from src.core.aggregators.aggregator_manager import aggregator_manager

            self._aggregator_manager = aggregator_manager

        return self._aggregator_manager

    def ensure_data_downloaded(self):
        """
        Ensure that the local `data/` directory contains the dataset.
        First tries to use git, falls back to HTTP download if git is not available.
        """
        repo_url = "https://github.com/SkillCorner/opendata.git"
        temp_repo_dir = "_tmp_opendata"
        local_data_dir = self.data_path

        # Check if the local data directory exists and is non-empty
        if not os.path.exists(local_data_dir) or len(os.listdir(local_data_dir)) == 0:
            logger.info("📦 Local data folder is empty. Downloading dataset...")

            # Try multiple methods in order
            if self._try_git_download(repo_url, temp_repo_dir, local_data_dir):
                return

            logger.warning("⚠️ Git not available, trying Google Drive download...")
            if self._download_from_google_drive(local_data_dir):
                return

            # If Google Drive failed, try HTTP download as last resort
            logger.warning("⚠️ Google Drive download failed, falling back to HTTP")
            self._download_via_http(local_data_dir)
        else:
            logger.info(
                "✔️ Local data folder already contains files. No download required."
            )

    def _download_from_google_drive(self, local_data_dir):
        """
        Download dataset from Google Drive using gdown or direct requests.
        Supports both direct file links and folder links.
        """
        try:
            # Create data directory if it doesn't exist
            os.makedirs(local_data_dir, exist_ok=True)

            # Method 1: Using gdown (recommended for folders)
            logger.info("🔄 Downloading from Google Drive using gdown...")

            # If it's a folder link, we need to download individual files
            folder_id = "1MqF_g6F47ytNY_FxtxYehxPs8tpYfrxY"

            # Try to download as folder using gdown
            try:
                import gdown

                # Download the entire folder
                output = os.path.join(local_data_dir, "dataset.zip")
                gdown.download_folder(
                    id=folder_id, output=local_data_dir, quiet=False, use_cookies=False
                )

                # Check if download was successful
                if len(os.listdir(local_data_dir)) > 0:
                    logger.info("✅ Successfully downloaded from Google Drive")
                    return True

            except ImportError:
                logger.info("⚠️ gdown not installed. Installing...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown"])
                import gdown

                return self._download_from_google_drive(local_data_dir)

            except Exception as e:
                logger.info(f"⚠️ gdown failed: {e}. Trying alternative method...")

            # Method 2: Using direct download (if files are publicly accessible)
            return self._download_google_drive_direct(local_data_dir)

        except Exception as e:
            logger.error(f"❌ Google Drive download failed: {e}")
            return False

    def _download_google_drive_direct(self, local_data_dir):
        """
        Alternative method to download from Google Drive using direct links.
        This works for publicly shared files.
        """
        try:
            # List of files to download (you'll need to get the actual file IDs)
            # You can get these by sharing each file individually and getting the shareable link
            drive_files = {
                "matches.csv": "GOOGLE_DRIVE_FILE_ID_1",
                "events.csv": "GOOGLE_DRIVE_FILE_ID_2",
                "players.csv": "GOOGLE_DRIVE_FILE_ID_3",
                # Add more files as needed
            }

            base_url = "https://drive.google.com/uc?export=download&id="

            for filename, file_id in drive_files.items():
                file_url = f"{base_url}{file_id}"
                file_path = os.path.join(local_data_dir, filename)

                logger.info(f"📥 Downloading {filename}...")

                # Use requests with session to handle large files
                session = requests.Session()

                # First request to get the confirmation token
                response = session.get(file_url, stream=True)
                token = None

                # Check for confirmation token
                for key, value in response.cookies.items():
                    if key.startswith("download_warning"):
                        token = value
                        break

                if token:
                    # Second request with confirmation token
                    params = {"id": file_id, "confirm": token}
                    response = session.get(file_url, params=params, stream=True)
                else:
                    # If no token, use original response
                    response.raise_for_status()

                # Get file size for progress bar
                total_size = int(response.headers.get("content-length", 0))

                # Download with progress bar
                with open(file_path, "wb") as f:
                    for data in response.iter_content(chunk_size=8192):
                        f.write(data)

                logger.info(f"✅ Downloaded {filename}")

            return True

        except Exception as e:
            logger.error(f"❌ Direct Google Drive download failed: {e}")
            return False

    def _download_google_drive_via_cli(self, local_data_dir):
        """
        Alternative method using gdown CLI command.
        Useful if you prefer command-line approach.
        """
        try:
            folder_id = "1MqF_g6F47ytNY_FxtxYehxPs8tpYfrxY"

            # Install gdown if not available
            try:
                import gdown
            except ImportError:
                logger.info("Installing gdown...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown"])

            # Download using gdown CLI
            logger.info("🔄 Downloading from Google Drive using CLI...")

            # Command to download folder
            cmd = [
                "gdown",
                f"https://drive.google.com/drive/folders/{folder_id}",
                "-O",
                local_data_dir,
                "--folder",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("✅ Successfully downloaded from Google Drive")
                return True
            else:
                logger.info(f"❌ CLI download failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"❌ Google Drive CLI download failed: {e}")
            return False

    def _extract_zip_file(self, zip_path, extract_to):
        """
        Helper method to extract zip files if needed.
        """
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_to)
            logger.info(f"✅ Extracted {zip_path} to {extract_to}")
            # Remove zip file after extraction
            os.remove(zip_path)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to extract {zip_path}: {e}")
            return False

    def _try_git_download(
        self, repo_url: str, temp_repo_dir: str, local_data_dir: str | Path
    ) -> bool:
        """
        Try to download data using git.
        Returns True if successful, False otherwise.
        """
        try:
            # Check if git is available
            git_path = shutil.which("git")
            if git_path is None:
                logger.warning("❌ Git command not found in PATH")
                return False

            # Check if git-lfs is available
            git_lfs_path = shutil.which("git-lfs")

            logger.info("🔄 Attempting to download data via git...")

            # Full clone, not shallow, because LFS does not work with --depth 1
            subprocess.run(
                [git_path, "clone", repo_url, temp_repo_dir],
                check=True,
                capture_output=True,
                text=True,
            )

            # If git-lfs is available, try to pull LFS files
            if git_lfs_path and os.path.exists(temp_repo_dir):
                try:
                    subprocess.run(
                        [git_lfs_path, "install"],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    subprocess.run(
                        [git_lfs_path, "pull"],
                        cwd=temp_repo_dir,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                except subprocess.CalledProcessError as e:
                    logger.warning(f"⚠️ Git LFS pull failed: {e.stderr}")
                    # Continue without LFS files

            # Path to the 'data/' directory inside the cloned repository
            cloned_data_dir = os.path.join(temp_repo_dir, "data")

            if os.path.exists(cloned_data_dir):
                # Create local directory if it doesn't exist
                os.makedirs(local_data_dir, exist_ok=True)

                # Copy everything from the cloned 'data/' folder into the local one
                shutil.copytree(cloned_data_dir, local_data_dir, dirs_exist_ok=True)
                logger.info("✅ Dataset successfully downloaded via git.")

                # Clean up the temporary clone
                shutil.rmtree(temp_repo_dir)
                return True
            else:
                logger.error("❌ 'data/' directory not found in cloned repository")
                if os.path.exists(temp_repo_dir):
                    shutil.rmtree(temp_repo_dir)
                return False

        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            logger.error(f"❌ Git download failed: {e}")
            # Clean up temp directory if it exists
            if os.path.exists(temp_repo_dir):
                shutil.rmtree(temp_repo_dir)
            return False

    def _download_via_http(self, local_data_dir: str | Path):
        """
        Download data via HTTP/ZIP as fallback when git is not available.
        """
        try:
            logger.info("🔄 Downloading data via HTTP...")

            # URL for the GitHub repository as a ZIP file
            zip_url = (
                "https://github.com/SkillCorner/opendata/archive/refs/heads/main.zip"
            )

            # Create a temporary directory for the zip file
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = os.path.join(temp_dir, "opendata.zip")

                # Download the zip file
                logger.info(f"📥 Downloading from {zip_url}")
                response = requests.get(zip_url, stream=True, timeout=60)
                response.raise_for_status()

                # Save the zip file
                with open(zip_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                logger.info("📦 Extracting ZIP file...")

                # Extract the zip file
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    # Get the root folder name inside the zip
                    zip_info = zip_ref.infolist()
                    if zip_info:
                        # First entry gives us the root folder name
                        root_folder = zip_info[0].filename.split("/")[0]
                    else:
                        raise

                    # Extract all files
                    zip_ref.extractall(temp_dir)

                # Path to the extracted data directory
                extracted_data_dir = os.path.join(temp_dir, root_folder, "data")

                if os.path.exists(extracted_data_dir):
                    # Create local directory
                    os.makedirs(local_data_dir, exist_ok=True)

                    # Copy data files
                    logger.info(
                        f"📁 Copying data from {extracted_data_dir} to {local_data_dir}"
                    )

                    for item in os.listdir(extracted_data_dir):
                        src = os.path.join(extracted_data_dir, item)
                        dst = os.path.join(local_data_dir, item)

                        if os.path.isdir(src):
                            shutil.copytree(src, dst, dirs_exist_ok=True)
                        else:
                            shutil.copy2(src, dst)

                    logger.info("✅ Dataset successfully downloaded via HTTP.")
                else:
                    logger.error(
                        f"❌ 'data/' directory not found in extracted ZIP at {extracted_data_dir}"
                    )

                    # Try to find the data directory
                    for root, dirs, files in os.walk(
                        os.path.join(temp_dir, root_folder)
                    ):
                        if "data" in dirs:
                            extracted_data_dir = os.path.join(root, "data")
                            logger.info(
                                f"📁 Found data directory at: {extracted_data_dir}"
                            )
                            break

                    if os.path.exists(extracted_data_dir):
                        os.makedirs(local_data_dir, exist_ok=True)
                        shutil.copytree(
                            extracted_data_dir, local_data_dir, dirs_exist_ok=True
                        )
                        logger.info(
                            "✅ Dataset downloaded (found alternative data path)."
                        )
                    else:
                        logger.error(
                            "❌ Could not find data directory in downloaded archive"
                        )
                        raise FileNotFoundError(
                            "Data directory not found in downloaded archive"
                        )

        except requests.RequestException as e:
            logger.error(f"❌ HTTP download failed: {e}")
            # Create an empty data directory to avoid repeated attempts
            os.makedirs(local_data_dir, exist_ok=True)
            logger.warning(
                "⚠️ Created empty data directory. Some features may not work."
            )

        except (zipfile.BadZipFile, OSError) as e:
            logger.error(f"❌ ZIP extraction failed: {e}")
            os.makedirs(local_data_dir, exist_ok=True)

        except Exception as e:
            logger.error(f"❌ Unexpected error during HTTP download: {e}")
            os.makedirs(local_data_dir, exist_ok=True)

    def load_xg_model(self, model_path: str):
        """Load xG model from file."""
        try:
            self.xg_model = load(model_path)
            logger.info(f"✅ [DataManager] xG model loaded from {model_path}")
        except Exception as e:
            logger.error(f"❌ [DataManager] Failed to load xG model: {e}")
            self.xg_model = None

    def set_xg_model(self, model):
        """Set xG model directly."""
        self.xg_model = model
        logger.info("✅ [DataManager] xG model set")

    def load_player_data(self) -> Dict[str, Any]:
        """
        Load player data from all match JSON files.

        Returns:
            Dict with player_id as key and player info as value
        """
        if self._players_data is not None:
            return self._players_data

        logger.info("👤 [DataManager] Loading player data from match files...")

        players_data = {}
        data_dir = Path("data/matches")

        for match_dir in sorted(data_dir.iterdir()):
            if match_dir.is_dir():
                json_file = match_dir / f"{match_dir.name}_match.json"
                if json_file.exists():
                    try:
                        with open(json_file, "r", encoding="utf-8") as f:
                            match_data = json.load(f)

                            # Build team_id -> team_name mapping for this match
                            team_id_to_name = {}

                            if "home_team" in match_data:
                                team_id_to_name[
                                    str(match_data["home_team"]["id"])
                                ] = match_data["home_team"]["name"]

                            if "away_team" in match_data:
                                team_id_to_name[
                                    str(match_data["away_team"]["id"])
                                ] = match_data["away_team"]["name"]

                        # Extract players from this match
                        if "players" in match_data:
                            for player in match_data["players"]:
                                player_id = str(player.get("id"))
                                if player_id not in players_data:
                                    # Store comprehensive player info
                                    players_data[player_id] = {
                                        "player_id": player_id,
                                        "first_name": player.get("first_name", ""),
                                        "last_name": player.get("last_name", ""),
                                        "short_name": player.get("short_name", ""),
                                        "full_name": f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
                                        "birthday": player.get("birthday"),
                                        "gender": player.get("gender", "male"),
                                        "teams": set(),  # Will track all teams player played for
                                        "positions": set(),  # All positions played
                                        "matches": set(),  # Match IDs where player appeared
                                        "trackable_object": player.get(
                                            "trackable_object"
                                        ),
                                        "player_role": player.get("player_role", {}),
                                        "number": player.get("number"),
                                        "playing_time_total": None,
                                        "last_seen_match": match_dir.name,
                                        "last_seen_team": None,
                                    }

                                # Update existing player with additional info
                                existing = players_data[player_id]
                                existing["matches"].add(match_dir.name)

                                # Add team info
                                team_id = str(player.get("team_id"))
                                if team_id:
                                    team_name = team_id_to_name.get(team_id, team_id)
                                    existing["teams"].add(team_name)

                                # Add position info
                                if "player_role" in player:
                                    position_name = player["player_role"].get(
                                        "name", ""
                                    )
                                    if position_name:
                                        existing["positions"].add(position_name)

                                # Update playing time if available
                                if "playing_time" in player and player["playing_time"]:
                                    playing_time = player["playing_time"].get(
                                        "total", {}
                                    )
                                    if playing_time:
                                        existing[
                                            "playing_time_total"
                                        ] = playing_time.get("minutes_played", 0)

                                # Update last seen team
                                existing["last_seen_team"] = team_id

                        logger.debug(
                            f"[DataManager] Loaded players from {match_dir.name}"
                        )

                    except Exception as e:
                        logger.warning(f"[DataManager] Error reading {json_file}: {e}")

        # Convert sets to lists for JSON serialization
        for player_id, player_info in players_data.items():
            player_info["teams"] = list(player_info["teams"])
            player_info["positions"] = list(player_info["positions"])
            player_info["matches"] = list(player_info["matches"])

            # Calculate age from birthday
            if player_info["birthday"]:
                try:
                    from datetime import datetime

                    birth_date = datetime.strptime(player_info["birthday"], "%Y-%m-%d")
                    today = datetime.now()
                    age = (
                        today.year
                        - birth_date.year
                        - (
                            (today.month, today.day)
                            < (birth_date.month, birth_date.day)
                        )
                    )
                    player_info["age"] = age
                except (ValueError, TypeError):
                    player_info["age"] = None
            else:
                player_info["age"] = None

        self._players_data = players_data
        logger.info(f"✅ [DataManager] Loaded {len(players_data)} unique players")

        return players_data

    def load_physical_aggregates(self) -> pd.DataFrame:
        """
        Load physical aggregated data from CSV files.

        Returns:
            pd.DataFrame: Physical aggregates (cached)
        """
        # FIXME : Ensure we have a single row for each player
        if self._physical_aggregates is not None:
            return self._physical_aggregates

        logger.info("🏃 [DataManager] Loading physical aggregated data...")

        data_dir = Path("data/aggregates")
        all_dfs = []

        if not data_dir.exists():
            logger.warning(
                "⚠️ [DataManager] Physical data directory not found: %s", data_dir
            )
            self._physical_aggregates = pd.DataFrame()
            return self._physical_aggregates

        for csv_file in sorted(data_dir.glob("*.csv")):
            try:
                df = pd.read_csv(csv_file, low_memory=False)

                df["_source_file"] = csv_file.name
                all_dfs.append(df)

                logger.debug(
                    "[DataManager] ✓ Loaded physical data: %s (%d rows)",
                    csv_file.name,
                    len(df),
                )

            except Exception as e:
                logger.warning(
                    "[DataManager] ✗ Error reading physical data %s: %s",
                    csv_file,
                    e,
                )

        if all_dfs:
            self._physical_aggregates = pd.concat(all_dfs, ignore_index=True)
            logger.info(
                "✅ [DataManager] Loaded physical aggregates: %d rows",
                len(self._physical_aggregates),
            )
        else:
            self._physical_aggregates = pd.DataFrame()
            logger.warning("⚠️ [DataManager] No physical aggregate data loaded")

        return self._physical_aggregates

    @property
    def physical_aggregates(self) -> pd.DataFrame:
        """Get physical aggregated data (load if needed)."""
        if self._physical_aggregates is None:
            self.load_physical_aggregates()
        return self._physical_aggregates  # type: ignore

    def _build_physical_aggregation_map(self, df: pd.DataFrame) -> dict[str, AggFunc]:
        """
        Build an aggregation map for physical stats based on column names and content.
        """

        agg: dict[str, AggFunc] = {}

        # 1. Identification columns - first occurrence
        id_cols = {
            "player_id",
            "player_name",
            "player_short_name",
            "player_birthdate",
            "team_id",
            "team_name",
            "season_id",
            "season_name",
            "competition_id",
            "competition_name",
            "birth_date",
        }

        # 2. Position/role columns - unique list
        position_cols = {"position", "position_name", "role", "position_group"}

        # 3. Minutes/playing time columns - SUM (cumulative)
        time_match_cols = {"minutes_", "_minutes", "count_match", "count_match_failed"}

        # 4. Distance/volume columns - SUM (cumulative)
        distance_volume_patterns = {
            "_distance_",
            "_count_",
            "total_distance",
            "running_distance",
            "hsr_distance",
            "sprint_distance",
            "hi_distance",
            "medaccel",
            "highaccel",
            "meddecel",
            "highdecel",
            "explaccel",
        }

        # 5. Ratio/intensity columns - WEIGHTED AVERAGE by minutes
        ratio_intensity_patterns = {
            "_metersperminute_",
            "_perminute",
            "per_90",
            "avg",
            "mean",
            "rate",
            "_rate",
        }

        # 6. Performance metrics - specific handling
        performance_metrics = {
            # Peak/benchmark metrics - take MAX (best performance)
            "psv99": "max",
            "psv99_top5": "max",
            # Time-based performance metrics - take MIN (fastest time)
            "timetohsr_top3": "min",
            "timetosprint_top3": "min",
            # Maximum speed/acceleration metrics
            "max_speed": "max",
            "top_speed": "max",
            "speed_max": "max",
            "acceleration_max": "max",
            "deceleration_max": "max",
            # Top/Best metrics
            "_top": "max",
            "top_": "max",
            "_max": "max",
            "max_": "max",
            "_best": "max",
            "best_": "max",
            "_peak": "max",
            "peak_": "max",
        }

        # Process each column
        for col in df.columns:
            col_lower = col.lower()

            # 1. Identification columns
            if col in id_cols or col_lower in {c.lower() for c in id_cols}:
                agg[col] = "first"

            # 2. Position/role columns
            elif col in position_cols or any(
                pattern in col_lower for pattern in ["position", "role", "pos_"]
            ):
                agg[col] = lambda x: list(x.dropna().unique())

            # 3. Minutes/playing time - SUM
            elif (
                any(pattern in col_lower for pattern in time_match_cols)
                or col_lower.startswith("minutes")
                or col_lower.endswith("_minutes")
            ):
                agg[col] = "sum"

            # 4. Performance metrics - specific handling
            elif col in performance_metrics:
                agg[col] = performance_metrics[col]

            # Check for performance patterns in column names
            elif any(pattern in col_lower for pattern in ["timetohsr", "timetosprint"]):
                if "top3" in col_lower:
                    agg[col] = "min"  # Fastest time is best
                else:
                    agg[col] = "mean"

            elif "psv99" in col_lower:
                agg[col] = "max"  # Highest score is best

            # 5. Distance/volume metrics - SUM
            elif (
                any(pattern in col_lower for pattern in distance_volume_patterns)
                or "_distance" in col_lower
                or "_count" in col_lower
            ):
                agg[col] = "sum"

            # 6. Ratio/intensity metrics - WEIGHTED AVERAGE
            elif (
                any(pattern in col_lower for pattern in ratio_intensity_patterns)
                or "_metersperminute" in col_lower
                or "_perminute" in col_lower
            ):
                # Special handling for meters per minute - weighted average by minutes
                if "_metersperminute" in col_lower:
                    # Create a custom aggregation function for weighted average
                    def weighted_avg(series):
                        # Get the corresponding minutes column
                        if "_all" in col_lower:
                            minutes_col = "minutes_full_all"
                        elif "_tip" in col_lower:
                            minutes_col = "minutes_full_tip"
                        elif "_otip" in col_lower:
                            minutes_col = "minutes_full_otip"
                        else:
                            minutes_col = "minutes_full_all"

                        if minutes_col in df.columns:
                            weights = df.loc[series.index, minutes_col]
                            # Avoid division by zero
                            if weights.sum() > 0:  # type: ignore
                                return np.average(series, weights=weights)
                        return series.mean()

                    agg[col] = weighted_avg
                else:
                    agg[col] = "mean"

            # 7. Default for numeric columns - SUM
            elif df[col].dtype.kind in {"i", "f", "u"}:
                agg[col] = "sum"

            # 8. Fallback for non-numeric columns
            else:
                agg[col] = "first"

        return agg

    def _weighted_mean(self, values: pd.Series, weights: pd.Series) -> float:
        mask = values.notna() & weights.notna()
        if not mask.any():
            return float("nan")
        return (values[mask] * weights[mask]).sum() / weights[mask].sum()

    def get_player_physical_stats(
        self,
        player_id: str,
        season_id: Optional[str] = None,
        competition_id: Optional[str] = None,
        aggregate: bool = True,
    ) -> pd.DataFrame:
        df = self.physical_aggregates

        if df.empty:
            return df

        out = df[df["player_id"] == str(player_id)]

        if season_id is not None and "season_id" in out.columns:
            out = out[out["season_id"] == str(season_id)]

        if competition_id is not None and "competition_id" in out.columns:
            out = out[out["competition_id"] == str(competition_id)]

        if out.empty or not aggregate:
            return out.reset_index(drop=True)

        # -------------------------------
        # Aggregation
        # -------------------------------
        minutes_col = None
        for c in ["minutes_played", "minutes", "mins"]:
            if c in out.columns:
                minutes_col = c
                break

        agg_map = self._build_physical_aggregation_map(out)

        # Handle weighted per_90 columns
        if minutes_col is not None:
            for col in out.columns:
                if "per_90" in col:
                    agg_map[col] = lambda x, c=col: self._weighted_mean(
                        x, out.loc[x.index, minutes_col]  # type: ignore
                    )

        aggregated = out.groupby("player_id", as_index=False).agg(agg_map)

        return aggregated.reset_index(drop=True)

    def get_player_info(self, player_id: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive information for a specific player.

        Args:
            player_id: Player ID string

        Returns:
            Dict with player information or None if not found
        """
        # Check cache first
        if player_id in self._players_cache:
            return self._players_cache[player_id]

        # Load all player data if not already loaded
        if self._players_data is None:
            self.load_player_data()

        if isinstance(self._players_data, dict) and player_id in self._players_data:
            player_info = self._players_data[player_id].copy()

            # Try to get team names for teams
            team_names = []
            for team_id in player_info.get("teams", []):
                team_name = self._get_team_name_by_id(team_id)
                if team_name:
                    team_names.append(team_name)

            if team_names:
                player_info["team_names"] = team_names

            # Cache the result
            self._players_cache[player_id] = player_info
            return player_info

        return None

    def _get_team_name_by_id(self, team_id: str) -> Optional[str]:
        """
        Get team name by team ID.

        Args:
            team_id: Team ID string

        Returns:
            str: Team name or None if not found
        """
        # Try to find team in events data
        if self.events_df is not None and not self.events_df.empty:
            # Look for team columns
            team_cols = [
                col
                for col in self.events_df.columns
                if "team" in col.lower() and "name" in col.lower()
            ]
            if team_cols:
                for col in team_cols:
                    # Try to find team ID mapping (this is simplified)
                    # In a real implementation, you'd need proper team ID to name mapping
                    pass

        # Try to find in matches data
        if self.matches_df is not None and not self.matches_df.empty:
            # This depends on your matches.json structure
            pass

        return None

    def search_players(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search players by name.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of player information dicts
        """
        if self._players_data is None:
            self.load_player_data()

        query = query.lower().strip()
        results = []

        if self._players_data is not None:
            for _, player_info in self._players_data.items():
                # Search in various name fields
                search_fields = [
                    player_info.get("first_name", "").lower(),
                    player_info.get("last_name", "").lower(),
                    player_info.get("short_name", "").lower(),
                    player_info.get("full_name", "").lower(),
                ]

                if any(query in field for field in search_fields if field):
                    results.append(player_info)
                    if len(results) >= limit:
                        break

        return results

    def get_players_by_team(self, team_id: str) -> List[Dict[str, Any]]:
        """
        Get all players who have played for a specific team.

        Args:
            team_id: Team ID string

        Returns:
            List of player information dicts
        """
        if self._players_data is None:
            self.load_player_data()

        team_players = []
        if self._players_data is not None:
            for _, player_info in self._players_data.items():
                if team_id in player_info.get("teams", []):
                    team_players.append(player_info)

        return team_players

    def get_player_stats(self, player_id: str) -> Dict[str, Any]:
        """
        Get statistical summary for a player.

        Args:
            player_id: Player ID string

        Returns:
            Dict with player statistics
        """
        player_info = self.get_player_info(player_id)
        if not player_info:
            return {}

        stats = {
            "total_matches": len(player_info.get("matches", [])),
            "positions": player_info.get("positions", []),
            "teams_played_for": len(player_info.get("teams", [])),
            "total_playing_time": player_info.get("playing_time_total", 0),
            "age": player_info.get("age"),
            "gender": player_info.get("gender", "male"),
            "player_number": player_info.get("number"),
        }

        # Add position role details if available
        if "player_role" in player_info:
            role = player_info["player_role"]
            stats.update(
                {
                    "position_group": role.get("position_group", ""),
                    "position_name": role.get("name", ""),
                    "position_acronym": role.get("acronym", ""),
                }
            )

        return stats

    def load_tracking_data(
        self, match_id: str, sample_rate: float = 1 / 10
    ) -> Optional[pd.DataFrame]:
        """
        Load tracking data for a specific match.

        Args:
            match_id: Match ID (e.g. "1886347")
            sample_rate: Sampling rate (default: 1/10 = 10 seconds)

        Returns:
            DataFrame containing tracking data, or None in case of error
        """
        # Check cache
        if match_id in self._tracking_cache:
            logger.debug(f"📊 [Tracking] Cached data found for match {match_id}")
            return self._tracking_cache[match_id]

        try:
            logger.info(f"📊 [Tracking] Loading data for match {match_id}...")

            # Load via kloppy
            dataset = skillcorner.load_open_data(
                match_id=int(match_id),
                coordinates="skillcorner",
                sample_rate=sample_rate,
            )

            # Transform and convert to DataFrame
            df = dataset.transform(to_orientation="STATIC_HOME_AWAY").to_df(
                engine="pandas"
            )  # type: ignore

            # Add match ID as a column
            df["match_id"] = match_id

            # Cache the result
            self._tracking_cache[match_id] = df

            logger.info(
                f"✅ [Tracking] Data loaded: {len(df)} frames for match {match_id}"
            )
            return df

        except Exception as e:
            logger.error(f"❌ [Tracking] Error while loading match {match_id}: {e}")
            return None

    def load_all_tracking_data(
        self, sample_rate: float = 1 / 10
    ) -> Dict[str, pd.DataFrame]:
        """
        Load tracking data for all available matches.

        Args:
            sample_rate: Sampling rate

        Returns:
            Dict with match_id as key and DataFrame as value
        """
        # Get available matches
        match_ids = self.get_available_matches()
        logger.info(f"📊 [Tracking] Loading data for {len(match_ids)} matches...")

        all_data = {}
        loaded_count = 0

        for match_id in match_ids[:2]:
            df = self.load_tracking_data(match_id, sample_rate)
            if df is not None:
                all_data[match_id] = df
                loaded_count += 1

        logger.info(
            f"✅ [Tracking] {loaded_count}/{len(match_ids)} matches successfully loaded"
        )
        return all_data

    def _load_dynamic_events_data(self, apply_xg: bool = True) -> pd.DataFrame:
        """Load all dynamic_events.csv files and combine them."""
        logger.info("📊 [DataManager] Loading dynamic_events data...")

        data_dir = Path("data/matches")
        all_dataframes = []

        for match_dir in sorted(
            data_dir.iterdir()
        ):  # FIXME : Memory leak on free render plan
            if match_dir.is_dir():
                csv_file = match_dir / f"{match_dir.name}_dynamic_events.csv"
                if csv_file.exists():
                    try:
                        # Read file with low_memory disabled to reduce dtype warnings
                        df = pd.read_csv(csv_file, low_memory=False)
                        df["match_id"] = match_dir.name

                        # Apply xG model if requested and available
                        if apply_xg and self.xg_model is not None:
                            df = self._add_xg_to_df(df)

                        # Apply advanced features
                        df = self._add_advanced_features(df)

                        all_dataframes.append(df)
                        logger.debug(
                            "[DataManager]  ✓ %s: %d events", match_dir.name, len(df)
                        )
                    except Exception as e:
                        logger.warning(
                            "[DataManager]  ✗ Error reading %s: %s", csv_file, e
                        )
        if all_dataframes:
            combined_df = pd.concat(all_dataframes, ignore_index=True)

            # Post-process combined dataframe with xG if not done per file
            if (
                apply_xg
                and self.xg_model is not None
                and "xG" not in combined_df.columns
            ):
                combined_df = self._add_xg_to_df(combined_df)

                # Apply advanced custom features
                combined_df = self._add_advanced_features(combined_df)

            logger.info(
                "✅ [DataManager] Data loaded: %d total events", len(combined_df)
            )

            # Log available team-like columns for debugging
            team_cols = [c for c in combined_df.columns if "team" in c.lower()]
            logger.debug("🎯 [DataManager] Available team columns: %s", team_cols)

            return combined_df
        else:
            logger.warning("⚠️ [DataManager] No data found: returning empty DataFrame")
            return pd.DataFrame()

    def _add_xg_to_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add xG predictions to DataFrame."""
        try:
            # Keep original dataframe for non-shot events
            df_result = df.copy()

            # Filter shots
            shot_mask = df_result["end_type"] == "shot"
            shots_df = df_result[shot_mask].copy()

            if len(shots_df) == 0:
                logger.debug("[DataManager] No shots found for xG calculation")
                df_result["xG"] = 0.0
                return df_result

            # Prepare features
            features_df = self._prepare_xg_features(shots_df)

            # Predict xG
            if hasattr(self.xg_model, "predict_proba"):
                xg_predictions = self.xg_model.predict_proba(features_df)[:, 1]  # type: ignore
            else:
                xg_predictions = self.xg_model.predict(features_df)  # type: ignore

            # Add predictions to og dataset
            df_result.loc[shot_mask, "xG"] = xg_predictions
            df_result["xG"] = df_result["xG"].astype(float)

            logger.debug(f"[DataManager] xG calculated for {len(shots_df)} shots")
            return df_result

        except Exception as e:
            logger.error(f"[DataManager] Error calculating xG: {e}")
            df["xG"] = 0.0
            return df

    def _prepare_xg_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for xG model inference."""
        # Check required features
        required_cols = ["x_end", "y_end", "is_header"]
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            logger.warning(f"[DataManager] Missing columns for xG: {missing_cols}")
            # Create default columns
            # FIXME : find a better way
            for col in missing_cols:
                if col == "is_header":
                    df[col] = False
                elif col == "x_end":
                    df[col] = df.get("x", 0)
                elif col == "y_end":
                    df[col] = df.get("y", 0)

        # Compute geo features
        GOAL_X, GOAL_Y = 52.5, 0.0

        dx = GOAL_X - df["x_end"]
        dy = np.abs(GOAL_Y - df["y_end"])

        distance = np.sqrt(dx**2 + dy**2)
        angle = np.arctan2(7.32 * dx, dx**2 + dy**2 - (7.32 / 2) ** 2)

        # Create dataframe
        features = pd.DataFrame(
            {
                "distance": distance,
                "angle": angle,
                "headers": df["is_header"].astype(int),
            }
        )

        return features

    def calculate_xg_for_shots(
        self, df: Optional[pd.DataFrame] = None
    ) -> Optional[pd.DataFrame]:
        """Calculate xG for shots in a DataFrame."""
        if self.xg_model is None:
            logger.warning("[DataManager] No xG model loaded")
            return df

        if df is None:
            df = self.events_df.copy()

        return self._add_xg_to_df(df)

    def _normalize_coordinates(
        self,
        x: pd.Series,
        y: pd.Series,
        attacking_side: pd.Series,
    ) -> tuple[pd.Series, pd.Series]:
        """
        Normalize coordinates so that all actions are expressed
        in the same attacking direction.
        """
        flip = attacking_side == "right_to_left"

        x_norm = x.where(~flip, -x)
        y_norm = y.where(~flip, -y)

        return x_norm, y_norm

    def _build_possession_associated_df(self, df: pd.DataFrame) -> pd.DataFrame:
        possessions = df[df["event_type"] == "player_possession"].copy()
        possessions["_poss_index"] = possessions.index

        assoc = df.copy()
        assoc["_assoc_index"] = assoc.index

        merged = possessions.merge(
            assoc,
            left_on=["match_id", "event_id"],
            right_on=["match_id", "associated_player_possession_event_id"],
            suffixes=("_poss", "_assoc"),
            how="inner",
        )

        return merged

    def _add_advanced_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Build once
        merged = self._build_possession_associated_df(df)

        df = self._add_shot_features(df)
        df = self._add_pressing_features(df, merged)
        df = self._add_passing_decision_features(df, merged)
        df = self._add_xpass_features(df, merged)

        return df

    def _add_shot_features(self, df: pd.DataFrame) -> pd.DataFrame:
        shot_mask = (df["event_type"] == "player_possession") & (
            df["end_type"] == "shot"
        )

        # ---- Distance to goal ----
        goal_x = 52.5  # NOTE : attacking_side has no influence here
        goal_y = 0.0

        df.loc[shot_mask, "shot_distance_to_goal"] = np.sqrt(
            (df.loc[shot_mask, "x_end"] - goal_x) ** 2
            + (df.loc[shot_mask, "y_end"] - goal_y) ** 2
        )

        # ---- xG delta ----
        scored = df["lead_to_goal"] == True

        df.loc[shot_mask & scored, "shot_xg_delta"] = (
            1.0 - df.loc[shot_mask & scored, "xG"]
        )

        df.loc[shot_mask & ~scored, "shot_xg_delta"] = -df.loc[
            shot_mask & ~scored, "xG"
        ]

        return df

    def _add_pressing_features(
        self,
        df: pd.DataFrame,
        merged: pd.DataFrame,
    ) -> pd.DataFrame:
        press = merged[merged["event_type_assoc"] == "on_ball_engagement"]

        if press.empty:
            return df

        poss_idx = press["_poss_index"]
        assoc_idx = press["_assoc_index"]

        # --------------------------------------------------
        # Normalize data as attacking_side matters
        # --------------------------------------------------
        poss_x, poss_y = self._normalize_coordinates(
            press["x_start_poss"],
            press["y_start_poss"],
            press["attacking_side_poss"],
        )

        assoc_x, assoc_y = self._normalize_coordinates(
            press["x_start_assoc"],
            press["y_start_assoc"],
            press["attacking_side_assoc"],
        )

        # --------------------
        # Distance defender ↔ player in possession
        # --------------------
        dx = assoc_x - poss_x
        dy = assoc_y - poss_y
        distance = np.sqrt(dx**2 + dy**2)

        # Validity constraints
        MAX_PRESS_DISTANCE = 6
        MAX_FRAME_DIFF = 20

        close_enough = distance <= MAX_PRESS_DISTANCE

        same_time = (
            press["frame_start_assoc"].sub(press["frame_start_poss"]).abs()
            <= MAX_FRAME_DIFF
        )

        valid_press = close_enough & same_time

        # --------------------
        # Distance
        # --------------------
        df.loc[assoc_idx, "defender_distance_to_ball_carrier"] = np.where(
            valid_press,
            distance,
            np.nan,
        )

        # --------------------
        # Ball recovery
        # --------------------
        lost = press["end_type_poss"] == "possession_loss"
        df.loc[assoc_idx, "defender_ball_recovery"] = lost.values

        # xLoss delta
        xloss = press["xloss_player_possession_start_assoc"]

        df.loc[poss_idx, "xloss_delta_under_pressure"] = np.where(
            lost,
            -(1.0 - xloss),
            xloss,
        )

        return df

    def _add_passing_decision_features(
        self,
        df: pd.DataFrame,
        merged: pd.DataFrame,
    ) -> pd.DataFrame:
        options = merged[
            merged["event_type_assoc"].isin(["off_ball_run", "passing_option"])
        ]

        for poss_event_id, group in options.groupby("event_id_poss"):
            if group["targeted_assoc"].sum() == 0:
                continue

            chosen = group.loc[
                group["targeted_assoc"], "passing_option_score_assoc"
            ].iloc[0]
            best = group["passing_option_score_assoc"].max()

            delta = chosen - best

            poss_idx = group.loc[group["targeted_assoc"], "_poss_index"]
            df.loc[poss_idx, "passing_decision_delta"] = delta

        return df

    def _add_xpass_features(
        self,
        df: pd.DataFrame,
        merged: pd.DataFrame,
    ) -> pd.DataFrame:
        options = merged[
            merged["event_type_assoc"].isin(["off_ball_run", "passing_option"])
            & (merged["targeted_assoc"] == True)
        ]

        received = options["received_assoc"] == True
        xpass = options["xpass_completion_assoc"]

        is_cross = options["event_subtype_assoc"] == "cross_receiver"

        poss_idx = options["_poss_index"]

        df.loc[poss_idx, "xpass_delta"] = np.where(
            ~is_cross & received,
            1.0 - xpass,
            np.where(~is_cross & ~received, -xpass, np.nan),
        )

        df.loc[poss_idx, "xcross_delta"] = np.where(
            is_cross & received,
            1.0 - xpass,
            np.where(is_cross & ~received, -xpass, np.nan),
        )

        return df

    def get_aggregated_data(
        self,
        config_name: str,
        group_by: List[str],
        filters: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """
        Get aggregated data for a specific configuration.

        Args:
            config_name: Aggregation configuration name
            group_by: Columns to group by
            filters: Optional filters to apply

        Returns:
            pd.DataFrame: Aggregated data
        """
        logger.info(f"[DataManager] Getting aggregated data for: {config_name}")

        try:
            # Use the aggregator manager
            result = self.aggregator_manager.execute_aggregation(
                df=self.events_df,
                config_name=config_name,
                group_by=group_by,
                filters=filters,
            )

            logger.info(
                f"[DataManager] Aggregation complete: {config_name} → {len(result)} rows"
            )
            return result

        except Exception as e:
            logger.error(
                f"[DataManager] Failed to aggregate data for {config_name}: {e}"
            )
            return pd.DataFrame()

    def _load_matches_data(self) -> pd.DataFrame:
        """Load matches metadata from `matches.json`.

        Returns:
            DataFrame with match metadata (empty DataFrame on error)
        """
        matches_json_path = Path("data/matches.json")

        if not matches_json_path.exists():
            logger.warning(
                "⚠️ [DataManager] matches.json not found: %s", matches_json_path
            )
            return pd.DataFrame()

        try:
            with open(matches_json_path, "r") as f:
                matches_data = json.load(f)

            # Convert to DataFrame
            matches_df = pd.DataFrame(matches_data)
            logger.info("✅ Matches metadata loaded: %d matches", len(matches_df))

            return matches_df

        except Exception as e:
            logger.exception("❌ [DataManager] Error loading matches.json: %s", e)
            return pd.DataFrame()

    def get_available_matches(self) -> List[str]:
        """
        Get list of available match IDs.

        Returns:
            List of match ID strings
        """
        try:
            # First try to get match IDs from matches.json
            if self.matches_df is not None and not self.matches_df.empty:
                if "match_id" in self.matches_df.columns:
                    match_ids = (
                        self.matches_df["match_id"].astype(str).unique().tolist()
                    )
                elif "id" in self.matches_df.columns:
                    match_ids = self.matches_df["id"].astype(str).unique().tolist()
                else:
                    # Fallback: use first column
                    match_ids = self.matches_df.iloc[:, 0].astype(str).unique().tolist()

                logger.debug(
                    "🎯 [DataManager] Match IDs from matches.json: %d matches",
                    len(match_ids),
                )
                return sorted(match_ids)

            # Fallback: extract from events
            if self.events_df is not None and not self.events_df.empty:
                if "match_id" in self.events_df.columns:
                    match_ids = self.events_df["match_id"].astype(str).unique().tolist()
                    logger.debug(
                        "🎯 [DataManager] Match IDs from events: %d matches",
                        len(match_ids),
                    )
                    return sorted(match_ids)

            # Fallback: read directories
            data_dir = Path("data/matches")
            match_dirs = [d.name for d in data_dir.iterdir() if d.is_dir()]
            logger.debug(
                "🎯 [DataManager] Match IDs from directories: %d matches",
                len(match_dirs),
            )
            return sorted(match_dirs)

        except Exception as e:
            logger.exception("❌ [DataManager] Error retrieving matches: %s", e)
            # Return default values for development
            return ["1886347", "1899585", "1925299", "1953632", "1996435"]

    def get_available_teams(self) -> List[str]:
        """
        Get list of available team names.

        Returns:
            List of team name strings
        """
        try:
            if self.events_df is None or self.events_df.empty:
                logger.warning("⚠️ [DataManager] No event data available")
                return ["Team A", "Team B", "Team C"]  # Default values

            # Look for columns containing team names
            team_columns = [
                col
                for col in self.events_df.columns
                if "team" in col.lower() and "name" in col.lower()
            ]

            if not team_columns:
                # Fallback to any column that mentions 'team'
                team_columns = [
                    col for col in self.events_df.columns if "team" in col.lower()
                ]

            if team_columns:
                # Use the first matching team column
                team_col = team_columns[0]
                teams = self.events_df[team_col].dropna().unique().tolist()
                logger.debug(
                    "🎯 [DataManager] Teams found in column '%s': %d teams",
                    team_col,
                    len(teams),
                )
                return sorted([str(t) for t in teams])
            else:
                # Try to extract teams from matches.json
                if self.matches_df is not None and not self.matches_df.empty:
                    teams = []
                    for col in self.matches_df.columns:
                        if "team" in col.lower():
                            unique_teams = self.matches_df[col].dropna().unique()
                            teams.extend([str(t) for t in unique_teams])

                    if teams:
                        unique_teams = sorted(set(teams))
                        logger.debug(
                            "🎯 [DataManager] Teams from matches.json: %d teams",
                            len(unique_teams),
                        )
                        return unique_teams

            # Default values if nothing is found
            logger.warning("⚠️ [DataManager] No team column found; using default teams")
            return ["Adelaide United", "Brisbane Roar", "Melbourne City", "Sydney FC"]

        except Exception as e:
            logger.exception("❌ [DataManager] Error retrieving teams: %s", e)
            return ["Team A", "Team B", "Team C"]  # Default fallback

    def get_match_info(self, match_id: str) -> dict:
        """
        Get information about a specific match.

        Args:
            match_id: Match ID string

        Returns:
            Dictionary with match information
        """
        try:
            if self.matches_df is not None and not self.matches_df.empty:
                # Search across possible ID columns
                for id_col in ["match_id", "id", "matchId", "match"]:
                    if id_col in self.matches_df.columns:
                        match_row = self.matches_df[
                            self.matches_df[id_col].astype(str) == match_id
                        ]
                        if not match_row.empty:
                            return match_row.iloc[0].to_dict()

            # If not found, return a minimal dict
            return {
                "match_id": match_id,
                "home_team": f"Team A ({match_id})",
                "away_team": f"Team B ({match_id})",
                "date": "2024-01-01",
                "competition": "A-League",
            }

        except Exception as e:
            logger.exception(
                "❌ [DataManager] Error retrieving match info for %s: %s", match_id, e
            )
            return {}

    def get_filtered_data(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Get filtered data based on filters.

        Args:
            filters: Dict with keys 'match', 'team', 'time_range'

        Returns:
            Filtered DataFrame
        """
        df = self.events_df.copy()

        filters = filters or {}
        if not filters:
            return df

        # Apply match filter
        if filters.get("match") and filters["match"] != "all":
            df = df[df["match_id"] == str(filters["match"])]
            logger.debug(
                "🔍 [DataManager] Match filter: %s -> %d events",
                filters["match"],
                len(df),
            )

        # Apply team filter
        if filters.get("team") and filters["team"] != "all":
            team_cols = [
                c for c in df.columns if "team" in c.lower() and "name" in c.lower()
            ]
            if team_cols:
                team_col = team_cols[0]
                df = df[df[team_col] == filters["team"]]
                logger.debug(
                    "🔍 [DataManager] Team filter: %s -> %d events",
                    filters["team"],
                    len(df),
                )

        # Apply time range filter
        if filters.get("time_range"):
            start, end = filters["time_range"]
            if "minute" in df.columns:
                df = df[(df["minute"] >= start) & (df["minute"] <= end)]
                logger.debug(
                    "🔍 [DataManager] Time range filter: %s-%s -> %d events",
                    start,
                    end,
                    len(df),
                )

        return df

    def clear_cache(self):
        """Clear cached data (for testing)."""
        logger.info("🧹 [DataManager] Clearing DataManager cache")
        self._tracking_cache.clear()
        self._events_df = None
        self._matches_df = None
        self._aggregator = None
        self.__initialized = False


# Singleton instance - created once
data_manager = DataManager(xg_model_path="models/xg_xgboost_v1.joblib")
