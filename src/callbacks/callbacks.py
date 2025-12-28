"""Navigation callbacks."""
import dash
from dash import Input, Output, html, State, dcc

from src.core.logging_config import logger
from src.components.widgets.registry import WidgetRegistry

# Follow registered pages
_REGISTERED_CALLBACKS = {
    "teams": False,
    "players": False,
    "match": False,
    "team_focus": False,
    "player_focus": False,
    "advanced": False,
}

def register_callbacks(app):
    """Register navigation callbacks."""
    
    @app.callback(
        Output("page-content", "children"),
        [
            Input("nav-home", "n_clicks"),
            Input("nav-teams", "n_clicks"),
            Input("nav-players", "n_clicks"),
            Input("nav-match", "n_clicks"),
            Input("nav-team-focus", "n_clicks"),
            Input("nav-player-focus", "n_clicks"),
            Input("nav-advanced", "n_clicks"),
        ],
        prevent_initial_call=True,
    )
    def navigate(*args):
        ctx = dash.callback_context
        from main import dashboard_page
        if not ctx.triggered:
            return dashboard_page

        trigger = ctx.triggered[0]["prop_id"].split(".")[0]
        
        # Import lazy des pages
        from src.pages.teams.page import teams_page, teams_page_instance
        from src.pages.players.page import players_page, players_page_instance
        from src.pages.match.page import match_page, match_page_instance
        from src.pages.team_focus.page import team_focus_page, team_focus_page_instance
        from src.pages.player_focus.page import player_focus_page, player_focus_page_instance
        
        page_map = {
            "nav-home": ("dashboard", dashboard_page, None),
            "nav-teams": ("teams", teams_page, teams_page_instance),
            "nav-players": ("players", players_page, players_page_instance),
            "nav-match": ("match", match_page, match_page_instance),
            "nav-team-focus": ("team_focus", team_focus_page, team_focus_page_instance),
            "nav-player-focus": ("player_focus", player_focus_page, player_focus_page_instance),
        }

        if trigger in page_map:
            page_key, page_layout, page_instance = page_map[trigger]

            if page_instance and not _REGISTERED_CALLBACKS.get(page_key, False):
                try:
                    page_instance.register_callbacks(app)
                    _REGISTERED_CALLBACKS[page_key] = True
                    logger.info(f"✅ Registered callbacks for {page_key}")
                except Exception as e:
                    logger.error(f"❌ Failed to register callbacks for {page_key}: {e}")

            return page_layout

        return dashboard_page
    
    logger.info("✅ Navigation callbacks registered")

    @app.callback(
        Output("widget-store", "data"),
        Input("last-added-widget-id", "data"),
        Input("widget-update", "data"),
        State("widget-store", "data"),
        prevent_initial_call=True,
    )
    def update_widget_store(new_id, update, store):
        """Update the `widget-store` content.

        Triggers:
        - `last-added-widget-id` (new_id): ensures an entry exists for a newly
        created widget with minimal metadata.
        - `widget-update` (update): merges provided `meta` into the stored widget
        metadata keyed by `update['id']`.

        Returns the updated store dict or `dash.no_update` when appropriate.
        """
        if store is None:
            store = {}

        ctx = dash.callback_context
        if not ctx.triggered:
            logger.debug("update_widget_store: no trigger -> no update")
            return dash.no_update

        trigger = ctx.triggered[0]["prop_id"].split(".")[0]

        # 1. New id added
        if trigger == "last-added-widget-id" and new_id:
            logger.debug("Adding new widget id=%s to store", new_id)
            if new_id not in store:
                # TODO : Populate minimal metadata for the widget; real payloads come
                # from interactive creation flows that update this store later.
                store[new_id] = {
                    "id": new_id,
                    "title": "Widget",
                    "type": "placeholder",
                    "payload": None,
                }
            return store

        # 2. Update a widget's meta
        if trigger == "widget-update" and update:
            wid = update.get("id")
            meta = update.get("meta") or {}
            logger.debug("Updating widget=%s meta=%s", wid, meta)
            if not wid:
                logger.warning("widget-update triggered without an id: %s", update)
                return dash.no_update
            store[wid] = {**store.get(wid, {}), **meta}
            return store

        return dash.no_update


    # Open add widget modal (the add-tile click triggers the Dash button via client JS)
    @app.callback(
        Output("add-widget-modal", "is_open"),
        [
            Input("open-add-widget", "n_clicks"),
            Input("store-close-modal", "data"),
        ],
        [State("add-widget-modal", "is_open")],
    )
    def toggle_add_modal(open_clicks, close_signal, is_open):
        if open_clicks:
            return not is_open
        if close_signal == "close":
            return False
        return is_open
    

    @app.callback(
        [
            Output("player-info", "children"),
            Output("player-style-profile", "children"),
            Output("player-attributes", "children"),
            Output("player-table", "children"),
            Output("player-tracking", "children"),
        ],
        Input("player-filter-store", "data"),
        prevent_initial_call=True,
    )
    def update_all_widgets_from_filters(filter_data):
        """
        Update all widgets that use filters when filter data changes.
        """
        logger.info(f"[GlobalFilters] Updating widgets from filter data")

        if not filter_data:
            logger.warning("[GlobalFilters] No filter data received")
            return [dash.no_update] * 5

        try:
            results = []

            # Widget 1: Player Info
            player_widget = WidgetRegistry.get_instance("player-info")
            from src.components.widgets.player_info import PlayerInfoWidget

            if player_widget and isinstance(player_widget, PlayerInfoWidget):
                player_content = player_widget.update_from_filters(filter_data)
                results.append(player_content)
            else:
                results.append(dash.no_update)

            # Widget 2: Player Style Profile
            style_widget = WidgetRegistry.get_instance("player-style-profile")
            from src.components.widgets.player_roles import PlayerStyleProfileWidget

            if style_widget and isinstance(style_widget, PlayerStyleProfileWidget):
                update_result = style_widget.update_from_filters(filter_data)

                if "error" not in update_result:
                    widget_html = html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        dcc.Graph(
                                            id=style_widget.graph_id,
                                            figure=update_result.get("figure")
                                            or style_widget._create_empty_figure(),
                                            config={
                                                "displayModeBar": False,
                                                "displaylogo": False,
                                                "responsive": True,
                                            },
                                        ),
                                        className="player-style-profile-chart-area",
                                    ),
                                ],
                                className="player-style-profile-main-content",
                            ),
                            html.Div(
                                update_result.get(
                                    "strengths_html",
                                    style_widget._create_strengths_html(None),
                                ),
                                className="player-style-profile-strengths-container",
                            ),
                        ],
                        className="tile",
                    )
                    results.append(widget_html)
                else:
                    logger.error(
                        f"[GlobalFilters] Error updating player style profile: {update_result.get('error')}"
                    )
                    results.append(dash.no_update)
            else:
                results.append(dash.no_update)

            # Widget 3: Player Attributes (RADAR)
            attributes_widget = WidgetRegistry.get_instance("player-attributes")
            from src.components.widgets.player_card import PlayerAttributesWidget

            if attributes_widget and isinstance(attributes_widget, PlayerAttributesWidget):
                update_result = attributes_widget.update_from_filters(filter_data)

                if "error" not in update_result:
                    # For radar view
                    if attributes_widget.viz_type == "radar":
                        widget_html = html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div(
                                            dcc.Graph(
                                                id=attributes_widget.graph_id,
                                                figure=update_result.get("figure")
                                                or attributes_widget._create_empty_figure(),
                                                config={
                                                    "displayModeBar": False,
                                                    "displaylogo": False,
                                                    "responsive": True,
                                                },
                                            ),
                                            className="player-attributes-chart-area",
                                        ),
                                        html.Div(
                                            update_result.get(
                                                "scores_html",
                                                attributes_widget._create_scores_html(None),
                                            ),
                                            id=attributes_widget.scores_id,
                                            className="player-attributes-scores-area",
                                        ),
                                    ],
                                    className="player-attributes-main-content",
                                ),
                            ],
                            className="tile",
                        )
                    else:
                        # For table view
                        widget_html = html.Div(
                            [
                                html.Div(
                                    dcc.Graph(
                                        id=attributes_widget.table_id,
                                        figure=update_result.get("figure")
                                        or attributes_widget._create_empty_figure(),
                                        config={
                                            "displayModeBar": False,
                                            "displaylogo": False,
                                            "responsive": True,
                                            "scrollZoom": False,
                                        },
                                        style={"height": "600px"},
                                    ),
                                    className="player-attributes-table-area",
                                ),
                            ],
                            className="tile",
                        )
                    results.append(widget_html)
                else:
                    logger.error(
                        f"[GlobalFilters] Error updating player attributes: {update_result.get('error')}"
                    )
                    results.append(dash.no_update)
            else:
                results.append(dash.no_update)

            # Widget 4: Player Table
            attributes_table_widget = WidgetRegistry.get_instance("player-table")
            # Note: Same import as above

            if attributes_table_widget and isinstance(
                attributes_table_widget, PlayerAttributesWidget
            ):
                update_result = attributes_table_widget.update_from_filters(filter_data)

                if "error" not in update_result:
                    # For table view
                    if attributes_table_widget.viz_type == "table":
                        widget_html = html.Div(
                            [
                                html.Div(
                                    dcc.Graph(
                                        id=attributes_table_widget.table_id,
                                        figure=update_result.get("figure")
                                        or attributes_table_widget._create_empty_figure(),
                                        config={
                                            "displayModeBar": False,
                                            "displaylogo": False,
                                            "responsive": True,
                                            "scrollZoom": False,
                                        },
                                        style={"height": "600px"},
                                    ),
                                    className="player-attributes-table-area",
                                ),
                            ],
                            className="tile",
                        )
                    else:
                        # For radar view (should not happen for this widget)
                        widget_html = html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div(
                                            dcc.Graph(
                                                id=attributes_table_widget.graph_id,
                                                figure=update_result.get("figure")
                                                or attributes_table_widget._create_empty_figure(),
                                                config={
                                                    "displayModeBar": False,
                                                    "displaylogo": False,
                                                    "responsive": True,
                                                },
                                            ),
                                            className="player-attributes-chart-area",
                                        ),
                                        html.Div(
                                            update_result.get(
                                                "scores_html",
                                                attributes_table_widget._create_scores_html(
                                                    None
                                                ),
                                            ),
                                            id=attributes_table_widget.scores_id,
                                            className="player-attributes-scores-area",
                                        ),
                                    ],
                                    className="player-attributes-main-content",
                                ),
                            ],
                            className="tile",
                        )
                    results.append(widget_html)
                else:
                    logger.error(
                        f"[GlobalFilters] Error updating player table: {update_result.get('error')}"
                    )
                    results.append(dash.no_update)
            else:
                results.append(dash.no_update)

            # Widget 5: Heatmap
            attributes_heatmap_widget = WidgetRegistry.get_instance("player-tracking")
            from src.components.widgets.tracking_widget import TrackingWidget

            if attributes_heatmap_widget and isinstance(
                attributes_heatmap_widget, TrackingWidget
            ):
                update_result = attributes_heatmap_widget.update_from_filters(filter_data)
                if "error" not in update_result:
                    widget_html = html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        dcc.Graph(
                                            id=attributes_heatmap_widget.graph_id,
                                            figure=update_result.get("figure")
                                            or attributes_heatmap_widget._create_empty_figure(),
                                            config={
                                                "displayModeBar": False,
                                                "displaylogo": False,
                                                "responsive": True,
                                            },
                                        ),
                                        className="player-style-profile-chart-area",
                                    ),
                                ],
                                className="player-style-profile-main-content",
                            ),
                        ],
                        className="tile",
                    )
                    results.append(widget_html)
                else:
                    logger.error(
                        f"[GlobalFilters] Error updating player style profile: {update_result.get('error')}"
                    )
                    results.append(dash.no_update)
            else:
                results.append(dash.no_update)

            return results

        except Exception as e:
            logger.error(f"[GlobalFilters] Error updating widgets: {e}", exc_info=True)
            return [dash.no_update] * 5
        

    @app.callback(
        Output("widget-focus-modal", "is_open"),
        Output("widget-focus-title", "children"),
        Output("widget-focus-body", "children"),
        Input("focus-store", "data"),
        State("widget-store", "data"),
        State("widget-focus-modal", "is_open"),
        prevent_initial_call=True,
    )
    def show_widget_focus(focus_data, widget_store, is_open):
        """
        Open focus modal for widget content with support for all widget types.
        """
        if not focus_data:
            return is_open, dash.no_update, dash.no_update

        # Extract widget ID
        wid = focus_data.get("id") if isinstance(focus_data, dict) else focus_data

        if not wid:
            logger.warning(f"[show_widget_focus] No widget ID in focus data: {focus_data}")
            return is_open, dash.no_update, dash.no_update

        logger.info(f"[show_widget_focus] Processing widget: {wid}")

        # ========== SPECIAL CASE: FILTER WIDGETS ==========
        if wid == "filters" or wid.endswith("-filters"):
            return _handle_filter_widget_focus(wid, is_open)

        # ========== REGULAR WIDGETS ==========
        try:
            # Get widget instance from registry
            widget = WidgetRegistry.get_instance(wid)
            
            if not widget:
                logger.warning(f"[show_widget_focus] Widget not found in registry: {wid}")
                return _create_fallback_preview(wid, widget_store, is_open)

            # Skip filter widgets
            if hasattr(widget, 'config') and hasattr(widget.config, 'widget_type'):
                if widget.config.widget_type in ["filter", "filter_panel", "compact_filter"]:
                    logger.info(f"[show_widget_focus] Skipping filter widget: {wid}")
                    return is_open, dash.no_update, dash.no_update

            # Get widget title
            title = getattr(widget.config, 'title', f"Widget: {wid}") if hasattr(widget, 'config') else f"Widget: {wid}"
            
            # ========== FIRST TRY HTML CONTENT ==========
            html_content = None
            
            # 1. First try to retrieve complete HTML content
            if hasattr(widget, "get_current_content"):
                content = widget.get_current_content() # type: ignore
                if content:
                    # If widget has pure HTML (without figure)
                    if "html" in content and "figure" not in content:
                        logger.info(f"[show_widget_focus] Found HTML content for {wid}")
                        return _create_html_modal(content["html"], title, wid)
                    # If widget has both HTML and figure
                    elif "strengths_html" in content or "scores_html" in content:
                        logger.info(f"[show_widget_focus] Found combined content for {wid}")
                        return _create_combined_modal(content, title, wid)
            
            # 2. Then try specific HTML methods
            if hasattr(widget, "get_current_html"):
                html_content = widget.get_current_html() # type: ignore
                if html_content:
                    logger.info(f"[show_widget_focus] Found HTML via get_current_html for {wid}")
                    return _create_html_modal(html_content, title, wid)
            
            # ========== THEN TRY FIGURE ==========
            figure = None
            
            # 3. Try to retrieve cached figure
            if hasattr(widget, "get_current_figure"):
                figure = widget.get_current_figure() # type: ignore
                if figure:
                    logger.info(f"[show_widget_focus] Retrieved cached figure for {wid}")
                    return _create_figure_modal(figure, title, wid)
            
            # 4. Fallback: try to retrieve via other methods
            if figure is None and hasattr(widget, 'viz_instance') and widget.viz_instance: # type: ignore
                if hasattr(widget.viz_instance, "get_figure"): # type: ignore
                    figure = widget.viz_instance.get_figure() # type: ignore
                elif hasattr(widget.viz_instance, "create_figure"): # type: ignore
                    # Only calculate if absolutely necessary
                    logger.warning(f"[show_widget_focus] Calculating figure for {wid} (no cache)")
                    figure = widget.viz_instance.create_figure() # type: ignore
            
            if figure is not None:
                return _create_figure_modal(figure, title, wid)
            
            # ========== LAST RESORT: FULL RENDER ==========
            # 5. If nothing worked, try full render
            if hasattr(widget, "render"):
                try:
                    rendered = widget.render()
                    logger.info(f"[show_widget_focus] Using full render for {wid}")
                    return _create_html_modal(rendered, title, wid)
                except Exception as e:
                    logger.warning(f"[show_widget_focus] Render failed for {wid}: {e}")
            
            # Final fallback
            return _create_fallback_preview(wid, widget_store, is_open)

        except Exception as e:
            logger.error(f"[show_widget_focus] Error processing widget {wid}: {e}", exc_info=True)
            return _create_error_preview(wid, str(e), is_open)


    def _create_html_modal(html_content, title, wid):
        """Create a modal for displaying HTML content."""
        modal_body = html.Div(
            [
                html.Div(
                    html_content,
                    style={
                        "padding": "30px",
                        "backgroundColor": "var(--panel)",
                        "borderRadius": "12px",
                        "height": "100%",
                    }
                )
            ],
            className="modal-html-container",
        )
        
        # Determine the icon
        icon = _get_widget_icon(wid, title)
        
        logger.info(f"[show_widget_focus] Created HTML modal for '{title}'")
        return True, f"{icon} {title}", modal_body


    def _create_combined_modal(content, title, wid):
        """Create a modal for widgets that combine figure and HTML."""
        components = []
        
        # Add figure if available
        if "figure" in content and content["figure"]:
            fig = content["figure"]
            fig.update_layout(
                autosize=True,
                height=400,
                margin=dict(l=20, r=20, t=50, b=20),
            )
            
            components.append(
                html.Div(
                    dcc.Graph(
                        id=f"focus-modal-graph-{wid}",
                        figure=fig,
                        config={
                            "displayModeBar": True,
                            "displaylogo": False,
                            "responsive": True,
                        },
                        style={"height": "45vh"}
                    ),
                    style={"marginBottom": "20px"}
                )
            )
        
        # Add HTML if available
        html_content = None
        if "strengths_html" in content:
            html_content = content["strengths_html"]
        elif "scores_html" in content:
            html_content = content["scores_html"]
        
        if html_content:
            components.append(
                html.Div(
                    html_content,
                    style={
                        "padding": "20px",
                        "backgroundColor": "var(--panel-secondary)",
                        "borderRadius": "8px",
                        "maxHeight": "25vh",
                    }
                )
            )
        
        modal_body = html.Div(
            components,
            className="modal-combined-container",
        )
        
        icon = _get_widget_icon(wid, title)
        logger.info(f"[show_widget_focus] Created combined modal for '{title}'")
        return True, f"{icon} {title}", modal_body


    def _create_figure_modal(figure, title, wid):
        """Create a modal for displaying a Plotly figure."""
        figure.update_layout(
            autosize=True,
            height=600,
            margin=dict(l=50, r=50, t=80, b=50),
            title=dict(
                text=title,
                x=0.5,
                font=dict(size=18, color="white")
            )
        )

        modal_body = html.Div(
            [
                dcc.Graph(
                    id=f"focus-modal-graph-{wid}",
                    figure=figure,
                    config={
                        "displayModeBar": True,
                        "displaylogo": False,
                        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                        "responsive": True,
                        "toImageButtonOptions": {
                            "format": "png",
                            "filename": f"{title.lower().replace(' ', '_')}_focus",
                            "height": 800,
                            "width": 1200,
                            "scale": 2
                        }
                    },
                )
            ],
            className="modal-plotly-container",
        )

        icon = _get_widget_icon(wid, title)
        logger.info(f"[show_widget_focus] Created figure modal for '{title}'")
        return True, f"{icon} {title}", modal_body


    def _get_widget_icon(wid, title):
        """Determine icon based on widget ID and title."""
        widget_lower = wid.lower()
        title_lower = title.lower()
        
        if "tracking" in widget_lower or "tracking" in title_lower:
            return "📍"
        elif "attribute" in widget_lower or "attribute" in title_lower:
            return "📈"
        elif "style" in widget_lower or "profile" in widget_lower or "style" in title_lower:
            return "🎭"
        elif "info" in widget_lower or "info" in title_lower:
            return "👤"
        elif "player" in widget_lower or "player" in title_lower:
            return "👤"
        elif "chart" in widget_lower or "graph" in widget_lower:
            return "📊"
        elif "table" in widget_lower or "table" in title_lower:
            return "📋"
        else:
            return "📊"

    def _handle_filter_widget_focus(wid, is_open):
        """Handle focus modal for filter widgets."""
        logger.info(f"[show_widget_focus] Filter widget detected: {wid}")

        # Extract page prefix from widget ID
        page_prefix = wid.replace("-filters", "") if "-filters" in wid else "teams"

        try:
            # Import the specific page instance
            if page_prefix == "teams":
                from src.pages.teams.page import teams_page_instance
                filter_widget = teams_page_instance.widgets.get(wid)
            elif page_prefix == "players":
                from src.pages.players.page import players_page_instance
                filter_widget = players_page_instance.widgets.get(wid)
            elif page_prefix == "tracking":
                from src.pages.advanced.page import advanced_page_instance
                filter_widget = advanced_page_instance.widgets.get(wid)
            elif page_prefix == "player_focus":
                from src.pages.player_focus.page import player_focus_page_instance
                filter_widget = player_focus_page_instance.widgets.get(wid)
            # TODO: Add other pages
            else:
                logger.warning(f"[show_widget_focus] Unknown page prefix: {page_prefix}")
                return is_open, dash.no_update, dash.no_update

            if filter_widget and hasattr(filter_widget, "create_modal_content"):
                logger.info(f"[show_widget_focus] Creating filter modal for {wid}")

                # Create modal content from filter widget
                modal_content = filter_widget.create_modal_content()
                modal_title = getattr(filter_widget, "modal_title", f"Advanced Filters")

                return True, f"⚙️ {modal_title}", modal_content
            else:
                logger.warning(f"[show_widget_focus] No filter widget found: {wid}")
                return is_open, dash.no_update, dash.no_update

        except Exception as e:
            logger.error(f"[show_widget_focus] Error handling filter widget: {e}")
            return is_open, dash.no_update, dash.no_update


    def _create_fallback_preview(wid, widget_store, is_open):
        """Create basic fallback preview."""
        logger.debug(f"[show_widget_focus] Falling back to basic preview for '{wid}'")

        meta = widget_store.get(wid, {}) if widget_store else {}
        title = meta.get("title", f"Widget: {wid}")
        widget_type = meta.get("type", "unknown")

        # Create appropriate fallback content
        if widget_type == "text":
            content = html.Div(
                [
                    html.H4(title, style={"color": "var(--accent)"}),
                    html.Pre(
                        meta.get("content", "No content available"),
                        style={
                            "whiteSpace": "pre-wrap",
                            "background": "var(--panel)",
                            "padding": "20px",
                            "borderRadius": "8px",
                            "maxHeight": "60vh",
                            "overflow": "auto",
                        },
                    ),
                ],
                style={"padding": "20px"},
            )
        else:
            content = html.Div(
                [
                    html.H4("Widget Preview", style={"color": "var(--accent)"}),
                    html.P(f"Type: {widget_type}"),
                    html.P(f"ID: {wid}"),
                    html.P(f"Title: {title}"),
                    html.P(
                        "This widget doesn't support focus view yet.",
                        style={"color": "var(--text-secondary)", "marginTop": "20px"},
                    ),
                ],
                style={"padding": "30px", "textAlign": "center"},
            )

        return True, f"📊 {title}", content


    def _create_error_preview(wid, error_msg, is_open):
        """Create error preview."""
        content = html.Div(
            [
                html.H4("Error Loading Widget", style={"color": "#ff6b6b"}),
                html.P(f"Widget ID: {wid}"),
                html.P(f"Error: {error_msg}", style={"color": "var(--text-secondary)"}),
                html.P(
                    "Please try again or contact support.",
                    style={"color": "var(--text-secondary)", "marginTop": "20px"},
                ),
            ],
            style={"padding": "30px", "textAlign": "center"},
        )
        return True, "⚠️ Error", content