# PoCForge

PoCForge 用于从智能合约审计报告中的漏洞条目生成 Foundry PoC，并通过本地 fork 测试验证结果。输入是 `dataset/` 中的目标 JSON；输出包括 `Exploit.t.sol`、运行记录和结果摘要。

## 目录

- `code/`: 主程序。`code/main.py` 是入口；`agent_loop.py` 负责迭代生成与修复；`executor/` 负责 Foundry 执行和 trace 解析；`tools/` 负责源码获取、Slither 分析和文件写入。
- `dataset/`: 数据集，包含 `D_log/`、`D_mix/`、`rag_knowledge_base/` 和统计辅助文件。
- `experimental_artifact/`: 实验结果、PoC、日志和统计表。
- `foundry_sandbox/`: Foundry 沙箱，生成的测试会在这里编译和运行。
- `.env.example`: 环境变量模板。

## 环境要求

- Python 3.10+
- Foundry (`forge`, `cast`)
- Slither
- 可用的 LLM API key、RPC URL 和区块浏览器 API key

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r code/requirements.txt
cp .env.example .env
```

编辑 `.env`，至少填写 `LLM_API_KEY`。如果需要从链上拉取源码或 fork 运行，还要配置 `ETH_RPC_URL`、`BSC_RPC_URL`、`ETHERSCAN_API_KEY`、`BSCSCAN_API_KEY`。

## 运行

单个目标：

```bash
.venv/bin/python code/main.py \
  --target dataset/D_log/1-vit.json \
  --finding-id 0 \
  --output experimental_artifact/results/local_run
```

批量运行：

```bash
.venv/bin/python code/main.py \
  --batch dataset/D_mix \
  --output experimental_artifact/results/local_batch
```

常用参数：

- `--finding-id`: 只处理某个漏洞条目。
- `--severity high medium critical`: 指定批量筛选的严重等级。
- `--max-attempts 3`: 设置每个漏洞的最大修复轮数。
- `--block-number <number>`: 使用指定区块做 fork 测试。
- `--verbose`: 输出调试日志。

## 输出

每个漏洞的结果保存在：

```text
<output>/<project>/finding_<id>/
```

主要文件：

- `Exploit.t.sol`: 最终生成的 Foundry 测试。
- `result.json`: 运行状态和统计信息。
- `violation_target.json`: 结构化漏洞目标。
- `attempt_history.json`: 每轮生成、编译和执行记录。

## 数据和结果

- 数据集在 `dataset/D_log/` 和 `dataset/D_mix/`。
- 对比实验和消融实验结果在 `experimental_artifact/results/`。
- 汇总表在 `experimental_artifact/Statistical Results/`。
