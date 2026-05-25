# Context Sheet Data Contract

Version: **v1**
Last updated: 2026-05-25

## Purpose

This contract defines the data format exchanged between:

- **HOARD** (Heritage Observation And Report Drafter) — produces context sheet JSON
- **StratiGraph** — consumes context sheet JSON for stratigraphic visualisation

Both projects validate against the shared schemas in this directory.

## Schemas

| File | Validates | Used by |
|------|-----------|---------|
| `context-sheet-v1.json` | A single context record | HOARD Phase 1 output, StratiGraph input |
| `context-relationships-v1.json` | Stratigraphic edge constraints (DAG validation) | StratiGraph graph builder, HOARD Harris Matrix |

## Versioning

- Schema version follows semver: `v{major}.{minor}`
- Breaking changes (field removal, type change) → increment major version
- Additive changes (new optional field) → increment minor version
- The `$schema` field in each JSON file should reference the exact version

## Validation

### HOARD (Python)

```python
import json
from jsonschema import validate

with open("schemas/context-sheet-v1.json") as f:
    schema = json.load(f)

with open("erd_workspace/project/01_digitised/ctx_101.json") as f:
    data = json.load(f)

validate(instance=data, schema=schema)
```

### StratiGraph (TypeScript)

```typescript
import { validate } from 'jsonschema'
import schema from '../schemas/context-sheet-v1.json'

const data = JSON.parse(fs.readFileSync('ctx_101.json', 'utf-8'))
validate(data, schema)
```

## Fields

See individual schema files for full definitions. Key fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `context_number` | string (e.g. `[101]`) | ✅ | Unique context identifier |
| `type` | string | ✅ | layer/cut/deposit/fill/structure |
| `description` | string | ✅ | Sedimentological description |
| `interpretation` | string | ✅ | Archaeological interpretation |
| `period` | string | ✅ | Chronological period |
| `cuts` | string[] | — | Contexts this one cuts |
| `cut_by` | string[] | — | Contexts that cut this one |
| `fills` | string[] | — | Contexts that fill this one |
| `filled_by` | string[] | — | Contexts this one fills |
| `same_as` | string or null | — | Equivalent context number |
| `finds` | array | — | Recovered finds |
| `samples` | array | — | Environmental samples |
