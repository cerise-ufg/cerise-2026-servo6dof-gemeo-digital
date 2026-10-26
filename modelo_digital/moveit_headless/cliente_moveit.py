#!/usr/bin/env python3
"""Cliente headless do move_group: planeja E executa (hardware falso) uma
sequencia de objetivos em espaco de juntas e um objetivo de POSICAO cartesiana
do efetuador (base_garra), registrando:
  - codigo de erro, tempo de planejamento, n. de pontos e duracao de cada plano;
  - a trajetoria planejada (pontos com time_from_start);
  - os /joint_states efetivamente executados pelo ros2_control (mock).
Saida: resultados/moveit_planejamento.json
"""
import json
import math
import os
import sys
import time

import rclpy
from geometry_msgs.msg import Pose
from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import (BoundingVolume, Constraints, JointConstraint, MotionPlanRequest,
                             PlanningOptions, PositionConstraint, WorkspaceParameters)
from rclpy.action import ActionClient
from rclpy.node import Node
from sensor_msgs.msg import JointState
from shape_msgs.msg import SolidPrimitive

JUNTAS = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]
OBJETIVOS = [
    ("recolhido", "juntas", [0.0, -1.20, 1.20, 0.0, 0.0]),
    ("giro_esquerda", "juntas", [1.20, 0.55, -0.35, 0.40, 0.0]),
    ("estendido", "juntas", [0.0, 0.90, -0.60, 0.0, 0.30]),
    # alvo cartesiano (posicao de base_garra no mundo), alcancavel por construcao:
    # FK de q = [-0.6, 0.4, 0.5, -0.3, 0] calculada por modelo_digital/cinematica.py
    ("alvo_cartesiano", "posicao", None),
    ("home", "juntas", [0.0, 0.0, 0.0, 0.0, 0.0]),
]
CODIGOS = {1: "SUCCESS", -1: "PLANNING_FAILED", -2: "INVALID_MOTION_PLAN", -4: "CONTROL_FAILED",
           -6: "TIMED_OUT", -10: "START_STATE_IN_COLLISION", -12: "GOAL_IN_COLLISION",
           -31: "NO_IK_SOLUTION", 99999: "FAILURE"}


class Cliente(Node):
    def __init__(self, alvo_xyz):
        super().__init__("cliente_moveit_headless")
        self.cli = ActionClient(self, MoveGroup, "/move_action")
        self.js = []
        self.t0 = time.time()
        self.alvo_xyz = alvo_xyz
        self.create_subscription(JointState, "/joint_states", self.cb_js, 50)

    def cb_js(self, m):
        d = dict(zip(m.name, m.position))
        if all(j in d for j in JUNTAS):
            self.js.append([time.time() - self.t0] + [d[j] for j in JUNTAS])

    def requisicao(self, tipo, valores):
        req = MotionPlanRequest()
        req.group_name = "arm"
        req.pipeline_id = "ompl"
        req.planner_id = "RRTConnectkConfigDefault"
        req.num_planning_attempts = 5
        req.allowed_planning_time = 5.0
        req.max_velocity_scaling_factor = 0.5
        req.max_acceleration_scaling_factor = 0.5
        ws = WorkspaceParameters()
        ws.header.frame_id = "world"
        ws.min_corner.x = ws.min_corner.y = ws.min_corner.z = -5.0
        ws.max_corner.x = ws.max_corner.y = ws.max_corner.z = 5.0
        req.workspace_parameters = ws
        req.start_state.is_diff = True
        c = Constraints()
        if tipo == "juntas":
            for j, v in zip(JUNTAS, valores):
                jc = JointConstraint()
                jc.joint_name = j
                jc.position = float(v)
                jc.tolerance_above = 0.01
                jc.tolerance_below = 0.01
                jc.weight = 1.0
                c.joint_constraints.append(jc)
        else:
            pc = PositionConstraint()
            pc.header.frame_id = "world"
            pc.link_name = "base_garra"
            esfera = SolidPrimitive()
            esfera.type = SolidPrimitive.SPHERE
            esfera.dimensions = [0.02]
            bv = BoundingVolume()
            bv.primitives.append(esfera)
            p = Pose()
            p.position.x, p.position.y, p.position.z = self.alvo_xyz
            p.orientation.w = 1.0
            bv.primitive_poses.append(p)
            pc.constraint_region = bv
            pc.weight = 1.0
            c.position_constraints.append(pc)
        req.goal_constraints.append(c)
        return req

    def so_planeja(self, tipo, valores, n=10):
        """n pedidos plan_only a partir do estado atual -> estatisticas do planejador."""
        tempos, pontos, compr, ok = [], [], [], 0
        for _ in range(n):
            meta = MoveGroup.Goal()
            meta.request = self.requisicao(tipo, valores)
            meta.planning_options = PlanningOptions()
            meta.planning_options.plan_only = True
            fut = self.cli.send_goal_async(meta)
            rclpy.spin_until_future_complete(self, fut, timeout_sec=20)
            h = fut.result()
            if h is None or not h.accepted:
                continue
            rf = h.get_result_async()
            rclpy.spin_until_future_complete(self, rf, timeout_sec=30)
            r = rf.result().result
            if r.error_code.val == 1:
                ok += 1
                tempos.append(r.planning_time)
                q = [list(p.positions) for p in r.planned_trajectory.joint_trajectory.points]
                pontos.append(len(q))
                compr.append(sum(math.dist(a, b) for a, b in zip(q[:-1], q[1:])))
        return {"n_pedidos": n, "n_sucesso": ok, "tempo_planejamento_s": tempos,
                "n_pontos": pontos, "comprimento_caminho_juntas_rad": compr}

    def executa(self, nome, tipo, valores):
        estat = self.so_planeja(tipo, valores)
        meta = MoveGroup.Goal()
        meta.request = self.requisicao(tipo, valores)
        meta.planning_options = PlanningOptions()
        meta.planning_options.plan_only = False
        meta.planning_options.replan = False
        t_ini = time.time() - self.t0
        fut = self.cli.send_goal_async(meta)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=20)
        h = fut.result()
        if h is None or not h.accepted:
            print("%-16s objetivo recusado" % nome, flush=True)
            return {"nome": nome, "aceito": False}
        rf = h.get_result_async()
        rclpy.spin_until_future_complete(self, rf, timeout_sec=60)
        r = rf.result().result
        t_fim = time.time() - self.t0
        jt = r.planned_trajectory.joint_trajectory
        pts = [{"t": p.time_from_start.sec + p.time_from_start.nanosec * 1e-9,
                "q": list(p.positions)} for p in jt.points]
        cod = r.error_code.val
        out = {"nome": nome, "tipo": tipo, "alvo": valores if tipo == "juntas" else self.alvo_xyz,
               "codigo": cod, "status": CODIGOS.get(cod, str(cod)),
               "tempo_planejamento_s": r.planning_time, "n_pontos": len(pts),
               "duracao_trajetoria_s": pts[-1]["t"] if pts else None,
               "juntas": list(jt.joint_names), "trajetoria": pts,
               "t_inicio_s": t_ini, "t_fim_s": t_fim, "estatisticas_plan_only": estat}
        tp = estat["tempo_planejamento_s"]
        print("%-16s exec %-8s | %3d pontos | dur %.2f s | plan_only %d/%d ok, tempo medio %.1f ms (max %.1f)" % (
            nome, out["status"], len(pts), out["duracao_trajetoria_s"] or 0, estat["n_sucesso"],
            estat["n_pedidos"], 1000 * sum(tp) / max(len(tp), 1), 1000 * max(tp or [0])), flush=True)
        return out


def main():
    saida = sys.argv[1]
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from cinematica import ModeloURDF
    m = ModeloURDF()
    q_alvo = dict(zip(JUNTAS, [-0.6, 0.4, 0.5, -0.3, 0.0]))
    alvo = [float(x) for x in m.fk(q_alvo)["base_garra"][:3, 3]]
    rclpy.init()
    c = Cliente(alvo)
    if not c.cli.wait_for_server(timeout_sec=90):
        print("move_action indisponivel")
        sys.exit(2)
    t = time.time()
    while not c.js and time.time() - t < 30:
        rclpy.spin_once(c, timeout_sec=0.1)
    res = []
    for nome, tipo, val in OBJETIVOS:
        res.append(c.executa(nome, tipo, val))
        t = time.time()
        while time.time() - t < 1.0:
            rclpy.spin_once(c, timeout_sec=0.02)
    final = dict(zip(JUNTAS, c.js[-1][1:])) if c.js else {}
    for r in res:
        if r.get("nome") == "alvo_cartesiano" and r.get("trajetoria"):
            qf = dict(zip(r["juntas"], r["trajetoria"][-1]["q"]))
            pos = [float(x) for x in m.fk(qf)["base_garra"][:3, 3]]
            r["posicao_final_fk"] = pos
            r["erro_posicao_m"] = math.dist(pos, alvo)
            print("alvo cartesiano: erro de posicao final (FK) = %.4f m" % r["erro_posicao_m"], flush=True)
    ok = sum(1 for r in res if r.get("status") == "SUCCESS")
    print("objetivos com SUCCESS: %d/%d" % (ok, len(res)), flush=True)
    json.dump({"objetivos": res, "joint_states": c.js, "juntas": JUNTAS, "estado_final": final,
               "alvo_cartesiano_q_origem": q_alvo}, open(saida, "w"), indent=1)
    print("salvo:", saida)
    c.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
