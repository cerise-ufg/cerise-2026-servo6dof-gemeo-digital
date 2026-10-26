#!/usr/bin/env bash
# Gera o URDF "achatado" do servo6dof a partir do xacro (roda DENTRO do
# container cerise26_gemeo / servo6dof:humble, com o repositorio em /repo).
#   sudo docker run --rm --name cerise26_gemeo_urdf -v ~/cerise2026/gemeo/repo:/repo \
#        cerise26_gemeo:latest bash /repo/modelo_digital/gerar_urdf.sh
set -e
source /opt/ros/humble/setup.bash
cd /repo/ros2_ws
colcon build --symlink-install --event-handlers console_cohesion- 2>&1 | tail -n 6
source install/setup.bash
SAIDA=/repo/modelo_digital/urdf
mkdir -p "$SAIDA"
XACRO=src/servo6dof/servo6dof_description/urdf/servo6dof.urdf.xacro
# is_ignition:=true -> mesmo URDF que o Gazebo Fortress recebe na geracao do dataset
xacro "$XACRO" is_ignition:=true > "$SAIDA/servo6dof.urdf"
echo "URDF gerado: $SAIDA/servo6dof.urdf ($(wc -c < "$SAIDA/servo6dof.urdf") bytes)"
python3 - "$SAIDA/servo6dof.urdf" <<'PY'
import sys, xml.etree.ElementTree as ET
r = ET.parse(sys.argv[1]).getroot()
links = r.findall("link"); joints = r.findall("joint")
tipos = {}
for j in joints: tipos[j.get("type")] = tipos.get(j.get("type"), 0) + 1
mim = [j.get("name") for j in joints if j.find("mimic") is not None]
print("robot:", r.get("name"), "| links:", len(links), "| joints:", len(joints), tipos)
print("juntas mimic:", ", ".join(mim))
PY
