(function () {
    'use strict';

    // ============================================
    // 1. MODULE: GLOBAL STATE
    // ============================================
    const GlobalState = (function() {
        /**
         * Global state kept on the window object intentionally so other scripts
         * (e.g. React/Dash) can read/write. Keep names stable to avoid breaking
         * integrations that expect these globals.
         */
        const state = {
            grid: window._myGrid || null,
            lastLayout: window._lastGridLayout || null,
            isDragging: window._gsIsDragging || false,
            widgetStore: window._widgetStore || null,
            focusStore: window._focusStore || null,
            previousState: window._previousGridState || null,
            pendingAddPos: window._pendingAddPos || null
        };

        // Expose getters/setters to maintain compatibility
        window._myGrid = state.grid;
        window._lastGridLayout = state.lastLayout;
        window._gsIsDragging = state.isDragging;
        window._widgetStore = state.widgetStore;
        window._focusStore = state.focusStore;
        window._previousGridState = state.previousState;
        window._pendingAddPos = state.pendingAddPos;

        return {
            get grid() { return window._myGrid; },
            set grid(value) { window._myGrid = value; state.grid = value; },

            get lastLayout() { return window._lastGridLayout; },
            set lastLayout(value) { window._lastGridLayout = value; state.lastLayout = value; },

            get isDragging() { return window._gsIsDragging; },
            set isDragging(value) { window._gsIsDragging = value; state.isDragging = value; },

            get widgetStore() { return window._widgetStore; },
            set widgetStore(value) { window._widgetStore = value; state.widgetStore = value; },

            get focusStore() { return window._focusStore; },
            set focusStore(value) { window._focusStore = value; state.focusStore = value; },

            get pendingAddPos() { return window._pendingAddPos; },
            set pendingAddPos(value) { window._pendingAddPos = value; state.pendingAddPos = value; }
        };
    })();

    // ============================================
    // 2. MODULE: DASH STORE COMMUNICATION
    // ============================================
    const DashStore = (function() {
        /**
         * Write a payload to a Dash dcc.Store element.
         */
        function pushToStore(storeId, payload) {
            console.debug('[pushToStore] request -> id=%s', storeId, payload);

            if (window.dash_clientside && typeof window.dash_clientside.set_props === 'function') {
                try {
                    window.dash_clientside.set_props(storeId, { data: payload });
                    console.debug('[pushToStore] OK -> via dash_clientside.set_props (%s)', storeId);
                    return true;
                } catch (e) {
                    console.warn('[pushToStore] dash_clientside.set_props failed -> falling back', e);
                }
            }

            const attemptWrite = (el) => {
                try {
                    el.data = payload;
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    console.debug('[pushToStore] OK -> via el.data (%s)', storeId);
                    return true;
                } catch (err) {
                    console.warn('[pushToStore] el.data failed for %s', storeId, err);
                }

                try {
                    el.setAttribute('data-dash-store', JSON.stringify(payload));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    console.debug('[pushToStore] OK -> via setAttribute (%s)', storeId);
                    return true;
                } catch (err) {
                    console.warn('[pushToStore] setAttribute fallback failed for %s', storeId, err);
                }

                return false;
            };

            const el = document.getElementById(storeId);
            if (el) return attemptWrite(el);

            console.debug('[pushToStore] Store %s not found -> waiting for DOM...', storeId);

            const obs = new MutationObserver(() => {
                const found = document.getElementById(storeId);
                if (found) {
                    obs.disconnect();
                    console.debug('[pushToStore] Store %s appeared -> writing now', storeId);
                    attemptWrite(found);
                }
            });

            obs.observe(document.body, { childList: true, subtree: true });
            return false;
        }

        /**
         * Minimal store reader that reads widget-store or focus-store values.
         */
        function readFromStore(storeId) {
            switch (storeId) {
                case 'widget-store':
                    return GlobalState.widgetStore || {};
                case 'focus-store':
                    return GlobalState.focusStore || {};
                default:
                    console.warn('[readFromStore] unknown storeId:', storeId);
                    return null;
            }
        }

        return {
            pushToStore,
            readFromStore
        };
    })();
    window.DashStore = DashStore;

    // ============================================
    // 3. MODULE: LAYOUT MANAGEMENT
    // ============================================
    const LayoutManager = (function() {
        /**
         * Save the current stable layout to window._lastGridLayout.
         */
        function saveStableLayout() {
            if (!GlobalState.grid || typeof GlobalState.grid.save !== 'function') return;

            try {
                // Get layout from GridStack
                const saved = GlobalState.grid.save();

                // Enrich with DOM attributes that GridStack might lose
                const enrichedLayout = saved.map((item) => {
                    const widgetEl = document.getElementById(item.id);
                    if (widgetEl) {
                        return {
                            id: item.id,
                            x: item.x,
                            y: item.y,
                            w: item.w,
                            h: item.h,
                            // Preserve additional attributes
                            type: widgetEl.dataset.type || null,
                            // Force data-gs-id to match id
                            'data-gs-id': item.id
                        };
                    }
                    return item;
                });

                GlobalState.lastLayout = enrichedLayout;
                console.debug('[saveStableLayout] Layout saved with', enrichedLayout.length, 'items');
            } catch (e) {
                console.warn('[saveStableLayout] Failed to save layout', e);
            }
        }

        /**
         * Repair missing attributes on widgets after GridStack operations
         */
        function repairWidgetAttributes() {
            if (!GlobalState.grid) return;

            const widgets = document.querySelectorAll('#grid-root-wrapper .grid-stack-item');
            widgets.forEach(widget => {
                // Ensure id is present
                if (!widget.id) {
                    // Generate a new ID if missing
                    const newId = 'gs-' + Date.now().toString(36) + '-' + Math.floor(Math.random() * 10000);
                    widget.id = newId;
                    console.log('[repairWidgetAttributes] Added missing id:', newId);
                }

                // Ensure data-gs-id matches id
                if (!widget.dataset.gsId || widget.dataset.gsId !== widget.id) {
                    widget.dataset.gsId = widget.id;
                    console.log('[repairWidgetAttributes] Fixed data-gs-id for:', widget.id);
                }

                // Ensure widget has proper attributes for GridStack
                const gsId = widget.getAttribute('gs-id');
                if (!gsId || gsId !== widget.id) {
                    widget.setAttribute('gs-id', widget.id);
                }
            });
        }


        /**
         * Expose layout serialization for external callers
         */
        function saveGridLayout() {
            try {
                if (GlobalState.grid && typeof GlobalState.grid.save === 'function') {
                    // First repair any broken attributes
                    repairWidgetAttributes();

                    const layout = JSON.stringify(GlobalState.grid.save());
                    GlobalState.lastLayout = GlobalState.grid.save();
                    console.log('[GridStack] saveGridLayout called');
                    return layout;
                }
            } catch (e) {
                console.error('[GridStack] saveGridLayout error', e);
            }
            return null;
        }

        return {
            saveStableLayout,
            saveGridLayout,
            repairWidgetAttributes
        };
    })();

    // ============================================
    // 4. MODULE: CLEANUP UTILITIES
    // ============================================
    const CleanupManager = (function() {
        /**
         * Perform an aggressive cleanup of GridStack instances and related DOM elements.
         */
        function proactiveCleanup() {
            console.log('[ProactiveCleanup] Proactive cleanup before navigation');

            const pageGrids = document.querySelectorAll('.page-grid-stack');
            console.log('[ProactiveCleanup] Found', pageGrids.length, 'page grids');

            pageGrids.forEach((grid) => {
                try {
                    if (grid.__gs_instance) {
                        console.log('[ProactiveCleanup] Destroying GridStack instance');
                        grid.__gs_instance.destroy(false);
                        grid.__gs_instance = null;
                        grid.__gs_initialized = false;

                        if (grid.__gs_instance?.engine?.id) {
                            grid.classList.remove('grid-stack-instance-' + grid.__gs_instance.engine.id);
                        }
                        grid.classList.remove('grid-stack-static', 'grid-stack-animate');
                    }
                } catch (e) {
                    console.warn('[ProactiveCleanup] Error destroying instance', e);
                }

                try {
                    const gridStackItems = grid.querySelectorAll('.grid-stack-item[data-gs-id]');
                    gridStackItems.forEach((item) => {
                        // Skip items that look like Plotly graphs, add-tiles, or add-helper
                        if (!item) return;

                        // Son't remove the "add-tile" (plus) placeholders or our helper
                        if (item.classList.contains('add-tile') || item.id === 'grid-add-helper') {
                            console.debug('[ProactiveCleanup] Preserving add-tile or add-helper:', item.id || item.className);
                            return;
                        }

                        // if item already contains a Plotly figure or Dash graph, preserve it
                        if (item.querySelector && (
                            item.querySelector('.js-plotly-plot') ||
                            item.querySelector('.plot-container') ||
                            item.querySelector('.dash-graph') ||
                            item.querySelector('.plotly-graph-div') ||
                            item.closest && item.closest('.dash-graph')
                        )) {
                            console.debug('[ProactiveCleanup] Preserving Plotly/Dash widget:', item.id || item.className);
                            return;
                        }

                        // Otherwise remove
                        if (item.parentNode === grid) item.remove();
                    });
                } catch (e) {
                    console.warn('[ProactiveCleanup] Error removing grid items', e);
                }
            });

            if (GlobalState.grid) {
                try {
                    GlobalState.grid.destroy(false);
                } catch (e) {
                    console.warn('[ProactiveCleanup] Error destroying main grid', e);
                }
                GlobalState.grid = null;
            }
        }

        /**
         * Attempt to safely destroy the main grid and perform cleanup of helpers.
         */
        function safeDestroyGrid() {
            if (!GlobalState.grid) return;

            try {
                console.log('[GridStack] Safe destroy called');
                // REPAIR ATTRIBUTES BEFORE SAVING
                LayoutManager.repairWidgetAttributes();

                if (GlobalState.grid.save) {
                    GlobalState.lastLayout = GlobalState.grid.save();
                    console.log('[GridStack] Layout saved before destroy');
                }
                GlobalState.grid.destroy();
            } catch (e) {
                console.warn('[GridStack] Destroy error', e);
            } finally {
                GlobalState.grid = null;

                const addHelper = document.getElementById('grid-add-helper');
                if (addHelper) addHelper.remove();
            }
        }


        /**
         * Gracefully destroy GridStack instances attached to page grids.
         */
        function safeCleanupPageGrids() {
            console.log('[SafeCleanup] Safe cleanup of page grids');
            const pageGrids = document.querySelectorAll('.page-grid-stack');
            console.log('[SafeCleanup] Found', pageGrids.length, 'page grids to clean');

            pageGrids.forEach((grid) => {
                if (grid.__gs_instance) {
                    try {
                        grid.__gs_instance.destroy();
                    } catch (e) {
                        console.warn('[SafeCleanup] Error destroying GridStack instance', e);
                    }
                    grid.__gs_instance = null;
                    grid.__gs_initialized = false;
                    console.log('[SafeCleanup] GridStack instance destroyed for a page grid');
                }
            });
        }

        return {
            proactiveCleanup,
            safeDestroyGrid,
            safeCleanupPageGrids
        };
    })();

    // ============================================
    // 5. MODULE: NAVIGATION LISTENERS
    // ============================================
    const NavigationManager = (function() {
        /**
         * Attach listeners to navigation buttons and history API calls.
         */
        function setupNavigationButtonListeners() {
            console.log('[NavButtons] Setting up navigation button listeners');

            const attachListeners = () => {
                const allButtons = document.querySelectorAll('button, a');

                allButtons.forEach((btn) => {
                    if (btn.__navListener) return;

                    const onClick = (e) => {
                        // Ignore clicks originating from Plotly modebar or plot controls
                        if (e.target.closest && e.target.closest('.modebar, .modebar-container, .plotly, .plot-container, .js-plotly-plot, .plotly-graph-div, .dash-graph')) {
                            console.debug('[NavButtons] Click inside Plotly controls ignoring');
                            return;
                        }

                        // Ignore clicks inside modals or our add-helper
                        if (e.target.closest && e.target.closest('.modal, .react-modal, #focus-modal, .focus-modal, #grid-add-helper, .add-helper')) {
                            return;
                        }

                        // Ignore clicks on add-tile placeholders
                        if (e.target.closest && e.target.closest('.add-tile')) {
                            return;
                        }

                        // Ignore clicks on filter widgets
                        if (e.target.closest && e.target.closest('#filters')) {
                            console.debug('[NavButtons] Click inside filter widget ignoring');
                            return;
                        }

                        const teamsGrid = document.querySelector('.page-grid-stack');
                        if (teamsGrid && teamsGrid.offsetParent !== null) {
                            console.log('[NavButtons] Navigation click detected from Teams Overview');
                            CleanupManager.proactiveCleanup();
                        }
                    };

                    btn.addEventListener('click', onClick, true);
                    btn.__navListener = true;
                });
            };

            const wrapHistoryMethod = (methodName) => {
                const original = history[methodName];
                history[methodName] = function (...args) {
                    // If the call was initiated while focus is inside a Plotly graph, skip proactive cleanup
                    const activeInsidePlotly = document.activeElement && document.activeElement.closest &&
                        document.activeElement.closest('.js-plotly-plot, .plot-container, .modebar, .dash-graph');

                    if (!activeInsidePlotly) {
                        const teamsGrid = document.querySelector('.page-grid-stack');
                        if (teamsGrid && teamsGrid.offsetParent !== null) {
                            console.log('[NavButtons] ' + methodName + ' from Teams Overview');
                            setTimeout(CleanupManager.proactiveCleanup, 0);
                        }
                    } else {
                        console.debug('[NavButtons] history.' + methodName + ' ignored because activeElement is inside Plotly');
                    }

                    return original.apply(this, args);
                };
            };

            attachListeners();
            setInterval(attachListeners, 2000);

            const observer = new MutationObserver(attachListeners);
            observer.observe(document.body, { childList: true, subtree: true });

            wrapHistoryMethod('pushState');
            wrapHistoryMethod('replaceState');
        }

        return {
            setupNavigationButtonListeners
        };
    })();

    // ============================================
    // 6. MODULE: WIDGET CREATION
    // ============================================
    const WidgetFactory = (function() {
        /**
         * Create a widget element with the given parameters.
         */
        function createWidgetElement(params, uid, pos) {
            const el = document.createElement('div');
            el.id = uid;
            el.className = 'grid-stack-item';
            el.dataset.gsId = uid;
            el.setAttribute('gs-id', uid); // Additional attribute for safety
            el.setAttribute('gs-w', params.w);
            el.setAttribute('gs-h', params.h);
            el.setAttribute('gs-x', pos.x);
            el.setAttribute('gs-y', pos.y);

            const inner = document.createElement('div');
            inner.className = 'tile';

            const hdr = document.createElement('div');
            hdr.className = 'tile-header';
            hdr.innerText = params.title || 'Widget';

            const del = document.createElement('button');
            del.className = 'tile-delete';
            del.innerText = '❌';
            hdr.appendChild(del);

            const body = document.createElement('div');
            body.className = 'tile-body';
            body.innerText = params.type === 'chart' ? 'Chart (mock)'
                : params.type === 'list' ? 'List (mock)'
                : 'Text widget';

            inner.appendChild(hdr);
            inner.appendChild(body);
            el.appendChild(inner);

            return { el, del };
        }

        /**
         * Create a static page widget element.
         */
        function createPageWidgetElement(item) {
            const el = document.createElement('div');
            el.className = 'grid-stack-item';
            if (item.id) { el.id = item.id; el.dataset.gsId = item.id; }

            el.setAttribute('gs-x', String(item.x || 0));
            el.setAttribute('gs-y', String(item.y || 0));
            el.setAttribute('gs-w', String(item.w || 4));
            el.setAttribute('gs-h', String(item.h || 3));

            const inner = document.createElement('div');
            inner.className = 'tile';
            const hdr = document.createElement('div');
            hdr.className = 'tile-header';
            hdr.innerText = item.title || 'Widget';
            const body = document.createElement('div');
            body.className = 'tile-body';

            if (item.type === 'filter') {
                inner.classList.add('filter-tile');
                const compact = document.createElement('div');
                compact.className = 'filter-placeholder';
                compact.innerHTML = '<div class="tile-label">Filters</div>';
                body.appendChild(compact);
            } else if (item.type === 'chart') {
                const ph = document.createElement('div');
                ph.className = 'plotly-placeholder';
                ph.innerText = 'Chart (placeholder)';
                body.appendChild(ph);
            } else if (item.type === 'list') {
                body.innerText = 'List (placeholder)';
            } else {
                body.innerText = 'Widget content';
            }

            inner.appendChild(hdr);
            inner.appendChild(body);
            el.appendChild(inner);

            return el;
        }

        return {
            createWidgetElement,
            createPageWidgetElement
        };
    })();


    // ============================================
    // 7. MODULE: MAIN GRIDSTACK DASHBOARD
    // ============================================
    const MainGridStack = (function() {
        /**
         * Initialize the main editable GridStack instance.
         */
        function tryInitGridStack() {
            if (GlobalState.grid) {
                console.log('[GridStack] already initialized — skipping tryInitGridStack');
                return;
            }

            const gridElem = document.querySelector('#grid-root-wrapper .grid-stack');
            if (!gridElem) {
                console.log('[GridStack] dashboard grid not found — skipping init');
                return;
            }

            if (typeof GridStack === 'undefined') {
                console.warn('[GridStack] GridStack library not loaded yet — retrying later');
                return;
            }

            console.log('[GridStack] Initializing...');

            const editable = gridElem.dataset && gridElem.dataset.editable !== 'false';
            const gridOpts = {
                row: 8,
                column: 12,
                float: true,
                maxRow: 12,
                disableOneColumnMode: true,
                cellHeight: 60,
                resizable: editable ? { handles: 'se' } : false,
                draggable: editable ? { handle: '.tile-header, .tile-header-wrapper' } : false,
            };

            const grid = GridStack.init(gridOpts, gridElem);
            GlobalState.grid = grid;

            restoreLayout(grid);
            setupDragResizeHandlers(grid);
            setupAddHelper(gridElem, grid);
            setupEventDelegation(gridElem, grid);
            exposeGlobalMethods(grid);

            console.log('[GridStack] initialization complete');
        }

        /**
         * Restore layout from saved state.
         */
        function restoreLayout(grid) {
            if (!GlobalState.lastLayout || !Array.isArray(GlobalState.lastLayout) || GlobalState.lastLayout.length === 0) {
                return;
            }

            const widgetMeta = DashStore.readFromStore('widget-store') || {};
            console.log('[GridStack] restoring, widgetMeta read:', widgetMeta);

            try {
                if (typeof grid.removeAll === 'function') grid.removeAll();
            } catch (e) {
                // ignore
            }

            GlobalState.lastLayout.forEach((item) => {
                try {
                    const el = document.createElement('div');
                    el.className = 'grid-stack-item';

                    // CRITICAL: Always set both id and data-gs-id
                    if (item.id) {
                        el.id = item.id;
                        el.dataset.gsId = item.id;
                        // Also set gs-id attribute for GridStack compatibility
                        el.setAttribute('gs-id', item.id);
                    }

                    el.setAttribute('gs-x', String(item.x));
                    el.setAttribute('gs-y', String(item.y));
                    el.setAttribute('gs-w', String(item.w));
                    el.setAttribute('gs-h', String(item.h));

                    if (item.type) el.dataset.type = item.type;

                    const tile = document.createElement('div');
                    tile.className = 'tile';

                    const hdr = document.createElement('div');
                    hdr.className = 'tile-header';

                    const meta = widgetMeta[item.id] || {};
                    hdr.innerText = meta.title || 'Widget';

                    const btn = document.createElement('button');
                    btn.className = 'tile-delete';
                    btn.innerText = '❌';
                    hdr.appendChild(btn);

                    const body = document.createElement('div');
                    body.className = 'tile-body';
                    if (meta.type === 'chart') body.innerText = 'Chart (mock)';
                    else if (meta.type === 'list') body.innerText = 'List (mock)';
                    else body.innerText = 'Text widget';

                    tile.appendChild(hdr);
                    tile.appendChild(body);
                    el.appendChild(tile);

                    grid.addWidget(el, {
                        x: item.x,
                        y: item.y,
                        w: item.w,
                        h: item.h,
                        // CRITICAL: Pass id to GridStack options
                        id: item.id
                    });

                    btn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        grid.removeWidget(el);
                        LayoutManager.saveStableLayout();
                    });
                } catch (err) {
                    console.warn('[GridStack] failed to restore widget', err);
                }
            });

            console.log('[GridStack] Layout restored successfully');
            // REPAIR ATTRIBUTES AFTER RESTORATION
            setTimeout(() => LayoutManager.repairWidgetAttributes(), 100);
        }

        /**
         * Setup drag and resize event handlers.
         */
        function setupDragResizeHandlers(grid) {
            grid.on && grid.on('dragstart', () => {
                GlobalState.isDragging = true;
                console.log('[GridStack] dragstart — marking isDragging=true');
            });

            grid.on && grid.on('dragstop', () => {
                GlobalState.isDragging = false;
                console.log('[GridStack] dragstop — marking isDragging=false and saving layout');
                LayoutManager.saveStableLayout();
                // REPAIR ATTRIBUTES AFTER DRAG
                setTimeout(() => LayoutManager.repairWidgetAttributes(), 10);
            });

            grid.on && grid.on('resizestart', () => {
                GlobalState.isDragging = true;
                console.log('[GridStack] resizestart — marking isDragging=true');
            });

            grid.on && grid.on('resizestop', () => {
                console.log('[GridStack] resizestop — marking isDragging=false and saving layout');
                setTimeout(() => {
                    GlobalState.isDragging = false;
                    LayoutManager.saveStableLayout();
                    // REPAIR ATTRIBUTES AFTER RESIZE
                    LayoutManager.repairWidgetAttributes();
                    PlotlyResizer.debouncedResize();
                }, 50);
            });

            grid.on && grid.on('resize', () => {
                if (!GlobalState.isDragging) return;
                PlotlyResizer.debouncedResize();
            });

            // ADD NEW EVENT LISTENER FOR GRID UPDATES
            grid.on && grid.on('change', () => {
                // Repair attributes whenever GridStack changes the layout
                setTimeout(() => {
                    LayoutManager.repairWidgetAttributes();
                    PlotlyResizer.debouncedResize();
                }, 50);
            });
        }

        /**
         * Setup the floating add helper button.
         */
        function setupAddHelper(gridElem, grid) {
            let lastHover = { x: 0, y: 0 };
            const addHelper = document.createElement('div');
            addHelper.id = 'grid-add-helper';
            addHelper.className = 'hidden add-helper';
            addHelper.innerText = '+';
            gridElem.appendChild(addHelper);

            requestAnimationFrame(() => {
                addHelper.dataset.ready = '1';
                console.log('[GridStack] add-helper ready');
            });

            const updateHelperPosition = (x, y) => {
                const bounds = gridElem.getBoundingClientRect();
                const col = grid.getColumn();
                const row = grid.getRow();
                const cellW = bounds.width / col;
                const cellH = bounds.height / row;
                addHelper.style.left = (x * cellW + (cellW - addHelper.offsetWidth) / 2) + 'px';
                addHelper.style.top = (y * cellH + (cellH - addHelper.offsetHeight) / 2) + 'px';
            };

            const hideHelper = () => addHelper.classList.add('hidden');
            const showHelper = () => addHelper.classList.remove('hidden');

            gridElem.addEventListener('mousemove', (ev) => {
                try {
                    const bounds = gridElem.getBoundingClientRect();
                    const col = grid.getColumn();
                    const row = grid.getRow();
                    const mx = ev.clientX - bounds.left;
                    const my = ev.clientY - bounds.top;
                    if (mx < 0 || my < 0 || mx > bounds.width || my > bounds.height) {
                        hideHelper();
                        return;
                    }
                    const x = Math.floor(mx / (bounds.width / col));
                    const y = Math.floor(my / (bounds.height / row));

                    let occupied = false;
                    if (GlobalState.grid && typeof GlobalState.grid.isAreaEmpty === 'function') {
                        occupied = !GlobalState.grid.isAreaEmpty(x, y, 1, 1);
                    } else if (grid && typeof grid.isAreaEmpty === 'function') {
                        occupied = !grid.isAreaEmpty(x, y, 1, 1);
                    } else if (grid && grid.engine && typeof grid.engine.isAreaEmpty === 'function') {
                        occupied = !grid.engine.isAreaEmpty(x, y, 1, 1);
                    }
                    if (occupied) {
                        hideHelper();
                        return;
                    }

                    if (!addHelper.dataset.ready) return;
                    updateHelperPosition(x, y);
                    showHelper();
                    lastHover = { x, y };
                } catch (err) {
                    console.warn('[GridStack] mousemove helper error', err);
                }
            });

            addHelper.addEventListener('click', () => {
                try {
                    GlobalState.pendingAddPos = { ...lastHover };
                    const dashBtn = document.querySelector('#open-add-widget');
                    if (dashBtn) {
                        console.log('[GridStack] addHelper clicked — triggering #open-add-widget');
                        dashBtn.click();
                    } else {
                        console.warn('[GridStack] addHelper click: #open-add-widget not found');
                    }
                } catch (err) {
                    console.error('[GridStack] addHelper click error', err);
                }
            });
        }

        /**
         * Setup event delegation for the grid.
         */
        function setupEventDelegation(gridElem, grid) {
            // Delegate delete button clicks
            gridElem.addEventListener('click', (ev) => {
                try {
                    const btn = ev.target.closest('.tile-delete');
                    if (!btn) return;
                    const item = btn.closest('.grid-stack-item');
                    if (!item) return;

                    // TRY MULTIPLE WAYS TO GET THE WIDGET ID
                    let widgetId = item.id ||
                                item.dataset?.gsId ||
                                item.getAttribute('gs-id') ||
                                item.getAttribute('data-gs-id');

                    if (!widgetId && item.classList.contains('grid-stack-item')) {
                        // Last resort: check GridStack's internal data
                        const gsId = item.getAttribute('gs-id');
                        if (gsId) widgetId = gsId;
                    }

                    if (widgetId && GlobalState.grid) {
                        console.log('[GridStack] removeWidget called for', widgetId);
                        GlobalState.grid.removeWidget(item);
                        LayoutManager.saveStableLayout();
                    }
                } catch (err) {
                    console.error('[GridStack] delete handler error', err);
                }
            });

            // Tile click -> send widget metadata to focus-store
            // MAKE MORE ROBUST TO HANDLE MISSING ATTRIBUTES
            gridElem.addEventListener('click', (ev) => {
                try {
                    if (ev.target.closest('.tile-delete')) return;
                    const tile = ev.target.closest('.grid-stack-item');
                    if (!tile) return;

                    if (GlobalState.isDragging) {
                        console.log('[GridStack] click ignored because drag/resize was active');
                        return;
                    }

                    // MULTIPLE FALLBACKS FOR GETTING WIDGET ID
                    let widgetId = tile.id ||
                                tile.dataset?.gsId ||
                                tile.getAttribute('gs-id') ||
                                tile.getAttribute('data-gs-id');

                    if (!widgetId) {
                        console.warn('[GridStack] Cannot find widget ID for clicked tile');
                        // Try to repair attributes before giving up
                        LayoutManager.repairWidgetAttributes();
                        widgetId = tile.id || tile.dataset?.gsId;
                    }

                    if (!widgetId) {
                        console.error('[GridStack] No widget ID found even after repair');
                        return;
                    }

                    const widgetMeta = GlobalState.widgetStore?.[widgetId];
                    if (!widgetMeta) {
                        console.warn('[GridStack] No metadata found for widget ID:', widgetId);
                        return;
                    }

                    console.log('[GridStack] tile clicked — sending to focus-store', widgetMeta);
                    DashStore.pushToStore('focus-store', widgetMeta);
                } catch (err) {
                    console.warn('[GridStack] tile click handler error', err);
                }
            });
        }

        /**
         * Expose global methods for external callers.
         */
        function exposeGlobalMethods(grid) {
            // Expose helper to create a widget from params
            window.addWidgetFromParams = function (params) {
                if (!GlobalState.grid) return false;
                const pos = GlobalState.pendingAddPos || { x: 0, y: 0 };
                const uid = 'gs-' + Date.now().toString(36) + '-' + Math.floor(Math.random() * 10000);

                const { el, del } = WidgetFactory.createWidgetElement(params, uid, pos);

                // CRITICAL: Set both id and data-gs-id
                el.id = uid;
                el.dataset.gsId = uid;
                el.setAttribute('gs-id', uid);

                GlobalState.widgetStore = GlobalState.widgetStore || {};
                GlobalState.widgetStore[uid] = {
                    id: uid,
                    title: params.title || 'Widget',
                    type: params.type || 'placeholder',
                    payload: null,
                };

                DashStore.pushToStore('widget-store', GlobalState.widgetStore);

                GlobalState.grid.addWidget(el, {
                    id: uid, // IMPORTANT: Pass id to GridStack
                    x: pos.x,
                    y: pos.y,
                    w: params.w,
                    h: params.h,
                });

                del.addEventListener('click', (e) => {
                    e.stopPropagation();
                    GlobalState.grid.removeWidget(el);
                    LayoutManager.saveStableLayout();
                });

                LayoutManager.saveStableLayout();
                return true;
            };

            // Expose layout serialization
            window.saveGridLayout = LayoutManager.saveGridLayout;

            // Expose attribute repair function
            window.repairGridAttributes = LayoutManager.repairWidgetAttributes;

            // Wire legacy "add-tile" elements
            document.querySelectorAll('.grid-stack-item.add-tile').forEach((el) => {
                if (!el.__wired) {
                    el.addEventListener('click', () => { window.location.hash = '#add-widget'; });
                    el.__wired = true;
                }
            });
        }

        return {
            tryInitGridStack
        };
    })();

    // ============================================
    // 8. MODULE: PAGE GRIDS (STATIC)
    // ============================================
    const PageGrids = (function() {
        /**
         * Initialize page-specific, static GridStack instances from JSON.
         * Create only containers; content is populated by Dash/Python.
         */
        function initPageGridsFromJSON() {
            const grids = document.querySelectorAll('.page-grid-stack');
            console.log('[PageGrid] Found', grids.length, 'page grids');

            grids.forEach((grid, idx) => {
                if (grid.__gs_initialized && grid.offsetParent !== null) {
                    console.log(`[PageGrid][${idx}] Already initialized - skipping`);
                    return;
                }

                if (typeof GridStack === 'undefined') {
                    console.warn('[PageGrid] GridStack not available');
                    return;
                }

                try {
                    let layout = [];
                    const script = grid.querySelector('script[type="application/json"]');

                    if (script && script.textContent?.trim()) {
                        try {
                            layout = JSON.parse(script.textContent);
                            console.log(`[PageGrid][${idx}] Parsed layout:`, layout);
                        } catch (parseError) {
                            console.warn(`[PageGrid][${idx}] Failed to parse JSON:`, parseError);
                            return;
                        }
                    } else {
                        console.warn(`[PageGrid][${idx}] No JSON configuration`);
                        return;
                    }

                    // Clean previous instance
                    if (grid.__gs_instance) {
                        try { grid.__gs_instance.destroy(); } catch (e) {
                            console.warn(`[PageGrid][${idx}] Error destroying previous instance`, e);
                        }
                    }

                    // Initialize GridStack with static options
                    const opts = {
                        maxRow: 12,
                        row: 8,
                        column: 12,
                        float: true,
                        cellHeight: 60,
                        disableOneColumnMode: true,
                        disableDrag: true,
                        disableResize: true,
                        staticGrid: true,
                    };

                    const gs = GridStack.init(opts, grid);
                    grid.__gs_instance = gs;

                    layout.forEach((item, widx) => {
                        try {
                            // Search for existing element by ID
                            const existingEl = document.getElementById(item.id);

                            if (existingEl && !existingEl.querySelector(".js-plotly-plot") && !existingEl.querySelector(".dash-graph")) {
                                // The element already exists in the DOM
                                console.log(`[PageGrid][${idx}][Widget ${widx}] Using existing element: ${item.id}`);

                                // Ensure it has correct classes and attributes
                                existingEl.className = 'grid-stack-item';
                                existingEl.dataset.gsId = item.id;

                                // Add to GridStack
                                gs.addWidget(existingEl, {
                                    x: item.x || 0,
                                    y: item.y || 0,
                                    w: item.w || 4,
                                    h: item.h || 3,
                                });
                            }
                            else if (existingEl) {
                                console.log("[PageGrid] Existing Dash content preserved:", item.id);
                                gs.addWidget(existingEl, {
                                    x: item.x, y: item.y, w: item.w, h: item.h
                                });
                                return;
                            }
                            else {
                                // Create an empty container for Dash to fill later (by Dash callbacks)
                                console.log(`[PageGrid][${idx}][Widget ${widx}] Creating container for: ${item.id}`);

                                const container = document.createElement('div');
                                container.id = item.id;
                                container.className = 'grid-stack-item';
                                container.dataset.gsId = item.id;

                                // Content placeholder
                                const placeholder = document.createElement('div');
                                placeholder.className = 'tile';
                                placeholder.innerHTML = `
                                    <div class="tile-header">${item.title || 'Chart'}</div>
                                    <div class="tile-body">
                                        <div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--muted);">
                                            Loading chart...
                                        </div>
                                    </div>
                                `;
                                container.appendChild(placeholder);

                                gs.addWidget(container, {
                                    x: item.x || 0,
                                    y: item.y || 0,
                                    w: item.w || 4,
                                    h: item.h || 3,
                                });
                            }
                        } catch (err) {
                            console.warn(`[PageGrid][${idx}][Widget ${widx}] Error:`, err);
                        }
                    });

                    grid.__gs_initialized = true;
                    console.log(`[PageGrid][${idx}] Initialized with ${layout.length} widgets`);

                    // Setup click events for tiles
                    setupTileClickEvents(grid);
                    console.log(`[PageGrid][${idx}] Click events added to widgets`);

                } catch (err) {
                    console.error(`[PageGrid][${idx}] Init failed`, err);
                }
            });
        }

        /**
         * Setup click events for tiles to open focus modal
         */
        function setupTileClickEvents(gridElement) {
            console.log('[PageGrid] Setting up click events for grid');

            gridElement.addEventListener('click', function(ev) {
                try {

                    // If click originates from Plotly graph or its toolbar → ignore
                    // prev. : ev.target.closest('.js-plotly-plot') ||
                    if (ev.target.closest('.modebar')) {
                        return; // do not open modal
                    }

                    if (ev.target.closest('#filters') && !ev.target.closest('.filters-gear-btn')) {
                        console.log('[PageGrid] Click inside filter widget ignoring');
                        return;
                    }

                    console.log('[PageGrid] Click event triggered on:', ev.target);

                    // Ignore delete button clicks
                    if (ev.target.closest('.tile-delete')) {
                        console.log('[PageGrid] Ignoring delete button click');
                        return;
                    }

                    // Find the tile
                    const tile = ev.target.closest('.grid-stack-item');
                    if (!tile) {
                        console.log('[PageGrid] Click not on a grid-stack-item');
                        return;
                    }

                    console.log('[PageGrid] Tile found:', {
                        id: tile.id,
                        dataset: tile.dataset,
                        className: tile.className
                    });

                    // Check if dragging is in progress
                    if (GlobalState && GlobalState.isDragging) {
                        console.log('[PageGrid] Dragging in progress, ignoring click');
                        return;
                    }

                    // Get the ID
                    const widgetId = tile.id ||
                                    tile.dataset?.gsId ||
                                    tile.getAttribute('gs-id') ||
                                    tile.getAttribute('data-gs-id');

                    if (!widgetId) {
                        console.error('[PageGrid] No widget ID found! Tile attributes:', {
                            id: tile.id,
                            'data-gs-id': tile.getAttribute('data-gs-id'),
                            'gs-id': tile.getAttribute('gs-id'),
                            dataset: tile.dataset
                        });
                        return;
                    }

                    console.log('[PageGrid] Widget ID:', widgetId);

                    // Method 1 : dash_clientside.set_props
                    if (window.dash_clientside && typeof window.dash_clientside.set_props === 'function') {
                        console.log('[PageGrid] Using dash_clientside.set_props');
                        try {
                            window.dash_clientside.set_props('focus-store', { data: { id: widgetId } });
                            console.log('[PageGrid] Successfully sent to focus-store via dash_clientside');
                            return;
                        } catch (e) {
                            console.error('[PageGrid] dash_clientside.set_props failed:', e);
                        }
                    }

                    // Method 2 : Direct DOM manipulation
                    const focusStoreEl = document.getElementById('focus-store');
                    if (focusStoreEl) {
                        console.log('[PageGrid] Found focus-store element, updating directly');
                        try {
                            focusStoreEl.data = { id: widgetId };
                            // Trigger event
                            focusStoreEl.dispatchEvent(new Event('change', { bubbles: true }));
                            console.log('[PageGrid] Successfully updated focus-store element');
                            return;
                        } catch (e) {
                            console.error('[PageGrid] Direct update failed:', e);
                        }
                    } else {
                        console.error('[PageGrid] focus-store element not found in DOM');
                    }

                    // Method 3 : Fallback to DashStore
                    if (typeof DashStore !== 'undefined' && typeof DashStore.pushToStore === 'function') {
                        console.log('[PageGrid] Using DashStore module');
                        DashStore.pushToStore('focus-store', { id: widgetId });
                    } else {
                        console.error('[PageGrid] No method available to update focus-store');
                    }

                } catch (err) {
                    console.error('[PageGrid] Unexpected error in click handler:', err);
                }
            });

            // Style feedback
            const tiles = gridElement.querySelectorAll('.grid-stack-item');
            console.log('[PageGrid] Found', tiles.length, 'tiles to make clickable');

            tiles.forEach(tile => {
                tile.title = 'Click to view in focus mode';
            });
        }
        return {
            initPageGridsFromJSON,
            setupTileClickEvents
        };
    })();

    // ============================================
    // 9. MODULE: GRID STATE OBSERVER
    // ============================================
    const GridStateObserver = (function() {
        let observerTimeout = null;
        let lastGridStateLocal = null;

        function observeGridState() {
            const observer = new MutationObserver((mutations) => {

                // Ignore mutations triggered by Plotly
                const isPlotlyMutation = mutations.some(m => {
                    const target = m.target;
                    return (
                        target.closest?.(".js-plotly-plot") ||    // chart root
                        target.closest?.(".plot-container") ||    // dash graph wrapper
                        target.classList?.contains("js-plotly-plot")
                    );
                });

                if (isPlotlyMutation) {
                    // Do nothing, we ignore Plotly mutations
                    return;
                }

                // Debounce
                if (observerTimeout) clearTimeout(observerTimeout);

                observerTimeout = setTimeout(() => {
                    try {
                        const dashboardGrid = document.querySelector('#grid-root-wrapper .grid-stack');
                        const pageGrids = document.querySelectorAll('.page-grid-stack');

                        // Visibility detection
                        const dashboardVisible = dashboardGrid &&
                            dashboardGrid.offsetParent !== null &&
                            getComputedStyle(dashboardGrid).display !== 'none' &&
                            dashboardGrid.getBoundingClientRect().width > 0;

                        const pageGridVisible = Array.from(pageGrids).some(grid =>
                            grid.offsetParent !== null &&
                            getComputedStyle(grid).display !== 'none' &&
                            grid.getBoundingClientRect().width > 0
                        );

                        const currentState = {
                            dashboard: dashboardVisible,
                            pageGrid: pageGridVisible,
                            timestamp: Date.now(),
                        };

                        // Transitory states
                        if (lastGridStateLocal) {

                            // Teams → Dashboard
                            if (lastGridStateLocal.pageGrid && !currentState.pageGrid && currentState.dashboard) {
                                console.log('[GridStateObserver] Transition detected: Teams → Dashboard');
                                CleanupManager.safeCleanupPageGrids();
                                if (GlobalState.grid) CleanupManager.safeDestroyGrid();
                                setTimeout(MainGridStack.tryInitGridStack, 50);
                            }

                            // Dashboard → Teams
                            else if (lastGridStateLocal.dashboard && !currentState.dashboard && currentState.pageGrid) {
                                 console.log('[GridStateObserver] Transition detected: Dashboard → Teams');
                                if (GlobalState.grid) CleanupManager.safeDestroyGrid();
                                setTimeout(PageGrids.initPageGridsFromJSON, 50);
                            }
                        }

                        lastGridStateLocal = currentState;

                        // Simple Initialization Logic
                        if (currentState.dashboard && !GlobalState.grid) {
                            console.log('[GridStateObserver] Dashboard visible, initializing');
                            MainGridStack.tryInitGridStack();
                        } else if (currentState.pageGrid) {
                            console.log('[GridStateObserver] Page grid visible, initializing');
                            PageGrids.initPageGridsFromJSON();
                        } else if (!currentState.dashboard && !currentState.pageGrid && GlobalState.grid) {
                            console.log('[GridStateObserver] Nothing visible, cleaning up');
                            CleanupManager.safeDestroyGrid();
                            CleanupManager.safeCleanupPageGrids();
                        }
                    } catch (err) {
                        console.error('[GridStateObserver] Error', err);
                    }

                }, 120);

            });

            observer.observe(document.body, {
                childList: true,
                subtree: true,
            });

            console.log('[GridStack] Grid state observer started');
        }

        return { observeGridState };
    })();

    // ============================================
    // 10. MODULE: PLOTLY RESIZER
    // ============================================
    const PlotlyResizer = (function() {
        let resizeTimeout = null;
        let resizeObserver = null;

        /**
         * Force Plotly charts to resize to fit their containers
         */
        function forcePlotlyResize() {
            console.debug('[PlotlyResizer] Forcing resize of Plotly charts');

            // Resize all visible Plotly charts
            const plotlyContainers = document.querySelectorAll('.js-plotly-plot, .plot-container.plotly');

            plotlyContainers.forEach(container => {
                try {
                    // Method 1: Use the Plotly API if available
                    if (typeof Plotly === 'object' && Plotly.Plots && container.__plotly) {
                        Plotly.Plots.resize(container);
                        console.debug('[PlotlyResizer] Resized via Plotly API');
                        return;
                    }

                    // Method 2: Dispatch a resize event
                    if (typeof Event === 'function') {
                        const resizeEvent = new Event('resize');
                        window.dispatchEvent(resizeEvent);
                        container.dispatchEvent(resizeEvent);
                    }

                    // Method 3: Force a layout reflow
                    if (container.parentNode) {
                        const parent = container.parentNode;
                        const originalDisplay = parent.style.display;

                        // Force a reflow
                        parent.style.display = 'none';
                        // eslint-disable-next-line no-unused-expressions
                        parent.offsetHeight;
                        parent.style.display = originalDisplay;
                    }

                    // Method 4: If this is a Dash graph container
                    const dashGraph = container.closest('.dash-graph');
                    if (dashGraph && dashGraph.style) {
                        // Force recalculation of dimensions
                        dashGraph.style.width = '100%';
                        dashGraph.style.height = '100%';
                        dashGraph.style.minHeight = '0';
                        dashGraph.style.flex = '1 1 auto';
                    }

                } catch (error) {
                    console.warn('[PlotlyResizer] Error resizing plotly container:', error);
                }
            });

            // Resize Dash charts by ID
            const dashGraphs = document.querySelectorAll('[id$="-graph"]');
            dashGraphs.forEach(graph => {
                try {
                    // Get the full ID
                    const graphId = graph.id;
                    console.debug(`[PlotlyResizer] Processing Dash graph: ${graphId}`);

                    // Ensure the container has valid dimensions
                    const container = graph.closest('.tile-body') || graph.closest('.grid-stack-item');
                    if (container) {
                        const containerRect = container.getBoundingClientRect();
                        if (containerRect.width > 0 && containerRect.height > 0) {
                            // Adjust graph styles
                            graph.style.width = '100%';
                            graph.style.height = '100%';
                            graph.style.minHeight = '0';
                            graph.style.flex = '1 1 auto';

                            // If Plotly is loaded, call resize
                            if (typeof Plotly === 'object' && Plotly.Plots) {
                                Plotly.Plots.resize(graph);
                            }
                        }
                    }
                } catch (error) {
                    console.warn(`[PlotlyResizer] Error resizing graph ${graph.id}:`, error);
                }
            });
        }

        /**
         * Debounced resize to avoid calling resize too frequently
         */
        function debouncedResize() {
            if (resizeTimeout) {
                clearTimeout(resizeTimeout);
            }

            resizeTimeout = setTimeout(() => {
                forcePlotlyResize();
            }, 150); // Delay 150ms
        }

        /**
         * Observe size changes of GridStack widgets
         */
        function setupGridStackResizeObserver() {
            if (resizeObserver) {
                resizeObserver.disconnect();
            }

            // Create an observer for widget attribute changes
            resizeObserver = new MutationObserver((mutations) => {
                let needsResize = false;

                mutations.forEach((mutation) => {
                    // If a GridStack widget changes size
                    if (mutation.type === 'attributes' &&
                        (mutation.attributeName === 'gs-w' ||
                         mutation.attributeName === 'gs-h' ||
                         mutation.attributeName === 'style')) {

                        const widget = mutation.target;
                        // Check whether the widget contains a chart
                        if (widget.querySelector && widget.querySelector('.js-plotly-plot')) {
                            needsResize = true;
                        }
                    }

                    // If nodes are added (new charts)
                    if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                        for (let i = 0; i < mutation.addedNodes.length; i++) {
                            const node = mutation.addedNodes[i];
                            if (node.nodeType === Node.ELEMENT_NODE) {
                                if (node.querySelector && node.querySelector('.js-plotly-plot')) {
                                    needsResize = true;
                                    break;
                                }
                            }
                        }
                    }
                });

                if (needsResize) {
                    console.debug('[PlotlyResizer] GridStack resize detected, updating plots');
                    debouncedResize();
                }
            });

            // Observe all GridStack items
            const gridItems = document.querySelectorAll('.grid-stack-item');
            gridItems.forEach(item => {
                resizeObserver.observe(item, {
                    attributes: true,
                    attributeFilter: ['gs-w', 'gs-h', 'style'],
                    childList: true,
                    subtree: true
                });
            });

            console.debug('[PlotlyResizer] GridStack resize observer setup complete');
        }

        /**
         * Watch window size changes and trigger resizes accordingly
         */
        function setupWindowResizeHandler() {
            // Resize when the window is resized
            window.addEventListener('resize', debouncedResize);

            // Resize after full page load
            window.addEventListener('load', () => {
                setTimeout(debouncedResize, 500);
            });

        }

        /**
         * Apply responsive styles for Plotly and GridStack widgets.
         */
        function applyResponsiveStyles() {
            const linkId = 'plotly-responsive-styles-link';
            let linkElement = document.getElementById(linkId);

            // If the stylesheet is already present, just return
            if (linkElement) {
                console.debug('[PlotlyResizer] Responsive stylesheet already present');
                return;
            }

            // Create a <link> to the external stylesheet. Keep path consistent
            // with project assets. Update the href if your static server serves
            // assets from a different location.
            linkElement = document.createElement('link');
            linkElement.id = linkId;
            linkElement.rel = 'stylesheet';
            linkElement.type = 'text/css';
            linkElement.href = '/assets/css/plotly-responsive.css';

            // When stylesheet loads, trigger a debounced resize to ensure
            // charts pick up the new rules.
            linkElement.onload = function() {
                console.debug('[PlotlyResizer] Responsive stylesheet loaded');
                try { debouncedResize(); } catch (e) { /* ignore */ }
            };

            linkElement.onerror = function(err) {
                console.warn('[PlotlyResizer] Failed to load responsive stylesheet:', err);
            };

            document.head.appendChild(linkElement);
            console.debug('[PlotlyResizer] Responsive stylesheet appended');
        }

        /**
         * Initialize the Plotly resizer module
         */
        function init() {
            console.log('[PlotlyResizer] Initializing...');

            // Apply responsive styles
            applyResponsiveStyles();

            // Set up event handlers
            setupWindowResizeHandler();

            // Trigger initial resize after a short delay
            setTimeout(() => {
                debouncedResize();
                setupGridStackResizeObserver();
            }, 1000);

            // Watch for new Plotly charts added to the DOM
            const graphObserver = new MutationObserver((mutations) => {
                let newGraphs = false;

                mutations.forEach((mutation) => {
                    if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                        for (let i = 0; i < mutation.addedNodes.length; i++) {
                            const node = mutation.addedNodes[i];
                            if (node.nodeType === Node.ELEMENT_NODE) {
                                if (node.classList &&
                                    (node.classList.contains('js-plotly-plot') ||
                                     node.classList.contains('dash-graph'))) {
                                    newGraphs = true;
                                } else if (node.querySelector &&
                                          node.querySelector('.js-plotly-plot, .dash-graph')) {
                                    newGraphs = true;
                                }
                            }
                        }
                    }
                });

                if (newGraphs) {
                    console.debug('[PlotlyResizer] New Plotly charts detected');
                    setTimeout(debouncedResize, 200);
                }
            });

            graphObserver.observe(document.body, {
                childList: true,
                subtree: true
            });

            console.log('[PlotlyResizer] Initialization complete');
        }

        /**
         * Public API
         */
        return {
            init,
            forcePlotlyResize,
            debouncedResize,
            setupGridStackResizeObserver,
            applyResponsiveStyles
        };
    })();

    // ============================================
    // 12. MODULE: FILTER BADGE MANAGER
    // ============================================
    const FilterBadgeManager = (function() {
        /**
         * Update the badges and tooltips for multi-select dropdowns.
         */
        function updateSelectBadges() {
            document.querySelectorAll('.Select--multi').forEach(select => {
                const valuesWrapper = select.querySelector('.Select-multi-value-wrapper');
                if (!valuesWrapper) return;

                // Count selected events
                const selectedValues = select.querySelectorAll('.Select-value');
                const selectedCount = selectedValues.length;

                // Get labels of selected items
                const selectedLabels = Array.from(selectedValues)
                    .map(value => value.querySelector('.Select-value-label')?.textContent || '')
                    .filter(label => label.trim() !== '');

                // Update data attributes
                valuesWrapper.setAttribute('data-selected-count',
                    selectedCount > 0 ? selectedCount : '');

                // Create the tooltip
                let tooltipText = 'Selected:';
                if (selectedLabels.length > 0) {
                    tooltipText += '\n' + selectedLabels.join('\n - ');
                } else {
                    tooltipText = 'No items selected';
                }

                valuesWrapper.setAttribute('data-tooltip', tooltipText);

                // Handle placeholder
                const placeholder = select.querySelector('.Select-placeholder');
                if (placeholder) {
                    // Save original placeholder text
                    if (!placeholder.dataset.originalText) {
                        placeholder.dataset.originalText = placeholder.textContent;
                    }

                    if (selectedCount > 0) {
                        placeholder.textContent = selectedLabels[0] || 'Multiple selected';
                        if (selectedCount > 1) {
                            placeholder.textContent += ` (+${selectedCount - 1})`;
                        }
                    } else {
                        placeholder.textContent = placeholder.dataset.originalText;
                    }
                }
            });
        }

        /**
         * Observe changes in the select dropdowns to update badges dynamically.
         */
        function observeSelectChanges() {
            const observer = new MutationObserver((mutations) => {
                let shouldUpdate = false;
                mutations.forEach(mutation => {
                    if (mutation.type === 'childList' ||
                        mutation.type === 'attributes' ||
                        (mutation.target && mutation.target.classList &&
                        mutation.target.classList.contains('Select-value'))) {
                        shouldUpdate = true;
                    }
                });
                if (shouldUpdate) {
                    setTimeout(updateSelectBadges, 0);
                }
            });

            // Observe all dropdowns
            document.querySelectorAll('.Select').forEach(select => {
                observer.observe(select, {
                    childList: true,
                    subtree: true,
                    attributes: true,
                    attributeFilter: ['class']
                });
            });

            // Initial update
            setTimeout(updateSelectBadges, 100);
        }

        /**
         * Initialise the FilterBadgeManager module
         */
        function init() {
            console.log('[FilterBadgeManager] Initializing...');

            // Wait for select elements to be available
            const checkSelectsInterval = setInterval(() => {
                const selects = document.querySelectorAll('.Select');
                if (selects.length > 0) {
                    clearInterval(checkSelectsInterval);
                    observeSelectChanges();
                    console.log('[FilterBadgeManager] Selects found, badges initialized');
                }
            }, 500);

            // Listen for global DOM changes to re-apply observers
            const globalObserver = new MutationObserver((mutations) => {
                mutations.forEach(mutation => {
                    if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                        mutation.addedNodes.forEach(node => {
                            if (node.nodeType === Node.ELEMENT_NODE) {
                                if (node.classList && node.classList.contains('Select')) {
                                    observeSelectChanges();
                                } else if (node.querySelector && node.querySelector('.Select')) {
                                    observeSelectChanges();
                                }
                            }
                        });
                    }
                });
            });

            globalObserver.observe(document.body, {
                childList: true,
                subtree: true
            });
        }

        /**
         * Reinitialize the select badges and tooltips after navigation or reset
         */
        function reset() {
            document.querySelectorAll('.Select--multi .Select-multi-value-wrapper').forEach(wrapper => {
                wrapper.removeAttribute('data-selected-count');
                wrapper.removeAttribute('data-tooltip');
            });

            document.querySelectorAll('.Select-placeholder').forEach(placeholder => {
                if (placeholder.dataset.originalText) {
                    placeholder.textContent = placeholder.dataset.originalText;
                }
            });

            setTimeout(updateSelectBadges, 100);
        }

        return {
            init,
            reset,
            updateSelectBadges
        };
    })();

    // ============================================
    // 13. Player dropdown monitor
    // ============================================
    const PlayerSync = (function() {
        console.log('[PlayerSync] Module initialized');

        let currentPlayer = null;
        let isInitialized = false;
        let monitoringInterval = null;
        let initializationInterval = null;

        // Get current player from dropdown
        function getCurrentPlayer() {
            const labelElement = document.querySelector('#react-select-2--value-item') ||
                                document.querySelector('#player_focus-player .Select-value-label');

            if (!labelElement) return null;

            return labelElement.textContent.trim();
        }

        // Send player data to Dash store
        function sendToStore(playerLabel) {
            console.log(`[PlayerSync] Sending to store: ${playerLabel}`);

            const playerId = extractPlayerId(playerLabel);
            const payload = {
                player_label: playerLabel,
                player_id: playerId,
                timestamp: Date.now(),
                source: 'player_dropdown'
            };

            // Use dash_clientside.set_props for reliable store updates
            if (window.dash_clientside && window.dash_clientside.set_props) {
                try {
                    window.dash_clientside.set_props('player-filter-store', {
                        data: payload
                    });
                    console.log('[PlayerSync] Store update successful');
                } catch (error) {
                    console.error('[PlayerSync] Store update failed:', error);
                }
            } else {
                console.warn('[PlayerSync] dash_clientside.set_props not available');
            }
        }

        // Extract player ID (simplified - adjust as needed)
        function extractPlayerId(playerLabel) {
            // Check dropdown options for ID
            try {
                const dropdown = document.querySelector('#player_focus-player');
                if (dropdown) {
                    const options = dropdown.querySelectorAll('.Select-option');
                    for (const option of options) {
                        if (option.textContent === playerLabel) {
                            return option.getAttribute('data-value') || playerLabel;
                        }
                    }
                }
            } catch (e) {
                console.warn('[PlayerSync] Could not extract player ID:', e);
            }

            return playerLabel; // Fallback
        }

        // Monitor dropdown for changes
        function startMonitoring() {
            console.log('[PlayerSync] Starting dropdown monitoring');

            // Clear any existing monitoring interval
            if (monitoringInterval) {
                clearInterval(monitoringInterval);
            }

            monitoringInterval = setInterval(() => {
                const newPlayer = getCurrentPlayer();

                if (newPlayer && newPlayer !== currentPlayer) {
                    console.log(`[PlayerSync] Player changed: ${currentPlayer} -> ${newPlayer}`);
                    currentPlayer = newPlayer;

                    sendToStore(newPlayer);

                    // Dispatch custom event for other listeners
                    document.dispatchEvent(new CustomEvent('playerChanged', {
                        detail: { playerLabel: newPlayer }
                    }));
                }
            }, 300); // Check every 300ms
        }

        // Check if dropdown exists and initialize monitoring
        function checkAndInitialize() {
            const dropdown = document.querySelector('#player_focus-player');

            if (dropdown && !isInitialized) {
                console.log('[PlayerSync] Dropdown found, initializing...');

                // Clear any existing initialization interval
                if (initializationInterval) {
                    clearInterval(initializationInterval);
                    initializationInterval = null;
                }

                // Get initial value
                currentPlayer = getCurrentPlayer();
                console.log(`[PlayerSync] Initial player: ${currentPlayer || 'None'}`);

                // Start monitoring
                startMonitoring();
                isInitialized = true;

                console.log('[PlayerSync] Initialization complete');
                return true;
            }

            if (!dropdown && isInitialized) {
                // Dropdown was removed (page navigation)
                console.log('[PlayerSync] Dropdown disappeared - resetting for page navigation');
                reset();
            }

            return false;
        }

        // Reset the module (for page navigation)
        function reset() {
            if (monitoringInterval) {
                clearInterval(monitoringInterval);
                monitoringInterval = null;
            }

            if (initializationInterval) {
                clearInterval(initializationInterval);
                initializationInterval = null;
            }

            currentPlayer = null;
            isInitialized = false;
            console.log('[PlayerSync] Reset for page navigation');
        }

        // Initialize the module with persistent checking
        function init() {
            if (isInitialized) {
                console.log('[PlayerSync] Already initialized');
                return;
            }

            console.log('[PlayerSync] Starting initialization with persistent checking...');

            // Initial check
            checkAndInitialize();

            // Start persistent checking interval (checks every 2 seconds)
            initializationInterval = setInterval(() => {
                if (!isInitialized) {
                    console.log('[PlayerSync] Persistent check for dropdown...');
                    checkAndInitialize();
                }
            }, 2000);

            // Listen for page navigation events
            setupNavigationListeners();

            console.log('[PlayerSync] Initialization started (persistent mode)');
        }

        // Setup listeners for page navigation
        function setupNavigationListeners() {
            // Listen for custom events that might indicate page changes
            document.addEventListener('playerDropdownReset', reset);

            // Listen for URL hash changes (single-page app navigation)
            window.addEventListener('hashchange', () => {
                console.log('[PlayerSync] Hash change detected, resetting...');
                setTimeout(reset, 100);
            });

            // Observe DOM changes that might indicate new page content
            const domObserver = new MutationObserver((mutations) => {
                for (const mutation of mutations) {
                    if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                        // Check if new content was added that might contain the dropdown
                        for (const node of mutation.addedNodes) {
                            if (node.nodeType === Node.ELEMENT_NODE) {
                                if (node.querySelector && node.querySelector('#player_focus-player')) {
                                    console.log('[PlayerSync] Dropdown added to DOM via mutation');
                                    setTimeout(() => checkAndInitialize(), 500);
                                    break;
                                }
                            }
                        }
                    }
                }
            });

            domObserver.observe(document.body, {
                childList: true,
                subtree: true
            });
        }

        // Public API
        return {
            init,
            reset,
            getCurrentPlayer: getCurrentPlayer,
            sendToStore: sendToStore,
            isInitialized: () => isInitialized
        };
    })();

    // ============================================
    // 15. MAIN INITIALIZATION
    // ============================================

    // Setup navigation listeners immediately
    NavigationManager.setupNavigationButtonListeners();

    // Start grid state observer
    GridStateObserver.observeGridState();

    // Initialize Plotly resizer
    PlotlyResizer.init();

    // Initialize PlayerSync with persistent checking
    PlayerSync.init();

    // Expose tryInitGridStack for external callers
    window.tryInitGridStack = MainGridStack.tryInitGridStack;

    // Expose Plotly resizer functions
    window.forcePlotlyResize = PlotlyResizer.forcePlotlyResize;
    window.debouncedPlotlyResize = PlotlyResizer.debouncedResize;

    // Expose filter sync
    window.PlayerSync = PlayerSync;

    // Expose a manual reset function for debugging
    window.resetPlayerSync = function() {
        console.log('[Debug] Manually resetting PlayerSync');
        PlayerSync.reset();
        setTimeout(() => PlayerSync.init(), 1000);
    };

    console.log('[Debug] Player sync script loaded with persistent dropdown detection');

})();
