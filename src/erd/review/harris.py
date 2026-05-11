"""harris.py — Harris Matrix SVG Generator.

Generates stratigraphic Harris Matrix SVG diagrams from context sheet
JSON data. Uses pure Python (no graphviz dependency) — renders a
directed acyclic graph showing the chronological relationships between
archaeological contexts.

exports: generate_harris_matrix, render_harris_svg
used_by: erd.phases.phase5  → appendices
         erd.review.dashboard → visual review aid
rules:   Must never import torch or any GPU-bound library.
         Context numbers rendered as [N] per archaeological convention.
         Direction: earliest at bottom, latest at top (standard Harris).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── Layout Constants ─────────────────────────────────────────────────────────

NODE_WIDTH = 100
NODE_HEIGHT = 40
NODE_PADDING_X = 30
NODE_PADDING_Y = 60
LEVEL_GAP = 20
MARGIN = 40
ARROW_SIZE = 6

# ── Data Structures ──────────────────────────────────────────────────────────


class StratigraphicNode:
    """A single context node in the Harris Matrix."""

    def __init__(self, context_number: str, label: str = "", period: str = "") -> None:
        self.context_number = context_number
        self.label = label
        self.period = period
        self.level: int = 0
        self.x: float = 0.0
        self.y: float = 0.0
        self.parents: list[str] = []  # contexts that this context is later than
        self.children: list[str] = []  # contexts that this context is earlier than

    @property
    def display_label(self) -> str:
        parts = [f"[{self.context_number}]"]
        if self.label and len(self.label) < 30:
            parts.append(self.label)
        return "\\n".join(parts)

    @property
    def period_colour(self) -> str:
        """Return an SVG fill colour based on period."""
        period_map = {
            "prehistoric": "#8B4513",
            "neolithic": "#A0522D",
            "bronze_age": "#CD853F",
            "iron_age": "#DAA520",
            "roman": "#B22222",
            "early_medieval": "#4169E1",
            "medieval": "#6495ED",
            "post_medieval": "#3CB371",
            "modern": "#808080",
            "undated": "#D3D3D3",
            "natural": "#F5DEB3",
        }
        key = (self.period or "").lower().replace(" ", "_").replace("-", "_")
        return period_map.get(key, "#D3D3D3")


# ── Matrix Builder ───────────────────────────────────────────────────────────


def build_matrix_from_contexts(contexts: list[dict[str, Any]]) -> list[StratigraphicNode]:
    """Build a stratigraphic node graph from a list of context JSON dicts.

    Each context dict should follow the Phase 1 output schema with
    fields: context_number, type, cuts, cut_by, fills, filled_by,
    same_as, description, interpretation, period.
    """
    nodes: dict[str, StratigraphicNode] = {}

    def _normalise(num_str: str) -> str:
        """Strip brackets and whitespace from a context number."""
        return str(num_str).strip("[]").strip()

    for ctx in contexts:
        raw = str(ctx.get("context_number", ""))
        if not raw:
            continue
        num = _normalise(raw)

        if num not in nodes:
            nodes[num] = StratigraphicNode(
                context_number=num,
                label=str(ctx.get("interpretation", ctx.get("description", "")))[:40],
                period=str(ctx.get("period", "")),
            )

        node = nodes[num]

        # 'cuts' means this context cuts into others → this is later (higher)
        for target in ctx.get("cuts", []):
            target_str = str(target).strip("[]")
            node.children.append(target_str)
            if target_str not in nodes:
                nodes[target_str] = StratigraphicNode(target_str)
            nodes[target_str].parents.append(num)

        # 'cut_by' means another context cuts this → that other is later
        for source in ctx.get("cut_by", []):
            source_str = str(source).strip("[]")
            node.parents.append(source_str)
            if source_str not in nodes:
                nodes[source_str] = StratigraphicNode(source_str)
            nodes[source_str].children.append(num)

        # 'fills' means this context fills another → this is later
        for target in ctx.get("fills", []):
            target_str = str(target).strip("[]")
            node.children.append(target_str)
            if target_str not in nodes:
                nodes[target_str] = StratigraphicNode(target_str)
            nodes[target_str].parents.append(num)

        # 'filled_by' means another context fills this → that is later
        for source in ctx.get("filled_by", []):
            source_str = str(source).strip("[]")
            node.parents.append(source_str)
            if source_str not in nodes:
                nodes[source_str] = StratigraphicNode(source_str)
            nodes[source_str].children.append(num)

        # 'same_as' groups equivalent contexts — render grouped later
        for eq in ctx.get("same_as", []):
            eq_str = str(eq).strip("[]")
            if eq_str not in nodes:
                nodes[eq_str] = StratigraphicNode(eq_str)

    # Deduplicate edges
    for node in nodes.values():
        node.parents = list(dict.fromkeys(node.parents))
        node.children = list(dict.fromkeys(node.children))

    return list(nodes.values())


def _assign_levels(nodes: list[StratigraphicNode]) -> None:
    """Assign stratigraphic levels using topological sort from earliest to latest.

    Level 0 = earliest (bottom), highest level = latest (top).

    In this data model:
      - node.parents = LATER contexts (drawn above)
      - node.children = EARLIER contexts (drawn below)
    So nodes with no children are the earliest leaves.
    """
    node_map = {n.context_number: n for n in nodes}

    # Find leaves (no children = earliest contexts)
    leaves = [n for n in nodes if not n.children]

    # BFS from leaves, assigning increasing levels
    queue = list(leaves)
    visited: set[str] = set()

    for leaf in leaves:
        leaf.level = 0

    while queue:
        current = queue.pop(0)
        if current.context_number in visited:
            continue
        visited.add(current.context_number)

        for parent_num in current.parents:
            if parent_num in node_map:
                parent = node_map[parent_num]
                parent.level = max(parent.level, current.level + 1)
                if parent.context_number not in visited:
                    queue.append(parent)

    # Handle disconnected nodes (no relationships)
    for node in nodes:
        if node.context_number not in visited:
            node.level = 0


def _assign_positions(nodes: list[StratigraphicNode]) -> None:
    """Assign x,y positions based on level assignment.

    Levels are arranged vertically (Y). Nodes at the same level
    are spaced horizontally (X) to avoid overlap.
    """
    if not nodes:
        return

    # Group by level
    levels: dict[int, list[StratigraphicNode]] = {}
    for node in nodes:
        levels.setdefault(node.level, []).append(node)

    # Sort levels
    sorted_levels = sorted(levels.keys())

    max_nodes_per_level = max((len(level) for level in levels.values()), default=1)
    canvas_width = max_nodes_per_level * (NODE_WIDTH + NODE_PADDING_X) - NODE_PADDING_X + MARGIN * 2

    for level_idx, level in enumerate(sorted_levels):
        level_nodes = levels[level]
        # Sort by context number for deterministic layout
        level_nodes.sort(key=lambda n: int(n.context_number) if n.context_number.isdigit() else 9999)

        row_width = len(level_nodes) * (NODE_WIDTH + NODE_PADDING_X) - NODE_PADDING_X
        start_x = MARGIN + (canvas_width - MARGIN * 2 - row_width) / 2

        for i, node in enumerate(level_nodes):
            node.x = start_x + i * (NODE_WIDTH + NODE_PADDING_X)
            node.y = MARGIN + level_idx * (NODE_HEIGHT + LEVEL_GAP + NODE_PADDING_Y)


# ── SVG Rendering ────────────────────────────────────────────────────────────


def render_harris_svg(
    nodes: list[StratigraphicNode],
    title: str = "Harris Matrix",
) -> str:
    """Render the Harris Matrix as an SVG string.

    Context boxes are colour-coded by period. Arrows point from later
    contexts to earlier contexts (standard Harris convention).
    """
    if not nodes:
        return _empty_svg(title)

    _assign_levels(nodes)
    _assign_positions(nodes)

    # Calculate canvas dimensions
    node_map = {n.context_number: n for n in nodes}
    max_x = max((n.x for n in nodes), default=0) + NODE_WIDTH + MARGIN
    max_y = max((n.y for n in nodes), default=0) + NODE_HEIGHT + MARGIN
    canvas_w = max(max_x, 400)
    canvas_h = max(max_y, 300)

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {canvas_h}"',
        f'     width="{canvas_w}" height="{canvas_h}">',
        "  <defs>",
        "    <marker id='arrowhead' markerWidth='10' markerHeight='7'",
        "            refX='10' refY='3.5' orient='auto'>",
        "      <polygon points='0 0, 10 3.5, 0 7' fill='#555' />",
        "    </marker>",
        "  </defs>",
        '  <rect width="100%" height="100%" fill="#FAFAFA" rx="4"/>',
        f'  <text x="{canvas_w / 2}" y="20" text-anchor="middle"',
        '        font-family="sans-serif" font-size="14" font-weight="bold" fill="#333">',
        f'    {_xml_escape(title)}',
        "  </text>",
    ]

    # Draw edges (arrows from later → earlier)
    for node in nodes:
        for parent_num in node.parents:
            if parent_num in node_map:
                parent = node_map[parent_num]
                line = _compute_edge_path(node, parent)
                svg_parts.append(
                    f'  <path d="{line}" stroke="#555" stroke-width="1.5" '
                    f'fill="none" marker-end="url(#arrowhead)" opacity="0.6"/>'
                )

    # Draw nodes
    for node in nodes:
        fill = node.period_colour
        text_colour = "#FFF" if node.period and node.period.lower() not in ("undated", "natural", "") else "#333"

        svg_parts.extend([
            f'  <rect x="{node.x}" y="{node.y}" width="{NODE_WIDTH}" height="{NODE_HEIGHT}"',
            f'        rx="4" ry="4" fill="{fill}" stroke="#555" stroke-width="1.5"/>',
            f'  <text x="{node.x + NODE_WIDTH / 2}" y="{node.y + NODE_HEIGHT / 2 + 4}"',
            f'        text-anchor="middle" font-family="monospace" font-size="12" fill="{text_colour}">',
            f'    [{_xml_escape(node.context_number)}]',
            "  </text>",
        ])

        # Period indicator (small coloured dot or label)
        if node.period:
            period_label = node.period.replace("_", " ").title()
            svg_parts.append(
                f'  <text x="{node.x + NODE_WIDTH / 2}" y="{node.y - 4}"'
                f'        text-anchor="middle" font-family="sans-serif" font-size="9" fill="#888">'
                f'    {_xml_escape(period_label)}'
                "  </text>"
            )

    # Legend
    svg_parts.append(_render_legend())

    # Key
    svg_parts.append(
        f'  <text x="{MARGIN}" y="{canvas_h - 10}" font-family="sans-serif" font-size="9" fill="#999">'
        "    Earlier contexts at bottom; arrows point from later to earlier"
        "  </text>"
    )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def _compute_edge_path(later: StratigraphicNode, earlier: StratigraphicNode) -> str:
    """Compute an SVG path from a later node to an earlier node.

    Uses a simple L-shaped or straight path depending on alignment.
    """
    x1 = later.x + NODE_WIDTH / 2
    y1 = later.y
    x2 = earlier.x + NODE_WIDTH / 2
    y2 = earlier.y + NODE_HEIGHT

    # If vertically aligned, draw straight line
    if abs(x1 - x2) < 10:
        return f"M {x1} {y1} L {x2} {y2}"

    # L-shaped path: down from source, across, down to target
    mid_y = (y1 + y2) / 2
    return f"M {x1} {y1} L {x1} {mid_y} L {x2} {mid_y} L {x2} {y2}"


def _render_legend() -> str:
    """Render a colour legend for periods."""
    periods = [
        ("Prehistoric", "#8B4513"),
        ("Roman", "#B22222"),
        ("Medieval", "#6495ED"),
        ("Post-Medieval", "#3CB371"),
        ("Modern", "#808080"),
        ("Undated", "#D3D3D3"),
    ]
    parts = ['  <g transform="translate(20, 40)">', '    <text x="0" y="0" font-family="sans-serif" font-size="10" font-weight="bold" fill="#555">Period Key:</text>']
    for i, (name, colour) in enumerate(periods):
        y = 14 + i * 14
        parts.extend([
            f'    <rect x="0" y="{y - 8}" width="10" height="10" fill="{colour}" stroke="#555" stroke-width="0.5" rx="1"/>',
            f'    <text x="14" y="{y}" font-family="sans-serif" font-size="9" fill="#555">{name}</text>',
        ])
    parts.append("  </g>")
    return "\n".join(parts)


def _xml_escape(text: str) -> str:
    """Escape special XML characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _empty_svg(title: str) -> str:
    """Return an SVG for an empty matrix."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200" width="400" height="200">'
        f'  <rect width="100%" height="100%" fill="#FAFAFA" rx="4"/>'
        f'  <text x="200" y="100" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#999">'
        f'    {_xml_escape(title)} — No stratigraphic data'
        f'  </text>'
        f'</svg>'
    )


# ── Public API ───────────────────────────────────────────────────────────────


def generate_harris_matrix(
    context_files: list[Path],
    output_path: Path,
    title: str = "Harris Matrix",
) -> Path | None:
    """Load context JSON files and generate a Harris Matrix SVG.

    Args:
        context_files: List of paths to Phase 1 digitised context JSON files.
        output_path: Path to write the SVG file.
        title: Title for the matrix diagram.

    Returns:
        The output path if generation succeeded, None if no context data found.
    """
    contexts: list[dict[str, Any]] = []
    for path in context_files:
        try:
            data = json.loads(path.read_text())
            contexts.append(data)
        except (json.JSONDecodeError, OSError):
            continue

    if not contexts:
        return None

    nodes = build_matrix_from_contexts(contexts)
    if not nodes:
        return None

    svg = render_harris_svg(nodes, title=title)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg)
    return output_path


def generate_from_json_list(
    context_json_list: list[dict[str, Any]],
    output_path: Path,
    title: str = "Harris Matrix",
) -> Path | None:
    """Generate a Harris Matrix from an in-memory list of context dicts."""
    nodes = build_matrix_from_contexts(context_json_list)
    if not nodes:
        return None

    svg = render_harris_svg(nodes, title=title)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg)
    return output_path
