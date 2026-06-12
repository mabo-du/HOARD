"""dashboard.py — Interactive review session for flagged pipeline items.

Loads flagged items from pipeline state and phase output JSON, then
presents them one-at-a-time via a Rich terminal TUI for the site
director to accept, correct, or defer.

exports: ReviewItem, ReviewDecision, FlagSource, ReviewSession,
         load_flags_from_manifest, load_flags_from_workspace
used_by: hoard.cli.review  → `hoard review` command
rules:   Must never import torch or any GPU-bound library.
         All state mutations write through Workspace/PipelineState.
"""

from __future__ import annotations

import dataclasses
import json
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from hoard.config import Config
from hoard.workspace import Workspace

console = Console()

# ── Types ────────────────────────────────────────────────────────────────────


class ReviewDecision(Enum):
    """What the site director decided for a flagged item."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    CORRECTED = "corrected"
    DEFERRED = "deferred"


class FlagSource(Enum):
    """Where the flag originated."""

    PHASE0_MANIFEST = "phase0_manifest"
    PHASE1_DIGITISED = "phase1_digitised"
    PHASE2_SPATIAL = "phase2_spatial"
    PHASE3_DRAFT = "phase3_draft"
    PHASE4_COMPLIANCE = "phase4_compliance"


@dataclasses.dataclass
class ReviewItem:
    """A single flagged item needing human review."""

    item_id: str
    phase: int
    source: FlagSource
    source_file: str
    field: str
    issue: str
    confidence: float | None
    current_value: str
    corrected_value: str | None = None
    decision: ReviewDecision = ReviewDecision.PENDING
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "phase": self.phase,
            "source": self.source.value,
            "source_file": self.source_file,
            "field": self.field,
            "issue": self.issue,
            "confidence": self.confidence,
            "current_value": self.current_value,
            "corrected_value": self.corrected_value,
            "decision": self.decision.value,
            "notes": self.notes,
        }


# ── Flag Loaders ─────────────────────────────────────────────────────────────


def load_flags_from_manifest(manifest_source: Path | dict) -> list[ReviewItem]:
    """Extract review flags from a Phase 0 manifest.json.

    Accepts either a Path to the manifest file or a pre-loaded dict
    (useful for testing).
    """
    items: list[ReviewItem] = []

    if isinstance(manifest_source, dict):
        manifest = manifest_source
    else:
        if not manifest_source.exists():
            return items
        try:
            manifest = json.loads(manifest_source.read_text())
        except (json.JSONDecodeError, OSError):
            return items

    files = manifest.get("files", [])
    for entry in files:
        quality = entry.get("quality", {})
        flag = quality.get("flag")
        if not flag:
            continue

        file_id = entry.get("id", "unknown")
        file_path = entry.get("path", "")
        blur = quality.get("blur_score", 0)
        skew = quality.get("skew_deg", 0)

        issue = _describe_quality_flag(flag, blur, skew)
        items.append(ReviewItem(
            item_id=f"p0_{file_id}_{flag}",
            phase=0,
            source=FlagSource.PHASE0_MANIFEST,
            source_file=file_path,
            field="_quality",
            issue=issue,
            confidence=None,
            current_value=flag,
        ))

    mandatory_check = manifest.get("mandatory_check", "PASS")
    if mandatory_check != "PASS":
        missing = manifest.get("missing_mandatory", [])
        items.append(ReviewItem(
            item_id="p0_mandatory_check",
            phase=0,
            source=FlagSource.PHASE0_MANIFEST,
            source_file="manifest.json",
            field="_mandatory",
            issue=f"Mandatory file check failed: missing {', '.join(missing)}",
            confidence=None,
            current_value=mandatory_check,
        ))

    finds_issues = manifest.get("finds_validation_issues", [])
    for idx, fi in enumerate(finds_issues):
        items.append(ReviewItem(
            item_id=f"p0_finds_{idx}",
            phase=0,
            source=FlagSource.PHASE0_MANIFEST,
            source_file="finds_catalogue",
            field=fi.get("field", "unknown"),
            issue=fi.get("message", "Validation issue"),
            confidence=None,
            current_value=str(fi.get("value", "")),
        ))

    return items


def _describe_quality_flag(flag: str, blur: float, skew: float) -> str:
    """Produce a human-readable quality issue description.

    Thresholds mirrored from phase0.py constants:
      BLUR_LAPLACIAN_VARIANCE_THRESHOLD = 10.0
      SKEW_ANGLE_THRESHOLD = 45.0
      EXPOSURE_MEAN_THRESHOLD = 15
    """
    descriptions = {
        "BLUR_LOW": f"Image blur score {blur:.1f} (threshold: 10.0) — text may be unreadable",
        "SKEW_HIGH": f"Image skew {skew:.1f}° (threshold: 45°) — may need deskewing",
        "EXPOSURE_LOW": "Image underexposed (mean pixel value < 15) — details may be lost",
    }
    return descriptions.get(flag, f"Quality flag: {flag}")


def _scan_digitised_json(digitised_dir: Path) -> list[ReviewItem]:
    """Scan Phase 1 digitised JSON files for low-confidence fields."""
    items: list[ReviewItem] = []
    if not digitised_dir.is_dir():
        return items

    for json_file in sorted(digitised_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        # Overall confidence
        overall = data.get("confidence_overall", 1.0)
        if overall < 0.65:
            items.append(ReviewItem(
                item_id=f"p1_{json_file.stem}_overall",
                phase=1,
                source=FlagSource.PHASE1_DIGITISED,
                source_file=json_file.name,
                field="_overall",
                issue=f"Overall digitisation confidence {overall:.2f} (threshold: 0.65)",
                confidence=overall,
                current_value=f"confidence={overall:.2f}",
            ))

        # Per-field flags
        for flag in data.get("review_flags", []):
            field = flag.get("field", "unknown")
            conf = flag.get("confidence", 0.0)
            items.append(ReviewItem(
                item_id=f"p1_{json_file.stem}_{field}",
                phase=1,
                source=FlagSource.PHASE1_DIGITISED,
                source_file=json_file.name,
                field=field,
                issue=f"Low-confidence field '{field}' ({conf:.2f})",
                confidence=conf,
                current_value=str(data.get(field, "")),
            ))

    return items


def _scan_spatial_json(spatial_dir: Path) -> list[ReviewItem]:
    """Scan Phase 2 spatial JSON files for low-confidence or failed geometry."""
    items: list[ReviewItem] = []
    if not spatial_dir.is_dir():
        return items

    for json_file in sorted(spatial_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        # Low-confidence grounding
        for grounding in data.get("grounding", []):
            conf = grounding.get("confidence", 1.0)
            if conf < 0.6:
                label = grounding.get("label", "unknown")
                items.append(ReviewItem(
                    item_id=f"p2_{json_file.stem}_{label}",
                    phase=2,
                    source=FlagSource.PHASE2_SPATIAL,
                    source_file=json_file.name,
                    field=f"grounding:{label}",
                    issue=f"Low grounding confidence for '{label}' ({conf:.2f})",
                    confidence=conf,
                    current_value=json.dumps(grounding),
                ))

        # Cross-check inconsistencies
        cross = data.get("cross_check", {})
        for inc in cross.get("inconsistencies", []):
            items.append(ReviewItem(
                item_id=f"p2_{json_file.stem}_xcheck",
                phase=2,
                source=FlagSource.PHASE2_SPATIAL,
                source_file=json_file.name,
                field="cross_check",
                issue=f"Cross-check inconsistency: {inc}",
                confidence=None,
                current_value=str(inc),
            ))

        # Geometry failures
        if data.get("geometry_status") == "FAIL":
            items.append(ReviewItem(
                item_id=f"p2_{json_file.stem}_geom",
                phase=2,
                source=FlagSource.PHASE2_SPATIAL,
                source_file=json_file.name,
                field="_geometry",
                issue="CadQuery geometry execution failed — requires human reconstruction",
                confidence=None,
                current_value="GEOMETRY_FAIL",
            ))

    return items


def _scan_draft_json(draft_dir: Path) -> list[ReviewItem]:
    """Scan Phase 3 draft output for review triggers."""
    items: list[ReviewItem] = []
    if not draft_dir.is_dir():
        return items

    for md_file in sorted(draft_dir.glob("*.md")):
        text = md_file.read_text()

        # Check for uncertainty markers
        uncertainty_phrases = [
            "insufficient data", "conflicting evidence", "cannot determine",
            "insufficient evidence", "unclear", "possibly", "may indicate",
        ]
        for phrase in uncertainty_phrases:
            for idx, line in enumerate(text.split("\n"), 1):
                if phrase.lower() in line.lower():
                    items.append(ReviewItem(
                        item_id=f"p3_{md_file.stem}_uncert_{idx}",
                        phase=3,
                        source=FlagSource.PHASE3_DRAFT,
                        source_file=md_file.name,
                        field=f"uncertainty_line_{idx}",
                        issue=f"Draft expresses uncertainty ('{phrase}')",
                        confidence=None,
                        current_value=line.strip()[:120],
                    ))
                    break  # One flag per phrase per file

    return items


def _scan_compliance_json(refined_dir: Path) -> list[ReviewItem]:
    """Scan Phase 4 compliance report for findings."""
    items: list[ReviewItem] = []
    if not refined_dir.is_dir():
        return items

    for json_file in sorted(refined_dir.glob("compliance_*.json")):
        try:
            data = json.loads(json_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        for finding in data.get("findings", []):
            section = finding.get("section_id", "unknown")
            ftype = finding.get("type", "unknown")
            message = finding.get("message", "")
            severity = finding.get("severity", "warning")

            items.append(ReviewItem(
                item_id=f"p4_{json_file.stem}_{section}_{ftype}",
                phase=4,
                source=FlagSource.PHASE4_COMPLIANCE,
                source_file=json_file.name,
                field=f"{section}:{ftype}",
                issue=f"[{severity}] {message}",
                confidence=None,
                current_value=json.dumps(finding),
            ))

    return items


def load_flags_from_workspace(workspace: Workspace, config: Config) -> list[ReviewItem]:
    """Load all review flags from across the workspace.

    Scans manifest, digitised outputs, spatial outputs, drafts, and
    compliance reports. Items are ordered by phase.
    """
    items: list[ReviewItem] = []

    # Phase 0 manifest flags
    manifest_path = config.manifest_dir / "manifest.json"
    items.extend(load_flags_from_manifest(manifest_path))

    # Phase 1 digitised flags
    items.extend(_scan_digitised_json(config.digitised_dir))

    # Phase 2 spatial flags
    items.extend(_scan_spatial_json(config.spatial_dir))

    # Phase 3 draft flags
    items.extend(_scan_draft_json(config.draft_dir))

    # Phase 4 compliance flags
    items.extend(_scan_compliance_json(config.refined_dir))

    return items


# ── Review Session ───────────────────────────────────────────────────────────


class ReviewSession:
    """Interactive review session.

    Loads flagged items from a workspace, presents them one at a time,
    and records decisions. After all items are reviewed, optionally writes
    corrections back and updates pipeline state.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.ws = Workspace(config.project_dir)
        self.items: list[ReviewItem] = []
        self._current_index = 0

    def load(self) -> None:
        """Load all flagged items from the workspace."""
        self.items = load_flags_from_workspace(self.ws, self.config)
        # Sort by phase, then by id
        self.items.sort(key=lambda i: (i.phase, i.item_id))
        self._current_index = 0

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def remaining(self) -> int:
        return sum(1 for i in self.items if i.decision == ReviewDecision.PENDING)

    @property
    def current(self) -> ReviewItem | None:
        if 0 <= self._current_index < len(self.items):
            return self.items[self._current_index]
        return None

    def advance(self) -> bool:
        """Move to the next pending item. Returns False if no more pending items."""
        while self._current_index < len(self.items) - 1:
            self._current_index += 1
            if self.items[self._current_index].decision == ReviewDecision.PENDING:
                return True
        # Wrap around check
        for idx, item in enumerate(self.items):
            if item.decision == ReviewDecision.PENDING:
                self._current_index = idx
                return True
        return False

    def accept_current(self) -> None:
        """Mark current item as accepted."""
        if self.current:
            self.current.decision = ReviewDecision.ACCEPTED

    def correct_current(self, new_value: str, notes: str = "") -> None:
        """Mark current item as corrected with a new value."""
        if self.current:
            self.current.corrected_value = new_value
            self.current.decision = ReviewDecision.CORRECTED
            self.current.notes = notes

    def defer_current(self, notes: str = "") -> None:
        """Mark current item as deferred (to revisit later)."""
        if self.current:
            self.current.decision = ReviewDecision.DEFERRED
            self.current.notes = notes

    def save_corrections(self) -> int:
        """Write all corrected values back to source JSON files.

        Returns the number of corrections written.
        """
        written = 0
        for item in self.items:
            if item.decision != ReviewDecision.CORRECTED or not item.corrected_value:
                continue

            # Determine the target file
            target_dir = {
                FlagSource.PHASE0_MANIFEST: self.config.manifest_dir,
                FlagSource.PHASE1_DIGITISED: self.config.digitised_dir,
                FlagSource.PHASE2_SPATIAL: self.config.spatial_dir,
                FlagSource.PHASE4_COMPLIANCE: self.config.refined_dir,
            }.get(item.source)

            if target_dir is None:
                continue

            source_path = target_dir / item.source_file
            if not source_path.exists():
                continue

            try:
                data = json.loads(source_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            # Apply the correction
            if item.field.startswith("grounding:"):
                label = item.field.split(":", 1)[1]
                for g in data.get("grounding", []):
                    if g.get("label") == label:
                        g["label"] = item.corrected_value
                        break
            elif item.field == "_overall":
                pass  # Overall confidence isn't user-editable
            elif item.field == "_quality":
                _update_quality_flag(data, item)
            elif item.field == "_geometry":
                pass  # Geometry failures need re-run, not direct edit
            elif item.field == "_mandatory":
                pass  # Need to add missing files, not edit JSON
            elif ":" in item.field:
                _update_nested_field(data, item.field, item.corrected_value)
            else:
                data[item.field] = item.corrected_value

            source_path.write_text(json.dumps(data, indent=2))
            written += 1

        # If corrections were made, update pipeline state to allow re-run
        if written > 0:
            phases_to_invalidate = set(i.phase for i in self.items if i.decision == ReviewDecision.CORRECTED)
            for ph in phases_to_invalidate:
                if self.ws.state.is_phase_complete(ph):
                    # Mark as needing re-review (user can re-run from this phase)
                    self.ws.state.fail_phase(ph, "Corrections applied — re-run phase for updated output")

        return written

    def summary_table(self) -> Table:
        """Build a Rich Table summarising review results."""
        table = Table(title="Review Summary", show_header=True)
        table.add_column("Phase", style="cyan")
        table.add_column("Item", style="white")
        table.add_column("Decision", style="bold")
        table.add_column("Notes")

        for item in self.items:
            decision_colour = {
                ReviewDecision.ACCEPTED: "green",
                ReviewDecision.CORRECTED: "yellow",
                ReviewDecision.DEFERRED: "red",
                ReviewDecision.PENDING: "dim",
            }.get(item.decision, "dim")
            table.add_row(
                str(item.phase),
                item.item_id[:40],
                f"[{decision_colour}]{item.decision.value}[/]",
                item.notes[:40] if item.notes else "",
            )
        return table

    def run_interactive(self) -> None:
        """Run the full interactive review session.

        Presents each pending item, accepts keyboard input for decisions,
        then shows a summary and optionally saves corrections.
        """
        self.load()

        if self.total == 0:
            console.print("[green]✓[/] No flagged items found — all clear!")
            return

        pending = self.remaining
        console.print(f"\n[bold]Review Dashboard[/] — {self.total} flagged item(s), {pending} pending\n")

        if pending == 0:
            console.print("[yellow]ℹ[/] All items already reviewed. Run with --reset to re-review.")
            return

        # Main review loop
        while self.current and self.remaining > 0:
            item = self.current
            assert item is not None

            self._render_item(item)
            action = Prompt.ask(
                "[bold]Action[/]",
                choices=["a", "e", "d", "s", "q"],
                default="a",
            )

            if action == "a":
                self.accept_current()
                console.print("[green]  ✓ Accepted[/]")
            elif action == "e":
                console.print(f"\n  Current value: [yellow]{item.current_value}[/]")
                new_val = Prompt.ask("  New value")
                notes = Prompt.ask("  Notes (optional)", default="")
                self.correct_current(new_val, notes)
                console.print("[yellow]  ✎ Corrected[/]")
            elif action == "d":
                notes = Prompt.ask("  Reason for deferring", default="")
                self.defer_current(notes)
                console.print("[red]  → Deferred[/]")
            elif action == "s":
                self._show_summary(interactive=True)
                continue
            elif action == "q":
                console.print("\n[yellow]ℹ[/] Review session paused.")
                break

            if not self.advance():
                break

        # Session complete
        self._show_summary(interactive=False)

        if self.remaining == 0 and any(i.decision == ReviewDecision.CORRECTED for i in self.items):
            save = Prompt.ask(
                "\n[bold]Save corrections to disk?[/]", choices=["y", "n"], default="y"
            )
            if save == "y":
                written = self.save_corrections()
                console.print(f"[green]✓[/] {written} correction(s) written back to workspace.")

    def _render_item(self, item: ReviewItem) -> None:
        """Render a single review item with rich formatting."""
        phase_colour = {
            0: "cyan", 1: "blue", 2: "magenta", 3: "yellow", 4: "green",
        }.get(item.phase, "white")

        info_lines = [
            f"Phase: [{phase_colour}]{item.phase}[/]   File: [bold]{item.source_file}[/]",
            f"Field: [bold]{item.field}[/]   Confidence: {f'[red]{item.confidence:.2f}[/]' if item.confidence and item.confidence < 0.6 else str(item.confidence) if item.confidence else 'N/A'}",
            f"Issue: {item.issue}",
            f"\nCurrent value: [yellow]{item.current_value}[/]",
        ]

        panel = Panel(
            "\n".join(info_lines),
            title=f"[bold]Review #{item.item_id}[/]  "
                  f"({self.items.index(item) + 1}/{self.total})",
            border_style="bright_blue",
        )
        console.print("\n")
        console.print(panel)
        console.print("\n[a]ccept  [e]dit  [d]efer  [s]ummary  [q]uit")

    def _show_summary(self, interactive: bool = False) -> None:
        """Show summary of all reviewed items."""
        accepted = sum(1 for i in self.items if i.decision == ReviewDecision.ACCEPTED)
        corrected = sum(1 for i in self.items if i.decision == ReviewDecision.CORRECTED)
        deferred = sum(1 for i in self.items if i.decision == ReviewDecision.DEFERRED)
        pending = self.remaining

        console.print("\n[bold]=== Review Summary ===[/]")
        console.print(f"  [green]Accepted:[/]  {accepted}")
        console.print(f"  [yellow]Corrected:[/] {corrected}")
        console.print(f"  [red]Deferred:[/]   {deferred}")
        if pending > 0:
            console.print(f"  [dim]Pending:[/]    {pending}")
        console.print(f"  Total:    {self.total}")

        if interactive:
            Prompt.ask("\nPress Enter to continue reviewing")


def _update_quality_flag(data: dict, item: ReviewItem) -> None:
    """Update a quality flag in manifest file entries."""
    for entry in data.get("files", []):
        if entry.get("id", "") in item.source_file:
            quality = entry.setdefault("quality", {})
            quality["flag"] = None
            quality["review_notes"] = item.corrected_value


def _update_nested_field(data: dict, field_path: str, value: str) -> None:
    """Update a nested field from colon-delimited path (e.g. 'section:field')."""
    parts = field_path.split(":")
    target = data
    for part in parts[:-1]:
        if isinstance(target, dict):
            target = target.get(part, {})
        else:
            return
    if isinstance(target, dict):
        target[parts[-1]] = value
