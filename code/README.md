# PoCForge: From Bug Report to Exploit for Smart Contract via Trace-Guided Agentic Generation

PoCForge is an agent-driven automated exploit generation framework for smart contracts. Instead of direct text-to-code transformation, PoCForge engages in a trace-guided agentic generation paradigm.

## Repository Structure

- **`main.py`**: The core CLI entry point. Handles target parsing, AST extraction, and initiates the agent loop.
- **`code/`**: Contains the main engine.
  - `agent_loop.py`: The iterative prompt generation and fix loop.
  - `executor/`: Local Foundry testing and execution trace parsing.
  - `tools/`: Extractor for Slither AST, code writers, and source fetchers.
- **`data/`**: Standardized datasets (`D_log_dataset` and `D_mix_dataset`).
- **`scripts/`**: Utilities for benchmarking, plotting, and evaluating success metrics.
- **`experiment/`**: Contains all raw PoC execution logs (`results/`) and compiled statistical tables (`Statistical Results/`).
- **`foundry_sandbox/`**: The isolated environment where generated exploits are compiled and run natively.

## Prerequisites

1. **Python 3.10+**
2. **[Foundry](https://book.getfoundry.sh/)**: Must be installed and accessible in your system `PATH` (provides `forge` and `cast`).
3. **Slither**: Required for AST extraction.

## Installation

1. Install Python dependencies:
   ```bash
   pip install -r code/requirements.txt
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Fill in your `.env` file with the necessary API keys. The default LLM provider is DeepSeek:
   ```bash
   LLM_API_URL=https://api.deepseek.com
   LLM_MODEL=deepseek-reasoner
   LLM_API_KEY=<your-deepseek-api-key>
   ```

3. Set up Foundry:
   The `foundry_sandbox` folder automatically manages the execution of PoCs. Ensure `remappings.txt` is correctly set up inside the sandbox to link standard libraries like OpenZeppelin.

## Usage

### 1. Run a Single Target
Execute the pipeline against a specific vulnerability target JSON:
```bash
python main.py --target data/D_log_dataset/your_target.pdf.json --output experiment/results/single_run
```
Add `--finding-id <ID>` if you only want to test a specific finding from the dataset.

### 2. Run Batch Benchmarks
You can process entire directories of vulnerabilities using the built-in batch mode, or use the provided script:
```bash
bash scripts/run_benchmark.sh
```

### 3. Evaluate Metrics
To parse the output directories and calculate CSR (Compilation Success Rate), ERR (EVM Revert Rate), and VPR (Verification Pass Rate):
```bash
python scripts/evaluate_results.py experiment/results/your_run_name
```
Metrics will be output directly to the console.

### 4. Run the Pure LLM Baseline
The paper compares PoCForge with a direct text-to-PoC baseline. This mode sends the report, ABI, and source code directly to the LLM and runs the generated Foundry test once, without VES, EDG, dependency tools, or feedback repair:
```bash
python code/pure_llm_baseline.py --target dataset/D_log/your_target.json --output experimental_artifact/results/Pure_LLM
```

## Datasets and Experimental Results

This repository contains the exact datasets and artifacts used to evaluate LogicGap against baselines (Quimera, AdvScanner) and multiple LLMs (DeepSeek, Qwen).

- Raw execution data and generated `Exploit.t.sol` files can be found in `experiment/results/`.
- Aggregated CSV and Markdown reports are available in `experiment/Statistical Results/`.

## License

[MIT License](LICENSE)
