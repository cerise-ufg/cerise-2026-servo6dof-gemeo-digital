#!/usr/bin/env bash
# Teste de ponta a ponta do no ROS 2 do gemeo (headless, sem RViz), DENTRO do container:
#   bash scripts/rodar_container.sh ros2twin "bash gemeo_digital/ros2/testar_no_ros2.sh"
# publicar_dataset.py (imagens + /joint_states do dataset) -> RSP referencia
#   -> gemeo_twin_node (predictor gt) -> /twin/joint_states -> RSP twin/ -> TF
D=/repo/gemeo_digital/ros2
URDF=/repo/modelo_digital/urdf/servo6dof.urdf
OUT=/repo/resultados
chmod +x $D/*.py
python3 - "$URDF" <<'PY'
import sys, yaml
yaml.safe_dump({"robot_state_publisher": {"ros__parameters": {"robot_description": open(sys.argv[1]).read()}}},
               open("/tmp/rsp_ref.yaml", "w"))
PY
ros2 run robot_state_publisher robot_state_publisher --ros-args --params-file /tmp/rsp_ref.yaml > /tmp/rsp_ref.log 2>&1 &
ros2 launch $D/twin.launch.py urdf:=$URDF predictor:=${PREDICTOR:-gt} > /tmp/twin_launch.log 2>&1 &
python3 $D/publicar_dataset.py --ros-args -p dataset:=/dataset -p n:=40 -p taxa:=2.0 > /tmp/pub.log 2>&1 &
sleep 14
{
echo "\$ ros2 node list"; ros2 node list
echo "\$ ros2 topic hz /twin/joint_states  (8 s)"; timeout 8 ros2 topic hz /twin/joint_states 2>&1 | tail -4
echo "\$ ros2 topic echo --once /twin/joint_states"; timeout 8 ros2 topic echo --once /twin/joint_states 2>&1 | head -24
echo "\$ python3 verificar_tf_twin.py"; python3 $D/verificar_tf_twin.py
} 2>&1 | tee $OUT/ros2_twin_teste.log
grep -E "predictor|quadros" /tmp/twin_launch.log | head -5 | tee -a $OUT/ros2_twin_teste.log
pkill -f publicar_dataset.py; pkill -f gemeo_twin_node.py; pkill -f robot_state_publisher; pkill -f static_transform; sleep 1
