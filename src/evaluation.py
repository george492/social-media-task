"""
evaluation.py
-------------
Clustering evaluation metrics for assessing community detection quality.
Implements internal, external, and coverage-based measures.
"""

import networkx as nx
import networkx.algorithms.community as nx_comm
from typing import Dict, List, Optional
import math


def modularity_score(G: nx.Graph, partition: Dict[str, int]) -> float:
    """
    Compute modularity Q for the given partition.
    Modularity measures the density of links inside communities vs. between them.
    Range: approximately [-0.5, 1.0]. Higher is better.

    Args:
        G: A NetworkX graph.
        partition: Dict mapping node_id -> community_id.

    Returns:
        Modularity score (float).
    """
    if G is None or not partition:
        return None

    base = G.to_undirected() if G.is_directed() else G
    graph_nodes = set(str(n) for n in base.nodes())
    # Filter partition to only nodes that exist in the graph
    filtered = {n: c for n, c in partition.items() if str(n) in graph_nodes}

    str_to_node = {str(n): n for n in base.nodes()}

    community_ids = set(filtered.values())
    communities = []
    for cid in community_ids:
        comp = {str_to_node[n] for n, c in filtered.items() if c == cid and n in str_to_node}
        if comp:
            communities.append(comp)
            
    # Add any missing nodes as singleton communities
    missing_nodes = graph_nodes - set(filtered.keys())
    for missing_node in missing_nodes:
        if missing_node in str_to_node:
            communities.append({str_to_node[missing_node]})

    try:
        val = round(nx_comm.modularity(base, communities), 4)
        if val == -0.0:
            val = 0.0
        return val
    except Exception as exc:
        print(f"[evaluation] modularity failed: {exc}")
        return None


def coverage_score(G: nx.Graph, partition: Dict[str, int]) -> float:
    """
    Compute coverage: fraction of intra-community edges over all edges.
    Range: [0, 1]. Higher means more edges are within communities.

    Args:
        G: A NetworkX graph.
        partition: Dict mapping node_id -> community_id.

    Returns:
        Coverage score (float).
    """
    if G is None or G.number_of_edges() == 0 or not partition:
        return None

    base = G.to_undirected() if G.is_directed() else G
    graph_nodes = set(str(n) for n in base.nodes())
    filtered = {n: c for n, c in partition.items() if str(n) in graph_nodes}

    str_to_node = {str(n): n for n in base.nodes()}

    community_ids = set(filtered.values())
    communities = []
    for cid in community_ids:
        comp = {str_to_node[n] for n, c in filtered.items() if c == cid and n in str_to_node}
        if comp:
            communities.append(comp)

    missing_nodes = graph_nodes - set(filtered.keys())
    for missing_node in missing_nodes:
        if missing_node in str_to_node:
            communities.append({str_to_node[missing_node]})

    try:
        # NetworkX has no nx_comm.coverage, it's partition_quality
        coverage, _ = nx_comm.partition_quality(base, communities)
        return round(coverage, 4)
    except Exception as exc:
        print(f"[evaluation] coverage failed: {exc}")
        return None


def performance_score(G: nx.Graph, partition: Dict[str, int]) -> float:
    """
    Compute partition performance: fraction of correctly classified pairs.
    A pair is correct if both nodes are in the same community AND connected,
    or in different communities AND not connected.
    Range: [0, 1]. Higher is better.
    SKIPPED for graphs with > 150 nodes (O(n²) complexity).

    Args:
        G: A NetworkX graph.
        partition: Dict mapping node_id -> community_id.

    Returns:
        Performance score (float), or None if skipped (large graph).
    """
    if G is None or G.number_of_nodes() < 2 or not partition:
        return None

    base = G.to_undirected() if G.is_directed() else G
    graph_nodes = set(str(n) for n in base.nodes())
    filtered = {n: c for n, c in partition.items() if str(n) in graph_nodes}

    str_to_node = {str(n): n for n in base.nodes()}

    community_ids = set(filtered.values())
    communities = []
    for cid in community_ids:
        comp = {str_to_node[n] for n, c in filtered.items() if c == cid and n in str_to_node}
        if comp:
            communities.append(comp)

    missing_nodes = graph_nodes - set(filtered.keys())
    for missing_node in missing_nodes:
        if missing_node in str_to_node:
            communities.append({str_to_node[missing_node]})

    try:
        _, performance = nx_comm.partition_quality(base, communities)
        return round(performance, 4)
    except Exception as exc:
        print(f"[evaluation] performance failed: {exc}")
        return None


def intra_inter_edge_ratio(G: nx.Graph, partition: Dict[str, int]) -> float:
    """
    Compute the ratio of intra-community edges to inter-community edges.
    Higher values indicate better community separation.

    Args:
        G: A NetworkX graph.
        partition: Dict mapping node_id -> community_id.

    Returns:
        Ratio (float). Returns 0.0 if no inter-community edges exist.
    """
    if G is None or G.number_of_edges() == 0 or not partition:
        return None

    intra, inter = 0, 0
    for u, v in G.edges():
        cu = partition.get(str(u))
        cv = partition.get(str(v))
        if cu is not None and cv is not None:
            if cu == cv:
                intra += 1
            else:
                inter += 1

    if inter == 0:
        return 999.0  # All edges are intra-community (perfect separation) — cap for display

    return round(intra / inter, 4)


def nmi_score(
    true_labels: Optional[Dict[str, int]],
    pred_labels: Dict[str, int],
) -> Optional[float]:
    """
    Compute Normalized Mutual Information (NMI) between ground-truth labels and predicted communities.
    Only available when ground-truth labels exist (e.g., 'group' column in nodes CSV).

    Args:
        true_labels: Dict mapping node_id -> true community id. None if not available.
        pred_labels: Dict mapping node_id -> predicted community id.

    Returns:
        NMI score [0, 1] if true_labels available, else None.
    """
    if true_labels is None or not pred_labels:
        return None

    # Find common nodes
    common_nodes = sorted(set(true_labels.keys()) & set(pred_labels.keys()))
    if len(common_nodes) < 2:
        return None

    y_true = [true_labels[n] for n in common_nodes]
    y_pred = [pred_labels[n] for n in common_nodes]

    # Compute NMI manually (no sklearn dependency)
    try:
        return round(_compute_nmi(y_true, y_pred), 4)
    except Exception:
        return None


def _compute_nmi(y_true: List[int], y_pred: List[int]) -> float:
    """
    Internal NMI computation without sklearn.
    Uses information-theoretic formula: NMI = 2 * MI(Y,C) / (H(Y) + H(C)).
    """
    n = len(y_true)
    if n == 0:
        return 0.0

    # Build contingency table
    true_classes = list(set(y_true))
    pred_classes = list(set(y_pred))
    contingency: Dict[tuple, int] = {}
    for t, p in zip(y_true, y_pred):
        contingency[(t, p)] = contingency.get((t, p), 0) + 1

    # Marginals
    true_counts = {c: y_true.count(c) for c in true_classes}
    pred_counts = {c: y_pred.count(c) for c in pred_classes}

    def entropy(counts: dict) -> float:
        total = sum(counts.values())
        return -sum((v / total) * math.log(v / total + 1e-12) for v in counts.values())

    h_true = entropy(true_counts)
    h_pred = entropy(pred_counts)

    # Mutual information
    mi = 0.0
    for (t, p), n_tp in contingency.items():
        if n_tp > 0:
            n_t = true_counts[t]
            n_p = pred_counts[p]
            mi += (n_tp / n) * math.log((n * n_tp) / (n_t * n_p) + 1e-12)

    denom = h_true + h_pred
    return 2 * mi / denom if denom > 0 else 0.0


def evaluate_partition(
    G: nx.Graph,
    partition: Dict[str, int],
    true_labels: Optional[Dict[str, int]] = None,
) -> Dict[str, float]:
    """
    Compute all available evaluation metrics for a partition.

    Args:
        G: A NetworkX graph.
        partition: Dict mapping node_id -> community_id.
        true_labels: Optional ground-truth labels dict.

    Returns:
        Dict with metric names as keys and scores as values.
    """
    results = {
        "modularity": modularity_score(G, partition),
        "coverage": coverage_score(G, partition),
        "intra_inter_ratio": intra_inter_edge_ratio(G, partition),
    }

    # Performance is O(n²) — only run on small graphs
    try:
        perf = performance_score(G, partition)
        if perf is not None:
            results["performance"] = perf
    except Exception as e:
        print(f"[evaluation] performance error: {e}")

    # NMI runs independently — never blocked by performance skip
    try:
        nmi = nmi_score(true_labels, partition)
        if nmi is not None:
            results["nmi"] = nmi
    except Exception as e:
        print(f"[evaluation] nmi error: {e}")

    return results
