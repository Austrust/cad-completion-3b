#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
device="${1:-Vulkan0}"
model='gguf/CAD-completion-3B-v1-Q4_K_M.gguf'
runtime='runtimes/linux-vulkan/llama-b11669'
if [[ ! -f "$model" ]]; then
  echo 'Missing gguf/CAD-completion-3B-v1-Q4_K_M.gguf. Extract the GPU model package into this directory.' >&2
  exit 1
fi
echo "71d5aafd4971c312a282fcd25b99a00aeaf1cfc4dc0655d2e78cc302bc1b068c  $model" | sha256sum -c -
if [[ ! -x "$runtime/llama-server" ]]; then
  echo 'e8709e5ba6c1b093dea7f3de57f4aba842f9a188fba6b465782d65d6fcfa4d9f  llama-b11669-bin-ubuntu-vulkan-x64.tar.gz' | sha256sum -c -
  mkdir -p runtimes/linux-vulkan
  tar -xzf llama-b11669-bin-ubuntu-vulkan-x64.tar.gz -C runtimes/linux-vulkan
fi
inventory="$("$runtime/llama-server" --list-devices 2>&1)"
printf '%s\n' "$inventory"
if ! grep -qF "$device:" <<< "$inventory"; then
  echo "Requested Vulkan device not found: $device" >&2
  exit 1
fi
exec "$runtime/llama-server" -m "$model" --device "$device" \
  --host 127.0.0.1 --port 18031 -ngl 99 -c 2048 --parallel 1 \
  -b 512 -ub 512 -t 8 --flash-attn off --no-context-shift
