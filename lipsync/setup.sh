#!/usr/bin/env bash
# Setup audio2lipsync service for Atlas Avatar
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_DIR="$SCRIPT_DIR/audio2lipsync"

echo "=== Atlas LipSync Service Setup ==="

if [ ! -d "$SERVICE_DIR" ]; then
    git clone https://github.com/aaryansachdeva/unreal-audio2lipsync "$SERVICE_DIR"
fi

cd "$SERVICE_DIR/python"
pip install -r requirements.txt

python3 - <<'EOF'
from huggingface_hub import hf_hub_download
import os
os.makedirs("checkpoints", exist_ok=True)
path = hf_hub_download(repo_id="fotonlabs/unreal-audio2lipsync", filename="best.pt", local_dir="checkpoints")
print(f"Downloaded: {path}")
EOF

echo ""
echo "=== Done! Start service with: ==="
echo "  cd $SERVICE_DIR/python && python src/server.py --ckpt checkpoints/best.pt --stats-dir stats --port 8766"
