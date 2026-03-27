#!/bin/bash
PYTHON=".venv/bin/python"

# Configuration
TARGET_DIR="data/complex_logic_pool"
OUTPUT_DIR="experimental_data/results/complex_run"
SEVERITY_FILTER="high critical"

echo "=================================================="
echo "🚀 Starting LogicGap Baseline Benchmark (60 Samples)"
echo "=================================================="
echo "Target Directory: $TARGET_DIR"
echo "Output Directory: $OUTPUT_DIR"
echo ""

# Run the batch Python command
$PYTHON main.py --batch "$TARGET_DIR" --output "$OUTPUT_DIR" --severity $SEVERITY_FILTER

echo ""
echo "=================================================="
echo "✅ Batch Run Complete!"
echo "Evaluating and Generating Reports..."
$PYTHON scripts/evaluate_results.py "$OUTPUT_DIR"
$PYTHON scripts/generate_report.py "$OUTPUT_DIR"
echo "=================================================="
