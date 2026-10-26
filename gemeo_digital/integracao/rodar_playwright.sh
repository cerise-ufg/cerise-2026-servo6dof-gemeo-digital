#!/usr/bin/env bash
# Dirige o front-end do gemeo digital com Playwright headless (Chromium + SwiftShader) na rede do host,
# para alcancar o servidor publicado so no loopback do Spark (127.0.0.1:8091).
#   bash gemeo_digital/integracao/rodar_playwright.sh avaliar
#   bash gemeo_digital/integracao/rodar_playwright.sh capturas
#   bash gemeo_digital/integracao/rodar_playwright.sh varredura --inicio 40 --n 60 --pasta /integ/varredura
# Saidas em $INTEG (padrao ~/cerise2026/gemeo/integracao), montado em /integ.
REPO="${REPO:-$HOME/cerise2026/gemeo/repo}"
INTEG="${INTEG:-$HOME/cerise2026/gemeo/integracao}"
# GL=gpu (padrao): WebGL na GPU (ANGLE/EGL da NVIDIA, headless); GL=swiftshader: software na CPU
GL="${GL:-gpu}"
mkdir -p "$INTEG/resultados" "$INTEG/evidencias"
GPUARGS=""
[ "$GL" = "gpu" ] && GPUARGS="--gpus all -e NVIDIA_DRIVER_CAPABILITIES=all"
sudo docker run --rm --name "cerise26_gemeo_playwright_$1" --network host --ipc=host --memory 3g --cpus 4 \
  $GPUARGS -e GEMEO_GL="$GL" \
  -v "$REPO":/repo:ro -v "$INTEG":/integ cerise26_gemeo_playwright:latest \
  python /repo/gemeo_digital/integracao/avaliar_gemeo.py "$@" --url "${URL:-http://127.0.0.1:8091}"
RC=$?
sudo chown -R "$(id -u):$(id -g)" "$INTEG" 2>/dev/null
exit $RC
