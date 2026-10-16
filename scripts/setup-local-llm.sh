#!/bin/bash
# Installs llama-server as a systemd service on the bababot VM, serving the self-hosted
# fine-tune that main.py uses when BOT_BACKEND=local. Run on the VM after copying the
# GGUF model (which is private and not in git) to $LLM_DIR/bababot.gguf.
set -euo pipefail

LLM_DIR=/opt/bababot-llm
LLAMA_CPP_BUILD="${LLAMA_CPP_BUILD:-b11623}"
RUN_USER=$(id -un)

sudo -n install -d -o "$RUN_USER" -g "$RUN_USER" "$LLM_DIR"
if [ ! -x "$LLM_DIR/llama-$LLAMA_CPP_BUILD/llama-server" ]; then
    curl -sL "https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_CPP_BUILD/llama-$LLAMA_CPP_BUILD-bin-ubuntu-x64.tar.gz" \
        | tar xz -C "$LLM_DIR"
fi
test -f "$LLM_DIR/bababot.gguf" || { echo "Missing $LLM_DIR/bababot.gguf"; exit 1; }

sudo -n tee /etc/systemd/system/bababot-llm.service >/dev/null <<UNIT
[Unit]
Description=llama-server for bababot
After=network-online.target

[Service]
Type=simple
User=$RUN_USER
Environment=LD_LIBRARY_PATH=$LLM_DIR/llama-$LLAMA_CPP_BUILD
ExecStart=$LLM_DIR/llama-$LLAMA_CPP_BUILD/llama-server -m $LLM_DIR/bababot.gguf \
    --host 127.0.0.1 --port 8088 --alias bababot -t 2 -c 4096 --parallel 1 \
    --jinja --chat-template-kwargs '{"enable_thinking":false}'
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT

sudo -n systemctl daemon-reload
sudo -n systemctl enable --now bababot-llm.service
