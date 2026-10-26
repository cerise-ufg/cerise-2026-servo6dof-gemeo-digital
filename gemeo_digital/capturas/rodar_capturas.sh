#!/usr/bin/env bash
# Capturas do front-end com Playwright headless (imagem derivada da oficial arm64 da Microsoft,
# ver docker/Dockerfile.playwright),
# na rede do host para alcancar o servidor em 127.0.0.1:8091.
#   bash gemeo_digital/capturas/rodar_capturas.sh lado sobreposto diagonal
REPO="${REPO:-$HOME/cerise2026/gemeo/repo}"
IMG=cerise26_gemeo_playwright:latest
sudo docker run --rm --name cerise26_gemeo_playwright --network host --ipc=host \
  --memory 3g --cpus 4 -v "$REPO":/repo $IMG \
  python /repo/gemeo_digital/capturas/capturar.py --url "${URL:-http://127.0.0.1:8091}" --cenarios "$@"
RC=$?
sudo chown -R "$(id -u):$(id -g)" "$REPO/evidencias" "$REPO/resultados" 2>/dev/null
exit $RC
