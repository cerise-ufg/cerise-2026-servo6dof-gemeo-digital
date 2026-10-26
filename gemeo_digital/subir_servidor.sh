#!/usr/bin/env bash
# Sobe o servidor do Gemeo Digital (FastAPI + WebSocket) no container cerise26_gemeo.
# Publicado SOMENTE no loopback do Spark (127.0.0.1:8091) - nao exposto a internet.
# Acesso do Windows: ssh -N -L 127.0.0.1:18091:localhost:8091 spark-bridge  ->  http://127.0.0.1:18091
#
# Uso:  bash gemeo_digital/subir_servidor.sh [auto|gt|ruido|pose|http]
#   auto  (padrao) usa o PosePredictor se ~/cerise2026/pose/READY.json existir; senao ground truth
#   gt    oraculo (verdade-base)          ruido  GT + ruido gaussiano (demonstracao do painel)
#   pose  exige o PosePredictor           http   GEMEO_PREDICTOR_URL=<url> (servico externo)
# Variaveis: IMAGEM (padrao cerise26_gemeo:latest; para o PosePredictor com torch use a imagem
#            da frente de pose, ex. cerise26_pose:latest - fastapi/uvicorn sao instalados se faltarem),
#            GPU=1 (passa --gpus all), PORTA (8091), NOME (cerise26_gemeo), N_QUADROS (150), RUIDO_GRAUS (3.0)
set -e
MODO="${1:-auto}"
NOME="${NOME:-cerise26_gemeo}"
REPO="${REPO:-$HOME/cerise2026/gemeo/repo}"
DATASET="${DATASET:-$HOME/braco/dataset}"
IMAGEM="${IMAGEM:-cerise26_gemeo:latest}"
PORTA="${PORTA:-8091}"
EXTRA=""
# so monta a pasta da frente de pose se ela ja existir (nao cria pasta como root)
# (montada em /pose e tambem em /workspace/pose, caminho usado pelos scripts da frente de pose)
[ -d "$HOME/cerise2026/pose" ] && EXTRA="$EXTRA -v $HOME/cerise2026/pose:/pose:ro -v $HOME/cerise2026/pose:/workspace/pose:ro"
[ "${GPU:-0}" = "1" ] && EXTRA="$EXTRA --gpus all --ipc=host"
# cache compartilhado do Hugging Face (pesos do Depth Anything usados pelo PosePredictor)
[ "${GPU:-0}" = "1" ] && [ -d "$HOME/cerise2026/hf_cache" ] && EXTRA="$EXTRA -v $HOME/cerise2026/hf_cache:/root/.cache/huggingface"
[ -n "$GEMEO_PREDICTOR_URL" ] && EXTRA="$EXTRA -e GEMEO_PREDICTOR_URL=$GEMEO_PREDICTOR_URL --add-host=host.docker.internal:host-gateway"
sudo docker rm -f $NOME >/dev/null 2>&1 || true
sudo docker run -d --name $NOME \
  -p 127.0.0.1:${PORTA}:8091 \
  --memory 4g --cpus 4 \
  -v "$REPO":/repo:ro -v "$DATASET":/dataset:ro $EXTRA \
  -e GEMEO_PREDICTOR="$MODO" -e GEMEO_POSE_DIR=/pose -e GEMEO_N_QUADROS="${N_QUADROS:-150}" \
  -e GEMEO_RUIDO_GRAUS="${RUIDO_GRAUS:-3.0}" -e PYTHONUNBUFFERED=1 \
  -w /repo/gemeo_digital/servidor "$IMAGEM" \
  bash -c 'python3 -c "import fastapi, uvicorn" 2>/dev/null || pip install -q "fastapi==0.115.6" "uvicorn[standard]==0.32.1"; exec python3 -m uvicorn app:app --host 0.0.0.0 --port 8091'
echo "aguardando o servidor..."
for i in $(seq 1 60); do
  if curl -s "http://127.0.0.1:${PORTA}/saude" >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -s "http://127.0.0.1:${PORTA}/saude"; echo
echo "servidor: http://127.0.0.1:${PORTA}  (container $NOME, so loopback do Spark)"
