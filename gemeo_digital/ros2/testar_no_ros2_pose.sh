#!/usr/bin/env bash
# Gemeo digital em ROS 2 com o MODELO DE POSE (Atividade 12), headless, DENTRO do container cerise26_gemeo_rviz:
#   publicar_dataset.py (imagens do TESTE + /joint_states verdade) -> RSP referencia
#     -> gemeo_twin_node (predictor=http: POST da imagem para /api/prever do servidor do gemeo, que roda o
#        PosePredictor na GPU) -> /twin/joint_states -> RSP twin/ -> TF -> RViz 2 em Xvfb (tela virtual :99)
# Requer o servidor do gemeo em modo pose em 127.0.0.1:8091 e GEMEO_PREDICTOR_URL=http://127.0.0.1:8091/api/prever.
# Saidas em $OUT (padrao /integ): resultados/ros2_twin_pose.json, resultados/ros2_twin_pose_terminal.log,
# evidencias/a12i_rviz_gemeo_*.png
D=/repo/gemeo_digital/ros2
URDF=/repo/modelo_digital/urdf/servo6dof.urdf
OUT=${OUT:-/integ}
mkdir -p $OUT/resultados $OUT/evidencias
chmod +x $D/*.py
Xvfb :99 -screen 0 1600x1000x24 -nolisten tcp > /tmp/xvfb.log 2>&1 &
export DISPLAY=:99
sleep 2
python3 - "$URDF" <<'PY'
import sys, yaml
yaml.safe_dump({"robot_state_publisher": {"ros__parameters": {"robot_description": open(sys.argv[1]).read()}}},
               open("/tmp/rsp_ref.yaml", "w"))
PY
ros2 run robot_state_publisher robot_state_publisher --ros-args --params-file /tmp/rsp_ref.yaml > /tmp/rsp_ref.log 2>&1 &
ros2 launch $D/twin.launch.py urdf:=$URDF predictor:=http rviz:=true qos_imagem:=${QOS:-confiavel} > /tmp/twin_launch.log 2>&1 &
sleep 6
python3 $D/publicar_dataset.py --ros-args -p dataset:=/dataset -p n:=${N:-60} -p taxa:=${TAXA:-2.0} -p qos_imagem:=${QOS:-confiavel} > /tmp/pub.log 2>&1 &
sleep 14
import -window root $OUT/evidencias/a12i_rviz_gemeo_1.png
{
echo "\$ ros2 node list"; ros2 node list
echo "\$ ros2 topic hz /twin/joint_states  (10 s)"; timeout 10 ros2 topic hz /twin/joint_states 2>&1 | tail -4
echo "\$ ros2 topic echo --once /twin/joint_states"; timeout 8 ros2 topic echo --once /twin/joint_states 2>&1 | head -22
echo "\$ python3 medir_twin_ros.py --duracao ${DURACAO:-40}"
python3 $D/medir_twin_ros.py --duracao ${DURACAO:-40} --saida $OUT/resultados/ros2_twin_pose.json &
PM=$!
sleep 9; import -window root $OUT/evidencias/a12i_rviz_gemeo_2.png
sleep 9; import -window root $OUT/evidencias/a12i_rviz_gemeo_3.png
wait $PM
} 2>&1 | tee $OUT/resultados/ros2_twin_pose_terminal.log
grep -E "predictor|quadros|WARN|ERROR" /tmp/twin_launch.log | head -12 | tee -a $OUT/resultados/ros2_twin_pose_terminal.log
grep -E "split|carregados" /tmp/pub.log | head -3 | tee -a $OUT/resultados/ros2_twin_pose_terminal.log
pkill -f publicar_dataset.py; pkill -f gemeo_twin_node.py; pkill -f rviz2; pkill -f robot_state_publisher; pkill -f static_transform
pkill Xvfb; sleep 1
