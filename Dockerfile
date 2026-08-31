FROM runpod/worker-comfyui:5.8.6-base-cuda12.8.1

# Upgrade the bundled ComfyUI to v0.34.0 (LTX-2.5 support landed in v0.32.0)
RUN set -e; \
    CUI_MAIN=$(find /comfyui -maxdepth 3 -name main.py | head -1); \
    cd "$(dirname "$CUI_MAIN")"; \
    git fetch --depth 1 origin tag v0.34.0 --no-tags || git fetch --tags origin; \
    git checkout v0.34.0; \
    pip install --no-cache-dir -r requirements.txt; \
    ls comfy_extras/nodes_lt_upsampler.py comfy_extras/nodes_lt.py

# Map the LTX-2.5 model folders on the network volume (base yaml lacks
# diffusion_models/text_encoders/latent_upscale_models)
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# Boot smoke test: catch startup-breaking issues at build time
RUN cd /comfyui && timeout 300 python main.py --quick-test-for-ci --cpu
