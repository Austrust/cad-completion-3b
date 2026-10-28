#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ ! -x .venv-npu/bin/python ]]; then
  echo 'Create the isolated runtime first: bash setup-npu.sh' >&2
  exit 1
fi
.venv-npu/bin/python openvino-server.py --check-device --device NPU
exec .venv-npu/bin/python openvino-server.py --device NPU
