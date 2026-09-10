#!/usr/bin/env bash
# enterprise-rag 一键演示：调冻结基线（只读），本仓不写核心检索代码。
# 前提：在本仓根执行，Python 3.8+，仅标准库。
set -euo pipefail
cd "$(dirname "$0")"
python3 baseline/rag_demo.py
echo "--- 单查询演示 ---"
python3 baseline/rag_demo.py --query "分块太大有什么坏处"