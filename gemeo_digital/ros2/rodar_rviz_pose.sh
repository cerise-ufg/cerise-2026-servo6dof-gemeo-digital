#!/usr/bin/env bash
# Roda o teste do no ROS 2 + RViz headless com o modelo de pose (ver testar_no_ros2_pose.sh), no Spark.
# Constroi a imagem cerise26_gemeo_rviz se faltar. Rede do host so para alcancar 127.0.0.1:8091;
# ROS_LOCALHOST_ONLY=1 e ROS_DOMAIN_ID=42 isolam o DDS. Nada e exposto fora do loopback.
#   bash gemeo_digital/ros2/rodar_rviz_pose.sh
REPO="${REPO:-$HOME/cerise2026/gemeo/repo}"
INTEG="${INTEG:-$HOME/cerise2026/gemeo/integracao}"
if ! sudo docker image inspect cerise26_gemeo_rviz:latest >/dev/null 2>&1; then
  (cd "$REPO" && nice -n 19 sudo docker build -f docker/Dockerfile.rviz -t cerise26_gemeo_rviz:latest .) || exit 1
fi
sudo docker run --rm --name cerise26_gemeo_rviz --network host --ipc=host --cpus 6 --memory 6g \
  -e ROS_DOMAIN_ID=42 -e ROS_LOCALHOST_ONLY=1 -e PYTHONUNBUFFERED=1 \
  -e GEMEO_PREDICTOR_URL="${GEMEO_PREDICTOR_URL:-http://127.0.0.1:8091/api/prever}" \
  -e N="${N:-60}" -e TAXA="${TAXA:-2.0}" -e DURACAO="${DURACAO:-40}" \
  -v "$REPO":/repo -v "$HOME/braco/dataset":/dataset:ro -v "$HOME/cerise2026/pose":/pose:ro -v "$INTEG":/integ \
  cerise26_gemeo_rviz:latest \
  bash -c "source /opt/ros/humble/setup.bash; [ -f /repo/ros2_ws/install/setup.bash ] && source /repo/ros2_ws/install/setup.bash; bash /repo/gemeo_digital/ros2/testar_no_ros2_pose.sh"
RC=$?
sudo chown -R "$(id -u):$(id -g)" "$INTEG" "$REPO" 2>/dev/null
exit $RC
