# Integration Test Datasets

Three real archaeological excavation datasets identified by Deep Research for
pipeline validation. Each contains matched raw field data AND the published
grey literature report.

All sourced from the UK Archaeology Data Service (ADS) under open-access
licences (CC-BY 4.0 or ADS Terms of Use). No registration required.

---

## Dataset 1: Pinn Brook Park, Pinhoe, Devon

**Best fit — right size for 8 GB VRAM testing**

| Metric | Details |
|--------|---------|
| Repository | [ADS Object ID 2183094](https://archaeologydataservice.ac.uk/archives/collections/view/object.cfm?object_id=2183094) |
| Unit | Cotswold Archaeology |
| Contexts | **35** (47000 to 47034) |
| Input | Single PDF with all scanned context sheets, site metadata, trench data |
| Output | Grey literature report for Pinn Brook Park + Tithebarn Lane evaluations |
| Licence | CC-BY 4.0 |
| Why | Cleanly bounded, standard commercial evaluation — representative workload |

---

## Dataset 2: Gallows Hill, Warwick

**Multi-phase, COVID-disrupted — tests synthesis capability**

| Metric | Details |
|--------|---------|
| Repository | [ADS Data Catalogue](https://archaeologydataservice.ac.uk/data-catalogue/resource/3822d3e4f0acea4d3cadf0c8ab4d64b6ba9114db3d5cfaf0689b05959768a850) |
| Unit | Headland Archaeology |
| Contexts | ~50-70 from 14 trenches + 3 strip/map/record areas |
| Input | Pro forma context sheets, post-excavation plans, spot heights, digital site plans |
| Output | 3 MB PDF report (headland1-501801_226361.pdf) |
| Licence | ADS Terms of Use |
| Why | Tests CIfA compliance, multi-phase fieldwork, pandemic-disrupted archives |

---

## Dataset 3: A14 Cambridge to Huntingdon (Alconbury)

**Large infrastructure — stress-test for scaling**

| Metric | Details |
|--------|---------|
| Repository | [ADS DOI 10.5284/1081249](https://archaeologydataservice.ac.uk/archives/collections/view/1003796/) |
| Unit | MOLA Headland Infrastructure consortium |
| Contexts | Scalable — context blocks of ~100 each (e.g., 058001-058099) |
| Input | High-res PDF scans, pottery/flint/animal bone registers, environmental data |
| Output | Published monographs for Alconbury 1 and 2 settlements |
| Licence | CC-BY 4.0 |
| Why | Iron Age/Romano-British rural settlement — complex stratigraphy, extensive finds |

**Recommended subset:** 30 contexts from the 058000-series block for 8 GB VRAM.

---

## Usage

These datasets must be downloaded manually from ADS (direct download, no API
available). Each dataset URL above links to the collection page with downloadable
files.

Place downloaded context sheet PDFs in the project `input/` directory and
configure the project via `hoard init`. The Phase 0 ingestion classifier will
auto-detect context sheets, finds catalogues, and site photos.

**For a full integration test:**
1. Download Pinn Brook Park (35 contexts) as the baseline
2. Run the full pipeline: `hoard run --project pinn_brook`
3. Compare HOARD output against the published report
4. Submit Gallows Hill for multi-phase validation
5. Use A14 Alconbury for scaling tests (10 → 50 → 100 contexts)

## Licensing Verification

All three datasets use open-access licences:
- Pinn Brook Park & A14 Alconbury: CC-BY 4.0 (free for research and commercial use, attribution required)
- Gallows Hill: ADS Terms of Use (permits reuse for AI training and research)

No paywalled or commercial-only data. Full compliance with open-source pipeline requirements.
