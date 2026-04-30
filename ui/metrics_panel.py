"""
metrics_panel.py
----------------
The bottom analytics panel: graph stats, degree distribution chart,
community comparison, clustering evaluation, link analysis tables,
and link prediction results.
"""

from dash import dcc, html
import plotly.graph_objects as go
from typing import Dict, Any, Optional, List

from ui.styles import COLORS, STYLE_CARD, STYLE_SECTION_TITLE, PLOTLY_LAYOUT, STYLE_STAT_BOX, STYLE_STAT_VALUE, STYLE_STAT_LABEL


def build_stats_bar(stats: Dict[str, Any]) -> html.Div:
    """Build the top stats bar with key graph metrics."""
    stat_items = [
        ("Nodes", stats.get("num_nodes", "—"), COLORS["accent_blue"]),
        ("Edges", stats.get("num_edges", "—"), COLORS["accent_purple"]),
        ("Avg Degree", stats.get("avg_degree", "—"), COLORS["accent_green"]),
        ("Density", stats.get("density", "—"), COLORS["accent_orange"]),
        ("Clustering", stats.get("clustering_coefficient", "—"), COLORS["accent_red"]),
        ("Avg Path Len", stats.get("avg_path_length", "—"), "#79c0ff"),
    ]

    return html.Div(
        style={
            "display": "flex",
            "gap": "8px",
            "padding": "12px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "flexWrap": "wrap",
        },
        children=[
            html.Div(
                style={**STYLE_STAT_BOX, "flex": "1", "minWidth": "90px"},
                children=[
                    html.Div(str(val), style={**STYLE_STAT_VALUE, "color": color}),
                    html.Div(label, style=STYLE_STAT_LABEL),
                ],
            )
            for label, val, color in stat_items
        ],
    )


def build_degree_distribution_chart(degree_dist: Dict[int, int]) -> dcc.Graph:
    """Build a bar chart of the degree distribution."""
    if not degree_dist:
        fig = go.Figure()
        fig.update_layout(
            **PLOTLY_LAYOUT,
            title={"text": "Degree Distribution", "font": {"size": 13}},
            annotations=[{
                "text": "Load a graph to see distribution",
                "xref": "paper", "yref": "paper",
                "x": 0.5, "y": 0.5,
                "showarrow": False,
                "font": {"color": COLORS["text_muted"], "size": 13},
            }],
        )
        return dcc.Graph(figure=fig, style={"height": "200px"}, config={"displayModeBar": False})

    degrees = list(degree_dist.keys())
    counts = list(degree_dist.values())

    fig = go.Figure(go.Bar(
        x=degrees,
        y=counts,
        marker=dict(
            color=counts,
            colorscale="Blues",
            showscale=False,
        ),
        text=counts,
        textposition="outside",
        textfont={"size": 9, "color": COLORS["text_secondary"]},
    ))

    fig.update_layout(
        **PLOTLY_LAYOUT,
        title={"text": "Degree Distribution", "font": {"size": 13}},
        xaxis={"title": "Degree", **PLOTLY_LAYOUT["xaxis"]},
        yaxis={"title": "Count", **PLOTLY_LAYOUT["yaxis"]},
        bargap=0.2,
    )

    return dcc.Graph(figure=fig, style={"height": "200px"}, config={"displayModeBar": False})


def build_community_comparison(comparison: Optional[Dict[str, Any]]) -> html.Div:
    """Build the side-by-side community algorithm comparison panel."""
    if not comparison:
        return html.Div(
            "Run community detection to see comparison.",
            style={"color": COLORS["text_muted"], "fontSize": "12px", "padding": "8px"},
        )

    def algo_card(name: str, data: dict, icon: str, color: str) -> html.Div:
        return html.Div(
            style={
                "flex": "1",
                "backgroundColor": COLORS["bg_dark"],
                "border": f"1px solid {color}40",
                "borderRadius": "8px",
                "padding": "12px",
                "textAlign": "center",
            },
            children=[
                html.Div(icon, style={"fontSize": "22px", "marginBottom": "6px"}),
                html.Div(name, style={"color": color, "fontWeight": "700", "fontSize": "13px", "marginBottom": "10px"}),
                html.Div([
                    html.Span("Communities: ", style={"color": COLORS["text_muted"], "fontSize": "11px"}),
                    html.Span(str(data.get("num_communities", "—")), style={"color": COLORS["text_primary"], "fontWeight": "700", "fontSize": "14px"}),
                ], style={"marginBottom": "5px"}),
                html.Div([
                    html.Span("Modularity: ", style={"color": COLORS["text_muted"], "fontSize": "11px"}),
                    html.Span(f"{data.get('modularity', 0):.4f}", style={"color": color, "fontWeight": "700", "fontSize": "14px"}),
                ]),
            ],
        )

    return html.Div(
        style={"display": "flex", "gap": "10px"},
        children=[
            algo_card("Girvan-Newman", comparison.get("girvan_newman", {}), "", COLORS["accent_blue"]),
            algo_card("Louvain", comparison.get("louvain", {}), "", COLORS["accent_purple"]),
        ],
    )


def build_evaluation_table(evaluation: Optional[Dict[str, float]]) -> html.Div:
    """Build the clustering evaluation metrics table."""
    if not evaluation:
        return html.Div(
            "Run community detection to see evaluation metrics.",
            style={"color": COLORS["text_muted"], "fontSize": "12px", "padding": "8px"},
        )

    metric_info = {
        "modularity": ("Modularity Q", COLORS["accent_blue"], "Internal quality of communities"),
        "coverage": ("Coverage", COLORS["accent_green"], "Fraction of intra-community edges"),
        "performance": ("Performance", COLORS["accent_purple"], "Correctly classified node pairs"),
        "intra_inter_ratio": ("Intra/Inter Ratio", COLORS["accent_orange"], "Internal vs external edge ratio"),
        "nmi": ("NMI (vs Group)", COLORS["accent_red"], "Normalized Mutual Information with ground truth"),
    }

    rows = []
    for key, (label, color, desc) in metric_info.items():
        val = evaluation.get(key)
        if val is None:
            continue
        rows.append(html.Tr([
            html.Td(label, style={"color": COLORS["text_secondary"], "fontSize": "12px", "padding": "5px 8px"}),
            html.Td(
                f"{val:.4f}",
                style={"color": color, "fontWeight": "700", "fontSize": "13px", "padding": "5px 8px", "textAlign": "right"},
            ),
            html.Td(desc, style={"color": COLORS["text_muted"], "fontSize": "11px", "padding": "5px 8px"}),
        ]))

    return html.Table(
        style={"width": "100%", "borderCollapse": "collapse"},
        children=[
            html.Thead(html.Tr([
                html.Th("Metric", style={"color": COLORS["text_muted"], "fontSize": "11px", "textAlign": "left", "padding": "4px 8px", "borderBottom": f"1px solid {COLORS['border']}"}),
                html.Th("Score", style={"color": COLORS["text_muted"], "fontSize": "11px", "textAlign": "right", "padding": "4px 8px", "borderBottom": f"1px solid {COLORS['border']}"}),
                html.Th("Description", style={"color": COLORS["text_muted"], "fontSize": "11px", "textAlign": "left", "padding": "4px 8px", "borderBottom": f"1px solid {COLORS['border']}"}),
            ])),
            html.Tbody(rows),
        ],
    )


def build_top_nodes_table(top_nodes: List[tuple], metric_name: str) -> html.Div:
    """Build a ranked table of most influential nodes."""
    if not top_nodes:
        return html.Div(
            "Run link analysis to see influential nodes.",
            style={"color": COLORS["text_muted"], "fontSize": "12px", "padding": "8px"},
        )

    rows = []
    for rank, (node_id, score) in enumerate(top_nodes, 1):
        medal = f"#{rank}"
        rows.append(html.Tr([
            html.Td(str(medal), style={"padding": "4px 8px", "fontSize": "12px", "color": COLORS["accent_orange"]}),
            html.Td(str(node_id), style={"padding": "4px 8px", "fontSize": "12px", "color": COLORS["text_primary"], "fontWeight": "600"}),
            html.Td(f"{score:.6f}", style={"padding": "4px 8px", "fontSize": "12px", "color": COLORS["accent_blue"], "textAlign": "right"}),
        ]))

    return html.Div([
        html.P(f"Top Nodes by {metric_name.replace('_', ' ').title()}", style={
            "fontSize": "11px",
            "color": COLORS["text_secondary"],
            "marginBottom": "6px",
            "fontWeight": "600",
            "letterSpacing": "0.06em",
            "textTransform": "uppercase",
        }),
        html.Table(
            style={"width": "100%", "borderCollapse": "collapse"},
            children=[
                html.Thead(html.Tr([
                    html.Th("Rank", style={"color": COLORS["text_muted"], "fontSize": "10px", "padding": "3px 8px", "borderBottom": f"1px solid {COLORS['border']}"}),
                    html.Th("Node", style={"color": COLORS["text_muted"], "fontSize": "10px", "padding": "3px 8px", "borderBottom": f"1px solid {COLORS['border']}"}),
                    html.Th("Score", style={"color": COLORS["text_muted"], "fontSize": "10px", "textAlign": "right", "padding": "3px 8px", "borderBottom": f"1px solid {COLORS['border']}"}),
                ])),
                html.Tbody(rows),
            ],
        ),
    ])


def build_link_prediction_table(predictions: list) -> html.Div:
    """Build a table of top predicted links (node_u, node_v, score)."""
    if not predictions:
        return html.Div(
            "Run link prediction to see top candidate edges.",
            style={"color": COLORS["text_muted"], "fontSize": "12px", "padding": "8px"},
        )

    rows = []
    for rank, (u, v, score) in enumerate(predictions, 1):
        medal = f"#{rank}"
        rows.append(html.Tr([
            html.Td(medal, style={"padding": "4px 6px", "fontSize": "11px", "color": COLORS["accent_orange"]}),
            html.Td(
                f"{u} — {v}",
                style={"padding": "4px 6px", "fontSize": "11px", "color": COLORS["text_primary"], "fontWeight": "600"},
            ),
            html.Td(
                f"{score:.4f}",
                style={"padding": "4px 6px", "fontSize": "11px", "color": COLORS["accent_blue"], "textAlign": "right"},
            ),
        ]))

    return html.Div([
        html.P("Top Predicted Links", style={
            "fontSize": "11px",
            "color": COLORS["text_secondary"],
            "marginBottom": "6px",
            "fontWeight": "600",
            "letterSpacing": "0.06em",
            "textTransform": "uppercase",
        }),
        html.Table(
            style={"width": "100%", "borderCollapse": "collapse"},
            children=[
                html.Thead(html.Tr([
                    html.Th("Rank", style={"color": COLORS["text_muted"], "fontSize": "10px", "padding": "3px 6px", "borderBottom": f"1px solid {COLORS['border']}"}),
                    html.Th("Edge", style={"color": COLORS["text_muted"], "fontSize": "10px", "padding": "3px 6px", "borderBottom": f"1px solid {COLORS['border']}"}),
                    html.Th("Score", style={"color": COLORS["text_muted"], "fontSize": "10px", "textAlign": "right", "padding": "3px 6px", "borderBottom": f"1px solid {COLORS['border']}"}),
                ])),
                html.Tbody(rows),
            ],
        ),
    ])


def build_link_prediction_eval(evaluation: dict) -> html.Div:
    """Build the evaluation metrics card for link prediction."""
    if not evaluation:
        return html.Div(
            "Evaluation results will appear here.",
            style={"color": COLORS["text_muted"], "fontSize": "12px", "padding": "8px"},
        )

    metric_info = [
        ("Precision", "precision", COLORS["accent_blue"]),
        ("Recall", "recall", COLORS["accent_green"]),
        ("F1 Score", "f1", COLORS["accent_purple"]),
        ("Accuracy", "accuracy", COLORS["accent_orange"]),
    ]

    rows = []
    for label, key, color in metric_info:
        val = evaluation.get(key)
        if val is None:
            continue
        rows.append(html.Tr([
            html.Td(label, style={"color": COLORS["text_secondary"], "fontSize": "11px", "padding": "4px 6px"}),
            html.Td(
                f"{val:.4f}",
                style={"color": color, "fontWeight": "700", "fontSize": "12px", "padding": "4px 6px", "textAlign": "right"},
            ),
        ]))

    tp = evaluation.get("true_positives", "—")
    fp = evaluation.get("false_positives", "—")
    fn = evaluation.get("false_negatives", "—")
    algo = evaluation.get("algorithm", "")
    n_test = evaluation.get("num_test_edges", "—")

    return html.Div([
        html.P(
            f"Eval: {algo} ({n_test} test edges)",
            style={"fontSize": "10px", "color": COLORS["text_muted"], "marginBottom": "4px"},
        ),
        html.Table(
            style={"width": "100%", "borderCollapse": "collapse"},
            children=[html.Tbody(rows)],
        ),
        html.Div(
            f"TP={tp}  FP={fp}  FN={fn}",
            style={"fontSize": "10px", "color": COLORS["text_muted"], "marginTop": "6px"},
        ),
    ])


def build_metrics_panel() -> html.Div:
    """Assemble the bottom analytics panel with all metric sections."""
    return html.Div(
        style={
            "borderTop": f"1px solid {COLORS['border']}",
            "backgroundColor": COLORS["bg_dark"],
            "display": "flex",
            "flexDirection": "column",
            "height": "280px",
            "flexShrink": "0",
            "overflow": "hidden",
        },
        children=[
            # Stats bar
            html.Div(id="stats-bar", children=build_stats_bar({})),

            # Tab content
            html.Div(
                style={"display": "flex", "flex": "1", "gap": "0", "overflow": "hidden"},
                children=[
                    # Degree distribution
                    html.Div(
                        style={
                            "flex": "1.3",
                            "borderRight": f"1px solid {COLORS['border']}",
                            "padding": "10px 12px",
                            "overflow": "hidden",
                        },
                        children=[
                            html.P("Degree Distribution", style={
                                "color": COLORS["text_secondary"],
                                "fontSize": "11px",
                                "fontWeight": "600",
                                "letterSpacing": "0.08em",
                                "textTransform": "uppercase",
                                "marginBottom": "8px",
                                "marginTop": "0",
                            }),
                            html.Div(id="degree-dist-chart"),
                        ],
                    ),

                    # Community comparison
                    html.Div(
                        style={
                            "flex": "1",
                            "borderRight": f"1px solid {COLORS['border']}",
                            "padding": "10px 12px",
                            "overflow": "auto",
                        },
                        children=[
                            html.P("Community Comparison", style={
                                "color": COLORS["text_secondary"],
                                "fontSize": "11px",
                                "fontWeight": "600",
                                "letterSpacing": "0.08em",
                                "textTransform": "uppercase",
                                "marginBottom": "8px",
                                "marginTop": "0",
                            }),
                            html.Div(id="community-comparison"),

                            html.P("Evaluation Metrics", style={
                                "color": COLORS["text_secondary"],
                                "fontSize": "11px",
                                "fontWeight": "600",
                                "letterSpacing": "0.08em",
                                "textTransform": "uppercase",
                                "marginBottom": "8px",
                                "marginTop": "14px",
                            }),
                            html.Div(id="evaluation-metrics"),
                        ],
                    ),

                    # Link analysis
                    html.Div(
                        style={
                            "flex": "1",
                            "borderRight": f"1px solid {COLORS['border']}",
                            "padding": "10px 12px",
                            "overflow": "auto",
                        },
                        children=[
                            html.Div(id="link-analysis-table"),
                        ],
                    ),

                    # Link prediction
                    html.Div(
                        style={
                            "flex": "1.1",
                            "padding": "10px 12px",
                            "overflow": "auto",
                        },
                        children=[
                            html.P("Link Prediction", style={
                                "color": COLORS["text_secondary"],
                                "fontSize": "11px",
                                "fontWeight": "600",
                                "letterSpacing": "0.08em",
                                "textTransform": "uppercase",
                                "marginBottom": "8px",
                                "marginTop": "0",
                            }),
                            html.Div(id="link-prediction-table"),
                            html.P("Prediction Accuracy", style={
                                "color": COLORS["text_secondary"],
                                "fontSize": "11px",
                                "fontWeight": "600",
                                "letterSpacing": "0.08em",
                                "textTransform": "uppercase",
                                "marginBottom": "6px",
                                "marginTop": "12px",
                            }),
                            html.Div(id="link-prediction-eval"),
                        ],
                    ),
                ],
            ),
        ],
    )
