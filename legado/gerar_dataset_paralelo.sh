#!/usr/bin/env bash
#
# Geracao PARALELA do dataset - 640x480 RGB, 2 cameras, ogre1.
# N instancias independentes do Gazebo, cada uma fotografando uma fatia
# diferente do espaco de poses, todas gravando na mesma pasta com nomes de
# arquivo sem colisao.
#
# A espera de cada pose e' por TEMPO DE SIMULACAO, lida do topico /clock.
# Isso e' robusto ao fator de tempo real da sim e independe do
# joint_state_broadcaster, que as vezes nao ativa no boot.
#
# Uso:
#   bash gerar_dataset_paralelo.sh <poses_total> <n_workers> [saida]
#   bash gerar_dataset_paralelo.sh 3000 2
#
TOTAL="${1:-3000}"
WORKERS="${2:-2}"
SAIDA="${3:-/mnt/e/cerise/braco/dataset}"
WS=/mnt/e/cerise/braco

source /opt/ros/humble/setup.bash >/dev/null 2>&1
source "$WS/install/setup.bash" >/dev/null 2>&1
mkdir -p "$SAIDA"

POR_WORKER=$(( (TOTAL + WORKERS - 1) / WORKERS ))
echo "=================================================="
echo " geracao paralela - 640x480 RGB"
echo "   poses total ... $TOTAL"
echo "   workers ....... $WORKERS  (~$POR_WORKER poses cada)"
echo "   saida ......... $SAIDA"
echo "=================================================="

pkill -f "ign gazebo" 2>/dev/null || true
sleep 3

PIDS=()
for w in $(seq 0 $((WORKERS - 1))); do
    DOM=$((90 + w))
    PART="ds_w${w}"
    INI=$((w * POR_WORKER))
    SEM=$((2000 + w))
    LOG="/tmp/ds_w${w}.log"
    PARAMS="$WS/params_w${w}.yaml"

    cat > "$PARAMS" <<YAML
fotografo_servo6dof:
  ros__parameters:
    saida: $SAIDA
    n_aleatorias: $POR_WORKER
    semente: $SEM
    indice_inicial: $INI
    duracao: 3.0
    assentamento: 0.5
    use_sim_time: true
    cameras:
      - /camera_frontal/image
      - /camera_diagonal/image
YAML

    (
        source /opt/ros/humble/setup.bash >/dev/null 2>&1
        source "$WS/install/setup.bash" >/dev/null 2>&1
        export ROS_DOMAIN_ID=$DOM IGN_PARTITION=$PART
        export DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/1000
        ros2 launch servo6dof_camera estudio.launch.py headless:=true > "$LOG" 2>&1 &
        GZ=$!
        sleep 55
        ros2 run servo6dof_camera tirar_fotos.py --ros-args --params-file "$PARAMS" >> "$LOG" 2>&1
        kill $GZ 2>/dev/null
    ) &
    PIDS+=($!)
    echo "worker $w iniciado (dom $DOM, indices $INI..$((INI + POR_WORKER - 1)))"
    sleep 8
done

echo "aguardando os $WORKERS workers terminarem..."
for p in "${PIDS[@]}"; do wait "$p"; done

echo "=================================================="
du -sh "$SAIDA"
find "$SAIDA" -name "*.png" | wc -l | xargs echo "imagens PNG:"
find "$SAIDA" -name "*.json" | wc -l | xargs echo "anotacoes JSON:"
echo "=================================================="
