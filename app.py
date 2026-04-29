"""
app.py
------
Main Dash application entry point.
Assembles the layout and registers all interactive callbacks.

Run with:
    python app.py
Then open: http://localhost:8050
"""

import json
import pandas as pd
import networkx as nx
from dash import Dash, Input, Output, State, html, dcc, callback_context, no_update

# Internal modules
from src.graph_loader import parse_upload, load_graph_from_dataframes, get_graph_summary
from src.metrics import (
    compute_degree_distribution,
    compute_clustering_coefficient,
    compute_average_path_length,
    compute_centralities,
    compute_graph_stats,
    get_centrality_ranges,
)
from src.community import compare_algorithms, detect_louvain, detect_girvan_newman, partition_from_list, compute_modularity
from src.layout import get_layout
from src.link_analysis import compute_pagerank, compute_betweenness_centrality, get_top_nodes, scale_values, get_node_ranking_color
from src.evaluation import evaluate_partition
from src.link_prediction import predict_links, evaluate_link_prediction

from ui.styles import COLORS, STYLE_APP, STYLE_HEADER, STYLE_MAIN
from ui.sidebar import build_sidebar
from ui.graph_panel import build_graph_panel, build_cytoscape_elements, format_node_info
from ui.metrics_panel import (
    build_metrics_panel,
    build_stats_bar,
    build_degree_distribution_chart,
    build_community_comparison,
    build_evaluation_table,
    build_top_nodes_table,
    build_link_prediction_table,
    build_link_prediction_eval,
)

# ─── App initialisation ───────────────────────────────────────────────────────

app = Dash(
    __name__,
    title="Social Network Analysis Tool",
    suppress_callback_exceptions=True,
)

# ─── Layout ───────────────────────────────────────────────────────────────────

app.layout = html.Div(
    style=STYLE_APP,
    children=[
        # Global state stores (invisible)
        dcc.Store(id="store-nodes-raw"),   # Serialised nodes DataFrame JSON
        dcc.Store(id="store-edges-raw"),   # Serialised edges DataFrame JSON
        dcc.Store(id="store-graph-data"),  # Serialised graph elements + metadata
        dcc.Store(id="store-centralities"), # {node: {metric: value}} JSON
        dcc.Store(id="store-community"),   # current active partition dict JSON
        dcc.Store(id="store-comparison"),  # full comparison result JSON
        dcc.Store(id="store-pagerank"),    # pagerank scores JSON
        dcc.Store(id="store-betweenness"), # betweenness scores JSON
        dcc.Store(id="store-lp-predictions"), # link prediction results JSON
        dcc.Store(id="store-lp-evaluation"),  # link prediction eval JSON

        # Download components for export
        dcc.Download(id="download-nodes-csv"),
        dcc.Download(id="download-edges-csv"),
        dcc.Download(id="download-graph-json"),

        # ── Header ──────────────────────────────────────────────────────────
        html.Div(
            style=STYLE_HEADER,
            children=[
                html.Div([
                    html.Span("⬡", style={"fontSize": "22px", "marginRight": "10px"}),
                    html.Span("Social Network Analysis Tool", style={
                        "fontSize": "16px",
                        "fontWeight": "700",
                        "letterSpacing": "0.02em",
                    }),
                ], style={"display": "flex", "alignItems": "center"}),
                html.Div(
                    id="header-status",
                    style={"fontSize": "12px", "opacity": "0.8", "color": "#cde"},
                    children="Ready — load a graph to begin",
                ),
            ],
        ),

        # ── Body (sidebar + main) ──────────────────────────────────────────
        html.Div(
            style={"display": "flex", "flex": "1", "overflow": "hidden", "height": f"calc(100vh - 60px)"},
            children=[
                build_sidebar(),

                # Main area
                html.Div(
                    style={**STYLE_MAIN, "overflow": "hidden"},
                    children=[
                        build_graph_panel(),
                        build_metrics_panel(),
                    ],
                ),
            ],
        ),
    ],
)


# ─── Helper utilities ─────────────────────────────────────────────────────────

def _build_graph_from_stores(nodes_json, edges_json, directed: bool) -> nx.Graph:
    """Reconstruct a NetworkX graph from stored JSON DataFrames."""
    nodes_df = pd.read_json(nodes_json, dtype=str) if nodes_json else None
    edges_df = pd.read_json(edges_json) if edges_json else None
    if nodes_df is not None and "id" not in nodes_df.columns:
        nodes_df = None
    return load_graph_from_dataframes(nodes_df, edges_df, directed=directed)


def _get_community_colors(partition: dict) -> dict:
    """Map a node->community_id partition to hex colors."""
    palette = COLORS["node_communities"]
    return {node: palette[cid % len(palette)] for node, cid in partition.items()}


def _get_centrality_colors(centrality_scores: dict, colorscale: str = "plasma") -> dict:
    """Map centrality score dict to hex colors using a colorscale."""
    return get_node_ranking_color(centrality_scores, colorscale=colorscale)


def _get_group_colors(G: nx.Graph) -> dict:
    """Color nodes by their 'group' attribute from the nodes CSV."""
    palette = COLORS["node_communities"]
    colors = {}
    for node in G.nodes():
        group = G.nodes[node].get("group", "0")
        try:
            cid = int(float(str(group))) - 1
        except (ValueError, TypeError):
            cid = 0
        colors[str(node)] = palette[cid % len(palette)]
    return colors


# ─── Callbacks ────────────────────────────────────────────────────────────────

# 1. Store uploaded nodes CSV ─────────────────────────────────────────────────
@app.callback(
    Output("store-nodes-raw", "data"),
    Output("nodes-upload-status", "children"),
    Input("upload-nodes", "contents"),
    Input("btn-load-sample", "n_clicks"),
    prevent_initial_call=True,
)
def store_nodes(contents, n_clicks):
    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

    if "btn-load-sample" in trigger:
        try:
            df = pd.read_csv("data/sample_nodes.csv")
            return df.to_json(), f"✔ Sample nodes loaded ({len(df)} rows)"
        except Exception as e:
            return no_update, f"⚠ Error: {e}"

    if contents:
        df = parse_upload(contents)
        if df is not None:
            return df.to_json(), f"✔ Nodes loaded ({len(df)} rows)"
        return no_update, "⚠ Failed to parse nodes file"

    return no_update, ""


# 2. Store uploaded edges CSV ─────────────────────────────────────────────────
@app.callback(
    Output("store-edges-raw", "data"),
    Output("edges-upload-status", "children"),
    Input("upload-edges", "contents"),
    Input("btn-load-sample", "n_clicks"),
    prevent_initial_call=True,
)
def store_edges(contents, n_clicks):
    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

    if "btn-load-sample" in trigger:
        try:
            df = pd.read_csv("data/sample_edges.csv")
            return df.to_json(), f"✔ Sample edges loaded ({len(df)} rows)"
        except Exception as e:
            return no_update, f"⚠ Error: {e}"

    if contents:
        df = parse_upload(contents)
        if df is not None:
            return df.to_json(), f"✔ Edges loaded ({len(df)} rows)"
        return no_update, "⚠ Failed to parse edges file"

    return no_update, ""


# 3. Build graph + compute centralities ───────────────────────────────────────
@app.callback(
    Output("store-graph-data", "data"),
    Output("store-centralities", "data"),
    Output("store-pagerank", "data"),
    Output("store-betweenness", "data"),
    Output("header-status", "children"),
    Input("btn-build-graph", "n_clicks"),
    Input("btn-load-sample", "n_clicks"),
    State("store-nodes-raw", "data"),
    State("store-edges-raw", "data"),
    State("radio-graph-type", "value"),
    prevent_initial_call=True,
)
def build_graph(n_build, n_sample, nodes_json, edges_json, graph_type):
    if not nodes_json and not edges_json:
        return no_update, no_update, no_update, no_update, "⚠ No data loaded"

    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

    # Give sample data a moment to be stored first
    if "btn-load-sample" in trigger:
        try:
            nodes_df = pd.read_csv("data/sample_nodes.csv")
            edges_df = pd.read_csv("data/sample_edges.csv")
        except Exception as e:
            return no_update, no_update, no_update, no_update, f"⚠ Sample load error: {e}"
    else:
        nodes_df = pd.read_json(nodes_json, dtype=str) if nodes_json else None
        edges_df = pd.read_json(edges_json) if edges_json else None

    directed = (graph_type == "directed")
    G = load_graph_from_dataframes(nodes_df, edges_df, directed=directed)

    centralities = compute_centralities(G)
    pagerank = compute_pagerank(G)
    betweenness = compute_betweenness_centrality(G)

    summary = get_graph_summary(G)
    status = (
        f"Graph: {summary['num_nodes']} nodes, {summary['num_edges']} edges — "
        f"{'Directed' if summary['is_directed'] else 'Undirected'} — "
        f"{'Connected' if summary['is_connected'] else 'Disconnected'}"
    )

    # Serialize graph data as JSON-safe dict
    graph_meta = {
        "directed": directed,
        "nodes": [
            {"id": str(n), **{k: str(v) for k, v in G.nodes[n].items()}}
            for n in G.nodes()
        ],
        "edges": [
            {"source": str(u), "target": str(v), **{k: str(v2) for k, v2 in d.items()}}
            for u, v, d in G.edges(data=True)
        ],
    }

    return (
        json.dumps(graph_meta),
        json.dumps(centralities),
        json.dumps(pagerank),
        json.dumps(betweenness),
        status,
    )


# 4. Run community detection ──────────────────────────────────────────────────
@app.callback(
    Output("store-community", "data"),
    Output("store-comparison", "data"),
    Input("btn-run-community", "n_clicks"),
    Input("btn-build-graph", "n_clicks"),
    Input("btn-load-sample", "n_clicks"),
    State("store-nodes-raw", "data"),
    State("store-edges-raw", "data"),
    State("radio-graph-type", "value"),
    State("dropdown-community-algo", "value"),
    State("slider-gn-k", "value"),
    prevent_initial_call=True,
)
def run_community(n_comm, n_build, n_sample, nodes_json, edges_json, graph_type, algo, gn_k):
    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

    try:
        if "btn-load-sample" in trigger:
            nodes_df = pd.read_csv("data/sample_nodes.csv")
            edges_df = pd.read_csv("data/sample_edges.csv")
            directed = False
        else:
            if not nodes_json and not edges_json:
                return no_update, no_update
            nodes_df = pd.read_json(nodes_json, dtype=str) if nodes_json else None
            edges_df = pd.read_json(edges_json) if edges_json else None
            directed = (graph_type == "directed")

        G = load_graph_from_dataframes(nodes_df, edges_df, directed=directed)
        comparison = compare_algorithms(G, gn_k=int(gn_k or 4))

        # Select active partition based on chosen algorithm
        if algo == "girvan_newman":
            active_partition = comparison["girvan_newman"]["partition"]
        else:
            # Default to Louvain
            active_partition = comparison["louvain"]["partition"]

        return json.dumps(active_partition), json.dumps(comparison)
    except Exception as e:
        print(f"[community callback] Error: {e}")
        return no_update, no_update


# 5. Render graph (cytoscape elements) ───────────────────────────────────────
@app.callback(
    Output("cytoscape-graph", "elements"),
    Output("graph-status-badge", "children"),
    Input("store-graph-data", "data"),
    Input("store-community", "data"),
    Input("store-centralities", "data"),
    Input("store-pagerank", "data"),
    Input("store-betweenness", "data"),
    Input("dropdown-layout", "value"),
    Input("dropdown-color-by", "value"),
    Input("dropdown-size-by", "value"),
    Input("slider-node-size", "value"),
    Input("slider-edge-thickness", "value"),
    Input("filter-degree", "value"),
    Input("filter-betweenness", "value"),
    Input("filter-closeness", "value"),
    Input("check-link-analysis", "value"),
    Input("slider-top-n", "value"),
    prevent_initial_call=True,
)
def render_graph(
    graph_json, community_json, centralities_json,
    pagerank_json, betweenness_json,
    layout_name, color_by, size_by,
    node_size, edge_thickness,
    filter_degree, filter_betweenness, filter_closeness,
    link_checks, top_n,
):
    if not graph_json:
        return [], "No graph loaded"

    try:
        graph_meta = json.loads(graph_json)
        directed = graph_meta.get("directed", False)
        centralities = json.loads(centralities_json) if centralities_json else {}
        pagerank = json.loads(pagerank_json) if pagerank_json else {}
        betweenness = json.loads(betweenness_json) if betweenness_json else {}
        community = json.loads(community_json) if community_json else {}

        # Rebuild NetworkX graph from stored meta
        G = nx.DiGraph() if directed else nx.Graph()
        for n in graph_meta["nodes"]:
            node_id = n["id"]
            G.add_node(node_id, **{k: v for k, v in n.items() if k != "id"})
        for e in graph_meta["edges"]:
            G.add_edge(e["source"], e["target"], **{k: v for k, v in e.items() if k not in ("source", "target")})

        # ── Centrality filtering ──────────────────────────────────────────
        d_lo, d_hi = filter_degree or [0, 1]
        b_lo, b_hi = filter_betweenness or [0, 1]
        c_lo, c_hi = filter_closeness or [0, 1]

        hidden_nodes = set()
        for node_id, metrics in centralities.items():
            deg = metrics.get("degree", 0)
            bet = metrics.get("betweenness", 0)
            clo = metrics.get("closeness", 0)
            if not (d_lo <= deg <= d_hi and b_lo <= bet <= b_hi and c_lo <= clo <= c_hi):
                hidden_nodes.add(node_id)

        # ── Layout ────────────────────────────────────────────────────────
        visible_nodes = [n for n in G.nodes() if str(n) not in hidden_nodes]
        if not visible_nodes:
            return [], f"No nodes match filter ({G.number_of_nodes()} total)"

        subG = G.subgraph(visible_nodes)
        positions = get_layout(subG, layout_name or "spring")

        # ── Link analysis highlight ───────────────────────────────────────
        link_checks = link_checks or []
        highlight_nodes = set()
        if "pagerank" in link_checks and pagerank:
            top = get_top_nodes(pagerank, top_n=int(top_n or 5))
            highlight_nodes.update(n for n, _ in top)
        if "betweenness" in link_checks and betweenness:
            top = get_top_nodes(betweenness, top_n=int(top_n or 5))
            highlight_nodes.update(n for n, _ in top)

        # ── Node Colors ──────────────────────────────────────────────────
        if color_by == "community" and community:
            node_colors = _get_community_colors(community)
        elif color_by == "pagerank" and pagerank:
            node_colors = _get_centrality_colors(pagerank, "plasma")
        elif color_by == "betweenness" and betweenness:
            node_colors = _get_centrality_colors(betweenness, "magma")
        elif color_by == "degree" and centralities:
            degree_scores = {n: v["degree"] for n, v in centralities.items()}
            node_colors = _get_centrality_colors(degree_scores, "viridis")
        elif color_by == "closeness" and centralities:
            closeness_scores = {n: v["closeness"] for n, v in centralities.items()}
            node_colors = _get_centrality_colors(closeness_scores, "hot")
        elif color_by == "group":
            node_colors = _get_group_colors(G)
        else:
            node_colors = {str(n): COLORS["accent_blue"] for n in G.nodes()}

        # ── Node Sizes ───────────────────────────────────────────────────
        base_ns = float(node_size or 18)
        if size_by == "pagerank" and pagerank:
            node_sizes = scale_values(pagerank, min_size=base_ns * 0.5, max_size=base_ns * 2.5)
        elif size_by == "betweenness" and betweenness:
            node_sizes = scale_values(betweenness, min_size=base_ns * 0.5, max_size=base_ns * 2.5)
        elif size_by == "degree" and centralities:
            degree_scores = {n: v["degree"] for n, v in centralities.items()}
            node_sizes = scale_values(degree_scores, min_size=base_ns * 0.5, max_size=base_ns * 2.5)
        else:
            node_sizes = {str(n): base_ns for n in G.nodes()}

        # ── Build elements ────────────────────────────────────────────────
        elements = build_cytoscape_elements(
            subG, positions, node_colors, node_sizes,
            base_node_size=base_ns,
            base_edge_thickness=float(edge_thickness or 2),
            directed=directed,
            hidden_nodes=set(),  # Already filtered via subG
        )

        # Apply highlight classes for link analysis
        if highlight_nodes:
            for el in elements:
                if "source" not in el["data"]:
                    nid = el["data"]["id"]
                    if nid in highlight_nodes:
                        el["classes"] = "highlighted"
                    else:
                        el["classes"] = "faded"

        n_vis = len(visible_nodes)
        n_total = G.number_of_nodes()
        badge = f"{n_vis} nodes, {subG.number_of_edges()} edges"
        if n_vis < n_total:
            badge += f" (filtered from {n_total})"

        return elements, badge

    except Exception as e:
        print(f"[render_graph] Error: {e}")
        return [], f"Error rendering graph: {str(e)[:60]}"


# 6. Stats bar ─────────────────────────────────────────────────────────────────
@app.callback(
    Output("stats-bar", "children"),
    Input("store-graph-data", "data"),
    prevent_initial_call=True,
)
def update_stats(graph_json):
    if not graph_json:
        return build_stats_bar({})
    try:
        meta = json.loads(graph_json)
        G = nx.DiGraph() if meta.get("directed") else nx.Graph()
        for n in meta["nodes"]:
            G.add_node(n["id"])
        for e in meta["edges"]:
            G.add_edge(e["source"], e["target"])
        stats = compute_graph_stats(G)
        return build_stats_bar(stats)
    except Exception as e:
        return build_stats_bar({})


# 7. Degree distribution chart ────────────────────────────────────────────────
@app.callback(
    Output("degree-dist-chart", "children"),
    Input("store-graph-data", "data"),
    prevent_initial_call=True,
)
def update_degree_dist(graph_json):
    if not graph_json:
        return build_degree_distribution_chart({})
    try:
        meta = json.loads(graph_json)
        G = nx.DiGraph() if meta.get("directed") else nx.Graph()
        for n in meta["nodes"]:
            G.add_node(n["id"])
        for e in meta["edges"]:
            G.add_edge(e["source"], e["target"])
        dist = compute_degree_distribution(G)
        return build_degree_distribution_chart(dist)
    except Exception:
        return build_degree_distribution_chart({})


# 8. Community comparison + evaluation ────────────────────────────────────────
@app.callback(
    Output("community-comparison", "children"),
    Output("evaluation-metrics", "children"),
    Input("store-comparison", "data"),
    Input("store-community", "data"),
    State("store-graph-data", "data"),
    State("store-nodes-raw", "data"),
    prevent_initial_call=True,
)
def update_community_panels(comparison_json, community_json, graph_json, nodes_json):
    comparison_widget = build_community_comparison(None)
    eval_widget = build_evaluation_table(None)

    if comparison_json:
        try:
            comparison = json.loads(comparison_json)
            comparison_widget = build_community_comparison(comparison)
        except Exception:
            pass

    if community_json and graph_json:
        try:
            partition = json.loads(community_json)
            meta = json.loads(graph_json)
            G = nx.DiGraph() if meta.get("directed") else nx.Graph()
            for n in meta["nodes"]:
                G.add_node(n["id"])
            for e in meta["edges"]:
                G.add_edge(e["source"], e["target"])

            # Extract ground-truth labels from nodes CSV if 'group' column exists
            true_labels = None
            if nodes_json:
                try:
                    ndf = pd.read_json(nodes_json, dtype=str)
                    if "group" in ndf.columns and "id" in ndf.columns:
                        true_labels = {str(row["id"]): int(float(row["group"])) - 1 for _, row in ndf.iterrows()}
                except Exception:
                    pass

            evaluation = evaluate_partition(G, partition, true_labels=true_labels)
            eval_widget = build_evaluation_table(evaluation)
        except Exception as e:
            print(f"[eval callback] {e}")

    return comparison_widget, eval_widget


# 9. Link analysis top nodes table ────────────────────────────────────────────
@app.callback(
    Output("link-analysis-table", "children"),
    Input("store-pagerank", "data"),
    Input("store-betweenness", "data"),
    Input("check-link-analysis", "value"),
    Input("slider-top-n", "value"),
    prevent_initial_call=True,
)
def update_link_analysis_table(pagerank_json, betweenness_json, link_checks, top_n):
    link_checks = link_checks or []
    top_n = int(top_n or 5)
    widgets = []

    if "pagerank" in link_checks and pagerank_json:
        try:
            pr = json.loads(pagerank_json)
            top = get_top_nodes(pr, top_n=top_n)
            widgets.append(build_top_nodes_table(top, "PageRank"))
        except Exception:
            pass

    if "betweenness" in link_checks and betweenness_json:
        try:
            bc = json.loads(betweenness_json)
            top = get_top_nodes(bc, top_n=top_n)
            widgets.append(html.Div(style={"marginTop": "12px"}))
            widgets.append(build_top_nodes_table(top, "Betweenness"))
        except Exception:
            pass

    if not widgets:
        return build_top_nodes_table([], "")

    return html.Div(widgets)


# 10. Node info panel on click ─────────────────────────────────────────────────
@app.callback(
    Output("node-info-content", "children"),
    Input("cytoscape-graph", "tapNodeData"),
    State("store-centralities", "data"),
)
def update_node_info(node_data, centralities_json):
    centralities = json.loads(centralities_json) if centralities_json else {}
    return format_node_info(node_data or {}, centralities)


# 11. Fit / Reset zoom buttons ─────────────────────────────────────────────────
app.clientside_callback(
    """
    function(n_fit, n_reset) {
        const ctx = dash_clientside.callback_context;
        if (!ctx.triggered.length) return window.dash_clientside.no_update;
        const tid = ctx.triggered[0].prop_id;
        const cy = document.querySelector('#cytoscape-graph')._cyreg?.cy;
        if (!cy) return window.dash_clientside.no_update;
        if (tid.includes('btn-fit')) cy.fit(cy.elements(), 30);
        if (tid.includes('btn-reset-zoom')) cy.reset();
        return window.dash_clientside.no_update;
    }
    """,
    Output("cytoscape-graph", "zoom"),
    Input("btn-fit", "n_clicks"),
    Input("btn-reset-zoom", "n_clicks"),
    prevent_initial_call=True,
)



# 14. Export: Nodes CSV ────────────────────────────────────────────────────────
@app.callback(
    Output("download-nodes-csv", "data"),
    Input("btn-export-nodes", "n_clicks"),
    State("store-graph-data", "data"),
    prevent_initial_call=True,
)
def export_nodes_csv(n_clicks, graph_json):
    if not graph_json:
        return no_update
    try:
        meta = json.loads(graph_json)
        import io
        nodes_df = pd.DataFrame(meta["nodes"])
        return dcc.send_data_frame(nodes_df.to_csv, "nodes_export.csv", index=False)
    except Exception as e:
        print(f"[export nodes] Error: {e}")
        return no_update


# 15. Export: Edges CSV ────────────────────────────────────────────────────────
@app.callback(
    Output("download-edges-csv", "data"),
    Input("btn-export-edges", "n_clicks"),
    State("store-graph-data", "data"),
    prevent_initial_call=True,
)
def export_edges_csv(n_clicks, graph_json):
    if not graph_json:
        return no_update
    try:
        meta = json.loads(graph_json)
        edges_df = pd.DataFrame(meta["edges"])
        return dcc.send_data_frame(edges_df.to_csv, "edges_export.csv", index=False)
    except Exception as e:
        print(f"[export edges] Error: {e}")
        return no_update


# 16. Export: Full JSON ────────────────────────────────────────────────────────
@app.callback(
    Output("download-graph-json", "data"),
    Input("btn-export-json", "n_clicks"),
    State("store-graph-data", "data"),
    State("store-centralities", "data"),
    State("store-community", "data"),
    State("store-pagerank", "data"),
    State("store-betweenness", "data"),
    State("store-lp-predictions", "data"),
    State("store-lp-evaluation", "data"),
    prevent_initial_call=True,
)
def export_graph_json(n_clicks, graph_json, centralities_json, community_json,
                      pagerank_json, betweenness_json, predictions_json, evaluation_json):
    if not graph_json:
        return no_update
    try:
        export_data = {
            "graph": json.loads(graph_json),
            "centralities": json.loads(centralities_json) if centralities_json else {},
            "community": json.loads(community_json) if community_json else {},
            "pagerank": json.loads(pagerank_json) if pagerank_json else {},
            "betweenness": json.loads(betweenness_json) if betweenness_json else {},
            "link_predictions": json.loads(predictions_json) if predictions_json else [],
            "link_prediction_evaluation": json.loads(evaluation_json) if evaluation_json else {},
        }
        content = json.dumps(export_data, indent=2)
        return dict(content=content, filename="graph_export.json")
    except Exception as e:
        print(f"[export json] Error: {e}")
        return no_update

# 17. Toggle GN-K slider visibility ───────────────────────────────────────────
@app.callback(
    Output("gn-k-container", "style"),
    Input("dropdown-community-algo", "value")
)
def toggle_gn_slider(algo):
    if algo in ("girvan_newman", "both"):
        return {"display": "block"}
    return {"display": "none"}



# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Social Network Analysis Tool")
    print("  Open in browser: http://localhost:8050")
    print("=" * 60)
    app.run(debug=True, port=8050)
