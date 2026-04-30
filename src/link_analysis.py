"""
link_analysis.py
----------------
Link analysis algorithms: PageRank and Betweenness Centrality.
Provides node ranking, size/color scaling for visual highlighting.
"""

import networkx as nx
import numpy as np
from typing import Dict, List, Tuple


def compute_pagerank(G: nx.Graph, alpha: float = 0.85) -> Dict[str, float]:
    """
    Compute PageRank scores for all nodes.

    Args:
        G: A NetworkX graph (directed or undirected).
        alpha: Damping parameter (default 0.85).

    Returns:
        Dict mapping node_id (str) -> PageRank score (float).
    """
    if G is None or G.number_of_nodes() == 0:
        return {}

    try:
        pr = nx.pagerank(G, alpha=alpha, max_iter=500, tol=1e-6)
    except nx.PowerIterationFailedConvergence:
        # Fall back to uniform distribution
        n = G.number_of_nodes()
        pr = {node: 1.0 / n for node in G.nodes()}

    return {str(node): round(score, 8) for node, score in pr.items()}


def compute_betweenness_centrality(G: nx.Graph, normalized: bool = True) -> Dict[str, float]:
    """
    Compute Betweenness Centrality for all nodes.

    Args:
        G: A NetworkX graph.
        normalized: If True, normalize by the theoretical maximum.

    Returns:
        Dict mapping node_id (str) -> betweenness centrality (float).
    """
    if G is None or G.number_of_nodes() == 0:
        return {}

    n_nodes = G.number_of_nodes()
    # If the graph is large (>500 nodes), approximate by randomly sampling 100 nodes
    k_approx = min(n_nodes, 100) if n_nodes > 500 else None

    bc = nx.betweenness_centrality(G, k=k_approx, normalized=normalized)
    return {str(node): round(score, 8) for node, score in bc.items()}


def get_top_nodes(
    scores: Dict[str, float],
    top_n: int = 10,
) -> List[Tuple[str, float]]:
    """
    Return the top N nodes sorted by their score in descending order.

    Args:
        scores: Dict mapping node_id -> score.
        top_n: Number of top nodes to return.

    Returns:
        List of (node_id, score) tuples sorted descending.
    """
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_items[:top_n]


def scale_values(
    scores: Dict[str, float],
    min_size: float = 10.0,
    max_size: float = 60.0,
) -> Dict[str, float]:
    """
    Linearly scale raw score values to a [min_size, max_size] range for viz.

    Args:
        scores: Dict of node_id -> raw score.
        min_size: Minimum output size.
        max_size: Maximum output size.

    Returns:
        Dict of node_id -> scaled value.
    """
    if not scores:
        return {}

    values = list(scores.values())
    v_min, v_max = min(values), max(values)

    if v_max == v_min:
        return {n: (min_size + max_size) / 2 for n in scores}

    scaled = {}
    for node, val in scores.items():
        normalized = (val - v_min) / (v_max - v_min)
        scaled[node] = round(min_size + normalized * (max_size - min_size), 2)
    return scaled


def get_node_ranking_color(
    scores: Dict[str, float],
    colorscale: str = "plasma",
) -> Dict[str, str]:
    """
    Map node scores to hex colors along a colorscale.

    Supports colorscales: 'plasma', 'viridis', 'magma', 'inferno'.

    Args:
        scores: Dict of node_id -> score.
        colorscale: Which colorscale to use.

    Returns:
        Dict of node_id -> hex color string.
    """
    if not scores:
        return {}

    # Simple colorscale implementations (5 stops each)
    colorscales = {
        "plasma": [
            (0.0, (13, 8, 135)),
            (0.25, (126, 3, 168)),
            (0.5, (204, 71, 120)),
            (0.75, (248, 149, 64)),
            (1.0, (240, 249, 33)),
        ],
        "viridis": [
            (0.0, (68, 1, 84)),
            (0.25, (59, 82, 139)),
            (0.5, (33, 145, 140)),
            (0.75, (94, 201, 98)),
            (1.0, (253, 231, 37)),
        ],
        "magma": [
            (0.0, (0, 0, 4)),
            (0.25, (81, 18, 124)),
            (0.5, (183, 55, 121)),
            (0.75, (252, 136, 99)),
            (1.0, (252, 253, 191)),
        ],
        "hot": [
            (0.0, (20, 20, 80)),
            (0.25, (100, 20, 160)),
            (0.5, (220, 50, 80)),
            (0.75, (255, 160, 40)),
            (1.0, (255, 255, 100)),
        ],
    }

    stops = colorscales.get(colorscale, colorscales["plasma"])
    values = list(scores.values())
    v_min, v_max = min(values), max(values)

    def interpolate_color(t: float) -> str:
        """Interpolate between colorscale stops for value t in [0, 1]."""
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                ratio = (t - t0) / (t1 - t0)
                r = int(c0[0] + ratio * (c1[0] - c0[0]))
                g = int(c0[1] + ratio * (c1[1] - c0[1]))
                b = int(c0[2] + ratio * (c1[2] - c0[2]))
                return f"#{r:02x}{g:02x}{b:02x}"
        return "#ffffff"

    colors = {}
    for node, val in scores.items():
        t = (val - v_min) / (v_max - v_min) if v_max != v_min else 0.5
        colors[node] = interpolate_color(t)
    return colors
