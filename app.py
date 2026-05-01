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
from dash import Dash, Input, Output, State, html, dcc, callback_context, no_update, ALL

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

from ui.styles import COLORS, STYLE_APP, STYLE_HEADER, STYLE_MAIN
from ui.sidebar import build_sidebar
from ui.graph_panel import build_graph_panel, build_cytoscape_elements, format_node_info
from ui.metrics_panel import (
    build_metrics_panel,
    build_stats_bar,
    build_degree_distribution_chart,
    build_community_comparison,
    build_evaluation_table,
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
        dcc.Store(id="store-stats"),       # graph stats JSON
        dcc.Store(id="store-degree-dist"), # degree distribution JSON
        dcc.Store(id="store-node-overrides", data="{}"),  # per-node {id: {color, label}}
        dcc.Store(id="store-selected-node"),              # currently tapped node id
        dcc.Store(id="store-color-picker-value", data="#58a6ff"),  # mirrors html.Input color

        # ── Header ──────────────────────────────────────────────────────────
        html.Div(
            style=STYLE_HEADER,
            children=[
                html.Div([
                    html.Span("", style={"fontSize": "22px", "marginRight": "10px"}),
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
    State("upload-nodes", "filename"),
    prevent_initial_call=True,
)
def store_nodes(contents, n_clicks, filename):
    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

    if "btn-load-sample" in trigger:
        try:
            df = pd.read_csv("data/sample_nodes.csv")
            return df.to_json(), f"Sample nodes loaded ({len(df)} rows)"
        except Exception as e:
            return no_update, f"Error: {e}"

    if contents:
        df = parse_upload(contents)
        if df is not None:
            fname = filename or "Nodes"
            return df.to_json(), f"{fname} loaded ({len(df)} rows)"
        return no_update, "Failed to parse nodes file"

    return no_update, ""


# 2. Store uploaded edges CSV ─────────────────────────────────────────────────
@app.callback(
    Output("store-edges-raw", "data"),
    Output("edges-upload-status", "children"),
    Input("upload-edges", "contents"),
    Input("btn-load-sample", "n_clicks"),
    State("upload-edges", "filename"),
    prevent_initial_call=True,
)
def store_edges(contents, n_clicks, filename):
    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

    if "btn-load-sample" in trigger:
        try:
            df = pd.read_csv("data/sample_edges.csv")
            return df.to_json(), f"Sample edges loaded ({len(df)} rows)"
        except Exception as e:
            return no_update, f"Error: {e}"

    if contents:
        df = parse_upload(contents)
        if df is not None:
            fname = filename or "Edges"
            return df.to_json(), f"{fname} loaded ({len(df)} rows)"
        return no_update, "Failed to parse edges file"

    return no_update, ""


# 3. Build graph + compute centralities ───────────────────────────────────────
@app.callback(
    Output("store-graph-data", "data"),
    Output("store-centralities", "data"),
    Output("store-stats", "data"),
    Output("store-degree-dist", "data"),
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
        return no_update, no_update, no_update, no_update, "No data loaded"

    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

    # Give sample data a moment to be stored first
    if "btn-load-sample" in trigger:
        try:
            nodes_df = pd.read_csv("data/sample_nodes.csv")
            edges_df = pd.read_csv("data/sample_edges.csv")
        except Exception as e:
            return no_update, no_update, no_update, no_update, f"Sample load error: {e}"
    else:
        nodes_df = pd.read_json(nodes_json, dtype=str) if nodes_json else None
        edges_df = pd.read_json(edges_json) if edges_json else None

    directed = (graph_type == "directed")
    
    try:
        G = load_graph_from_dataframes(nodes_df, edges_df, directed=directed)

        centralities = compute_centralities(G)
        stats = compute_graph_stats(G)
        degree_dist = compute_degree_distribution(G)

        summary = get_graph_summary(G)

        status = (
            f"Graph: {summary['num_nodes']} nodes, {summary['num_edges']} edges — "
            f"{'Directed' if summary['is_directed'] else 'Undirected'} — "
            f"{'Connected' if summary['is_connected'] else 'Disconnected'}"
        )
        
        # Serialize full graph data as JSON-safe dict
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
            json.dumps(stats),
            json.dumps(degree_dist),
            status,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return no_update, no_update, no_update, no_update, f"Error building graph: {str(e)}"


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
            from io import StringIO
            nodes_df = pd.read_json(StringIO(nodes_json), dtype=str) if nodes_json else None
            edges_df = pd.read_json(StringIO(edges_json)) if edges_json else None
            directed = (graph_type == "directed")

        G = load_graph_from_dataframes(nodes_df, edges_df, directed=directed)
        comparison = compare_algorithms(G, gn_k=int(gn_k or 4), algo=algo)

        gn_partition  = comparison["girvan_newman"].get("partition", {})
        louv_partition = comparison["louvain"].get("partition", {})

        # Pick the active partition to colour the graph with
        if algo == "girvan_newman":
            # Use GN; fall back to empty or Louvain if GN returned nothing (graph too large)
            active_partition = gn_partition if gn_partition else {}
        elif algo == "both":
            # Show GN if it succeeded, otherwise Louvain
            active_partition = gn_partition if gn_partition else louv_partition
        else:
            active_partition = louv_partition

        print(f"[community] algo={algo}  gn_communities={comparison['girvan_newman']['num_communities']}  louvain_communities={comparison['louvain']['num_communities']}")
        return json.dumps(active_partition), json.dumps(comparison)
    except Exception as e:
        import traceback
        print(f"[community callback] Error: {e}")
        traceback.print_exc()
        return no_update, no_update




# 5. Render graph (cytoscape elements) ───────────────────────────────────────
@app.callback(
    Output("cytoscape-graph", "elements"),
    Output("graph-status-badge", "children"),
    Input("store-graph-data", "data"),
    Input("store-community", "data"),
    Input("store-centralities", "data"),
    Input("dropdown-layout", "value"),
    Input("dropdown-color-by", "value"),
    Input("dropdown-size-by", "value"),
    Input("dropdown-label-by", "value"),
    Input("dropdown-edge-color-by", "value"),
    Input("slider-node-size", "value"),
    Input("slider-edge-thickness", "value"),
    Input("dropdown-centrality-filter", "value"),
    Input("filter-centrality-slider", "value"),
    Input("store-node-overrides", "data"),
    prevent_initial_call=True,
)
def render_graph(
    graph_json, community_json, centralities_json,
    layout_name, color_by, size_by, label_by, edge_color_by,
    node_size, edge_thickness,
    centrality_filter_type, centrality_slider_value,
    overrides_json,
):
    if not graph_json:
        return [], "No graph loaded"

    try:
        graph_meta = json.loads(graph_json)
        directed = graph_meta.get("directed", False)
        centralities = json.loads(centralities_json) if centralities_json else {}
        community = json.loads(community_json) if community_json else {}

        # Rebuild NetworkX graph from stored meta
        G = nx.DiGraph() if directed else nx.Graph()
        for n in graph_meta["nodes"]:
            node_id = n["id"]
            G.add_node(node_id, **{k: v for k, v in n.items() if k != "id"})
        for e in graph_meta["edges"]:
            G.add_edge(e["source"], e["target"], **{k: v for k, v in e.items() if k not in ("source", "target")})

        # ── Centrality filtering ──────────────────────────────────────────
        c_lo, c_hi = centrality_slider_value or [0, 1]

        hidden_nodes = set()
        for node_id, metrics in centralities.items():
            val = metrics.get(centrality_filter_type, 0)
            if not (c_lo <= val <= c_hi):
                hidden_nodes.add(node_id)

        # ── Layout ────────────────────────────────────────────────────────
        visible_nodes = [n for n in G.nodes() if str(n) not in hidden_nodes]
        if not visible_nodes:
            return [], f"No nodes match filter ({G.number_of_nodes()} total)"

        subG = G.subgraph(visible_nodes)
        positions = get_layout(subG, layout_name or "spring")

        # ── Node Colors ──────────────────────────────────────────────────
        if color_by == "community" and community:
            node_colors = _get_community_colors(community)
        elif color_by == "pagerank" and centralities:
            scores = {n: v["pagerank"] for n, v in centralities.items() if "pagerank" in v}
            node_colors = _get_centrality_colors(scores, "plasma")
        elif color_by == "betweenness" and centralities:
            scores = {n: v["betweenness"] for n, v in centralities.items() if "betweenness" in v}
            node_colors = _get_centrality_colors(scores, "magma")
        elif color_by == "degree" and centralities:
            degree_scores = {n: v["degree"] for n, v in centralities.items()}
            node_colors = _get_centrality_colors(degree_scores, "viridis")
        elif color_by == "closeness" and centralities:
            closeness_scores = {n: v["closeness"] for n, v in centralities.items()}
            node_colors = _get_centrality_colors(closeness_scores, "hot")
        elif color_by == "group":
            node_colors = _get_group_colors(G)
        elif color_by and color_by.startswith("node_"):
            attr = color_by[5:]
            attr_vals = {str(n): G.nodes[n].get(attr) for n in G.nodes() if attr in G.nodes[n]}
            try:
                floats = {k: float(v) for k, v in attr_vals.items()}
                node_colors = _get_centrality_colors(floats, "viridis")
                # Fill missing nodes
                for n in G.nodes():
                    if str(n) not in node_colors:
                        node_colors[str(n)] = COLORS["text_muted"]
            except ValueError:
                # Categorical mapping
                unique_vals = list(set(attr_vals.values()))
                palette = COLORS["node_communities"]
                val_to_color = {val: palette[i % len(palette)] for i, val in enumerate(unique_vals)}
                node_colors = {k: val_to_color[v] for k, v in attr_vals.items()}
                for n in G.nodes():
                    if str(n) not in node_colors:
                        node_colors[str(n)] = COLORS["text_muted"]
        else:
            node_colors = {str(n): COLORS["accent_blue"] for n in G.nodes()}

        # ── Node Sizes ───────────────────────────────────────────────────
        base_ns = float(node_size or 18)
        if size_by == "pagerank" and centralities:
            scores = {n: v["pagerank"] for n, v in centralities.items() if "pagerank" in v}
            node_sizes = scale_values(scores, min_size=base_ns * 0.5, max_size=base_ns * 2.5)
        elif size_by == "betweenness" and centralities:
            scores = {n: v["betweenness"] for n, v in centralities.items() if "betweenness" in v}
            node_sizes = scale_values(scores, min_size=base_ns * 0.5, max_size=base_ns * 2.5)
        elif size_by == "degree" and centralities:
            degree_scores = {n: v["degree"] for n, v in centralities.items()}
            node_sizes = scale_values(degree_scores, min_size=base_ns * 0.5, max_size=base_ns * 2.5)
        elif size_by and size_by.startswith("node_"):
            attr = size_by[5:]
            try:
                floats = {str(n): float(G.nodes[n].get(attr, 0)) for n in G.nodes()}
                node_sizes = scale_values(floats, min_size=base_ns * 0.5, max_size=base_ns * 2.5)
            except ValueError:
                node_sizes = {str(n): base_ns for n in G.nodes()}
        else:
            node_sizes = {str(n): base_ns for n in G.nodes()}

        # ── Edge Colors ──────────────────────────────────────────────────
        edge_colors = {}
        if edge_color_by and edge_color_by.startswith("edge_"):
            attr = edge_color_by[5:]
            edge_vals = {}
            for u, v, d in G.edges(data=True):
                if attr in d:
                    edge_vals[(u, v)] = d[attr]
                    
            try:
                floats = {k: float(v) for k, v in edge_vals.items()}
                if floats:
                    min_val, max_val = min(floats.values()), max(floats.values())
                    import matplotlib.pyplot as plt
                    import matplotlib.colors as mcolors
                    cmap = plt.get_cmap("coolwarm")
                    for k, v in floats.items():
                        norm_v = (v - min_val) / (max_val - min_val) if max_val > min_val else 0.5
                        r, g, b, _ = cmap(norm_v)
                        edge_colors[k] = mcolors.to_hex((r, g, b))
            except ValueError:
                unique_vals = list(set(edge_vals.values()))
                palette = COLORS["node_communities"]
                val_to_color = {val: palette[i % len(palette)] for i, val in enumerate(unique_vals)}
                for k, v in edge_vals.items():
                    edge_colors[k] = val_to_color[v]

        # ── Build elements ────────────────────────────────────────────────
        overrides = json.loads(overrides_json) if overrides_json else {}

        # Apply per-node color overrides before building elements
        for node_id_ov, ov in overrides.items():
            if "color" in ov:
                node_colors[str(node_id_ov)] = ov["color"]
                
        # Handle label mapping
        label_map = {}
        if label_by and label_by.startswith("node_"):
            attr = label_by[5:]
            for n in G.nodes():
                if attr in G.nodes[n]:
                    label_map[str(n)] = str(G.nodes[n][attr])
                    
        # Apply manual overrides on top of mapped labels
        for node_id_ov, ov in overrides.items():
            if "label" in ov:
                label_map[str(node_id_ov)] = ov["label"]

        elements = build_cytoscape_elements(
            subG, positions, node_colors, node_sizes,
            edge_colors=edge_colors,
            base_node_size=base_ns,
            base_edge_thickness=float(edge_thickness or 2),
            directed=directed,
            hidden_nodes=set(),  # Already filtered via subG
            label_overrides=label_map,
        )

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
    Input("store-stats", "data"),
    prevent_initial_call=True,
)
def update_stats(stats_json):
    if not stats_json:
        return build_stats_bar({})
    try:
        stats = json.loads(stats_json)
        return build_stats_bar(stats)
    except Exception as e:
        return build_stats_bar({})


# 6.5. Update Centrality Slider Range ──────────────────────────────────────────
@app.callback(
    Output("filter-centrality-slider", "max"),
    Output("filter-centrality-slider", "marks"),
    Output("filter-centrality-slider", "value"),
    Input("store-stats", "data"),
    Input("dropdown-centrality-filter", "value"),
    prevent_initial_call=True,
)
def update_centrality_slider(stats_json, filter_type):
    if filter_type in ("betweenness", "closeness"):
        return 1, {0: "0", 0.5: "0.5", 1: "1"}, [0, 1]

    if not stats_json:
        return 1, {0: "0", 1: "1"}, [0, 1]
    try:
        stats = json.loads(stats_json)
        max_deg = stats.get("max_degree", 1)
        if max_deg == 0:
            max_deg = 1
            
        marks = {0: "0"}
        if max_deg > 1:
            marks[int(max_deg/2)] = str(int(max_deg/2))
        marks[max_deg] = str(max_deg)
        
        return max_deg, marks, [0, max_deg]
    except Exception:
        return 1, {0: "0", 1: "1"}, [0, 1]


# 7. Degree distribution chart ────────────────────────────────────────────────
@app.callback(
    Output("degree-dist-chart", "children"),
    Input("store-degree-dist", "data"),
    prevent_initial_call=True,
)
def update_degree_dist(dist_json):
    if not dist_json:
        return build_degree_distribution_chart({})
    try:
        dist = json.loads(dist_json)
        # Parse keys as integers (JSON dumps them as strings)
        dist = {int(k): v for k, v in dist.items()}
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
    from io import StringIO
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
            
            for n in meta.get("nodes", []):
                G.add_node(str(n["id"]))
                
            for e in meta.get("edges", []):
                try:
                    w = float(e.get("weight", 1.0))
                except (ValueError, TypeError):
                    w = 1.0
                G.add_edge(str(e["source"]), str(e["target"]), weight=w)

            # Extract ground-truth labels from nodes CSV if 'group' column exists.
            # Handles both numeric groups (1, 2, 3) and string groups ("5A", "5B", etc.)
            true_labels = None
            if nodes_json:
                try:
                    ndf = pd.read_json(StringIO(nodes_json), dtype=str)
                    ndf.columns = ndf.columns.str.strip().str.lower()

                    if "id" not in ndf.columns:
                        for syn in ["node_id", "node", "name", "user", "account", "userid"]:
                            if syn in ndf.columns:
                                ndf = ndf.rename(columns={syn: "id"})
                                break

                    # Also check for 'class' column synonym in case it wasn't renamed
                    if "group" not in ndf.columns:
                        for syn in ["class", "community", "cluster", "label", "category", "dept", "department"]:
                            if syn in ndf.columns:
                                ndf = ndf.rename(columns={syn: "group"})
                                break

                    if "group" in ndf.columns and "id" in ndf.columns:
                        # Build label encoder: map each unique group value → integer
                        unique_groups = sorted(ndf["group"].dropna().unique().tolist())
                        label_enc = {g: i for i, g in enumerate(unique_groups)}

                        true_labels = {}
                        for _, row in ndf.iterrows():
                            grp = str(row["group"]).strip()
                            if grp and grp.lower() not in ("nan", "none", ""):
                                try:
                                    # Numeric group: use as-is (0-indexed)
                                    true_labels[str(row["id"])] = int(float(grp))
                                except (ValueError, TypeError):
                                    # String group (e.g. "5B"): map via encoder
                                    true_labels[str(row["id"])] = label_enc.get(grp, 0)

                        if not true_labels:
                            true_labels = None
                        else:
                            print(f"[eval] true_labels: {len(true_labels)} nodes, "
                                  f"{len(set(true_labels.values()))} groups: {unique_groups[:8]}")
                except Exception as e:
                    print(f"[eval] true_labels error: {e}")

            if comparison_json:
                comparison = json.loads(comparison_json)
                gn_part = comparison.get("girvan_newman", {}).get("partition", {})
                louv_part = comparison.get("louvain", {}).get("partition", {})
                gn_num = comparison.get("girvan_newman", {}).get("num_communities", 0)
                louv_num = comparison.get("louvain", {}).get("num_communities", 0)

                if gn_part and louv_part and gn_num > 0 and louv_num > 0:
                    gn_eval = evaluate_partition(G, gn_part, true_labels=true_labels)
                    louv_eval = evaluate_partition(G, louv_part, true_labels=true_labels)
                    print(f"[eval] results GN: {gn_eval}")
                    print(f"[eval] results Louvain: {louv_eval}")
                    eval_widget = build_evaluation_table({"Girvan-Newman": gn_eval, "Louvain": louv_eval})
                else:
                    evaluation = evaluate_partition(G, partition, true_labels=true_labels)
                    print(f"[eval] results: {evaluation}")
                    eval_widget = build_evaluation_table(evaluation)
            else:
                evaluation = evaluate_partition(G, partition, true_labels=true_labels)
                print(f"[eval] results: {evaluation}")
                eval_widget = build_evaluation_table(evaluation)
        except Exception as e:
            import traceback
            print(f"[eval callback] {e}")
            traceback.print_exc()

    return comparison_widget, eval_widget


# 8.5. Dynamic Visual Dropdown Options ────────────────────────────────────────
@app.callback(
    Output("dropdown-color-by", "options"),
    Output("dropdown-size-by", "options"),
    Output("dropdown-label-by", "options"),
    Output("dropdown-edge-color-by", "options"),
    Input("store-graph-data", "data"),
    prevent_initial_call=True,
)
def update_dropdown_options(graph_json):
    color_opts = [
        {"label": "Uniform", "value": "uniform"},
        {"label": "Community", "value": "community"},
        {"label": "Degree", "value": "degree"},
        {"label": "PageRank", "value": "pagerank"},
        {"label": "Betweenness", "value": "betweenness"},
        {"label": "Closeness", "value": "closeness"},
    ]
    size_opts = [
        {"label": "Uniform", "value": "uniform"},
        {"label": "Degree", "value": "degree"},
        {"label": "PageRank", "value": "pagerank"},
        {"label": "Betweenness", "value": "betweenness"},
    ]
    label_opts = [{"label": "ID", "value": "id"}]
    edge_color_opts = [{"label": "Uniform", "value": "uniform"}]

    if not graph_json:
        return color_opts, size_opts, label_opts, edge_color_opts

    try:
        meta = json.loads(graph_json)
        
        # Node attributes
        node_attrs = set()
        for n in meta.get("nodes", []):
            for k in n.keys():
                if k != "id":
                    node_attrs.add(k)
                    
        for attr in sorted(list(node_attrs)):
            label = attr.replace("_", " ").title()
            color_opts.append({"label": f"Node: {label}", "value": f"node_{attr}"})
            size_opts.append({"label": f"Node: {label}", "value": f"node_{attr}"})
            label_opts.append({"label": f"Node: {label}", "value": f"node_{attr}"})
            
        # Edge attributes
        edge_attrs = set()
        for e in meta.get("edges", []):
            for k in e.keys():
                if k not in ("source", "target"):
                    edge_attrs.add(k)
                    
        for attr in sorted(list(edge_attrs)):
            label = attr.replace("_", " ").title()
            edge_color_opts.append({"label": f"Edge: {label}", "value": f"edge_{attr}"})
            
        return color_opts, size_opts, label_opts, edge_color_opts
    except Exception:
        return color_opts, size_opts, label_opts, edge_color_opts


# 10. Node info panel on click ─────────────────────────────────────────────────
@app.callback(
    Output("node-info-content", "children"),
    Output("node-editor-section", "style"),
    Output("node-color-picker", "value"),
    Output("node-color-preview", "style"),
    Output("node-label-input", "value"),
    Output("store-selected-node", "data"),
    Output("store-color-picker-value", "data", allow_duplicate=True),
    Input("cytoscape-graph", "tapNodeData"),
    State("store-centralities", "data"),
    State("store-node-overrides", "data"),
    prevent_initial_call=True,
)
def update_node_info(node_data, centralities_json, overrides_json):
    centralities = json.loads(centralities_json) if centralities_json else {}
    overrides = json.loads(overrides_json) if overrides_json else {}
    _hidden = {"display": "none"}

    if not node_data:
        return format_node_info({}, centralities), _hidden, "#58a6ff", {"backgroundColor": "#58a6ff"}, "", None, "#58a6ff"

    node_id = node_data.get("id", "")
    ov = overrides.get(node_id, {})

    current_color = ov.get("color", node_data.get("color", "#58a6ff"))
    current_label = ov.get("label", node_data.get("label", node_id))

    preview_style = {
        "flex": "1", "height": "32px", "borderRadius": "5px",
        "border": "1px solid #30363d", "display": "inline-block",
        "backgroundColor": current_color, "transition": "background-color 0.2s",
    }
    return (
        format_node_info(node_data, centralities),
        {"display": "block"},
        current_color,
        preview_style,
        current_label,
        node_id,
        current_color,
    )


# 10a. Quick-select color swatches ────────────────────────────────────────────
@app.callback(
    Output("node-color-picker", "value", allow_duplicate=True),
    Input({"type": "color-swatch", "color": ALL}, "n_clicks"),
    prevent_initial_call=True
)
def quick_select_color(n_clicks):
    ctx = callback_context
    if not ctx.triggered:
        return no_update
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    try:
        color = json.loads(triggered_id)["color"]
        return color
    except Exception:
        return no_update


# 10b. Sync html.Input color into store (clientside, fires on every change) ───
app.clientside_callback(
    """
    function(color) {
        return color || '#58a6ff';
    }
    """,
    Output("store-color-picker-value", "data"),
    Input("node-color-picker", "value"),
    prevent_initial_call=True,
)


# 10b2. Live color preview from store ────────────────────────────────────────
app.clientside_callback(
    """
    function(color) {
        return {
            flex: '1', height: '32px', borderRadius: '5px',
            border: '1px solid #30363d', display: 'inline-block',
            backgroundColor: color || '#58a6ff', transition: 'background-color 0.2s'
        };
    }
    """,
    Output("node-color-preview", "style", allow_duplicate=True),
    Input("store-color-picker-value", "data"),
    prevent_initial_call=True,
)


# 10c. Apply / Reset node style override ──────────────────────────────────────
@app.callback(
    Output("store-node-overrides", "data"),
    Input("btn-apply-node-style", "n_clicks"),
    Input("btn-reset-node-style", "n_clicks"),
    State("store-selected-node", "data"),
    State("store-color-picker-value", "data"),
    State("node-label-input", "value"),
    State("store-node-overrides", "data"),
    prevent_initial_call=True,
)
def apply_node_override(n_apply, n_reset, selected_node, color, label, overrides_json):
    if not selected_node:
        return no_update
    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
    overrides = json.loads(overrides_json) if overrides_json else {}

    if "btn-reset-node-style" in trigger:
        overrides.pop(selected_node, None)
    else:
        entry = overrides.get(selected_node, {})
        if color:
            entry["color"] = color
        if label is not None and label.strip() != "":
            entry["label"] = label.strip()
        else:
            entry.pop("label", None)  # blank = revert to original label
        overrides[selected_node] = entry

    return json.dumps(overrides)


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



# 17. Toggle GN-K slider visibility ───────────────────────────────────────────
@app.callback(
    Output("gn-k-container", "style"),
    Input("dropdown-community-algo", "value")
)
def toggle_gn_slider(algo):
    if algo in ("girvan_newman", "both"):
        return {"display": "block"}
    return {"display": "none"}



# 18. Link Analysis results panel ────────────────────────────────────────────
@app.callback(
    Output("link-analysis-results", "children"),
    Output("btn-la-pagerank",    "style"),
    Output("btn-la-betweenness", "style"),
    Output("btn-la-eigenvector", "style"),
    Output("btn-la-closeness",   "style"),
    Input("btn-la-pagerank",    "n_clicks"),
    Input("btn-la-betweenness", "n_clicks"),
    Input("btn-la-eigenvector", "n_clicks"),
    Input("btn-la-closeness",   "n_clicks"),
    Input("store-centralities", "data"),
    prevent_initial_call=False,
)
def update_link_analysis_panel(n_pr, n_bt, n_ev, n_cl, centralities_json):
    from ui.styles import COLORS

    _base = {
        "padding": "5px 14px", "fontSize": "12px", "fontWeight": "600",
        "cursor": "pointer", "whiteSpace": "nowrap", "borderRadius": "5px",
        "border": f"1px solid {COLORS['border']}",
        "backgroundColor": COLORS["bg_dark"], "color": COLORS["text_muted"],
        "letterSpacing": "0.04em", "transition": "all 0.2s",
    }
    _active_pr  = {**_base, "color": COLORS["accent_blue"],   "borderColor": COLORS["accent_blue"]}
    _active_bt  = {**_base, "color": COLORS["accent_orange"], "borderColor": COLORS["accent_orange"]}
    _active_ev  = {**_base, "color": COLORS["accent_green"],  "borderColor": COLORS["accent_green"]}
    _active_cl  = {**_base, "color": COLORS["accent_purple"], "borderColor": COLORS["accent_purple"]}

    metric_map = {
        "btn-la-pagerank":    ("pagerank",    _active_pr,  COLORS["accent_blue"]),
        "btn-la-betweenness": ("betweenness", _active_bt,  COLORS["accent_orange"]),
        "btn-la-eigenvector": ("eigenvector", _active_ev,  COLORS["accent_green"]),
        "btn-la-closeness":   ("closeness",   _active_cl,  COLORS["accent_purple"]),
    }

    ctx = callback_context
    if ctx.triggered:
        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    else:
        triggered_id = "btn-la-pagerank"

    active = triggered_id if triggered_id in metric_map else "btn-la-pagerank"

    # When triggered by data update, keep whichever tab was last clicked
    if triggered_id == "store-centralities":
        counts = {
            "btn-la-pagerank":    n_pr or 0,
            "btn-la-betweenness": n_bt or 0,
            "btn-la-eigenvector": n_ev or 0,
            "btn-la-closeness":   n_cl or 0,
        }
        active = max(counts, key=counts.get)

    metric_key, active_style, value_color = metric_map[active]
    styles = {k: (active_style if k == active else _base) for k in metric_map}

    def _out():
        return styles["btn-la-pagerank"], styles["btn-la-betweenness"], styles["btn-la-eigenvector"], styles["btn-la-closeness"]

    if not centralities_json:
        placeholder = html.Span(
            "Build a graph to see link analysis results.",
            style={"color": COLORS["text_muted"], "fontSize": "12px"},
        )
        return (placeholder,) + _out()

    centralities = json.loads(centralities_json)
    scores = {
        nid: data.get(metric_key, 0.0)
        for nid, data in centralities.items()
        if metric_key in data
    }
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:20]

    rows = [
        html.Div(
            style={
                "display": "flex", "justifyContent": "space-between",
                "alignItems": "center", "padding": "4px 6px",
                "borderBottom": f"1px solid {COLORS['border']}22",
            },
            children=[
                html.Span(
                    f"#{rank}  {nid}",
                    style={"color": COLORS["text_secondary"], "fontSize": "12px", "fontWeight": "600"},
                ),
                html.Span(
                    f"{score:.5f}",
                    style={"color": value_color, "fontSize": "12px", "fontWeight": "700"},
                ),
            ],
        )
        for rank, (nid, score) in enumerate(ranked, 1)
    ]

    header = html.Div(
        style={
            "display": "flex", "justifyContent": "space-between",
            "padding": "2px 6px 6px", "borderBottom": f"1px solid {COLORS['border']}",
            "marginBottom": "4px",
        },
        children=[
            html.Span("Node", style={"color": COLORS["text_muted"], "fontSize": "10px", "fontWeight": "700", "textTransform": "uppercase"}),
            html.Span("Score", style={"color": COLORS["text_muted"], "fontSize": "10px", "fontWeight": "700", "textTransform": "uppercase"}),
        ],
    )
    content = html.Div([header, *rows])
    return (content,) + _out()



# 19. Node Communities results panel ────────────────────────────────────────────
@app.callback(
    Output("node-communities-results", "children"),
    Input("store-comparison", "data"),
    prevent_initial_call=False,
)
def update_node_communities_panel(comparison_json):
    from ui.styles import COLORS

    if not comparison_json:
        return html.Span(
            "Run community detection (Both) to see node assignments.",
            style={"color": COLORS["text_muted"], "fontSize": "12px"},
        )

    comparison = json.loads(comparison_json)
    gn_part = comparison.get("girvan_newman", {}).get("partition", {})
    louv_part = comparison.get("louvain", {}).get("partition", {})

    if not gn_part and not louv_part:
        return html.Span(
            "No community data available.",
            style={"color": COLORS["text_muted"], "fontSize": "12px"},
        )

    # Gather all node IDs from both partitions
    all_nodes = set(gn_part.keys()).union(set(louv_part.keys()))
    
    # Sort nodes for display
    def natural_sort_key(s):
        import re
        return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', str(s))]
    
    sorted_nodes = sorted(list(all_nodes), key=natural_sort_key)

    rows = [
        html.Div(
            style={
                "display": "flex", "justifyContent": "space-between",
                "alignItems": "center", "padding": "4px 6px",
                "borderBottom": f"1px solid {COLORS['border']}22",
            },
            children=[
                html.Span(
                    str(nid),
                    style={"color": COLORS["text_primary"], "fontSize": "12px", "fontWeight": "600", "flex": "1"},
                ),
                html.Span(
                    str(gn_part.get(str(nid), "—")),
                    style={"color": COLORS["accent_blue"], "fontSize": "12px", "fontWeight": "700", "flex": "1", "textAlign": "center"},
                ),
                html.Span(
                    str(louv_part.get(str(nid), "—")),
                    style={"color": COLORS["accent_purple"], "fontSize": "12px", "fontWeight": "700", "flex": "1", "textAlign": "right"},
                ),
            ],
        )
        for nid in sorted_nodes
    ]

    header = html.Div(
        style={
            "display": "flex", "justifyContent": "space-between",
            "padding": "2px 6px 6px", "borderBottom": f"1px solid {COLORS['border']}",
            "marginBottom": "4px",
        },
        children=[
            html.Span("Node", style={"color": COLORS["text_muted"], "fontSize": "10px", "fontWeight": "700", "textTransform": "uppercase", "flex": "1"}),
            html.Span("GN Comm", style={"color": COLORS["text_muted"], "fontSize": "10px", "fontWeight": "700", "textTransform": "uppercase", "flex": "1", "textAlign": "center"}),
            html.Span("Louv Comm", style={"color": COLORS["text_muted"], "fontSize": "10px", "fontWeight": "700", "textTransform": "uppercase", "flex": "1", "textAlign": "right"}),
        ],
    )
    return html.Div([header, *rows])



# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Social Network Analysis Tool")
    print("  Open in browser: http://localhost:8050")
    print("=" * 60)
    app.run(debug=True, port=8050)
