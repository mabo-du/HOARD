# Gallows Hill E2E Test Plan

Second integration test for the HOARD pipeline using an independent
archaeological dataset to validate the pipeline works beyond Pinn Brook.

## Manual Download (required — ADS blocks automated tools)

Find a suitable ADS grey literature report with context sheets:

1. Browse: https://archaeologydataservice.ac.uk/library/
2. Search for recent excavations with context sheets available as PDF
3. Download the PDF and any metadata CSV to `~/Downloads/gallows_hill/`

> Recommended candidate: any mid-2020s Cotswold Archaeology or
> Oxford Archaeology grey lit report with 30-100 context sheets.
> Size ~50-80 MB PDF (similar to Pinn Brook).

## Setup

```bash
cd ~/Projects/HOARD

# Copy input files
mkdir -p /tmp/gallows_hill_test/input
cp ~/Downloads/gallows_hill/*.pdf /tmp/gallows_hill_test/input/

# Initialize project
PYTHONPATH=src python3 -m hoard init "Gallows Hill 2026" \
    --jurisdiction historic_england_cl3 \
    --output /tmp/gallows_hill_test

# Run full pipeline
PYTHONPATH=src python3 -m hoard run \
    --project gallows_hill_2026 \
    --input /tmp/gallows_hill_test/input \
    --workspace /tmp/gallows_hill_test

# Run with strict schema validation
PYTHONPATH=src python3 -m hoard run \
    --project gallows_hill_2026 \
    --input /tmp/gallows_hill_test/input \
    --workspace /tmp/gallows_hill_test \
    --strict
```

## Verification

| Check | Expected |
|-------|----------|
| Phase 0 | All pages extracted, quality flags OK |
| Phase 1 | >90% context extraction rate |
| Phase 2 | Photos/plans only (no context sheets in plates) |
| Phase 3 | 10-section draft with no MISSING sections |
| Phase 4 | Compliant report with field defaults applied |
| Phase 5 | DOCX + PDF/A-2b + ZIP exported |

## Validation on StratiGraph

After the pipeline completes:

1. Open StratiGraph (`cd ~/Projects/StratiGraph/app && npm run dev`)
2. Click **Import** → **HOARD JSON Import**
3. Select all `ctx_sheet_*.json` files from `01_digitised/`
4. Verify:
   - All contexts appear in the sidebar
   - Stratigraphic relationships are rendered as edges
   - No missing stub contexts for cross-referenced IDs
   - Matrix is cycle-free (auto-validated)
5. Export HOARD JSON payload → verify in downstream tools
