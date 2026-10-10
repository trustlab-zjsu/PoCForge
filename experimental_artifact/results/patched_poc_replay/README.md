# Paired patched-PoC replay

The final replay is finding-aligned: every Gemini baseline-success PoC for which a verified or archived source was available is included. Every included PoC is run twice with the same fork setup:

1. original compiled runtime (control), then
2. compiled `dataset/D_patched/.../Patched.sol` runtime.

The 177 baseline successes now have 176 source-backed replay records (90 D_mix and 86 D_log). This includes exact target-source recovery for the ten formerly mismatched cases; one D_log case still has no source/PoC artifact. The raw patched population therefore exceeds the requested 170 cases. 169 original-runtime controls pass (90 D_mix and 79 D_log); seven D_log controls are retained in `results.json` but excluded from the effectiveness subset because the original PoC did not reproduce on the current fork/state.

Across all 176 source-backed replays, 140 stop at patched code, 2 report no impact, and 34 still pass validation. On the valid-control subset, 135/169 no longer pass (79.9%). The remaining passes are predominantly already-mitigated contracts or PoCs whose oracle checks a normal ERC-20 operation, ownership/configuration behavior, or a static code-quality property rather than the vulnerable state transition. They are not silently counted as successful exploits.

The earlier 96-case run was invalid because the runner accidentally compiled the archived original source for both runtime variants and also included unrelated findings from the same project. Its conclusions must not be used; the corrected table and results are the files in this directory.
