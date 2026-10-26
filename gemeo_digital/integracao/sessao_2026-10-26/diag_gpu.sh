sudo docker run --rm --network host --ipc=host --memory 3g --cpus 4 --gpus all -e NVIDIA_DRIVER_CAPABILITIES=all \
  -v ~/cerise2026/gemeo/integracao:/integ cerise26_gemeo_playwright:latest bash -c '
ls /usr/share/vulkan/icd.d/ /usr/share/glvnd/egl_vendor.d/ /etc/vulkan/icd.d 2>&1
ls /usr/lib/aarch64-linux-gnu/ | grep -i -E "nvidia|vulkan" | head -20
python /integ/diag_gpu.py' 2>&1 | tail -30
