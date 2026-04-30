"""
layout.py
---------
Graph layout algorithms for computing 2D node positions.
Wraps NetworkX layout functions and provides a unified interface.
"""

import networkx as nx
import numpy as np
from typing import Dict, Tuple


# Registry of supported layout names
LAYOUT_OPTIONS = [
    {"label": "Force-Directed (Spring)", "value": "spring"},
    {"label": "Kamada-Kawai", "value": "kamada_kawai"},
    {"label": "Circular", "value": "circular"},
    {"label": "Shell", "value": "shell"},
    {"label": "Spectral", "value": "spectral"},
    {"label": "Hierarchical", "value": "hierarchical"},
    {"label": "Tree", "value": "tree"},
    {"label": "Radial", "value": "radial"},
]


def get_spring_layout(G: nx.Graph, seed: int = 42) -> Dict[str, Tuple[float, float]]:
    """
    Compute Fruchterman-Reingold (spring / force-directed) layout.

    Args:
        G: NetworkX graph.
        seed: Random seed for reproducibility.

    Returns:
        Dict mapping node_id -> (x, y) position tuple.
    """
    n_nodes = G.number_of_nodes()
    iters = 50
    if n_nodes > 1000:
        iters = 10
    elif n_nodes > 500:
        iters = 25
        
    pos = nx.spring_layout(G, seed=seed, k=1.5 / np.sqrt(max(n_nodes, 1)), iterations=iters)
    return {str(n): (float(p[0]), float(p[1])) for n, p in pos.items()}


def _sanitize_weights(G: nx.Graph) -> nx.Graph:
    """
    Return a copy of G with all edge 'weight' attributes cast to float.
    Needed because graphs serialised to JSON store everything as strings.
    """
    H = G.copy()
    for u, v, data in H.edges(data=True):
        if "weight" in data:
            try:
                H[u][v]["weight"] = float(str(data["weight"]))
            except (ValueError, TypeError):
                H[u][v]["weight"] = 1.0
    return H


def get_kamada_kawai_layout(G: nx.Graph) -> Dict[str, Tuple[float, float]]:
    """
    Compute Kamada-Kawai layout (energy minimization).

    Args:
        G: NetworkX graph.

    Returns:
        Dict mapping node_id -> (x, y) position tuple.
    """
    base = G.to_undirected() if G.is_directed() else G
    base = _sanitize_weights(base)  # cast string weights -> float

    # Kamada-Kawai requires connected graph; use largest component
    if not nx.is_connected(base):
        components = list(nx.connected_components(base))
        pos = {}
        x_offset = 0.0
        for component in sorted(components, key=len, reverse=True):
            subgraph = base.subgraph(component).copy()
            if subgraph.number_of_nodes() == 1:
                node = list(subgraph.nodes())[0]
                pos[node] = (x_offset, 0.0)
            else:
                if subgraph.number_of_nodes() > 300:
                    sub_pos = nx.spring_layout(subgraph, seed=42, iterations=15)
                else:
                    try:
                        sub_pos = nx.kamada_kawai_layout(subgraph)
                    except Exception:
                        sub_pos = nx.spring_layout(subgraph, seed=42)
                for n, p in sub_pos.items():
                    pos[n] = (p[0] + x_offset, p[1])
            x_offset += 2.5
        return {str(n): (float(p[0]), float(p[1])) for n, p in pos.items()}

    if base.number_of_nodes() > 300:
        raw = nx.spring_layout(base, seed=42, iterations=15)
    else:
        try:
            raw = nx.kamada_kawai_layout(base)
        except Exception:
            raw = nx.spring_layout(base, seed=42)
    return {str(n): (float(p[0]), float(p[1])) for n, p in raw.items()}


def get_circular_layout(G: nx.Graph) -> Dict[str, Tuple[float, float]]:
    """
    Compute circular layout (nodes evenly spaced on a circle).

    Args:
        G: NetworkX graph.

    Returns:
        Dict mapping node_id -> (x, y) position tuple.
    """
    pos = nx.circular_layout(G)
    return {str(n): (float(p[0]), float(p[1])) for n, p in pos.items()}


def get_shell_layout(G: nx.Graph) -> Dict[str, Tuple[float, float]]:
    """
    Compute shell (radial) layout using degree as shell grouping.
    Nodes with similar degrees are placed on the same concentric ring.

    Args:
        G: NetworkX graph.

    Returns:
        Dict mapping node_id -> (x, y) position tuple.
    """
    if G.number_of_nodes() < 3:
        return get_circular_layout(G)

    # Group nodes by degree bucket into shells
    degree_dict = dict(G.degree())
    max_degree = max(degree_dict.values()) if degree_dict else 1
    num_shells = max(2, min(5, max_degree))

    shells = [[] for _ in range(num_shells)]
    for node, deg in degree_dict.items():
        bucket = min(int((deg / (max_degree + 1)) * num_shells), num_shells - 1)
        shells[bucket].append(node)

    # Remove empty shells
    shells = [s for s in shells if s]
    if len(shells) < 2:
        return get_circular_layout(G)

    pos = nx.shell_layout(G, shells)
    return {str(n): (float(p[0]), float(p[1])) for n, p in pos.items()}


def get_spectral_layout(G: nx.Graph) -> Dict[str, Tuple[float, float]]:
    """
    Compute spectral layout using Laplacian eigenvectors.

    Args:
        G: NetworkX graph.

    Returns:
        Dict mapping node_id -> (x, y) position tuple.
    """
    try:
        pos = nx.spectral_layout(G)
        return {str(n): (float(p[0]), float(p[1])) for n, p in pos.items()}
    except Exception:
        return get_spring_layout(G)


def get_hierarchical_layout(G: nx.Graph) -> Dict[str, Tuple[float, float]]:
    """
    Compute a hierarchical (top-down tree) layout using BFS from the highest-degree node.
    Approximates a Sugiyama/dot layout without Graphviz dependency.

    Args:
        G: NetworkX graph.

    Returns:
        Dict mapping node_id -> (x, y) position tuple.
    """
    base = G.to_undirected() if G.is_directed() else G

    if base.number_of_nodes() == 0:
        return {}

    # Use highest-degree node as root
    root = max(dict(base.degree()).items(), key=lambda x: x[1])[0]

    # BFS to assign layers
    layers: Dict[str, int] = {}
    queue = [root]
    layers[root] = 0
    visited = {root}

    while queue:
        current = queue.pop(0)
        for neighbor in base.neighbors(current):
            if neighbor not in visited:
                visited.add(neighbor)
                layers[neighbor] = layers[current] + 1
                queue.append(neighbor)

    # Assign isolated nodes to a separate layer
    max_layer = max(layers.values()) if layers else 0
    for node in base.nodes():
        if node not in layers:
            layers[node] = max_layer + 1

    # Build layer -> [nodes] mapping for x-positioning
    layer_nodes: Dict[int, list] = {}
    for node, layer in layers.items():
        layer_nodes.setdefault(layer, []).append(node)

    pos = {}
    for layer, nodes in layer_nodes.items():
        for i, node in enumerate(nodes):
            x = (i - len(nodes) / 2) * 1.5
            y = -layer * 1.5  # top-to-bottom
            pos[str(node)] = (float(x), float(y))

    return pos


def get_tree_layout(G: nx.Graph) -> Dict[str, Tuple[float, float]]:
    """
    Compute a tree layout. Falls back to hierarchical layout logic, but spacing is 
    adjusted to look more like a traditional tree.
    """
    # For now, tree uses the hierarchical logic as it produces a top-down tree.
    return get_hierarchical_layout(G)


def get_radial_layout(G: nx.Graph) -> Dict[str, Tuple[float, float]]:
    """
    Compute a radial layout (concentric circles based on BFS distance from root).
    """
    base = G.to_undirected() if G.is_directed() else G
    if base.number_of_nodes() == 0:
        return {}

    # Use highest-degree node as root
    root = max(dict(base.degree()).items(), key=lambda x: x[1])[0]

    layers: Dict[str, int] = {}
    queue = [root]
    layers[root] = 0
    visited = {root}

    while queue:
        current = queue.pop(0)
        for neighbor in base.neighbors(current):
            if neighbor not in visited:
                visited.add(neighbor)
                layers[neighbor] = layers[current] + 1
                queue.append(neighbor)

    max_layer = max(layers.values()) if layers else 0
    for node in base.nodes():
        if node not in layers:
            layers[node] = max_layer + 1

    layer_nodes: Dict[int, list] = {}
    for node, layer in layers.items():
        layer_nodes.setdefault(layer, []).append(node)

    pos = {}
    for layer, nodes in layer_nodes.items():
        if layer == 0:
            for node in nodes:
                pos[str(node)] = (0.0, 0.0)
        else:
            radius = layer * 2.0
            angle_step = 2 * np.pi / len(nodes)
            for i, node in enumerate(nodes):
                angle = i * angle_step
                pos[str(node)] = (float(radius * np.cos(angle)), float(radius * np.sin(angle)))

    return pos


def get_layout(G: nx.Graph, layout_name: str) -> Dict[str, Tuple[float, float]]:
    """
    Unified interface to compute node positions for the given layout name.

    Args:
        G: NetworkX graph.
        layout_name: One of 'spring', 'kamada_kawai', 'circular', 'shell', 'spectral', 'hierarchical'.

    Returns:
        Dict mapping node_id (str) -> (x, y) position tuple.
    """
    if G is None or G.number_of_nodes() == 0:
        return {}

    dispatch = {
        "spring": get_spring_layout,
        "kamada_kawai": get_kamada_kawai_layout,
        "circular": get_circular_layout,
        "shell": get_shell_layout,
        "spectral": get_spectral_layout,
        "hierarchical": get_hierarchical_layout,
        "tree": get_tree_layout,
        "radial": get_radial_layout,
    }

    fn = dispatch.get(layout_name, get_spring_layout)
    return fn(G)
