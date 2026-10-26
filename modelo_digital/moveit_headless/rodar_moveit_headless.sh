#!/usr/bin/env bash
# MoveIt 2 headless com hardware falso. Roda DENTRO do container cerise26_gemeo:
#   bash scripts/rodar_container.sh moveit "bash modelo_digital/moveit_headless/rodar_moveit_headless.sh"
D=/repo/modelo_digital/moveit_headless
OUT=/repo/resultados
mkdir -p $OUT /tmp/mv
python3 $D/urdf_fake.py /repo/modelo_digital/urdf/servo6dof.urdf /tmp/mv/servo6dof_fake.urdf
ros2 launch $D/moveit_fake.launch.py urdf:=/tmp/mv/servo6dof_fake.urdf > /tmp/mv/launch.log 2>&1 &
LP=$!
python3 $D/cliente_moveit.py $OUT/moveit_planejamento.json 2>&1 | tee $OUT/moveit_cliente.log
RC=${PIPESTATUS[0]}
echo "--- ros2 control list_controllers ---" | tee -a $OUT/moveit_cliente.log
timeout 15 ros2 control list_controllers 2>&1 | tee -a $OUT/moveit_cliente.log
kill -INT $LP 2>/dev/null; sleep 3; kill $LP 2>/dev/null
grep -E "You can start planning|planning pipeline|Planning request|Solution found|ERROR|Error" /tmp/mv/launch.log | head -40 > $OUT/moveit_launch_trecho.log
cp /tmp/mv/launch.log $OUT/moveit_launch_completo.log
python3 $D/plot_trajetoria.py $OUT/moveit_planejamento.json /repo/evidencias/a11_moveit_trajetoria.png
exit $RC
