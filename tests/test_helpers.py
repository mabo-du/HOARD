"""test_helpers.py — Tests for shared utility functions.

Tests: load_json_safe, find_json_files, evict_ollama_model,
       generate_via_provider response parsing (mocked).
Runtimes: All tests are CPU-only and fast (< 0.5s).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock


from hoard.helpers import load_json_safe, find_json_files


class TestLoadJsonSafe:
    """Tests for the safe JSON loader with error handling."""

    def test_loads_valid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "test.json"
        p.write_text('{"a": 1, "b": 2}')
        assert load_json_safe(p) == {"a": 1, "b": 2}

    def test_returns_empty_for_missing_file(self) -> None:
        assert load_json_safe(Path("/nonexistent/file.json")) == {}

    def test_returns_empty_for_corrupt_json(self, tmp_path: Path) -> None:
        p = tmp_path / "corrupt.json"
        p.write_text("{invalid json}")
        result = load_json_safe(p)
        assert result == {}

    def test_skips_non_json_suffix(self, tmp_path: Path) -> None:
        p = tmp_path / "data.txt"
        p.write_text('{"a": 1}')
        assert load_json_safe(p) == {}

    def test_handles_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.json"
        p.write_text("")
        assert load_json_safe(p) == {}


class TestFindJsonFiles:
    """Tests for JSON file discovery with sorting."""

    def test_finds_json_files(self, tmp_path: Path) -> None:
        (tmp_path / "b.json").write_text("{}")
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "c.json").write_text("{}")
        files = find_json_files(tmp_path)
        assert len(files) == 3
        # Must be sorted alphabetically
        assert files[0].name == "a.json"
        assert files[1].name == "b.json"
        assert files[2].name == "c.json"

    def test_ignores_non_json(self, tmp_path: Path) -> None:
        (tmp_path / "data.txt").write_text("")
        (tmp_path / "notes.md").write_text("")
        assert find_json_files(tmp_path) == []

    def test_returns_empty_for_nonexistent_directory(self) -> None:
        assert find_json_files(Path("/nonexistent/dir")) == []

    def test_supports_custom_pattern(self, tmp_path: Path) -> None:
        (tmp_path / "doc.md").write_text("")
        (tmp_path / "note.md").write_text("")
        files = find_json_files(tmp_path, "*.md")
        assert len(files) == 2


class TestGenerateViaProvider:
    """Tests for generate_via_provider response parsing with mocked Ollama.

    These tests verify that the response dict format, reasoning extraction
    and error handling work correctly. They mock the httpx client to avoid
    requiring a real Ollama instance.
    """

    @patch("hoard.providers.get_router")
    def test_returns_expected_fields(self, mock_get_router) -> None:
        """Verify the return dict has all expected keys."""
        from hoard.helpers import generate_via_provider
        from hoard.providers.protocol import InferenceResponse, TokenUsage

        # Mock router to return a valid response
        mock_router = MagicMock()
        mock_router.route_sync.return_value = InferenceResponse(
            content="Simple text response",
            usage=TokenUsage(completion_tokens=42),
            provider_name="ollama",
            model_name="test-model",
        )
        mock_get_router.return_value = mock_router

        result = generate_via_provider(
            model="test-model",
            system="",
            prompt="Say hello",
            phase=3,
        )
        assert isinstance(result, dict)
        assert result["response"] == "Simple text response"
        assert result["model"] == "test-model"
        assert result["eval_count"] == 42
        assert "reasoning" not in result

    @patch("hoard.providers.get_router")
    def test_extracts_thinking_tags(self, mock_get_router) -> None:
        """Verify reasoning extraction from <think> blocks."""
        from hoard.helpers import generate_via_provider
        from hoard.providers.protocol import InferenceResponse, TokenUsage

        mock_router = MagicMock()
        # Response with thinking block
        content = "<think>I should respond concisely.</think>\nThe answer is 42."
        mock_router.route_sync.return_value = InferenceResponse(
            content=content,
            usage=TokenUsage(completion_tokens=20),
            provider_name="ollama",
            model_name="test-model",
        )
        mock_get_router.return_value = mock_router

        result = generate_via_provider(
            model="test-model",
            system="",
            prompt="What is the answer?",
            phase=3,
        )
        assert result["response"] == "The answer is 42."
        assert result["reasoning"] == "I should respond concisely."

    @patch("hoard.providers.get_router")
    def test_handles_missing_thinking_tags(self, mock_get_router) -> None:
        """Verify no reasoning when response has no <think>."""
        from hoard.helpers import generate_via_provider
        from hoard.providers.protocol import InferenceResponse, TokenUsage

        mock_router = MagicMock()
        mock_router.route_sync.return_value = InferenceResponse(
            content="Plain response without thinking.",
            usage=TokenUsage(completion_tokens=10),
            provider_name="ollama",
            model_name="test-model",
        )
        mock_get_router.return_value = mock_router

        result = generate_via_provider(
            model="test-model",
            system="",
            prompt="Say hello",
            phase=3,
        )
        assert result["response"] == "Plain response without thinking."
        assert result.get("reasoning") is None
