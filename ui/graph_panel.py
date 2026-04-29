"""
graph_panel.py
--------------
The main interactive graph visualization panel using Dash Cytoscape.
Converts NetworkX graph + positions + styling data into Cytoscape elements.
"""

from dash import dcc, html
import dash_cytoscape as cyto
from typing import Dict, List, Optional, Any
import networkx as nx

from ui.styles import COLORS, CYTOSCAPE_STYLESHEET, STYLE_CARD


def build_node_info_panel() -> html.Div:
    """Build the node info panel shown on the right when a node is selected."""
    return html.Div(
        id="node-info-panel",
        style={
            **STYLE_CARD,
            "minWidth": "220px",
            "maxWidth": "260px",
            "flexShrink": "0",
            "position": "relative",
        },
        children=[
            html.P("🔵 Node Info", style={
                "color": COLORS["text_secondary"],
                "fontSize": "11px",
                "fontWeight": "600",
                "letterSpacing": "0.08em",
                "textTransform": "uppercase",
                "marginBottom": "10px",
                "marginTop": "0",
            }),
            html.Div(
                id="node-info-content",
                style={"color": COLORS["text_secondary"], "fontSize": "12px"},
                children="Click a node to see its details.",
            ),
        ],
    )


def build_graph_cytoscape() -> cyto.Cytoscape:
    """Build the main Cytoscape graph component."""
    return cyto.Cytoscape(
        id="cytoscape-graph",
        layout={"name": "preset"},  # We provide positions via elements
        style={
            "width": "100%",
            "height": "100%",
            "backgroundColor": "#0a0f16",
        },
        stylesheet=CYTOSCAPE_STYLESHEET,
        elements=[],
        minZoom=0.1,
        maxZoom=5,
        responsive=True,
        userZoomingEnabled=True,
        userPanningEnabled=True,
        autoungrabify=False,
        boxSelectionEnabled=True,
    )


def build_graph_panel() -> html.Div:
    """Build the full graph panel: graph + node info side by side."""
    return html.Div(
        style={
            "display": "flex",
            "flex": "1",
            "gap": "12px",
            "padding": "12px",
            "minHeight": "0",
        },
        children=[
            # Graph container
            html.Div(
                style={
                    "flex": "1",
                    "backgroundColor": "#0a0f16",
                    "borderRadius": "10px",
                    "border": f"1px solid {COLORS['border']}",
                    "overflow": "hidden",
                    "position": "relative",
                    "minHeight": "400px",
                },
                children=[
                    # Toolbar overlay
                    html.Div(
                        style={
                            "position": "absolute",
                            "top": "12px",
                            "right": "12px",
                            "display": "flex",
                            "gap": "6px",
                            "zIndex": "10",
                        },
                        children=[
                            html.Button("⛶ Fit", id="btn-fit", style={
                                "backgroundColor": "rgba(22,27,34,0.9)",
                                "color": COLORS["text_primary"],
                                "border": f"1px solid {COLORS['border']}",
                                "borderRadius": "5px",
                                "padding": "5px 10px",
                                "cursor": "pointer",
                                "fontSize": "12px",
                                "backdropFilter": "blur(4px)",
                            }),
                            html.Button("⟳ Reset", id="btn-reset-zoom", style={
                                "backgroundColor": "rgba(22,27,34,0.9)",
                                "color": COLORS["text_primary"],
                                "border": f"1px solid {COLORS['border']}",
                                "borderRadius": "5px",
                                "padding": "5px 10px",
                                "cursor": "pointer",
                                "fontSize": "12px",
                                "backdropFilter": "blur(4px)",
                            }),
                        ],
                    ),
                    # Status badge
                    html.Div(
                        id="graph-status-badge",
                        style={
                            "position": "absolute",
                            "bottom": "12px",
                            "left": "12px",
                            "backgroundColor": "rgba(22,27,34,0.85)",
                            "border": f"1px solid {COLORS['border']}",
                            "borderRadius": "5px",
                            "padding": "4px 10px",
                            "fontSize": "11px",
                            "color": COLORS["text_secondary"],
                            "backdropFilter": "blur(4px)",
                            "zIndex": "10",
                        },
                        children="No graph loaded",
                    ),
                    build_graph_cytoscape(),
                ],
            ),
            build_node_info_panel(),
        ],
    )


def build_cytoscape_elements(
    G: nx.Graph,
    positions: Dict[str, tuple],
    node_colors: Dict[str, str],
    node_sizes: Dict[str, float],
    base_node_size: float = 18,
    base_edge_thickness: float = 2,
    directed: bool = False,
    hidden_nodes: Optional[set] = None,
) -> List[Dict[str, Any]]:
    """
    Convert a NetworkX graph + computed visual attributes into Cytoscape elements.

    Args:
        G: NetworkX graph.
        positions: Dict of node_id -> (x, y) from layout module.
        node_colors: Dict of node_id -> hex color string.
        node_sizes: Dict of node_id -> size (float).
        base_node_size: Default node size if not in node_sizes.
        base_edge_thickness: Default edge line thickness.
        directed: Whether to render arrows on edges.
        hidden_nodes: Set of node IDs to exclude from elements.

    Returns:
        List of Cytoscape element dicts (nodes + edges).
    """
    elements = []
    hidden_nodes = hidden_nodes or set()

    # Scale positions to Cytoscape coordinate space
    xs = [p[0] for p in positions.values()] if positions else [0]
    ys = [p[1] for p in positions.values()] if positions else [0]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    x_range = x_max - x_min if x_max != x_min else 1
    y_range = y_max - y_min if y_max != y_min else 1
    canvas_w, canvas_h = 900, 600

    def scale_x(x):
        return round(((x - x_min) / x_range) * (canvas_w - 80) + 40, 2)

    def scale_y(y):
        return round(((y - y_min) / y_range) * (canvas_h - 80) + 40, 2)

    # Nodes
    for node in G.nodes():
        node_id = str(node)
        if node_id in hidden_nodes:
            continue

        data = dict(G.nodes[node])
        pos = positions.get(node_id, (0, 0))
        color = node_colors.get(node_id, COLORS["accent_blue"])
        size = node_sizes.get(node_id, base_node_size)

        # Reserved keys that Cytoscape / the renderer manage — don't let CSV
        # columns with the same name overwrite the computed numeric values.
        _reserved = {"label", "size", "color", "id"}
        elements.append({
            "data": {
                "id": node_id,
                "label": data.get("label", node_id),
                "color": color,
                "size": round(float(size), 1),
                **{k: str(v) for k, v in data.items() if k not in _reserved},
            },
            "position": {
                "x": scale_x(pos[0]),
                "y": scale_y(pos[1]),
            },
        })

    # Edges
    max_weight = max(
        (abs(float(str(G.edges[u, v].get("weight", 1)))) for u, v in G.edges()),
        default=1,
    )
    if max_weight == 0:
        max_weight = 1

    for u, v, edata in G.edges(data=True):
        uid, vid = str(u), str(v)
        if uid in hidden_nodes or vid in hidden_nodes:
            continue

        weight = float(str(edata.get("weight", 1.0)))
        # Scale thickness: [0.5, base_edge_thickness * 3]
        thickness = round(0.5 + (weight / max_weight) * (base_edge_thickness * 2), 2)

        elements.append({
            "data": {
                "source": uid,
                "target": vid,
                "weight": round(weight, 2),
                "thickness": thickness,
                "color": COLORS["text_muted"],
                "directed": "true" if directed else "false",
            },
        })

    return elements


def format_node_info(node_data: dict, centralities: dict) -> List:
    """
    Format node properties and centrality scores for the info panel.

    Args:
        node_data: Cytoscape node data dict (from tapNodeData callback).
        centralities: Full centrality dict from metrics module.

    Returns:
        List of Dash html components.
    """
    if not node_data:
        return [html.Span("Click a node to see its details.", style={"color": COLORS["text_secondary"]})]

    node_id = node_data.get("id", "")
    node_centrality = centralities.get(node_id, {})

    rows = []

    # Node identifier
    rows.append(html.Div([
        html.Span("Node: ", style={"color": COLORS["text_muted"], "fontSize": "11px"}),
        html.Span(node_data.get("label", node_id), style={
            "color": COLORS["accent_blue"],
            "fontWeight": "700",
            "fontSize": "15px",
        }),
    ], style={"marginBottom": "10px"}))

    # Basic attributes
    skip = {"id", "label", "color", "size", "directed"}
    for key, val in node_data.items():
        if key in skip:
            continue
        rows.append(html.Div([
            html.Span(f"{key}: ", style={"color": COLORS["text_muted"], "fontSize": "11px"}),
            html.Span(str(val), style={"color": COLORS["text_primary"], "fontSize": "12px"}),
        ], style={"marginBottom": "3px"}))

    if rows:
        rows.append(html.Hr(style={"borderColor": COLORS["border"], "margin": "8px 0"}))

    # Centrality metrics
    metric_labels = {
        "degree": ("📊 Degree", COLORS["accent_blue"]),
        "betweenness": ("🔀 Betweenness", COLORS["accent_purple"]),
        "closeness": ("🎯 Closeness", COLORS["accent_green"]),
        "pagerank": ("⭐ PageRank", COLORS["accent_orange"]),
    }
    for key, (label, color) in metric_labels.items():
        val = node_centrality.get(key)
        if val is not None:
            rows.append(html.Div([
                html.Span(f"{label}: ", style={"color": COLORS["text_muted"], "fontSize": "11px"}),
                html.Span(f"{val:.4f}", style={"color": color, "fontWeight": "600", "fontSize": "12px"}),
            ], style={"marginBottom": "3px"}))

    return rows
