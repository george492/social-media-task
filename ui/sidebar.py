"""
sidebar.py
----------
Dash sidebar layout: file upload, graph controls, layout selector,
centrality filters, community detection, and link analysis controls.
"""

from dash import dcc, html
import dash_cytoscape as cyto
from ui.styles import COLORS, STYLE_CARD, STYLE_SECTION_TITLE, STYLE_LABEL, STYLE_BUTTON
from src.layout import LAYOUT_OPTIONS


def build_upload_card() -> html.Div:
    """Build the file upload section for nodes and edges CSVs."""
    return html.Div(
        style=STYLE_CARD,
        children=[
            html.P("Load Graph Data", style=STYLE_SECTION_TITLE),

            html.Label("Nodes CSV", style=STYLE_LABEL),
            dcc.Upload(
                id="upload-nodes",
                children=html.Div([
                    html.Span("", style={"fontSize": "16px"}),
                    "Drop or ",
                    html.A("select nodes file", style={"color": COLORS["accent_blue"]}),
                ]),
                style={
                    "width": "100%",
                    "padding": "10px",
                    "borderRadius": "6px",
                    "border": f"1px dashed {COLORS['border']}",
                    "textAlign": "center",
                    "cursor": "pointer",
                    "backgroundColor": COLORS["bg_dark"],
                    "color": COLORS["text_secondary"],
                    "fontSize": "12px",
                    "marginBottom": "8px",
                    "boxSizing": "border-box",
                },
            ),
            html.Div(id="nodes-upload-status", style={"fontSize": "11px", "color": COLORS["accent_green"], "marginBottom": "8px"}),

            html.Label("Edges CSV", style=STYLE_LABEL),
            dcc.Upload(
                id="upload-edges",
                children=html.Div([
                    html.Span("", style={"fontSize": "16px"}),
                    "Drop or ",
                    html.A("select edges file", style={"color": COLORS["accent_blue"]}),
                ]),
                style={
                    "width": "100%",
                    "padding": "10px",
                    "borderRadius": "6px",
                    "border": f"1px dashed {COLORS['border']}",
                    "textAlign": "center",
                    "cursor": "pointer",
                    "backgroundColor": COLORS["bg_dark"],
                    "color": COLORS["text_secondary"],
                    "fontSize": "12px",
                    "marginBottom": "8px",
                    "boxSizing": "border-box",
                },
            ),
            html.Div(id="edges-upload-status", style={"fontSize": "11px", "color": COLORS["accent_green"], "marginBottom": "12px"}),

            html.Button(
                "Load Sample Data",
                id="btn-load-sample",
                style={**STYLE_BUTTON, "backgroundColor": COLORS["accent_green"], "marginBottom": "6px"},
            ),
            html.Button(
                "Build Graph",
                id="btn-build-graph",
                style=STYLE_BUTTON,
            ),
        ],
    )


def build_graph_controls_card() -> html.Div:
    """Build the graph type + layout controls."""
    return html.Div(
        style=STYLE_CARD,
        children=[
            html.P("Graph Settings", style=STYLE_SECTION_TITLE),

            html.Label("Graph Type", style=STYLE_LABEL),
            dcc.RadioItems(
                id="radio-graph-type",
                options=[
                    {"label": " Undirected", "value": "undirected"},
                    {"label": " Directed", "value": "directed"},
                ],
                value="undirected",
                inline=True,
                style={"color": COLORS["text_primary"], "fontSize": "13px", "marginBottom": "12px"},
                inputStyle={"marginRight": "4px", "accentColor": COLORS["accent_blue"]},
                labelStyle={"marginRight": "14px"},
            ),

            html.Label("Layout Algorithm", style=STYLE_LABEL),
            dcc.Dropdown(
                id="dropdown-layout",
                options=LAYOUT_OPTIONS,
                value="spring",
                clearable=False,
                style={
                    "backgroundColor": COLORS["bg_dark"],
                    "color": COLORS["text_primary"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "6px",
                    "fontSize": "13px",
                    "marginBottom": "12px",
                },
                className="dark-dropdown",
            ),

            html.Label("Node Size Scale", style=STYLE_LABEL),
            dcc.Slider(
                id="slider-node-size",
                min=5, max=40, step=1, value=18,
                marks={5: "5", 20: "20", 40: "40"},
                tooltip={"placement": "bottom", "always_visible": False},
            ),
            html.Div(style={"marginBottom": "12px"}),

            html.Label("Edge Thickness Scale", style=STYLE_LABEL),
            dcc.Slider(
                id="slider-edge-thickness",
                min=1, max=8, step=0.5, value=2,
                marks={1: "1", 4: "4", 8: "8"},
                tooltip={"placement": "bottom", "always_visible": False},
            ),
        ],
    )


def build_coloring_card() -> html.Div:
    """Build the node coloring / highlighting controls."""
    return html.Div(
        style=STYLE_CARD,
        children=[
            html.P("Visual Highlighting", style=STYLE_SECTION_TITLE),

            html.Label("Color Nodes By", style=STYLE_LABEL),
            dcc.Dropdown(
                id="dropdown-color-by",
                options=[
                    {"label": "Community", "value": "community"},
                    {"label": "PageRank", "value": "pagerank"},
                    {"label": "Betweenness Centrality", "value": "betweenness"},
                    {"label": "Degree Centrality", "value": "degree"},
                    {"label": "Closeness Centrality", "value": "closeness"},
                    {"label": "Source Group", "value": "group"},
                ],
                value="community",
                clearable=False,
                style={
                    "backgroundColor": COLORS["bg_dark"],
                    "color": COLORS["text_primary"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "6px",
                    "fontSize": "13px",
                    "marginBottom": "10px",
                },
                className="dark-dropdown",
            ),

            html.Label("Size Nodes By", style=STYLE_LABEL),
            dcc.Dropdown(
                id="dropdown-size-by",
                options=[
                    {"label": "Uniform", "value": "uniform"},
                    {"label": "PageRank", "value": "pagerank"},
                    {"label": "Betweenness Centrality", "value": "betweenness"},
                    {"label": "Degree Centrality", "value": "degree"},
                ],
                value="uniform",
                clearable=False,
                style={
                    "backgroundColor": COLORS["bg_dark"],
                    "color": COLORS["text_primary"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "6px",
                    "fontSize": "13px",
                    "marginBottom": "10px",
                },
                className="dark-dropdown",
            ),

            html.Label("Label Nodes By", style=STYLE_LABEL),
            dcc.Dropdown(
                id="dropdown-label-by",
                options=[
                    {"label": "ID", "value": "id"},
                ],
                value="id",
                clearable=False,
                style={
                    "backgroundColor": COLORS["bg_dark"],
                    "color": COLORS["text_primary"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "6px",
                    "fontSize": "13px",
                    "marginBottom": "10px",
                },
                className="dark-dropdown",
            ),

            html.Label("Color Edges By", style=STYLE_LABEL),
            dcc.Dropdown(
                id="dropdown-edge-color-by",
                options=[
                    {"label": "Uniform", "value": "uniform"},
                ],
                value="uniform",
                clearable=False,
                style={
                    "backgroundColor": COLORS["bg_dark"],
                    "color": COLORS["text_primary"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "6px",
                    "fontSize": "13px",
                },
                className="dark-dropdown",
            ),
        ],
    )


def build_centrality_filter_card() -> html.Div:
    """Build centrality-based node filtering sliders."""
    return html.Div(
        style=STYLE_CARD,
        children=[
            html.P("Centrality Filters", style=STYLE_SECTION_TITLE),

            html.Label("Degree", style=STYLE_LABEL),
            dcc.RangeSlider(
                id="filter-degree",
                min=0, max=1, step=0.01,
                value=[0, 1],
                marks={0: "0", 0.5: "0.5", 1: "1"},
                tooltip={"placement": "bottom", "always_visible": False},
            ),
            html.Div(style={"marginBottom": "10px"}),

            html.Label("Betweenness Centrality", style=STYLE_LABEL),
            dcc.RangeSlider(
                id="filter-betweenness",
                min=0, max=1, step=0.01,
                value=[0, 1],
                marks={0: "0", 0.5: "0.5", 1: "1"},
                tooltip={"placement": "bottom", "always_visible": False},
            ),
            html.Div(style={"marginBottom": "10px"}),

            html.Label("Closeness Centrality", style=STYLE_LABEL),
            dcc.RangeSlider(
                id="filter-closeness",
                min=0, max=1, step=0.01,
                value=[0, 1],
                marks={0: "0", 0.5: "0.5", 1: "1"},
                tooltip={"placement": "bottom", "always_visible": False},
            ),
        ],
    )


def build_community_card() -> html.Div:
    """Build community detection controls."""
    return html.Div(
        style=STYLE_CARD,
        children=[
            html.P("Community Detection", style=STYLE_SECTION_TITLE),

            html.Label("Algorithm", style=STYLE_LABEL),
            dcc.Dropdown(
                id="dropdown-community-algo",
                options=[
                    {"label": "Louvain", "value": "louvain"},
                    {"label": "Girvan-Newman", "value": "girvan_newman"},
                    {"label": "Both (Compare)", "value": "both"},
                ],
                value="louvain",
                clearable=False,
                style={
                    "backgroundColor": COLORS["bg_dark"],
                    "color": COLORS["text_primary"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "6px",
                    "fontSize": "13px",
                    "marginBottom": "10px",
                },
                className="dark-dropdown",
            ),

            html.Div(
                id="gn-k-container",
                style={"display": "none"},  # Hidden by default since Louvain is default
                children=[
                    html.Label("Girvan-Newman K (communities)", style=STYLE_LABEL),
                    dcc.Slider(
                        id="slider-gn-k",
                        min=2, max=10, step=1, value=4,
                        marks={2: "2", 5: "5", 10: "10"},
                        tooltip={"placement": "bottom", "always_visible": False},
                    ),
                    html.Div(style={"marginBottom": "10px"}),
                ]
            ),

            html.Button(
                "Run Detection",
                id="btn-run-community",
                style=STYLE_BUTTON,
            ),
        ],
    )




def build_sidebar() -> html.Div:
    """Assemble the complete sidebar from all control cards."""
    from ui.styles import STYLE_SIDEBAR
    return html.Div(
        id="sidebar",
        style=STYLE_SIDEBAR,
        children=[
            build_upload_card(),
            build_graph_controls_card(),
            build_coloring_card(),
            build_centrality_filter_card(),
            build_community_card(),
        ],
    )
