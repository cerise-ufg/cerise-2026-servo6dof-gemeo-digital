#!/usr/bin/env python3
"""
Testa o MoveIt pela linha de comando: pede um plano ate uma pose em espaco
de juntas e manda executar.

Serve para conferir, sem depender da interface do RViz, que:
  - o move_group subiu e aceita objetivos
  - o SRDF define o grupo 'arm' corretamente
  - o moveit_controllers.yaml aponta para o controlador certo
    (e' aqui que os erros classicos aparecem: "Unable to identify any set of
     controllers" significa action_ns ou nome de controlador errado)

Pre-requisitos: a simulacao e o move_group ja rodando.

    ros2 run servo6dof_moveit testar_planejamento.py
    ros2 run servo6dof_moveit testar_planejamento.py --ros-args -p so_planejar:=true
"""

import math
import time

import rclpy
from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import (
    Constraints,
    JointConstraint,
    MotionPlanRequest,
    PlanningOptions,
)
from rclpy.action import ActionClient
from rclpy.node import Node

JUNTAS = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]

# (nome, [j1..j5]) — poses seguras, dentro dos limites de +-pi/2
ALVOS = [
    ("home", [0.0, 0.0, 0.0, 0.0, 0.0]),
    ("recolhido", [0.0, -1.20, 1.20, 0.0, 0.0]),
    ("giro_esquerda", [1.20, 0.55, -0.35, 0.40, 0.0]),
    ("home", [0.0, 0.0, 0.0, 0.0, 0.0]),
]

# valores reais de moveit_msgs/msg/MoveItErrorCodes
CODIGOS = {
    1: "SUCCESS",
    99999: "FAILURE (generico -- veja o log do move_group)",
    -1: "PLANNING_FAILED",
    -2: "INVALID_MOTION_PLAN",
    -3: "MOTION_PLAN_INVALIDATED_BY_ENVIRONMENT_CHANGE",
    -4: "CONTROL_FAILED",
    -5: "UNABLE_TO_AQUIRE_SENSOR_DATA",
    -6: "TIMED_OUT",
    -7: "PREEMPTED",
    -10: "START_STATE_IN_COLLISION",
    -11: "START_STATE_VIOLATES_PATH_CONSTRAINTS",
    -12: "GOAL_IN_COLLISION",
    -13: "GOAL_VIOLATES_PATH_CONSTRAINTS",
    -14: "GOAL_CONSTRAINTS_VIOLATED",
    -15: "INVALID_GROUP_NAME",
    -16: "INVALID_GOAL_CONSTRAINTS",
    -17: "INVALID_ROBOT_STATE",
    -18: "INVALID_LINK_NAME",
    -19: "INVALID_OBJECT_NAME",
    -21: "FRAME_TRANSFORM_FAILURE",
    -22: "COLLISION_CHECKING_UNAVAILABLE",
    -23: "ROBOT_STATE_STALE",
    -31: "NO_IK_SOLUTION",
}


class Testador(Node):
    def __init__(self):
        super().__init__("testar_planejamento")
        self.declare_parameter("so_planejar", False)
        self.declare_parameter("grupo", "arm")
        self.so_planejar = bool(self.get_parameter("so_planejar").value)
        self.grupo = self.get_parameter("grupo").value
        self.cli = ActionClient(self, MoveGroup, "/move_action")

    def monta_objetivo(self, valores):
        pedido = MotionPlanRequest()
        pedido.group_name = self.grupo
        pedido.num_planning_attempts = 10
        pedido.allowed_planning_time = 10.0
        pedido.max_velocity_scaling_factor = 0.3
        pedido.max_acceleration_scaling_factor = 0.3

        restricoes = Constraints()
        for nome, valor in zip(JUNTAS, valores):
            jc = JointConstraint()
            jc.joint_name = nome
            jc.position = float(valor)
            jc.tolerance_above = 0.01
            jc.tolerance_below = 0.01
            jc.weight = 1.0
            restricoes.joint_constraints.append(jc)
        pedido.goal_constraints.append(restricoes)

        objetivo = MoveGroup.Goal()
        objetivo.request = pedido
        objetivo.planning_options = PlanningOptions()
        objetivo.planning_options.plan_only = self.so_planejar
        objetivo.planning_options.planning_scene_diff.is_diff = True
        objetivo.planning_options.planning_scene_diff.robot_state.is_diff = True
        return objetivo

    def roda(self):
        modo = "PLANEJAR" if self.so_planejar else "PLANEJAR + EXECUTAR"
        self.get_logger().info("modo: " + modo + " | grupo: " + self.grupo)

        if not self.cli.wait_for_server(timeout_sec=30.0):
            self.get_logger().error(
                "/move_action nao apareceu. O move_group esta rodando? "
                "(ros2 launch servo6dof_moveit moveit.launch.py)"
            )
            return 1

        falhas = 0
        for nome, valores in ALVOS:
            graus = [round(math.degrees(v)) for v in valores]
            self.get_logger().info("-> " + nome + "  " + str(graus) + " graus")

            fut = self.cli.send_goal_async(self.monta_objetivo(valores))
            rclpy.spin_until_future_complete(self, fut, timeout_sec=30.0)
            handle = fut.result()
            if handle is None or not handle.accepted:
                self.get_logger().error("   objetivo recusado")
                falhas += 1
                continue

            fut_res = handle.get_result_async()
            rclpy.spin_until_future_complete(self, fut_res, timeout_sec=90.0)
            res = fut_res.result()
            if res is None:
                self.get_logger().error("   sem resultado (timeout)")
                falhas += 1
                continue

            codigo = res.result.error_code.val
            texto = CODIGOS.get(codigo, "codigo " + str(codigo))
            if codigo == 1:
                self.get_logger().info("   OK: " + texto)
            else:
                self.get_logger().error("   FALHOU: " + texto)
                falhas += 1
            time.sleep(0.5)

        total = len(ALVOS)
        if falhas:
            self.get_logger().error(
                "RESULTADO: {}/{} objetivos falharam".format(falhas, total)
            )
        else:
            self.get_logger().info(
                "RESULTADO: {}/{} objetivos concluidos".format(total, total)
            )
        return 1 if falhas else 0


def main():
    rclpy.init()
    no = Testador()
    try:
        codigo = no.roda()
    finally:
        no.destroy_node()
        rclpy.shutdown()
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
