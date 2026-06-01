"""test_harris.py — Unit tests for the Harris Matrix SVG generator.

Tests: build_matrix_from_contexts, render_harris_svg, level assignment,
       colour coding, edge rendering, empty/invalid input handling.

exports: (test functions)
used_by: pytest
rules:   Must not require graphviz or any external renderer.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from hoard.review.harris import (
    StratigraphicNode,
    build_matrix_from_contexts,
    generate_from_json_list,
    generate_harris_matrix,
    render_harris_svg,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def simple_stratigraphy() -> list[dict]:
    """Simple three-context stratigraphy: latest [3] cuts [2], [2] cuts [1]."""
    return [
        {"context_number": "[1]", "type": "layer", "description": "Natural clay", "period": "Natural",
         "cuts": [], "cut_by": ["[2]"], "fills": [], "filled_by": [], "same_as": []},
        {"context_number": "[2]", "type": "layer", "description": "Post-medieval ploughsoil", "period": "Post-medieval",
         "cuts": ["[1]"], "cut_by": ["[3]"], "fills": [], "filled_by": [], "same_as": []},
        {"context_number": "[3]", "type": "cut", "description": "Modern pit", "period": "Modern",
         "cuts": ["[2]"], "cut_by": [], "fills": [], "filled_by": [], "same_as": []},
    ]


@pytest.fixture
def complex_stratigraphy() -> list[dict]:
    """Multi-branch stratigraphy to test level assignment."""
    return [
        {"context_number": "101", "type": "layer", "description": "Natural", "period": "Natural",
         "cuts": [], "cut_by": ["102", "201"], "fills": [], "filled_by": []},
        {"context_number": "102", "type": "layer", "description": "Ploughsoil", "period": "Post-medieval",
         "cuts": ["101"], "cut_by": ["103"], "fills": [], "filled_by": []},
        {"context_number": "103", "type": "cut", "description": "Ditch", "period": "Post-medieval",
         "cuts": ["102"], "cut_by": [], "fills": [], "filled_by": ["104"]},
        {"context_number": "104", "type": "fill", "description": "Ditch fill", "period": "Post-medieval",
         "cuts": [], "cut_by": [], "fills": ["103"], "filled_by": []},
        {"context_number": "201", "type": "cut", "description": "Roman pit", "period": "Roman",
         "cuts": ["101"], "cut_by": [], "fills": [], "filled_by": ["202"]},
        {"context_number": "202", "type": "fill", "description": "Pit fill", "period": "Roman",
         "cuts": [], "cut_by": [], "fills": ["201"], "filled_by": []},
    ]


# ── Tests: StratigraphicNode ─────────────────────────────────────────────────


class TestStratigraphicNode:
    def test_create_node(self) -> None:
        node = StratigraphicNode(context_number="101", label="Test context", period="Roman")
        assert node.context_number == "101"
        assert node.label == "Test context"
        assert node.period == "Roman"
        assert node.level == 0
        assert node.parents == []
        assert node.children == []

    def test_period_colour(self) -> None:
        assert StratigraphicNode("1", period="Roman").period_colour == "#B22222"
        assert StratigraphicNode("1", period="Post-medieval").period_colour == "#3CB371"
        assert StratigraphicNode("1", period="Undated").period_colour == "#D3D3D3"
        assert StratigraphicNode("1", period="Natural").period_colour == "#F5DEB3"
        assert StratigraphicNode("1", period="").period_colour == "#D3D3D3"

    def test_period_colour_fuzzy_match(self) -> None:
        # Case insensitive, space-to-underscore
        assert StratigraphicNode("1", period="Post Medieval").period_colour == "#3CB371"


# ── Tests: build_matrix_from_contexts ────────────────────────────────────────


class TestBuildMatrixFromContexts:
    def test_simple_stratigraphy(self, simple_stratigraphy: list[dict]) -> None:
        nodes = build_matrix_from_contexts(simple_stratigraphy)
        assert len(nodes) == 3

        node_map = {n.context_number: n for n in nodes}
        assert "1" in node_map
        assert "2" in node_map
        assert "3" in node_map

        # [3] cuts [2], [2] cuts [1], so [3] is latest, [1] is earliest
        assert "2" in node_map["3"].children  # [3] is earlier than [2]
        assert "1" in node_map["2"].children  # [2] is earlier than [1]

    def test_bracket_normalisation(self) -> None:
        """Context numbers may come with or without square brackets."""
        contexts = [
            {"context_number": "1", "cuts": [], "cut_by": ["2"]},
            {"context_number": "2", "cuts": ["1"], "cut_by": []},
        ]
        nodes = build_matrix_from_contexts(contexts)  # type: ignore[arg-type]
        assert len(nodes) == 2

    def test_empty_input(self) -> None:
        nodes = build_matrix_from_contexts([])
        assert nodes == []

    def test_complex_stratigraphy(self, complex_stratigraphy: list[dict]) -> None:
        nodes = build_matrix_from_contexts(complex_stratigraphy)
        assert len(nodes) == 6

        node_map = {n.context_number: n for n in nodes}
        # 101 is earliest, cut by 102 and 201 (both later → parents)
        assert "102" in node_map["101"].parents
        assert "201" in node_map["101"].parents
        # 103 is latest in branch 1 → 104 fills 103 (104 later) → 104 is parent (above) of 103
        assert "104" in node_map.get("103", StratigraphicNode("")).parents

    def test_same_as_creates_edges(self) -> None:
        """'same_as' should be tracked but not create directional edges."""
        contexts = [
            {"context_number": "101", "cuts": [], "cut_by": [], "fills": [], "filled_by": [],
             "same_as": ["102"]},
            {"context_number": "102", "cuts": [], "cut_by": [], "fills": [], "filled_by": [],
             "same_as": ["101"]},
        ]
        nodes = build_matrix_from_contexts(contexts)  # type: ignore[arg-type]
        assert len(nodes) == 2


# ── Tests: SVG Rendering ─────────────────────────────────────────────────────


class TestRenderHarrisSvg:
    def test_empty_returns_valid_svg(self) -> None:
        svg = render_harris_svg([])
        assert svg.startswith("<svg")
        assert "No stratigraphic data" in svg
        assert svg.endswith("</svg>")

    def test_render_simple(self, simple_stratigraphy: list[dict]) -> None:
        nodes = build_matrix_from_contexts(simple_stratigraphy)
        svg = render_harris_svg(nodes, title="Test Matrix")
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        assert "Test Matrix" in svg
        assert "[1]" in svg
        assert "[2]" in svg
        assert "[3]" in svg

    def test_render_complex(self, complex_stratigraphy: list[dict]) -> None:
        nodes = build_matrix_from_contexts(complex_stratigraphy)
        svg = render_harris_svg(nodes, title="Complex Matrix")
        assert svg.startswith("<svg")
        assert "101" in svg
        assert "201" in svg

    def test_period_colour_in_svg(self, simple_stratigraphy: list[dict]) -> None:
        nodes = build_matrix_from_contexts(simple_stratigraphy)
        svg = render_harris_svg(nodes)
        # Natural = #F5DEB3, Post-medieval = #3CB371, Modern = #808080
        assert "#F5DEB3" in svg or "#3CB371" in svg or "#808080" in svg

    def test_arrows_drawn(self, simple_stratigraphy: list[dict]) -> None:
        nodes = build_matrix_from_contexts(simple_stratigraphy)
        svg = render_harris_svg(nodes)
        # arrowhead marker definition
        assert "arrowhead" in svg
        # Edge paths
        assert "M " in svg


# ── Tests: File-level API ────────────────────────────────────────────────────


class TestGenerateFromJsonList:
    def test_generates_file(self, simple_stratigraphy: list[dict], tmp_path: Path) -> None:
        out = tmp_path / "harris.svg"
        result = generate_from_json_list(simple_stratigraphy, out)  # type: ignore[arg-type]
        assert result is not None
        assert result.exists()
        svg = result.read_text()
        assert svg.startswith("<svg")
        assert "[1]" in svg

    def test_empty_list(self, tmp_path: Path) -> None:
        result = generate_from_json_list([], tmp_path / "empty.svg")
        assert result is None

    def test_no_relationships(self, tmp_path: Path) -> None:
        data = [{"context_number": "[1]", "cuts": [], "cut_by": []}]
        result = generate_from_json_list(data, tmp_path / "single.svg")
        assert result is not None  # Should still render a single node


class TestGenerateHarrisMatrix:
    def test_loads_json_files(self, tmp_path: Path) -> None:
        # Create context JSON files
        ctx_dir = tmp_path / "contexts"
        ctx_dir.mkdir()
        for i, (num, period) in enumerate([("1", "Natural"), ("2", "Roman")], 1):
            (ctx_dir / f"ctx_{i:03d}.json").write_text(json.dumps({
                "context_number": num,
                "type": "layer",
                "period": period,
                "cuts": [],
                "cut_by": [],
                "fills": [],
                "filled_by": [],
            }))

        out = tmp_path / "output" / "matrix.svg"
        result = generate_harris_matrix(list(ctx_dir.glob("*.json")), out)
        assert result is not None
        assert result.exists()
        assert "[1]" in result.read_text()

    def test_no_valid_json_files(self, tmp_path: Path) -> None:
        result = generate_harris_matrix([tmp_path / "nonexistent.json"], tmp_path / "out.svg")
        assert result is None


# ── Tests: Level Assignment ──────────────────────────────────────────────────


class TestLevelAssignment:
    def test_levels_assigned_correctly(self, simple_stratigraphy: list[dict]) -> None:
        from hoard.review.harris import _assign_levels

        nodes = build_matrix_from_contexts(simple_stratigraphy)
        _assign_levels(nodes)

        node_map = {n.context_number: n for n in nodes}
        # [1] is earliest → level 0
        # [2] cuts [1] → level 1
        # [3] cuts [2] → level 2
        assert node_map["1"].level == 0
        assert node_map["2"].level == 1
        assert node_map["3"].level == 2

    def test_levels_complex(self, complex_stratigraphy: list[dict]) -> None:
        from hoard.review.harris import _assign_levels

        nodes = build_matrix_from_contexts(complex_stratigraphy)
        _assign_levels(nodes)

        node_map = {n.context_number: n for n in nodes}
        # 101 is earliest, cut by 102 and 201 (both later, so they are parents)
        assert "102" in node_map["101"].parents
        assert "201" in node_map["101"].parents
        # 201 cuts 101 → level 1
        assert node_map["201"].level == 1
        # 202 fills 201 → level 2
        assert node_map["202"].level == 2
