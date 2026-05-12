# Contributing to HOARD

**Heritage Observation And Report Drafter** — a fully local, multi-stage AI
pipeline for archaeological grey literature reports.

---

## Development Setup

### Prerequisites

- **Python 3.11+**
- **pip** or **[uv](https://docs.astral.sh/uv/)** (recommended)
- **pandoc** — for DOCX/PDF export:

  ```bash
  # macOS
  brew install pandoc

  # Ubuntu/Debian
  sudo apt-get install pandoc

  # Windows (Chocolatey)
  choco install pandoc
  ```

- **libmagickwand-dev** (Linux) / **ImageMagick** (macOS) — for image processing via Wand.

### Clone & Install

```bash
git clone https://github.com/mabo-du/HOARD.git
cd HOARD

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install with dev dependencies
pip install -e ".[dev]"
```

Using **uv** (substantially faster):

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Verify the CLI works:

```bash
erd --help
```

### Optional Dependency Groups

| Group | Install | Purpose |
|-------|---------|---------|
| `dev`  | `.[dev]` | pytest, ruff, mypy (always install for development) |
| `ocr`  | `.[ocr]` | Transformers + PyTorch (for Phase 1 — GPU required) |
| `llm`  | `.[llm]` | llama-cpp-python (for Phase 3 — GPU required) |
| `doc`  | `.[doc]` | python-docx (for Phase 5 export) |

---

## Project Structure

```
HOARD/
├── src/
│   └── erd/
│       ├── __init__.py         # Package root
│       ├── __main__.py         # `python -m erd` support
│       ├── cli/                # Typer CLI commands
│       │   └── main.py         # init, run, review, export, templates
│       ├── config.py           # Configuration loading
│       ├── models/             # Pydantic models for pipeline data
│       ├── phases/             # Pipeline phase implementations
│       │   ├── phase0.py       # Ingestion & Triage (no GPU)
│       │   ├── phase1.py       # Multi-Modal Digitisation (GPU)
│       │   ├── phase2.py       # Spatial Reconstruction (GPU)
│       │   ├── phase3.py       # Synthesis & Drafting (GPU)
│       │   ├── phase4.py       # Compliance Refinement (GPU)
│       │   └── phase5.py       # Assembly & Export (no GPU)
│       ├── review/             # Review dashboard & Harris Matrix
│       │   ├── dashboard.py    # Interactive Rich TUI
│       │   └── harris.py       # Pure-Python SVG Harris Matrix
│       ├── templates/          # Jurisdiction YAML template loading
│       └── workspace.py        # Pipeline workspace state management
├── tests/                      # pytest test suite
├── templates/                  # 14 jurisdiction YAML templates
├── docs/
│   └── user-guide.md           # Full user documentation
├── migrations/                 # Workspace schema migrations
├── schemas/                    # JSON schemas for pipeline artifacts
├── seeds/                      # Sample/test data
├── test_data/                  # Test fixtures
└── .github/workflows/
    ├── ci.yml                  # CI: lint, type-check, test
    └── publish.yml             # PyPI release workflow
```

---

## Development Workflow

### 1. Pick an Issue

Check the [TODO.md](TODO.md) for pending tasks. Tasks are prefixed with IDs
(e.g. `t001`) — use these in commits and PR titles.

### 2. Create a Branch

```bash
git checkout -b hoard-feature-description
```

Work on the `main` branch is not permitted. All changes go through a feature
branch and pull request.

### 3. Make Changes

- Write or update code in `src/erd/`
- Add or update tests in `tests/`
- Keep imports clean — never import GPU-bound libraries (`torch`,
  `transformers`, `llama-cpp-python`) in GPU-free code paths. If a module
  conditionally uses GPU, guard imports with local `try/except` blocks.

### 4. Run Quality Checks

```bash
# Lint
ruff check src/

# Type-check (optional but encouraged)
mypy src/ --ignore-missing-imports

# Test
python -m pytest tests/ -v --tb=short

# Test with coverage
python -m pytest tests/ --cov=erd --cov-report=term-missing
```

These exact commands run in CI (GitHub Actions) on push/PR to `main`.

### 5. Commit

```bash
git add .
git commit -m "tNNN: short description of the change"
```

Use the task ID prefix if the change relates to a TODO.md task.

### 6. Push & Open a PR

```bash
git push origin hoard-feature-description
```

Then open a pull request on GitHub against `main`. CI will run
automatically.

---

## Code Conventions

### Style

- **Formatting**: [Ruff](https://docs.astral.sh/ruff/) with default rules.
  Run `ruff check src/` before committing.
- **Type annotations**: Use Python 3.11+ style annotations throughout.
  Enable `from __future__ import annotations` where beneficial.
- **Imports**: Group standard library, third-party, then local. Use Ruff's
  built-in import ordering.
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes,
  `UPPER_CASE` for constants.

### Testing

- **Framework**: pytest
- **Location**: Tests mirror `src/erd/` structure under `tests/`.
- **Coverage target**: 90%+ on GPU-free code paths.
- **No GPU in tests**: Tests must not import torch, transformers, or
  llama-cpp-python. GPU-phase tests are marked with `@pytest.mark.gpu` and
  are skipped when no GPU is available.

### GPU-boundary Discipline

To keep GPU-free code paths clean:

- GPU-bound models go in `src/erd/phases/phaseN.py` with guarded imports.
- Non-GPU code (review dashboard, config, templates, workspace, CLI)
  must never import GPU libraries.
- New GPU-free features go in separate modules under `src/erd/`.

---

## CI/CD

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| **CI** | Push/PR to `main` | Lint (ruff), type-check (mypy), test (pytest w/ coverage), CLI smoke test |
| **Publish** | GitHub Release published | Build wheel + sdist, upload to PyPI via Trusted Publishing |

---

## Adding a Jurisdiction Template

See the [user guide](docs/user-guide.md#jurisdiction-templates) for template
format. In short:

1. Create `templates/<code>.yaml` following the YAML schema.
2. Register it in `src/erd/templates/` if it requires custom logic.
3. Test with `erd templates validate --file templates/<code>.yaml`.

Templates are pure data — no pipeline code changes needed for new
jurisdictions.

---

## Code of Conduct

Be respectful, constructive, and inclusive. This project follows the
[Contributor Covenant](https://www.contributor-covenant.org/).

---

## Questions?

Open an issue on GitHub or check the
[user guide](docs/user-guide.md) for detailed documentation.
