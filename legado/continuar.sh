#!/usr/bin/env bash
#
# Continua a geracao do dataset a partir do PLANO DE POSES (plano_poses.json),
# pulando o que ja foi feito. Pode ser rodado quantas vezes quiser: cada
# execucao faz mais um pedaco, ate a meta (10.000 imagens / 5.000 poses).
#
# Uso:
#   bash continuar.sh                # faz TUDO que falta (2 workers)
#   bash continuar.sh 400            # faz so 400 poses nesta etapa, entao para
#   bash continuar.sh 400 1          # 400 poses, 1 worker
#   bash continuar.sh 0 2            # tudo que falta, 2 workers (0 = sem limite)
#
# Parar no meio: Ctrl+C. Os JSON/PNG ja gravados ficam; a proxima execucao
# continua de onde parou. Ver progresso: python3 status_dataset.py
#
MAX="${1:-0}"          # poses NESTA etapa (0 = todas as que faltam)
WORKERS="${2:-2}"      # instancias paralelas
WS=/mnt/e/cerise/braco
PLANO="$WS/plano_poses.json"
SAIDA="${SAIDA:-$WS/dataset}"

source /opt/ros/humble/setup.bash >/dev/null 2>&1
source "$WS/install/setup.bash" >/dev/null 2>&1

if [ ! -f "$PLANO" ]; then
    echo "ERRO: plano nao encontrado. Rode antes:  python3 gerar_plano.py"
    exit 1
fi

mkdir -p "$SAIDA"

# quantas poses faltam (para nao subir Gazebo a toa)
FALTAM=$(python3 - "$PLANO" "$SAIDA" <<'PY'
import json, os, sys
plano, saida = sys.argv[1], sys.argv[2]
ids = [int(p["id"]) for p in json.load(open(plano))["poses"]]
falta = sum(1 for i in ids
            if not os.path.exists(os.path.join(saida, "%06d.json" % i)))
print(falta)
PY
)
echo "=================================================="
echo " continuar dataset (640x480 RGB)"
echo "   faltam ........ $FALTAM poses"
echo "   nesta etapa ... $([ "$MAX" = 0 ] && echo 'todas' || echo "$MAX")"
echo "   workers ....... $WORKERS"
echo "   saida ......... $SAIDA"
echo "=================================================="
if [ "$FALTAM" -eq 0 ]; then
    echo "COMPLETO! nada a fazer."
    exit 0
fi

# limite por worker (reparte o MAX entre os workers)
if [ "$MAX" -gt 0 ]; then
    MAX_W=$(( (MAX + WORKERS - 1) / WORKERS ))
else
    MAX_W=0
fi

pkill -f "ign gazebo" 2>/dev/null || true
sleep 3

# mata os Gazebos ao sair (inclusive Ctrl+C)
GAZEBOS=()
limpar() { for g in "${GAZEBOS[@]}"; do kill "$g" 2>/dev/null; done
           pkill -f "ign gazebo" 2>/dev/null || true; }
trap limpar EXIT INT TERM

PIDS=()
for w in $(seq 0 $((WORKERS - 1))); do
    DOM=$((90 + w))
    PART="ds_w${w}"
    LOG="/tmp/continuar_w${w}.log"
    (
        source /opt/ros/humble/setup.bash >/dev/null 2>&1
        source "$WS/install/setup.bash" >/dev/null 2>&1
        export ROS_DOMAIN_ID=$DOM IGN_PARTITION=$PART
        export DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/1000
        ros2 launch servo6dof_camera estudio.launch.py headless:=true > "$LOG" 2>&1 &
        GZ=$!
        sleep 55
        ros2 run servo6dof_camera tirar_fotos.py --ros-args \
            -p plano:="$PLANO" \
            -p saida:="$SAIDA" \
            -p worker_id:=$w \
            -p n_workers:=$WORKERS \
            -p max_capturas:=$MAX_W \
            -p duracao:=3.0 \
            -p assentamento:=0.5 \
            -p use_sim_time:=true \
            >> "$LOG" 2>&1
        kill $GZ 2>/dev/null
    ) &
    PIDS+=($!)
    echo "worker $w iniciado (dom $DOM, log $LOG)"
    sleep 8
done

echo "capturando... (Ctrl+C para parar; a proxima execucao continua)"
for p in "${PIDS[@]}"; do wait "$p"; done

echo
python3 "$WS/status_dataset.py"
