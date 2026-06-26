# PoCForge Code

This directory contains the PoCForge implementation used by the supplementary artifact.

## Main Modules

- `main.py`: CLI entry point for single-target and batch runs.
- `formalizer.py`: Converts audit findings and program facts into a structured VES.
- `agent_loop.py`: Runs the trace-guided ReAct loop for PoC generation and repair.
- `edg.py`: Builds the Exploit Dependency Graph used by the main method.
- `executor/`: Runs Foundry and parses compile/runtime/oracle feedback.
- `tools/`: Source fetching, Slither analysis, interface generation, and PoC file writing.
- `pure_llm_baseline.py`: Direct text-to-PoC baseline without VES, EDG, dependency tools, or repair loops.

## Running

From the repository root:

```bash
.venv/bin/python code/main.py \
  --target dataset/D_log/1-vit.json \
  --finding-id 0 \
  --output experimental_artifact/results/local_run
```

Batch run:

```bash
.venv/bin/python code/main.py \
  --batch dataset/D_mix \
  --output experimental_artifact/results/local_batch
```

Pure LLM baseline:

```bash
.venv/bin/python code/pure_llm_baseline.py \
  --target dataset/D_log/1-vit.json \
  --output experimental_artifact/results/Pure_LLM
```
