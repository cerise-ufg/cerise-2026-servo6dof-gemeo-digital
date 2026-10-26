#!/usr/bin/env bash
# Geracao do dataset HD multimodal (RGB 1280x720 + profundidade + segmentacao)
# do servo6dof no container, rendering GPU NVIDIA (EGL). Resumavel, paralelo,
# com auto-recuperacao: cada "ronda" sobe N Gazebos isolados; se o Gazebo cair,
# a proxima ronda continua do disco ate zerar as poses faltantes.
WORKERS="${1:-8}"
WS=/ws
PLANO="$WS/plano_poses.json"
SAIDA="$WS/dataset"
DURACAO="${DURACAO:-3.0}"; ASSENT="${ASSENT:-0.5}"; BOOT="${BOOT:-50}"
LOGDIR="$WS/gen_logs"
source /opt/ros/humble/setup.bash; source "$WS/install/setup.bash"
mkdir -p "$SAIDA" "$LOGDIR"
export RENDER_DRIVER_OVERRIDE=""

faltam(){ python3 - "$PLANO" "$SAIDA" <<"PY"
import json,os,sys
ids=[int(p["id"]) for p in json.load(open(sys.argv[1]))["poses"]]
print(sum(1 for i in ids if not os.path.exists(os.path.join(sys.argv[2],"%06d.json"%i))))
PY
}

ronda(){
  pkill -f "ign gazebo" 2>/dev/null; sleep 3
  PIDS=()
  for w in $(seq 0 $((WORKERS-1))); do
    DOM=$((90+w)); PART="ds_w${w}"; LOG="$LOGDIR/w${w}.log"
    (
      source /opt/ros/humble/setup.bash; source "$WS/install/setup.bash"
      export ROS_DOMAIN_ID=$DOM IGN_PARTITION=$PART RENDER_DRIVER_OVERRIDE=""
      ros2 launch servo6dof_camera estudio.launch.py headless:=true hd:=true > "$LOG" 2>&1 &
      GZ=$!
      sleep $BOOT
      ros2 run servo6dof_camera tirar_fotos.py --ros-args --params-file "$WS/cams_hd.yaml" \
        -p plano:="$PLANO" -p saida:="$SAIDA" -p worker_id:=$w -p n_workers:=$WORKERS \
        -p duracao:=$DURACAO -p assentamento:=$ASSENT -p use_sim_time:=true >> "$LOG" 2>&1
      kill $GZ 2>/dev/null; pkill -f "ign gazebo" 2>/dev/null
    ) &
    PIDS+=($!); sleep 7
  done
  for p in "${PIDS[@]}"; do wait "$p"; done
}

echo "=== inicio $(date) | workers=$WORKERS | meta=5000 poses ==="
parados=0
while true; do
  N=$(faltam)
  echo "$(date +%H:%M:%S) faltam $N poses"
  if [ "$N" -eq 0 ]; then echo "=== COMPLETO $(date) ==="; break; fi
  antes=$N
  ronda
  depois=$(faltam)
  if [ "$depois" -ge "$antes" ]; then
    parados=$((parados+1)); echo "AVISO: ronda sem progresso ($parados/3)"
    if [ "$parados" -ge 3 ]; then echo "ABORT: 3 rondas sem progresso"; exit 1; fi
    sleep 5
  else parados=0; fi
done
