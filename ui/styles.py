"""
styles.py
---------
Centralized CSS-in-Python style definitions and color palette for the dashboard.
Keeps all styling out of layout files for easy theming.
"""

# === Color Palette ===
COLORS = {
    "bg_dark": "#0d1117",
    "bg_card": "#161b22",
    "bg_sidebar": "#0d1117",
    "bg_panel": "#161b22",
    "border": "#30363d",
    "accent_blue": "#58a6ff",
    "accent_purple": "#bc8cff",
    "accent_green": "#3fb950",
    "accent_orange": "#e3b341",
    "accent_red": "#f85149",
    "text_primary": "#e6edf3",
    "text_secondary": "#8b949e",
    "text_muted": "#484f58",
    "gradient_start": "#1f6feb",
    "gradient_end": "#388bfd",
    "node_communities": [
        "#58a6ff",  # 0 - blue
        "#3fb950",  # 1 - green
        "#ff7b72",  # 2 - coral
        "#d2a8ff",  # 3 - lavender
        "#ffa657",  # 4 - orange
        "#79c0ff",  # 5 - sky blue
        "#56d364",  # 6 - light green
        "#f0883e",  # 7 - amber
        "#a5d6ff",  # 8 - pale blue
        "#e3b341",  # 9 - gold
    ],
}

# === Layout Dimensions ===
SIDEBAR_WIDTH = "300px"
HEADER_HEIGHT = "60px"

# === Component Styles ===

STYLE_APP = {
    "backgroundColor": COLORS["bg_dark"],
    "minHeight": "100vh",
    "fontFamily": "'Inter', 'Segoe UI', sans-serif",
    "color": COLORS["text_primary"],
}

STYLE_HEADER = {
    "background": f"linear-gradient(135deg, {COLORS['gradient_start']}, {COLORS['gradient_end']})",
    "padding": "0 24px",
    "height": HEADER_HEIGHT,
    "display": "flex",
    "alignItems": "center",
    "justifyContent": "space-between",
    "boxShadow": "0 1px 0 rgba(255,255,255,0.06)",
    "position": "sticky",
    "top": "0",
    "zIndex": "100",
}

STYLE_SIDEBAR = {
    "width": SIDEBAR_WIDTH,
    "minWidth": SIDEBAR_WIDTH,
    "backgroundColor": COLORS["bg_sidebar"],
    "borderRight": f"1px solid {COLORS['border']}",
    "overflowY": "auto",
    "maxHeight": f"calc(100vh - {HEADER_HEIGHT})",
    "padding": "16px",
}

STYLE_MAIN = {
    "flex": "1",
    "display": "flex",
    "flexDirection": "column",
    "overflow": "hidden",
}

STYLE_CARD = {
    "backgroundColor": COLORS["bg_card"],
    "border": f"1px solid {COLORS['border']}",
    "borderRadius": "8px",
    "padding": "16px",
    "marginBottom": "12px",
}

STYLE_SECTION_TITLE = {
    "color": COLORS["text_secondary"],
    "fontSize": "11px",
    "fontWeight": "600",
    "letterSpacing": "0.08em",
    "textTransform": "uppercase",
    "marginBottom": "8px",
    "marginTop": "0",
}

STYLE_LABEL = {
    "color": COLORS["text_secondary"],
    "fontSize": "12px",
    "marginBottom": "4px",
    "display": "block",
}

STYLE_STAT_BOX = {
    "backgroundColor": COLORS["bg_dark"],
    "border": f"1px solid {COLORS['border']}",
    "borderRadius": "6px",
    "padding": "10px 14px",
    "textAlign": "center",
}

STYLE_STAT_VALUE = {
    "fontSize": "22px",
    "fontWeight": "700",
    "color": COLORS["accent_blue"],
    "lineHeight": "1.2",
}

STYLE_STAT_LABEL = {
    "fontSize": "11px",
    "color": COLORS["text_muted"],
    "marginTop": "2px",
}

STYLE_BUTTON = {
    "backgroundColor": COLORS["gradient_start"],
    "color": "#ffffff",
    "border": "none",
    "borderRadius": "6px",
    "padding": "8px 16px",
    "cursor": "pointer",
    "fontSize": "13px",
    "fontWeight": "500",
    "width": "100%",
    "transition": "all 0.2s ease",
}

STYLE_BADGE = {
    "display": "inline-block",
    "padding": "2px 8px",
    "borderRadius": "12px",
    "fontSize": "11px",
    "fontWeight": "600",
}

# Graph Cytoscape stylesheet
CYTOSCAPE_STYLESHEET = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "font-size": "10px",
            "font-family": "Inter, sans-serif",
            "color": "#e6edf3",
            "text-valign": "center",
            "text-halign": "center",
            "background-color": "data(color)",
            "width": "data(size)",
            "height": "data(size)",
            "border-width": "2px",
            "border-color": "rgba(255,255,255,0.15)",
            "text-outline-width": "2px",
            "text-outline-color": "#0d1117",
            "transition-property": "background-color, width, height, border-color",
            "transition-duration": "0.3s",
        },
    },
    {
        "selector": "node:selected",
        "style": {
            "border-width": "3px",
            "border-color": "#58a6ff",
            "box-shadow": "0 0 15px rgba(88, 166, 255, 0.6)",
        },
    },
    {
        "selector": "node.highlighted",
        "style": {
            "border-width": "3px",
            "border-color": "#e3b341",
            "box-shadow": "0 0 12px rgba(227, 179, 65, 0.5)",
        },
    },
    {
        "selector": "node.faded",
        "style": {
            "opacity": "0.25",
        },
    },
    {
        "selector": "edge",
        "style": {
            "width": "data(thickness)",
            "line-color": "data(color)",
            "opacity": "0.6",
            "curve-style": "bezier",
            "transition-property": "opacity, line-color",
            "transition-duration": "0.3s",
        },
    },
    {
        "selector": "edge[directed = 'true']",
        "style": {
            "target-arrow-color": "data(color)",
            "target-arrow-shape": "triangle",
            "arrow-scale": "0.8",
        },
    },
    {
        "selector": "edge:selected",
        "style": {
            "opacity": "1.0",
            "line-color": "#58a6ff",
            "width": "3px",
        },
    },
    {
        "selector": "edge.faded",
        "style": {
            "opacity": "0.08",
        },
    },
]

# Plotly figure layout template
PLOTLY_LAYOUT = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"color": "#e6edf3", "family": "Inter, sans-serif", "size": 12},
    "margin": {"l": 40, "r": 20, "t": 30, "b": 40},
    "xaxis": {
        "gridcolor": "#21262d",
        "linecolor": "#30363d",
        "title_font": {"size": 11},
    },
    "yaxis": {
        "gridcolor": "#21262d",
        "linecolor": "#30363d",
        "title_font": {"size": 11},
    },
}
