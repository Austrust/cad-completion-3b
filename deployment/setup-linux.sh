#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ -x runtimes/linux-vulkan/llama-b11669/llama-server ]]; then
  echo 'Linux Vulkan runtime is already installed.'
  exit 0
fi
echo 'e8709e5ba6c1b093dea7f3de57f4aba842f9a188fba6b465782d65d6fcfa4d9f  llama-b11669-bin-ubuntu-vulkan-x64.tar.gz' | sha256sum -c -
mkdir -p runtimes/linux-vulkan
tar -xzf llama-b11669-bin-ubuntu-vulkan-x64.tar.gz -C runtimes/linux-vulkan
test -x runtimes/linux-vulkan/llama-b11669/llama-server
echo 'Ready. Run: bash loader/start.sh'
