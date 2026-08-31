FROM runpod/worker-comfyui:5.8.7-base

# Upgrade the bundled ComfyUI to v0.34.0 (LTX-2.5 support landed in v0.32.0)
RUN set -e; \
    CUI_MAIN=$(find /comfyui -maxdepth 3 -name main.py | head -1); \
    cd "$(dirname "$CUI_MAIN")"; \
    git fetch --depth 1 origin tag v0.34.0 --no-tags || git fetch --tags origin; \
    git checkout v0.34.0; \
    pip install --no-cache-dir -r requirements.txt; \
    python -c "import importlib.util,glob; p=glob.glob('comfy_extras/nodes_lt*.py'); print('LTX node files:', p)"
