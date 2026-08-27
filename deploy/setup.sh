#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Reproducible GPU-server setup: Ollama + 30B coder (abliterated & stock) +
# Aider + OpenHands (patched). Verified on RTX 4090 24GB, Ubuntu 24.04 + CUDA.
#
# H100 80GB: run with  QUANT=Q6_K ./setup.sh   (see deploy/README.md).
# Usage:     chmod +x setup.sh && ./setup.sh
# ---------------------------------------------------------------------------
set -euo pipefail

QUANT="${QUANT:-Q4_K_M}"     # Q4_K_M fits 24GB. On 80GB use Q6_K or Q8_0.
ABLIT="hf.co/mradermacher/Huihui-Qwen3-Coder-30B-A3B-Instruct-abliterated-i1-GGUF"
STOCK="hf.co/mradermacher/Qwen3-Coder-30B-A3B-Instruct-i1-GGUF"
OH_APP="ghcr.io/all-hands-ai/openhands:latest"
OH_RT="ghcr.io/all-hands-ai/runtime:0.59-nikolaik"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "== 1/7 Ollama =="
command -v ollama >/dev/null 2>&1 || curl -fsSL https://ollama.com/install.sh | sh
sudo mkdir -p /etc/systemd/system/ollama.service.d
printf '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0:11434"\n' \
  | sudo tee /etc/systemd/system/ollama.service.d/override.conf >/dev/null
sudo systemctl daemon-reload && sudo systemctl restart ollama
sleep 3

echo "== 2/7 Models (quant=$QUANT) =="
ollama pull "$ABLIT:$QUANT" && ollama cp "$ABLIT:$QUANT" coder-abliterated
ollama pull "$STOCK:$QUANT" && ollama cp "$STOCK:$QUANT" coder-stock

echo "== 3/7 Docker =="
command -v docker >/dev/null 2>&1 || { curl -fsSL https://get.docker.com | sudo sh; }
sudo usermod -aG docker "$USER" || true

echo "== 4/7 Firewall (public: only SSH + Jupyter; Ollama/OpenHands closed) =="
sudo ufw allow 22/tcp
sudo ufw allow 8888/tcp
sudo ufw route allow in on docker0          # let containers reach host services
sudo ufw --force enable

echo "== 5/7 Aider =="
[ -x "$HOME/.local/bin/aider" ] || curl -LsSf https://aider.chat/install.sh | sh

echo "== 6/7 OpenHands (UI bound to localhost -> reach via SSH tunnel) =="
sudo docker pull "$OH_APP"
sudo docker pull "$OH_RT"
sudo docker rm -f openhands-app 2>/dev/null || true
sudo docker run -d --name openhands-app \
  -e SANDBOX_RUNTIME_CONTAINER_IMAGE="$OH_RT" \
  -e SANDBOX_TIMEOUT=300 -e SANDBOX_USER_ID=0 -e LOG_ALL_EVENTS=true \
  -e LLM_MODEL=openai/coder-abliterated \
  -e LLM_BASE_URL=http://host.docker.internal:11434/v1 \
  -e LLM_API_KEY=ollama \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$HOME/.openhands":/.openhands \
  -p 127.0.0.1:3000:3000 \
  --add-host host.docker.internal:host-gateway \
  "$OH_APP"

echo "== 7/7 Patch OpenHands runtime (drop heavy jupyter/vscode plugins) =="
# Needed on slow/network storage where the sandbox action-server hangs on
# plugin init. Harmless on fast NVMe. See deploy/README.md.
sleep 20
sudo docker cp "$HERE/oh_patch.py" openhands-app:/tmp/oh_patch.py
sudo docker exec openhands-app python3 /tmp/oh_patch.py
sudo docker restart openhands-app

cat <<'DONE'
============================================================
READY.
  Models:   coder-abliterated, coder-stock  (ollama list)
  Aider:    export OLLAMA_API_BASE=http://127.0.0.1:11434
            ~/.local/bin/aider --model ollama_chat/coder-abliterated
  OpenHands UI (from your laptop):
            ssh -i <key> -N -L 3000:localhost:3000 ubuntu@<server-ip>
            then open  http://localhost:3000
            LLM in UI: openai/coder-abliterated | http://host.docker.internal:11434/v1 | key: ollama
============================================================
DONE
