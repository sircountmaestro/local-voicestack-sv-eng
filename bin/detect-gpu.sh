#!/usr/bin/env bash
# 0 = Docker can use an NVIDIA GPU. 1 = use Kokoro CPU image.
set -u
[[ -e /dev/nvidia0 ]] || exit 1
command -v nvidia-smi >/dev/null || exit 1
nvidia-smi -L >/dev/null 2>&1 || exit 1
command -v docker >/dev/null || exit 1
info="$(docker info 2>/dev/null || true)"
echo "$info" | grep -qiE 'nvidia|nvidia.com/gpu' && exit 0
if timeout 20 docker run --rm --gpus all alpine:3.20 true >/dev/null 2>&1; then
  exit 0
fi
exit 1
