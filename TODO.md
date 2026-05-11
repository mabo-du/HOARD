---
mode: subagent
---

<!-- SPDX-License-Identifier: MIT -->
<!-- SPDX-FileCopyrightText: 2025-2026 Marcus Quinn -->
# TODO

Project task tracking with time estimates, dependencies, and TOON-enhanced parsing.

Compatible with [todo-md](https://github.com/todo-md/todo-md), [todomd](https://github.com/todomd/todo.md), [taskell](https://github.com/smallhadroncollider/taskell), and [Beads](https://github.com/steveyegge/beads).

## Format

**Human-readable:**

<!-- GH#17804: Format examples wrapped in HTML comment to prevent parsers
     from extracting them as real tasks during upgrade-planning migrations.
- [ ] t001 Task description @owner #tag ~30m risk:low logged:2025-01-15
- [ ] t002 Dependent task blocked-by:t001 ~15m risk:med
- [ ] t001.1 Subtask of t001 ~10m
- [x] t003 Completed task ~30m actual:25m logged:2025-01-10 completed:2025-01-15
- [-] Declined task
-->

Format: `- [ ] tNNN Description @owner #tag ~estimate risk:level logged:date`

**Task IDs:**
- `t001` - Top-level task
- `t001.1` - Subtask of t001
- `t001.1.1` - Sub-subtask

**Dependencies:**
- `blocked-by:t001` - This task waits for t001
- `blocked-by:t001,t002` - Waits for multiple tasks
- `blocks:t003` - This task blocks t003

**Time fields:**
- `~estimate` - AI-assisted execution time (~15m trivial, ~30m small, ~1h medium, ~2h large, ~4h major — see `reference/planning-detail.md`)
- `actual:` - Actual active time spent (from session-time-helper.sh)
- `logged:` - When task was added
- `started:` - When branch was created
- `completed:` - When task was marked done

**Risk (human oversight needed):**
- `risk:low` - Autonomous: fire-and-forget, review PR after
- `risk:med` - Supervised: check in mid-task, review before merge
- `risk:high` - Engaged: stay present, test thoroughly, potential regressions

<!--TOON:meta{version,format,updated}:
1.1,todo-md+toon,{{DATE}}
-->

## Backlog

- [ ] t001 Evaluate & select TrOCR variant for handwritten text recognition @hoard #phase1 ~2h risk:med logged:2026-05-11
- [ ] t002 Integrate HTRflow page segmenter with TrOCR pipeline @hoard #phase1 ~3h risk:med logged:2026-05-11
- [ ] t003 Set up Chandra OCR 2 (4-bit GGUF) for form/checkbox extraction @hoard #phase1 ~2h risk:med logged:2026-05-11
- [ ] t004 Set up MinerU2.5-Pro for complex table parsing @hoard #phase1 ~2h risk:med logged:2026-05-11
- [ ] t005 Set up PaddleOCR-VL-1.5 for distortion correction pre-processor @hoard #phase1 ~1h risk:low logged:2026-05-11
- [ ] t006 Implement Phase 1 model routing logic (type + quality → model dispatch) @hoard #phase1 ~3h risk:high logged:2026-05-11
- [ ] t007 Write Phase 1 unit tests (synthetic forms, known answers) @hoard #phase1 ~2h risk:med logged:2026-05-11
- [ ] t008 Set up Gemma 4-E2B (Q4_K_M) for photo captioning & visual grounding @hoard #phase2 ~2h risk:med logged:2026-05-11
- [ ] t009 Set up Zero-To-CAD (ADSKAILab/Zero-To-CAD-Qwen3-VL-2B) for sketch-to-CAD @hoard #phase2 ~2h risk:high logged:2026-05-11
- [ ] t010 Implement Phase 2 orchestration with CadQuery sandbox validation @hoard #phase2 ~3h risk:high logged:2026-05-11
- [ ] t011 Write Phase 2 unit tests @hoard #phase2 ~2h risk:med logged:2026-05-11
- [ ] t012 Set up llama.cpp server mode for Qwen3.5-4B inference @hoard #phase3 ~2h risk:med logged:2026-05-11
- [ ] t013 Implement Phase 3 context assembly (manifest → structured prompt) @hoard #phase3 ~3h risk:high logged:2026-05-11
- [ ] t014 Implement Thinking Mode reasoning capture + logging @hoard #phase3 ~1h risk:low logged:2026-05-11
- [ ] t015 Implement chunk-and-merge fallback for large sites (>500 contexts) @hoard #phase3 ~2h risk:med logged:2026-05-11
- [ ] t016 Implement Phase 3 human review triggers @hoard #phase3 ~2h risk:med logged:2026-05-11
- [ ] t017 Write Phase 3 unit tests @hoard #phase3 ~2h risk:med logged:2026-05-11
- [ ] t018 Implement Phase 4 compliance model runner (Gemma 4-E2B, section-by-section) @hoard #phase4 ~2h risk:med logged:2026-05-11
- [ ] t019 Implement compliance checks: mandatory sections, prohibited terms, heading style @hoard #phase4 ~3h risk:med logged:2026-05-11
- [ ] t020 Write Phase 4 unit tests @hoard #phase4 ~2h risk:med logged:2026-05-11
- [ ] t021 Implement terminal-based review dashboard (rich/textual) @hoard #review ~4h risk:med logged:2026-05-11
- [ ] t022 Implement flag review workflow (accept/correct/defer per flagged item) @hoard #review ~3h risk:med logged:2026-05-11
- [ ] t023 Write review dashboard tests @hoard #review ~2h risk:low logged:2026-05-11
- [ ] t024 Assemble integration test dataset (3 past excavations with known reports) @hoard #testing ~3h risk:low logged:2026-05-11
- [ ] t025 Add Harris Matrix SVG generation from stratigraphic relationships @hoard #feature ~2h risk:med logged:2026-05-11
- [ ] t026 Add ARK system direct data input (bypass Phase 1 OCR for digital-first sites) @hoard #feature ~4h risk:med logged:2026-05-11
- [ ] t027 Configure PyPI publish workflow (GitHub Actions release → PyPI) @hoard #infra ~2h risk:low logged:2026-05-11
- [ ] t028 Write user guide (CLI reference + pipeline walkthrough) @hoard #docs ~3h risk:low logged:2026-05-11
- [ ] t029 Write CONTRIBUTING.md with development setup guide @hoard #docs ~1h risk:low logged:2026-05-11
- [ ] t030 Benchmark full pipeline runtime against 6 GB VRAM target @hoard #testing ~2h risk:low logged:2026-05-11

<!--TOON:backlog[30]{id,desc,owner,tags,est,risk,logged,status}:
t001|Evaluate & select TrOCR variant|hoard|phase1|2h|med|2026-05-11|pending
t002|Integrate HTRflow page segmenter|hoard|phase1|3h|med|2026-05-11|pending
t003|Set up Chandra OCR 2 for forms|hoard|phase1|2h|med|2026-05-11|pending
t004|Set up MinerU2.5-Pro table parsing|hoard|phase1|2h|med|2026-05-11|pending
t005|Set up PaddleOCR-VL-1.5 distortion correction|hoard|phase1|1h|low|2026-05-11|pending
t006|Phase 1 model routing logic|hoard|phase1|3h|high|2026-05-11|pending
t007|Phase 1 unit tests|hoard|phase1|2h|med|2026-05-11|pending
t008|Gemma 4-E2B photo captioning|hoard|phase2|2h|med|2026-05-11|pending
t009|Zero-To-CAD sketch-to-CAD|hoard|phase2|2h|high|2026-05-11|pending
t010|Phase 2 orchestration + CadQuery sandbox|hoard|phase2|3h|high|2026-05-11|pending
t011|Phase 2 unit tests|hoard|phase2|2h|med|2026-05-11|pending
t012|llama.cpp server for Qwen3.5-4B|hoard|phase3|2h|med|2026-05-11|pending
t013|Phase 3 context assembly|hoard|phase3|3h|high|2026-05-11|pending
t014|Thinking Mode reasoning capture|hoard|phase3|1h|low|2026-05-11|pending
t015|Chunk-and-merge for large sites|hoard|phase3|2h|med|2026-05-11|pending
t016|Phase 3 human review triggers|hoard|phase3|2h|med|2026-05-11|pending
t017|Phase 3 unit tests|hoard|phase3|2h|med|2026-05-11|pending
t018|Phase 4 compliance model runner|hoard|phase4|2h|med|2026-05-11|pending
t019|Phase 4 compliance checks|hoard|phase4|3h|med|2026-05-11|pending
t020|Phase 4 unit tests|hoard|phase4|2h|med|2026-05-11|pending
t021|Terminal review dashboard|hoard|review|4h|med|2026-05-11|pending
t022|Flag review workflow|hoard|review|3h|med|2026-05-11|pending
t023|Review dashboard tests|hoard|review|2h|low|2026-05-11|pending
t024|Integration test dataset assembly|hoard|testing|3h|low|2026-05-11|pending
t025|Harris Matrix SVG generation|hoard|feature|2h|med|2026-05-11|pending
t026|ARK system direct data input|hoard|feature|4h|med|2026-05-11|pending
t027|PyPI publish workflow|hoard|infra|2h|low|2026-05-11|pending
t028|User guide|hoard|docs|3h|low|2026-05-11|pending
t029|CONTRIBUTING.md|hoard|docs|1h|low|2026-05-11|pending
t030|Full pipeline VRAM benchmark|hoard|testing|2h|low|2026-05-11|pending
-->

## In Progress

<!--TOON:in_progress[0]{id,desc,owner,tags,est,risk,logged,started,status}:
-->

## In Review

<!--TOON:in_review[0]{id,desc,owner,tags,est,pr_url,started,pr_created,status}:
-->

## Done

- [x] t031 Phase 0: Ingestion & Triage (rule-based, no GPU) ~8h actual:8h logged:2026-05-09 completed:2026-05-09
- [x] t032 Phase 5: Assembly & Export (rule-based, no GPU) ~6h actual:6h logged:2026-05-09 completed:2026-05-09
- [x] t033 Template engine with 14 jurisdiction templates ~4h actual:4h logged:2026-05-09 completed:2026-05-09
- [x] t034 GitHub Actions CI workflow (lint + test + type-check) ~1h actual:1h logged:2026-05-11 completed:2026-05-11
- [x] t035 GitHub repo migration + remote setup ~1h actual:1h logged:2026-05-11 completed:2026-05-11

<!--TOON:done[5]{id,desc,owner,tags,est,actual,logged,started,completed,status}:
t031|Phase 0: Ingestion & Triage|hoard|phase0|8h|8h|2026-05-09|2026-05-09|2026-05-09|completed
t032|Phase 5: Assembly & Export|hoard|phase5|6h|6h|2026-05-09|2026-05-09|2026-05-09|completed
t033|Template engine + 14 jurisdiction templates|hoard|templates|4h|4h|2026-05-09|2026-05-09|2026-05-09|completed
t034|GitHub Actions CI workflow|hoard|infra|1h|1h|2026-05-11|2026-05-11|2026-05-11|completed
t035|GitHub repo migration + remote setup|hoard|infra|1h|1h|2026-05-11|2026-05-11|2026-05-11|completed
-->

## Declined

<!--TOON:declined[0]{id,desc,reason,logged,status}:
-->

<!--TOON:dependencies-->
t006|blocked-by|t001
t006|blocked-by|t003
t006|blocked-by|t005
t007|blocked-by|t006
t010|blocked-by|t008
t010|blocked-by|t009
t011|blocked-by|t010
t013|blocked-by|t012
t015|blocked-by|t013
t016|blocked-by|t013
t017|blocked-by|t013
t019|blocked-by|t018
t020|blocked-by|t019
t022|blocked-by|t021
t023|blocked-by|t022
t024|blocked-by|t007
t024|blocked-by|t011
t024|blocked-by|t017
t024|blocked-by|t020
<!--/TOON:dependencies-->

<!--TOON:subtasks-->
t001|t002
t008|t009
<!--/TOON:subtasks-->

<!--TOON:summary{total,ready,pending,in_progress,in_review,done,declined,total_est,total_actual}:
35,0,30,0,0,5,0,72h,20h
-->
