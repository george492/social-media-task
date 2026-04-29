"""
link_prediction.py
------------------
Link prediction algorithms: Common Neighbors, Jaccard Coefficient,
Adamic-Adar Index, and Preferential Attachment.

Includes train/test split (edge masking), scoring, and evaluation
with precision, recall, and accuracy metrics.
"""

import random
import math
import networkx as nx
from typing import Dict, List, Tuple, Optional


# ─── Scoring functions ────────────────────────────────────────────────────────

def common_neighbors_score(G: nx.Graph, u: str, v: str) -> float:
    """Return the number of common neighbors between u and v."""
    try:
        return float(len(list(nx.common_neighbors(G, u, v))))
    except Exception:
        return 0.0


def jaccard_coefficient_score(G: nx.Graph, u: str, v: str) -> float:
    """
    Return the Jaccard Coefficient between u and v.
    |N(u) ∩ N(v)| / |N(u) ∪ N(v)|
    """
    try:
        neighbors_u = set(G.neighbors(u))
        neighbors_v = set(G.neighbors(v))
        union = neighbors_u | neighbors_v
        if not union:
            return 0.0
        return len(neighbors_u & neighbors_v) / len(union)
    except Exception:
        return 0.0


def adamic_adar_score(G: nx.Graph, u: str, v: str) -> float:
    """
    Return the Adamic-Adar index between u and v.
    Sum of 1/log(degree(w)) for each common neighbor w.
    """
    try:
        common = list(nx.common_neighbors(G, u, v))
        score = 0.0
        for w in common:
            deg = G.degree(w)
            if deg > 1:
                score += 1.0 / math.log(deg)
        return score
    except Exception:
        return 0.0


def preferential_attachment_score(G: nx.Graph, u: str, v: str) -> float:
    """
    Return the Preferential Attachment score: degree(u) * degree(v).
    """
    try:
        return float(G.degree(u) * G.degree(v))
    except Exception:
        return 0.0


# ─── Algorithm map ────────────────────────────────────────────────────────────

ALGORITHM_FUNCTIONS = {
    "common_neighbors": common_neighbors_score,
    "jaccard": jaccard_coefficient_score,
    "adamic_adar": adamic_adar_score,
    "preferential_attachment": preferential_attachment_score,
}

ALGORITHM_LABELS = {
    "common_neighbors": "Common Neighbors",
    "jaccard": "Jaccard Coefficient",
    "adamic_adar": "Adamic-Adar Index",
    "preferential_attachment": "Preferential Attachment",
}


# ─── Predict top candidate edges ─────────────────────────────────────────────

def predict_links(
    G: nx.Graph,
    algorithm: str = "jaccard",
    top_n: int = 10,
) -> List[Tuple[str, str, float]]:
    """
    Predict the most likely missing links using the chosen algorithm.

    Args:
        G: A NetworkX graph.
        algorithm: One of 'common_neighbors', 'jaccard', 'adamic_adar',
                   'preferential_attachment'.
        top_n: Number of top predicted edges to return.

    Returns:
        List of (node_u, node_v, score) tuples sorted by score descending.
    """
    if G is None or G.number_of_nodes() < 2:
        return []

    base = G.to_undirected() if G.is_directed() else G
    score_fn = ALGORITHM_FUNCTIONS.get(algorithm, jaccard_coefficient_score)

    nodes = list(base.nodes())
    existing_edges = set(base.edges())
    existing_edges_rev = {(v, u) for u, v in existing_edges}
    all_existing = existing_edges | existing_edges_rev

    candidates = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            u, v = nodes[i], nodes[j]
            if (u, v) not in all_existing and u != v:
                score = score_fn(base, u, v)
                candidates.append((str(u), str(v), round(score, 6)))

    candidates.sort(key=lambda x: x[2], reverse=True)
    return candidates[:top_n]


# ─── Train/Test evaluation ────────────────────────────────────────────────────

def evaluate_link_prediction(
    G: nx.Graph,
    algorithm: str = "jaccard",
    test_fraction: float = 0.2,
    seed: int = 42,
) -> Dict:
    """
    Evaluate a link prediction algorithm by hiding a fraction of edges (test set),
    scoring all non-edges on the training graph, then measuring precision, recall,
    and accuracy.

    Args:
        G: A NetworkX graph.
        algorithm: Prediction algorithm key.
        test_fraction: Fraction of edges to hide for testing (default 20%).
        seed: Random seed for reproducibility.

    Returns:
        Dict with keys: precision, recall, accuracy, f1, num_test_edges,
        num_predicted, algorithm.
    """
    if G is None or G.number_of_nodes() < 4 or G.number_of_edges() < 4:
        return {}

    base = G.to_undirected() if G.is_directed() else G

    # Only use the largest connected component for fair evaluation
    largest_cc = max(nx.connected_components(base), key=len)
    base = base.subgraph(largest_cc).copy()

    if base.number_of_edges() < 4:
        return {}

    all_edges = list(base.edges())
    random.seed(seed)
    random.shuffle(all_edges)

    n_test = max(1, int(len(all_edges) * test_fraction))
    test_edges = set(tuple(sorted(e)) for e in all_edges[:n_test])

    # Build training graph (remove test edges)
    train_G = base.copy()
    train_G.remove_edges_from(all_edges[:n_test])

    # Ensure train graph is still connected enough to be useful
    # If not, just use whatever remains
    score_fn = ALGORITHM_FUNCTIONS.get(algorithm, jaccard_coefficient_score)

    # Score all non-edges in the training graph
    nodes = list(train_G.nodes())
    train_edges_set = set(tuple(sorted(e)) for e in train_G.edges())

    all_existing = set(tuple(sorted(e)) for e in base.edges())  # original
    non_edges = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            u, v = nodes[i], nodes[j]
            key = tuple(sorted((u, v)))
            if key not in train_edges_set:
                score = score_fn(train_G, u, v)
                non_edges.append((key, score))

    if not non_edges:
        return {}

    # Use top-k threshold: predict the top |test_edges| non-edges as links
    non_edges.sort(key=lambda x: x[1], reverse=True)
    k = len(test_edges)
    predicted_edges = set(e for e, _ in non_edges[:k])

    # Compute metrics
    tp = len(predicted_edges & test_edges)
    fp = len(predicted_edges - test_edges)
    fn = len(test_edges - predicted_edges)
    tn = len(non_edges) - tp - fp - fn
    tn = max(0, tn)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0

    return {
        "algorithm": ALGORITHM_LABELS.get(algorithm, algorithm),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "num_test_edges": len(test_edges),
        "num_predicted": k,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
    }
