#!/usr/bin/env bash
# Executa um comando no container de ferramentas cerise26_gemeo:latest com o
# repositorio montado em /repo, o dataset (somente leitura) em /dataset e a
# pasta de metadados em /dataset_meta e ~/braco (somente leitura) em /braco.
# Nome do container: cerise26_gemeo_job_<tag>.
#   bash scripts/rodar_container.sh <tag> "<comando>"
# Variaveis: REPO (padrao ~/cerise2026/gemeo/repo), DATASET (~/braco/dataset),
#            META (~/cerise2026/gemeo/dataset_meta), EXTRA (args extras do docker run)
TAG="$1"; shift
REPO="${REPO:-$HOME/cerise2026/gemeo/repo}"
DATASET="${DATASET:-$HOME/braco/dataset}"
META="${META:-$HOME/cerise2026/gemeo/dataset_meta}"
mkdir -p "$META"
sudo docker run --rm --name "cerise26_gemeo_job_${TAG}" \
  --cpus="${CPUS:-6}" --cpu-shares=256 --memory="${MEM:-16g}" \
  -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}" -e PYTHONUNBUFFERED=1 -e MPLCONFIGDIR=/tmp/mpl \
  -v "$REPO":/repo -v "$DATASET":/dataset:ro -v "$META":/dataset_meta \
  -v "$HOME/braco":/braco:ro \
  ${EXTRA} -w /repo cerise26_gemeo:latest \
  bash -c "source /opt/ros/humble/setup.bash; [ -f /repo/ros2_ws/install/setup.bash ] && source /repo/ros2_ws/install/setup.bash; $*"
RC=$?
sudo chown -R "$(id -u):$(id -g)" "$REPO" "$META" 2>/dev/null || true
exit $RC
