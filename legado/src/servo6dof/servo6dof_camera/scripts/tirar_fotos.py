#!/usr/bin/env python3
"""
Percorre uma lista de poses do braco servo6dof e salva uma foto de cada
camera em cada pose.

Para cada pose:
    1. manda a trajetoria para /arm_controller e /gripper_controller
    2. espera a execucao terminar
    3. espera o tempo de assentamento (o braco parar de balancar)
    4. captura o quadro mais recente de cada camera e salva em PNG
    5. registra os angulos das juntas num CSV (util para montar dataset)

Exemplo:
    ros2 run servo6dof_camera tirar_fotos.py
    ros2 run servo6dof_camera tirar_fotos.py --ros-args -p saida:=/tmp/minhas_fotos
"""

import csv
import json
import math
import os
import random
import threading
import time

import cv2
import numpy as np
import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from control_msgs.action import FollowJointTrajectory
from cv_bridge import CvBridge
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Image, JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

JUNTAS_BRACO = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]
JUNTAS_GARRA = ["joint_6"]

# Limites do URDF. A amostragem aleatoria fica com uma folga de 5% nas
# pontas para nao encostar no batente e disparar recusa do controlador.
LIMITES_BRACO = [(-math.pi / 2, math.pi / 2)] * 5
LIMITE_GARRA = (-40 * math.pi / 180, 30 * math.pi / 180)
FOLGA = 0.05

CSV_NOME = "poses_registradas.csv"

# As imagens vindas do Gazebo sao "sensor data": BEST_EFFORT + fila 1.
# Um publisher RELIABLE consegue atender um subscriber BEST_EFFORT, entao
# esse perfil funciona nos dois casos.
QOS_IMAGEM = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
    durability=QoSDurabilityPolicy.VOLATILE,
)


class Fotografo(Node):
    def __init__(self):
        super().__init__("fotografo_servo6dof")

        pkg = get_package_share_directory("servo6dof_camera")

        self.declare_parameter("poses_file", os.path.join(pkg, "config", "poses.yaml"))
        self.declare_parameter("saida", os.path.expanduser("~/fotos_servo6dof"))
        self.declare_parameter(
            "cameras", ["/camera_frontal/image", "/camera_diagonal/image"]
        )
        self.declare_parameter("duracao", 3.0)       # s (de sim) da trajetoria
        self.declare_parameter("assentamento", 1.5)  # s de espera depois de chegar
        self.declare_parameter("timeout_camera", 20.0)
        self.declare_parameter("tol_junta", 0.03)    # rad: erro para considerar "chegou"
        self.declare_parameter("timeout_mov", 60.0)  # s: teto de espera do movimento
        # n_aleatorias > 0 ignora o poses_file e sorteia N poses cobrindo o
        # espaco de juntas -- e' assim que se escala o dataset.
        self.declare_parameter("n_aleatorias", 0)
        self.declare_parameter("semente", 42)
        # Para geracao paralela: cada worker recebe uma semente diferente
        # (poses diferentes) e um indice_inicial diferente (nomes de arquivo
        # sem colisao), escrevendo todos na mesma pasta.
        self.declare_parameter("indice_inicial", 0)

        # ---- geracao RESUMAVEL a partir de um plano fixo ----
        # 'plano' e' o caminho de um plano_poses.json (lista de poses com id
        # fixo). Quando definido, o script PULA as poses ja feitas (JSON +
        # imagens no disco) e faz so o que falta -- e' o que permite parar e
        # continuar em etapas ate atingir a meta.
        self.declare_parameter("plano", "")
        # max_capturas > 0 limita quantas poses fazer NESTA sessao (0 = todas
        # as que faltam). Util para rodar em pedacos curtos.
        self.declare_parameter("max_capturas", 0)
        # Divisao entre workers paralelos SEM colisao: o worker 'worker_id'
        # (de 0 a n_workers-1) so faz as poses cujo id % n_workers == worker_id.
        self.declare_parameter("worker_id", 0)
        self.declare_parameter("n_workers", 1)

        self.poses_file = self.get_parameter("poses_file").value
        self.saida = self.get_parameter("saida").value
        self.topicos = list(self.get_parameter("cameras").value)
        self.duracao = float(self.get_parameter("duracao").value)
        self.assentamento = float(self.get_parameter("assentamento").value)
        self.timeout_camera = float(self.get_parameter("timeout_camera").value)
        self.tol_junta = float(self.get_parameter("tol_junta").value)
        self.timeout_mov = float(self.get_parameter("timeout_mov").value)
        self.n_aleatorias = int(self.get_parameter("n_aleatorias").value)
        self.semente = int(self.get_parameter("semente").value)
        self.indice_inicial = int(self.get_parameter("indice_inicial").value)
        self.plano = self.get_parameter("plano").value
        self.max_capturas = int(self.get_parameter("max_capturas").value)
        self.worker_id = int(self.get_parameter("worker_id").value)
        self.n_workers = max(1, int(self.get_parameter("n_workers").value))

        os.makedirs(self.saida, exist_ok=True)

        self.ponte = CvBridge()
        self._lock = threading.Lock()
        self._ultimo_quadro = {t: None for t in self.topicos}
        self._juntas = {}   # ultimo /joint_states (para registrar a pose real)
        self._sim_t = None  # ultimo tempo de simulacao, de /clock
        self._futuros = []  # mantem vivos os objetivos em execucao (senao o GC os abandona)

        for topico in self.topicos:
            self.create_subscription(
                Image, topico, self._faz_callback(topico), QOS_IMAGEM
            )
            self.get_logger().info("assinando camera: " + topico)

        self.create_subscription(
            JointState, "/joint_states", self._cb_juntas, 10)
        self.create_subscription(Clock, "/clock", self._cb_clock, 10)

        # Comando por ACTION (leva as juntas ao alvo exato -- o comando por
        # topico movia so parte das juntas). Mas NAO se espera o resultado
        # "Goal reached": ele leva ~13s porque o controlador so declara
        # sucesso apos o goal_time_tolerance, enquanto o braco na verdade
        # chega ao alvo em ~duracao segundos. Espera-se apenas o tempo da
        # trajetoria + assentamento (ver vai_para).
        self.cli_braco = ActionClient(
            self, FollowJointTrajectory, "/arm_controller/follow_joint_trajectory")
        self.cli_garra = ActionClient(
            self, FollowJointTrajectory, "/gripper_controller/follow_joint_trajectory")
        self.cli_braco.wait_for_server(timeout_sec=15.0)
        self.cli_garra.wait_for_server(timeout_sec=15.0)

    # ---------- cameras ----------

    def _cb_juntas(self, msg):
        with self._lock:
            self._juntas = dict(zip(msg.name, msg.position))

    def _cb_clock(self, msg):
        self._sim_t = msg.clock.sec + msg.clock.nanosec * 1e-9

    def _espera_sim(self, segundos_sim):
        """Espera 'segundos_sim' de tempo de SIMULACAO (via /clock).

        Robusto ao fator de tempo real e independe do joint_state_broadcaster
        (que as vezes nao ativa). A trajetoria de 'duracao' segundos de sim se
        completa neste intervalo, entao o braco chega ao alvo.
        """
        # garante ter uma leitura de /clock
        t0 = time.time()
        while self._sim_t is None and time.time() - t0 < 5.0:
            rclpy.spin_once(self, timeout_sec=0.05)
        if self._sim_t is None:
            time.sleep(segundos_sim)   # sem /clock: cai no tempo de relogio
            return
        alvo = self._sim_t + segundos_sim
        teto = time.time() + segundos_sim / 0.02 + 30   # teto de relogio generoso
        while self._sim_t < alvo and time.time() < teto:
            rclpy.spin_once(self, timeout_sec=0.02)

    def _erro_ate(self, alvo):
        """Maior erro absoluto entre as juntas do braco e o alvo (rad)."""
        with self._lock:
            juntas = dict(self._juntas)
        if not all(j in juntas for j in JUNTAS_BRACO):
            return None
        return max(abs(juntas[j] - alvo[k]) for k, j in enumerate(JUNTAS_BRACO))

    def _faz_callback(self, topico):
        def cb(msg):
            with self._lock:
                self._ultimo_quadro[topico] = msg

        return cb

    def _pega_quadro(self, topico):
        with self._lock:
            return self._ultimo_quadro[topico]

    def _gira(self, segundos):
        """Processa callbacks (cameras, joint_states, actions) por N segundos."""
        fim = time.time() + segundos
        while time.time() < fim:
            rclpy.spin_once(self, timeout_sec=0.02)

    def espera_cameras(self):
        """Bloqueia ate cada camera ter entregue pelo menos um quadro."""
        limite = time.time() + self.timeout_camera
        while time.time() < limite:
            rclpy.spin_once(self, timeout_sec=0.05)
            if all(self._pega_quadro(t) is not None for t in self.topicos):
                return True
        faltando = [t for t in self.topicos if self._pega_quadro(t) is None]
        self.get_logger().error(
            "nenhuma imagem recebida de: {}. O Gazebo esta rodando com o "
            "plugin Sensors e o image_bridge esta ativo?".format(faltando))
        return False

    def descarta_quadros(self):
        """Zera o buffer para garantir que a proxima foto e' posterior ao movimento."""
        with self._lock:
            for t in self.topicos:
                self._ultimo_quadro[t] = None

    def sorteia_poses(self, quantidade):
        """Sorteia poses cobrindo o espaco de juntas, com semente fixa.

        Semente fixa importa: o dataset fica reproduzivel -- rodar de novo
        com a mesma semente gera exatamente as mesmas poses.
        """
        rng = random.Random(self.semente)
        poses = []
        for i in range(1, quantidade + 1):
            braco = []
            for lo, hi in LIMITES_BRACO:
                margem = (hi - lo) * FOLGA
                braco.append(round(rng.uniform(lo + margem, hi - margem), 4))
            lo, hi = LIMITE_GARRA
            margem = (hi - lo) * FOLGA
            poses.append({
                "nome": "p{:06d}".format(i),
                "arm": braco,
                "gripper": round(rng.uniform(lo + margem, hi - margem), 4),
            })
        return poses

    def _arquivos_da_pose(self, indice):
        """Nomes esperados dos arquivos de saida de uma pose (json + imagens)."""
        nomes = [os.path.join(self.saida, "{:06d}.json".format(indice))]
        for topico in self.topicos:
            apelido = "_".join(topico.strip("/").split("/"))
            nomes.append(os.path.join(
                self.saida, "{:06d}_{}.png".format(indice, apelido)))
        return nomes

    def pose_feita(self, indice):
        """True se a pose ja foi capturada por completo (json + todas as imagens)."""
        return all(os.path.exists(f) and os.path.getsize(f) > 0
                   for f in self._arquivos_da_pose(indice))

    def _converte(self, msg):
        """Converte a mensagem para uma matriz gravavel em PNG.

        RGB vem como bgr8/rgb8 e vai direto. Profundidade vem como 32FC1 em
        METROS: converto para uint16 em MILIMETROS, que e' a convencao usual
        de dataset RGB-D (e cabe num PNG de 16 bits). Pixels sem retorno
        (inf/NaN, alem do plano de corte) viram 0.
        """
        enc = msg.encoding
        if enc == "32FC1":
            bruto = self.ponte.imgmsg_to_cv2(msg, desired_encoding="passthrough")
            mm = np.asarray(bruto, dtype="float32") * 1000.0
            mm[~np.isfinite(mm)] = 0.0
            return np.clip(mm, 0, 65535).astype("uint16"), "profundidade"
        if enc in ("16UC1", "mono16"):
            return self.ponte.imgmsg_to_cv2(msg, "passthrough"), "profundidade"
        if enc in ("mono8", "8UC1"):
            return self.ponte.imgmsg_to_cv2(msg, "passthrough"), "mascara"
        return self.ponte.imgmsg_to_cv2(msg, desired_encoding="bgr8"), "cor"

    def salva_fotos(self, pose, indice):
        """Salva um PNG por modalidade e um JSON com a anotacao da captura."""
        nome_pose = pose["nome"]
        salvos = {}
        for topico in self.topicos:
            msg = self._pega_quadro(topico)
            if msg is None:
                self.get_logger().warn(
                    "sem quadro novo de {} na pose {}".format(topico, nome_pose)
                )
                continue
            imagem, tipo = self._converte(msg)
            # /camera_frontal/depth -> camera_frontal_depth
            apelido = "_".join(topico.strip("/").split("/"))
            arquivo = "{:06d}_{}.png".format(indice, apelido)
            cv2.imwrite(os.path.join(self.saida, arquivo), imagem)
            salvos[apelido] = {
                "arquivo": arquivo,
                "tipo": tipo,
                "largura": int(imagem.shape[1]),
                "altura": int(imagem.shape[0]),
            }

        # posicao REAL das juntas no momento da foto (verdade-base para a
        # imagem), alem da comandada. So difere se o braco nao chegou 100%.
        with self._lock:
            reais = dict(self._juntas)
        juntas_reais = {j: round(float(reais[j]), 5)
                        for j in JUNTAS_BRACO if j in reais}

        anotacao = {
            "id": indice,
            "pose": nome_pose,
            "juntas_comandadas": {
                j: pose["arm"][k] for k, j in enumerate(JUNTAS_BRACO)},
            "juntas_reais": juntas_reais,
            "garra_comandada": {JUNTAS_GARRA[0]: pose.get("gripper", 0.0)},
            "juntas_graus": {
                j: round(math.degrees(pose["arm"][k]), 2)
                for k, j in enumerate(JUNTAS_BRACO)
            },
            "cameras": salvos,
        }
        caminho_json = os.path.join(self.saida, "{:06d}.json".format(indice))
        with open(caminho_json, "w") as f:
            json.dump(anotacao, f, indent=2, ensure_ascii=False)

        return salvos

    # ---------- movimento ----------

    def _envia_objetivo(self, cliente, juntas, valores):
        """Envia o objetivo e devolve (handle, future_do_resultado).

        O future do resultado precisa ser mantido vivo pelo chamador: se for
        coletado pelo GC, o controlador abandona a trajetoria no meio.
        """
        ponto = JointTrajectoryPoint()
        ponto.positions = [float(v) for v in valores]
        ponto.time_from_start.sec = int(self.duracao)
        ponto.time_from_start.nanosec = int((self.duracao % 1) * 1e9)

        traj = JointTrajectory()
        traj.joint_names = juntas
        traj.points = [ponto]

        meta = FollowJointTrajectory.Goal()
        meta.trajectory = traj
        fut = cliente.send_goal_async(meta)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=10.0)
        handle = fut.result()
        if handle is None or not handle.accepted:
            return None, None
        return handle, handle.get_result_async()

    def _csv_path(self):
        # Um CSV por worker, para varios processos gravarem na mesma pasta sem
        # se sobrescrever. No modo plano o worker e' identificado por
        # worker_id; no modo antigo, pelo indice_inicial.
        if self.plano and self.n_workers > 1:
            base = CSV_NOME.replace(".csv", "_w{}.csv".format(self.worker_id))
        elif self.indice_inicial:
            base = CSV_NOME.replace(".csv", "_{:07d}.csv".format(self.indice_inicial))
        else:
            base = CSV_NOME
        return os.path.join(self.saida, base)

    def _grava_csv(self, linhas):
        with open(self._csv_path(), "w", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
            escritor.writeheader()
            escritor.writerows(linhas)

    def vai_para(self, pose):
        """Comanda braco e garra ao mesmo tempo e espera a trajetoria + assentar.

        Publica nos topicos dos controladores (sem action): a trajetoria de
        `duracao` segundos e' executada direto. Espera duracao + assentamento
        para o braco chegar e parar de balancar antes da foto.
        """
        # Dispara braco e garra e SEGURA os futures (senao o GC os coleta e o
        # controlador abandona a trajetoria).
        self._futuros = []
        _, fut_arm = self._envia_objetivo(self.cli_braco, JUNTAS_BRACO, pose["arm"])
        self._futuros.append(fut_arm)
        if "gripper" in pose:
            _, fut_gar = self._envia_objetivo(
                self.cli_garra, JUNTAS_GARRA, [pose["gripper"]])
            self._futuros.append(fut_gar)

        # Espera a trajetoria completar por TEMPO DE SIMULACAO (nao pelo
        # resultado da action, que aborta cedo, nem pelos joint_states, que
        # dependem do broadcaster). A trajetoria dura 'duracao' segundos de
        # sim; ao fim o braco esta no alvo. Mais o assentamento.
        self._espera_sim(self.duracao + self.assentamento)

        # Se o broadcaster estiver ativo, confere o erro so para registrar.
        e = self._erro_ate(pose["arm"])
        if e is not None and e > 0.15:
            self.get_logger().warn(
                "erro residual {:.3f} rad na pose {}".format(e, pose["nome"]))
        return True

    # ---------- sessao ----------

    def _carrega_tarefas(self):
        """Devolve a lista (id, pose) a capturar NESTA sessao.

        Tres modos:
          - plano:        le plano_poses.json, filtra por worker, PULA as ja
                          feitas e limita a max_capturas. E' o modo resumavel.
          - n_aleatorias: sorteia N poses (modo antigo, sem retomada).
          - poses_file:   le um YAML fixo (poses nomeadas).
        """
        if self.plano:
            with open(self.plano) as f:
                dados = json.load(f)
            todas = dados["poses"]
            # cada pose do plano ja tem um 'id' fixo
            minhas = [p for p in todas
                      if int(p["id"]) % self.n_workers == self.worker_id]
            faltando = [p for p in minhas if not self.pose_feita(int(p["id"]))]
            feitas = len(minhas) - len(faltando)
            if self.max_capturas > 0:
                faltando = faltando[:self.max_capturas]
            self.get_logger().info(
                "plano: {} poses (worker {}/{}), {} ja feitas, {} nesta sessao".format(
                    len(minhas), self.worker_id, self.n_workers,
                    feitas, len(faltando)))
            return [(int(p["id"]), p) for p in faltando]

        if self.n_aleatorias > 0:
            poses = self.sorteia_poses(self.n_aleatorias)
            return [(self.indice_inicial + k, p)
                    for k, p in enumerate(poses, start=1)]

        with open(self.poses_file) as f:
            poses = yaml.safe_load(f)["poses"]
        return [(self.indice_inicial + k, p)
                for k, p in enumerate(poses, start=1)]

    def sessao(self):
        tarefas = self._carrega_tarefas()
        total = len(tarefas)

        if total == 0:
            self.get_logger().info("nada a fazer: todas as poses ja estao feitas.")
            return 0

        self.get_logger().info(
            "{} poses a capturar | {} cameras | saida: {}".format(
                total, len(self.topicos), self.saida))

        if not self.espera_cameras():
            return 1
        self.get_logger().info("todas as cameras estao publicando")

        linhas = []
        for k, (i, pose) in enumerate(tarefas, start=1):
            nome = pose.get("nome", "p{:06d}".format(i))
            self.get_logger().info(
                "[{}/{}] id {} -> {}".format(k, total, i, pose["arm"]))

            # vai_para ja inclui o tempo de trajetoria + assentamento
            self.vai_para(pose)

            self.descarta_quadros()
            if not self.espera_cameras():
                self.get_logger().warn("pulando foto do id " + str(i))
                continue

            salvos = self.salva_fotos(pose, i)
            registro = {"indice": i, "pose": nome}
            for j, junta in enumerate(JUNTAS_BRACO):
                registro[junta] = pose["arm"][j]
            registro["joint_6"] = pose.get("gripper", 0.0)
            registro["arquivos"] = ";".join(
                v["arquivo"] for v in salvos.values()
            )
            linhas.append(registro)

            # Grava o CSV a cada 10 capturas. Interromper no meio (Ctrl+C)
            # deixa o dataset integro ate aqui -- e a proxima sessao continua.
            if k % 10 == 0:
                self._grava_csv(linhas)
                self.get_logger().info(
                    "[{}/{}] {} imagens nesta sessao".format(
                        k, total, k * len(self.topicos)))

        if linhas:
            self._grava_csv(linhas)
            self.get_logger().info("metadados salvos em " + self._csv_path())

        self.get_logger().info(
            "FIM: {} poses fotografadas em {}".format(len(linhas), self.saida)
        )
        return 0


def main():
    rclpy.init()
    no = Fotografo()
    # Sem executor em thread separada: a sessao roda no mesmo thread e chama
    # rclpy.spin_once explicitamente. Assim a comunicacao das actions e das
    # cameras acontece de forma deterministica (o dispara-e-esquece em thread
    # de fundo nao estabelecia o objetivo, e o braco nao se movia).
    codigo = 1
    try:
        codigo = no.sessao()
    finally:
        no.destroy_node()
        rclpy.shutdown()
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
