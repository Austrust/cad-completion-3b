#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ -e .venv-npu ]]; then
  echo 'Existing .venv-npu found; preserve it and inspect its dependencies.' >&2
  exit 1
fi
python3 -m venv .venv-npu
.venv-npu/bin/python -m pip install -r requirements-npu.txt
.venv-npu/bin/python openvino-server.py --check-device --device NPU
