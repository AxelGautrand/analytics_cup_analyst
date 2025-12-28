"""Web application layout and callbacks for the PySport × Skillcorner demo."""
import os
import sys
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

from src.callbacks import register_all_callbacks
from src.components.widgets.registry import WidgetRegistry
from src.core.data_manager import data_manager
from src.core.logging_config import logger

IS_RENDER = os.getenv("RENDER", "").lower() == "true"

if IS_RENDER:
    DATA_PATH = Path("/opt/render/project/src/data")
else:
    DATA_PATH = Path(__file__).parent.parent / "data"


def initialize_application():
    """Initialize the application"""

    logger.info("🚀 Initialization of application...")

    # If in Render
    if IS_RENDER:
        logger.info("🔄 Environment Render detected")
        # Create parents repo
        DATA_PATH.mkdir(parents=True, exist_ok=True)

    # Add src to path
    src_dir = os.path.dirname(__file__)
    if src_dir not in sys.path:
        sys.path.append(src_dir)

    # Initialize data manager and load data
    logger.info("📥 Initialization of DataManager...")
    try:
        # Will load data if not already loaded
        df = data_manager.events_df
        data_manager.tracking_data
        aggregator = data_manager.aggregator_manager

        logger.info(f"✅ DataManager ready: {len(df)} events")

    except Exception as e:
        logger.error(f"❌ Error DataManager: {e}", exc_info=True)

        df = pd.DataFrame()
        aggregator = None

    logger.info("✅ Application initialized successfully")


# Initialize now
initialize_application()

# Use absolute paths you provided
LOGO_LEFT = "logo/pysport_logo.png"
LOGO_RIGHT = "logo/sk_logo.png"

# GridStack via CDN
external_stylesheets = [
    dbc.themes.BOOTSTRAP,
    "https://cdn.jsdelivr.net/npm/gridstack@5.1.0/dist/gridstack.min.css",
    "assets/css/variables.css",
    "assets/css/base.css",
    "assets/css/layout.css",
    "assets/css/components.css",
    "assets/css/pages.css",
    "assets/css/utilities.css",
]

external_scripts = ["https://cdn.jsdelivr.net/npm/gridstack@5.1.0/dist/gridstack-h5.js"]

app = dash.Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    external_scripts=external_scripts,
    suppress_callback_exceptions=True,
)
server = app.server

# ----------------------
# Header
# ----------------------
header = html.Header(
    [
        html.Div(
            [
                html.Div(
                    [
                        # Using the absolute paths
                        html.Img(
                            src=app.get_asset_url(LOGO_LEFT), className="header-logo"
                        ),
                        html.Img(
                            src=app.get_asset_url(LOGO_RIGHT), className="header-logo"
                        ),
                        html.H1(
                            "PySport × Skillcorner — Analyst Cup Submission",
                            className="header-title",
                        ),
                    ],
                    className="header-left",
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Button(
                                    "🔍",
                                    id="search-btn",
                                    className="icon-btn",
                                    title="Search",
                                ),
                                dcc.Input(
                                    id="global-search",
                                    type="text",
                                    placeholder="Search players, teams, matches...",
                                    className="search-bar",
                                ),
                            ],
                            className="search-wrapper",
                        ),
                        html.Button(
                            "⚙️",
                            id="quick-settings",
                            className="icon-btn",
                            title="Settings",
                        ),
                        html.Button(
                            "🔔",
                            id="notifications",
                            className="icon-btn",
                            title="Notifications",
                        ),
                    ],
                    className="header-right",
                ),
            ],
            className="header-inner",
        )
    ],
    className="header",
)


# ----------------------
# Sidebar
# ----------------------
def nav_button(icon, label, id_str):
    return html.Button(
        [
            html.Span(icon, className="nav-icon"),
            html.Span(label, className="nav-label"),
        ],
        id=id_str,
        className="nav-btn",
        n_clicks=0,
        title=label,
    )


sidebar = html.Nav(
    html.Ul(
        [
            html.Li(nav_button("🏠", "Dashboard", "nav-home")),
            html.Li(nav_button("🧭", "Teams overview", "nav-teams")),
            html.Li(nav_button("🧑‍🤝‍🧑", "Players overview", "nav-players")),
            html.Li(nav_button("⚽", "Match analysis", "nav-match")),
            html.Li(nav_button("🔎", "Team Focus", "nav-team-focus")),
            html.Li(nav_button("👤", "Player Focus", "nav-player-focus")),
            html.Li(nav_button("📊", "Advanced", "nav-advanced")),
        ],
        className="sidebar-list",
    ),
    className="sidebar",
)


# ----------------------
# Grid area
# ----------------------
grid_html = html.Div(
    [
        html.Div(
            [
                # GridStack root with initial tiles
                html.Div(
                    id="grid-root-wrapper",
                    children=html.Div(
                        className="grid-stack",
                        children=[
                            html.Button(
                                id="open-add-widget", style={"display": "none"}
                            ),
                        ],
                    ),
                ),
                # NOTE: layout persistence may be implemented later. The
                # client-side script exposes `saveGridLayout()` which can be
                # wired to a `dcc.Store` or server endpoint. For now we keep
                # widget persistence in `widget-store` (local storage).
            ],
            className="grid-area",
        )
    ]
)

# ----------------------
# Pages
# ----------------------
# NOTE: individual page modules live in `src/pages/*.py` and register their
# callbacks using the shared `app` object. The navigate() callback below
# imports the pages lazily so we avoid circular import issues during module
# import time.
dashboard_page = html.Main(
    [
        html.Div(
            [
                html.H2("Dashboard Overview", className="page-title"),
                html.Div(
                    [
                        html.Button(
                            "Load layout", id="load-layout", className="control-btn"
                        ),
                        html.Button(
                            "Save layout", id="save-layout", className="control-btn"
                        ),
                        html.Button(
                            "Reset layout", id="reset-layout", className="control-btn"
                        ),
                    ],
                    className="page-title-actions",
                ),
            ],
            className="page-title-bar",
        ),
        grid_html,
    ],
    className="page",
)

# ----------------------
# Add Widget modal
# ----------------------
add_widget_modal = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle("Add widget")),
        dbc.ModalBody(
            [
                dbc.Label("Title"),
                dbc.Input(
                    id="add-widget-title", placeholder="Widget title", type="text"
                ),
                html.Br(),
                dbc.Label("Size (grid units)"),
                html.Div(
                    [
                        dbc.InputGroup(
                            [
                                dbc.InputGroupText("W"),
                                dbc.Input(
                                    id="add-widget-w",
                                    type="number",
                                    min=1,
                                    max=12,
                                    step=1,
                                    value=4,
                                ),
                                dbc.InputGroupText("H"),
                                dbc.Input(
                                    id="add-widget-h",
                                    type="number",
                                    min=1,
                                    max=12,
                                    step=1,
                                    value=3,
                                ),
                            ],
                            className="mb-2",
                        )
                    ]
                ),
                dbc.Label("Type"),
                dbc.Select(
                    id="add-widget-type",
                    options=[
                        {"label": "Placeholder (text)", "value": "placeholder"},
                        {"label": "Small chart (mock)", "value": "chart"},
                        {"label": "List / events", "value": "list"},
                    ],
                    value="placeholder",
                ),
            ]
        ),
        dbc.ModalFooter(
            dbc.Button("Add widget", id="add-widget-confirm", color="primary")
        ),
    ],
    id="add-widget-modal",
    is_open=False,
    centered=True,
    size="lg",
)

# ----------------------
# Widget focus modal
# ----------------------
widget_focus_modal = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle(id="widget-focus-title")),
        dbc.ModalBody(id="widget-focus-body", style={"minHeight": "60vh"}),
    ],
    id="widget-focus-modal",
    is_open=False,
    centered=True,
    size="xl",
)


# Footer
footer = html.Footer(
    "© 2025 PySport × Skillcorner — Tactical Demonstrator", className="footer"
)


# App layout
app.layout = html.Div(
    [
        header,
        sidebar,
        html.Div(dashboard_page, id="page-content", className="content"),
        add_widget_modal,
        widget_focus_modal,
        # Stores used by the client/server integration:
        # - `store-close-modal`: used by clientside callback to instruct Dash to close modals.
        dcc.Store(id="store-close-modal"),
        # - `widget-store` (local): persistent widget metadata and payloads (charts, lists...).
        dcc.Store(id="widget-store", storage_type="local"),
        # - `widget-update`: channel for partial updates to widget metadata (merged on receipt).
        dcc.Store(id="widget-update"),
        # - `focus-store`: client -> Dash channel to request widget focus/preview.
        dcc.Store(id="focus-store"),
        # - `last-added-widget-id`: written when a new widget is created (triggers store initialization).
        dcc.Store(id="last-added-widget-id"),
        # Player filter widget store
        dcc.Store(
            id="player-filter-store",
        ),
        # Filters modal (reused by pages)
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle(id="filters-modal-title")),
                dbc.ModalBody(id="filters-modal-body"),
                dbc.ModalFooter(
                    dbc.Button(
                        "Close", id="filters-modal-close", className="btn-secondary"
                    )
                ),
            ],
            id="filters-modal",
            is_open=False,
            centered=True,
            size="lg",
        ),
        # Hidden trigger buttons so callbacks referencing page-level open buttons
        # exist in the initial layout (avoids missing Input errors)
        html.Button(id="teams-open-filters", style={"display": "none"}),
        html.Button(id="players-open-filters", style={"display": "none"}),
        html.Button(id="match-open-filters", style={"display": "none"}),
        html.Button(id="teamfocus-open-filters", style={"display": "none"}),
        html.Button(id="playerfocus-open-filters", style={"display": "none"}),
        html.Button(id="advanced-open-filters", style={"display": "none"}),
        footer,
    ],
    className="app-root",
)


# ----------------------
# Callbacks
# ----------------------

from src.pages.teams.page import teams_page, teams_page_instance
from src.pages.players.page import players_page, players_page_instance
from src.pages.match.page import match_page, match_page_instance
from src.pages.team_focus.page import team_focus_page, team_focus_page_instance
from src.pages.player_focus.page import player_focus_page, player_focus_page_instance


register_all_callbacks(app)

# ---- Callback JS-only: no update to layout-store on add widget
app.clientside_callback(
    """
    function(addClicks, title, w, h, typ) {
        if (!addClicks) return window.dash_clientside.no_update;

        const params = {
            title: title || "New widget",
            w: parseInt(w)||4,
            h: parseInt(h)||3,
            type: typ || "placeholder"
        };

        if (window.addWidgetFromParams) {
            window.addWidgetFromParams(params);
        }

        // close the modal
        return "close";
    }
    """,
    Output("store-close-modal", "data"),
    Input("add-widget-confirm", "n_clicks"),
    State("add-widget-title", "value"),
    State("add-widget-w", "value"),
    State("add-widget-h", "value"),
    State("add-widget-type", "value"),
)


# Run
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(
        debug=False,
        host="0.0.0.0",  # listen on all interfaces
        port=port,
        dev_tools_ui=False,
        dev_tools_props_check=False,
    )
