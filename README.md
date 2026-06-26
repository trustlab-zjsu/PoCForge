# PoCForge

PoCForge generates Foundry proof-of-concept tests from smart contract audit findings and verifies them on local forked execution. Inputs are target JSON files under `dataset/`; outputs include `Exploit.t.sol`, execution logs, and result summaries.

## Repository Layout

- `code/`: Main implementation. `code/main.py` is the CLI entry point; `agent_loop.py` handles iterative generation and repair; `executor/` runs Foundry and parses traces; `tools/` handles source fetching, Slither analysis, and file writing.
- `dataset/`: Evaluation datasets, including `D_log/`, `D_mix/`, `rag_knowledge_base/`, and dataset metadata.
- `experimental_artifact/`: Experimental outputs, generated PoCs, logs, and summary tables.
- `foundry_sandbox/`: Foundry sandbox used to compile and run generated tests.
- `.env.example`: Environment variable template.

## Requirements

- Python 3.10+
- Foundry (`forge`, `cast`)
- Slither
- LLM API key, RPC URLs, and block explorer API keys

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r code/requirements.txt
cp .env.example .env
```

Edit `.env` and set at least `LLM_API_KEY`. To fetch verified source code or run fork tests, also set `ETH_RPC_URL`, `BSC_RPC_URL`, `ETHERSCAN_API_KEY`, and `BSCSCAN_API_KEY`. Set `FORGE_ARTIFACTS_DATASET` only if you want the CLI to search a local FORGE-Artifacts dataset for source files.

## Usage

Run a single target:

```bash
.venv/bin/python code/main.py \
  --target dataset/D_log/1-vit.json \
  --finding-id 0 \
  --output experimental_artifact/results/local_run
```

Run a batch:

```bash
.venv/bin/python code/main.py \
  --batch dataset/D_mix \
  --output experimental_artifact/results/local_batch
```

Common options:

- `--finding-id`: Process one finding only.
- `--severity high medium critical`: Filter findings by severity in batch mode.
- `--max-attempts 3`: Set the maximum repair attempts per finding.
- `--block-number <number>`: Use a fixed fork block.
- `--verbose`: Enable debug logs.

## Outputs

Each finding is written to:

```text
<output>/<project>/finding_<id>/
```

Main files:

- `Exploit.t.sol`: Final generated Foundry test.
- `result.json`: Status and run statistics.
- `violation_target.json`: Structured vulnerability target.
- `attempt_history.json`: Generation, compilation, and execution history.

## Data and Results

- Datasets are in `dataset/D_log/` and `dataset/D_mix/`.
- Comparison and ablation results are in `experimental_artifact/results/`.
- Aggregated tables are in `experimental_artifact/Statistical Results/`.
