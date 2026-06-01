# Pinn Brook Park E2E Test Plan

End-to-end pipeline validation using the 35-context Pinn Brook Park dataset
from Cotswold Archaeology (ADS Object ID 2183094, CC-BY 4.0).

## Manual Download (required — ADS blocks automated tools)

1. Visit: https://archaeologydataservice.ac.uk/archives/collections/view/object.cfm?object_id=2183094
2. Download: `RAMM_10_2020_PAD15_context_sheets_47000_to_47034.pdf` (72 MB)
3. Also download: `text_metadata.csv` (1 KB) for metadata validation
4. Place PDF in: `~/Downloads/pinnbrook/`

The grey literature report for comparison is at a separate URL:
- https://archaeologydataservice.ac.uk/library/browse/issue.xhtml?recordId=1213927
- "Tithebarn Lane Sewer Pipeline, Pinhoe, Devon: Results of Archaeological Monitoring and Recording"

## Setup (after manual download)

```bash
cd ~/Projects/HOARD

# Copy input files
mkdir -p /tmp/pinnbrook_test/input
cp ~/Downloads/pinnbrook/RAMM_10_2020_PAD15_context_sheets_47000_to_47034.pdf /tmp/pinnbrook_test/input/

# Initialize project
PYTHONPATH=src python3 -m hoard init "Pinn Brook Park 2026" \
    --jurisdiction historic_england_cl3 \
    --output /tmp/pinnbrook_test

# Run full pipeline
PYTHONPATH=src python3 -m hoard run \
    --project pinn_brook_park_2026 \
    --input /tmp/pinnbrook_test/input \
    --workspace /tmp/pinnbrook_test

# With VRAM benchmarking
PYTHONPATH=src python3 << 'PYEOF'
from hoard.config import Config
from hoard.workspace import Workspace
from hoard.cli.run import run_pipeline
from pathlib import Path

cfg = Config(
    project_id='pinn_brook_park_2026',
    project_name='Pinn Brook Park 2026',
    jurisdiction='historic_england_cl3',
    workspace_root=Path('/tmp/pinnbrook_test'),
    input_dir=Path('/tmp/pinnbrook_test/input'),
)
run_pipeline(cfg, benchmark=True)
PYEOF
```

## Validation

After pipeline completes, compare HOARD output against the published report:

1. Check `04_refined/` — does the compliant draft match the published report structure?
2. Check `05_final/report.docx` — does it look publication-ready?
3. Check `logs/benchmarks/` — what were the peak VRAM numbers?
4. Review flagged items with `hoard review --project pinn_brook_park_2026`

## Expected challenges

- The PDF is 72 MB of scanned handwritten context sheets — Phase 0 will classify
  it as a single `context_sheet` file, but it contains 35 sheets. May need manual
  page splitting or Phase 0 enhancement for multi-page PDFs.
- No site photos or section drawings in the dataset — Phase 2 will be skipped.
- GLM-OCR on handwritten forms is the main test — can it accurately extract all
  35 contexts with correct types, descriptions, and interpretations?
