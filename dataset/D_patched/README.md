# Patched contract dataset

This directory contains patched contract sources for 104 projects and 176 Gemini baseline-success findings. Missing Quimera prompts were recovered only when Sourcify supplied a verified source for the deployed target; no empty or fabricated contract is used.

## Contents

- `D_mix/<project>/Patched.sol` and `D_log/<project>/Patched.sol`: reviewed standalone/flattened source.
- `metadata.json`: target address, successful findings, patch status, patch summary, source hashes, and validation status.
- `manifest.json`: machine-readable index of 104 source-backed project entries and 176 baseline-success findings.
- `coverage.json`: coverage ledger for all 177 baseline successes (176 source-backed, one source-unavailable).

## Status summary

| Status | Contracts | Meaning |
| --- | ---: | --- |
| `patched` | 98 projects / 169 findings | Verified or archived source has a finding-directed guard recorded in metadata. |
| `reviewed_no_runtime_guard` | 4 projects / 4 findings | Verified source and PoC were reviewed, but the finding is static/already-mitigated and has no runtime entry point to change. |
| `already_mitigated` | 2 projects / 3 findings | The source already contains the relevant guard. |
| `source_mismatch` (recovered target) | 5 projects / 10 findings | The report prompt was mismatched, so the exact PoC target source was recovered separately from Sourcify and retained with mismatch provenance. |

One D_log finding (the separate Shield report entry) remains without a source/PoC artifact and is not counted in the replay population.

## Validation scope

All 104 source-backed entries compile under a pragma-selected local solc (including historical 0.4--0.7 sources). Regression replay covers 176 findings; 169 original controls pass and form the defensible effectiveness subset. The latest replay has 140 cases stopped at patched code, 2 with no reported impact, and 34 still passing validation. The filled table reports all 176 patched replays, while `summary.json` also reports the 169-case control-passing subset. Complete results are in `experimental_artifact/results/patched_poc_replay/results.json`, with the filled LaTeX table in `experimental_artifact/results/patched_poc_replay/patched_contracts_table.tex`.

The patches use conservative policies where the artifact has no application specification: privileged drains and hidden mint paths are disabled, mutable payout/router endpoints are frozen, configurable fees are capped, and CUSD requires an explicit immutable supply cap at deployment.

## Rebuilding the index

Run `python3 code/tools/build_patched_dataset.py` to reconstruct missing source skeletons without overwriting patched contracts, then run `python3 code/tools/finalize_patched_dataset.py` to refresh hashes, statuses, and `manifest.json`.
