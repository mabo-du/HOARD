"""config.py — Project configuration loading and management.

Loads project config from hoard_workspace/{project_id}/config.toml or
CLI flags. Provides a single Config dataclass used by all phases.

exports: Config, load_config, init_project_config
used_by: hoard.cli.*, hoard.phases.*
rules:   Config must be serialisable to YAML. Never store credentials or
         model paths in config — those belong in environment variables.
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Initial scaffold
"""

from __future__ import annotations

import dataclasses
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class Config:
    """Immutable pipeline configuration."""

    project_id: str
    project_name: str
    jurisdiction: str
    workspace_root: Path
    input_dir: Path
    strict: bool = False
    extractor: str = "glm-ocr"  # "glm-ocr" | "nuextract3"

    @property
    def project_dir(self) -> Path:
        return self.workspace_root / self.project_id

    @property
    def manifest_dir(self) -> Path:
        return self.project_dir / "00_manifest"

    @property
    def digitised_dir(self) -> Path:
        return self.project_dir / "01_digitised"

    @property
    def spatial_dir(self) -> Path:
        return self.project_dir / "02_spatial"

    @property
    def draft_dir(self) -> Path:
        return self.project_dir / "03_draft"

    @property
    def refined_dir(self) -> Path:
        return self.project_dir / "04_refined"

    @property
    def final_dir(self) -> Path:
        return self.project_dir / "05_final"

    @property
    def assets_dir(self) -> Path:
        return self.project_dir / "assets"

    @property
    def logs_dir(self) -> Path:
        return self.project_dir / "logs"

    @property
    def state_file(self) -> Path:
        return self.project_dir / "pipeline_state.json"


def load_config(project_id: str, workspace_root: Path = Path("./hoard_workspace")) -> Config | None:
    """Load a project config from its workspace directory.

    Reads the YAML file written by init_project_config() and returns
    a populated Config dataclass.

    Returns None if the project hasn't been initialised.
    """
    config_path = workspace_root / project_id / "config.toml"
    if not config_path.exists():
        return None

    import yaml
    try:
        raw = yaml.safe_load(config_path.read_text())
    except yaml.YAMLError:
        return None

    if not isinstance(raw, dict):
        return None

    jurisdiction = raw.get("jurisdiction", "historic_england_cl3")
    project_name = raw.get("project_name", project_id)

    return Config(
        project_id=project_id,
        project_name=project_name,
        jurisdiction=jurisdiction,
        workspace_root=workspace_root.resolve(),
        input_dir=workspace_root / project_id / "input",
        strict=raw.get("strict", False),
        extractor=raw.get("extractor", "glm-ocr"),
    )


def init_project_config(
    project_id: str,
    project_name: str,
    jurisdiction: str,
    workspace_root: Path,
    input_dir: Path,
) -> Config:
    """Create a new project config and write it to disk."""
    cfg = Config(
        project_id=project_id,
        project_name=project_name,
        jurisdiction=jurisdiction,
        workspace_root=workspace_root.resolve(),
        input_dir=input_dir.resolve(),
    )
    cfg.project_dir.mkdir(parents=True, exist_ok=True)

    import yaml as _yaml
    config_data = {
        "project_id": project_id,
        "project_name": project_name,
        "jurisdiction": jurisdiction,
        "extractor": cfg.extractor,
        "strict": cfg.strict,
    }
    config_text = f"# HOARD project: {project_id}\n" + _yaml.dump(
        config_data, default_flow_style=False, allow_unicode=True
    )
    (cfg.project_dir / "config.toml").write_text(config_text)
    return cfg
