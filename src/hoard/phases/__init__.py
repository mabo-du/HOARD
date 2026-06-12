"""hoard.phases — Pipeline phase implementations (Phase 0 through Phase 5).

Each phase is an independent callable invoked by the CLI orchestrator.
Phases communicate through the working directory (hoard_workspace/{project_id}/).
Phases 0 and 5 are rule-based. Phases 1-4 require GPU model inference.

exports: Phase0, Phase1, Phase2, Phase3, Phase4, Phase5  (callable classes)
used_by: hoard.cli.run  → orchestrator
rules:   Every phase must check pipeline_state.json before starting.
         Every phase must write pipeline_state.json on completion.
         Every phase must be resumable (idempotent after completion).
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Initial scaffold
"""
