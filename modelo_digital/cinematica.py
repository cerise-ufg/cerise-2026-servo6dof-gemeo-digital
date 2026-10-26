#!/usr/bin/env python3
"""
Modelo cinematico do braco servo6dof lido diretamente do URDF (numpy puro).

- Le links, juntas (tipo, eixo, limites, origem, mimic) e inerciais do URDF.
- Cinematica direta (FK) de qualquer link no referencial da raiz ("world"),
  inclusive das juntas mimic da garra (valor = multiplicador * mestre + offset).
- FK vetorizada em lote (N configuracoes de uma vez) para a analise do espaco
  de trabalho.
- Leitor de STL binario e transformacao das malhas visuais (para renders).
- Modelo de camera pinhole das cameras do estudio do Gazebo (estudio_hd.sdf),
  usado para projetar a cadeia cinematica sobre as imagens do dataset.

Nao depende de ROS: roda em qualquer Python 3 com numpy.
"""
import math
import os
import struct
import xml.etree.ElementTree as ET

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
URDF_PADRAO = os.path.join(AQUI, "urdf", "servo6dof.urdf")

JUNTAS_BRACO = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]
JUNTA_GARRA = "joint_6"


# ----------------------------------------------------------------- algebra
def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rpy_para_R(r, p, y):
    """Convencao URDF: R = Rz(yaw) * Ry(pitch) * Rx(roll) (eixos fixos)."""
    return rot_z(y) @ rot_y(p) @ rot_x(r)


def T_de(xyz, rpy):
    T = np.eye(4)
    T[:3, :3] = rpy_para_R(*rpy)
    T[:3, 3] = xyz
    return T


def rodrigues(eixo, ang):
    """Matriz de rotacao 3x3 de 'ang' rad em torno do eixo unitario."""
    k = np.asarray(eixo, float)
    k = k / np.linalg.norm(k)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * (K @ K)


def rodrigues_lote(eixo, angs):
    """N matrizes 3x3 (N,3,3) para um eixo fixo e um vetor de angulos."""
    k = np.asarray(eixo, float)
    k = k / np.linalg.norm(k)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    s = np.sin(angs)[:, None, None]
    c = np.cos(angs)[:, None, None]
    return np.eye(3)[None] + s * K[None] + (1 - c) * (K @ K)[None]


def _vec(txt, n=3, padrao=0.0):
    if txt is None:
        return [padrao] * n
    return [float(v) for v in txt.split()]


# ----------------------------------------------------------------- modelo
class Junta:
    def __init__(self, el):
        self.nome = el.get("name")
        self.tipo = el.get("type")
        self.pai = el.find("parent").get("link")
        self.filho = el.find("child").get("link")
        o = el.find("origin")
        self.xyz = _vec(o.get("xyz") if o is not None else None)
        self.rpy = _vec(o.get("rpy") if o is not None else None)
        a = el.find("axis")
        self.eixo = _vec(a.get("xyz") if a is not None else None, padrao=0.0)
        if a is None:
            self.eixo = [1.0, 0.0, 0.0]
        lim = el.find("limit")
        self.inf = float(lim.get("lower")) if lim is not None and lim.get("lower") else None
        self.sup = float(lim.get("upper")) if lim is not None and lim.get("upper") else None
        self.esforco = float(lim.get("effort")) if lim is not None and lim.get("effort") else None
        self.velocidade = float(lim.get("velocity")) if lim is not None and lim.get("velocity") else None
        m = el.find("mimic")
        self.mimic = None
        if m is not None:
            self.mimic = (m.get("joint"), float(m.get("multiplier", 1.0)), float(m.get("offset", 0.0)))
        self.T0 = T_de(self.xyz, self.rpy)


class Link:
    def __init__(self, el):
        self.nome = el.get("name")
        self.massa = None
        self.inercia = None
        ine = el.find("inertial")
        if ine is not None:
            m = ine.find("mass")
            self.massa = float(m.get("value")) if m is not None else None
            i = ine.find("inertia")
            if i is not None:
                self.inercia = {k: float(i.get(k)) for k in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz")}
        self.visuais = []
        for v in el.findall("visual"):
            o = v.find("origin")
            g = v.find("geometry/mesh")
            if g is None:
                continue
            cor = v.find("material/color")
            self.visuais.append({
                "arquivo": g.get("filename"),
                "escala": _vec(g.get("scale"), padrao=1.0) if g.get("scale") else [1.0, 1.0, 1.0],
                "T": T_de(_vec(o.get("xyz") if o is not None else None),
                          _vec(o.get("rpy") if o is not None else None)),
                "rgba": _vec(cor.get("rgba"), 4) if cor is not None else [0.7, 0.7, 0.7, 1.0],
            })


class ModeloURDF:
    def __init__(self, caminho=URDF_PADRAO):
        self.caminho = caminho
        raiz = ET.parse(caminho).getroot()
        self.nome = raiz.get("name")
        self.links = {l.get("name"): Link(l) for l in raiz.findall("link")}
        self.juntas = {j.get("name"): Junta(j) for j in raiz.findall("joint")}
        self.junta_do_filho = {j.filho: j for j in self.juntas.values()}
        filhos = {j.filho for j in self.juntas.values()}
        raizes = [n for n in self.links if n not in filhos]
        assert len(raizes) == 1, raizes
        self.raiz = raizes[0]
        # juntas "ativas" = moveis e nao-mimic (o que se comanda)
        self.ativas = [j.nome for j in self.juntas.values()
                       if j.tipo in ("revolute", "prismatic", "continuous") and j.mimic is None]

    # caminho de juntas da raiz ate um link
    def cadeia(self, link):
        cad = []
        while link != self.raiz:
            j = self.junta_do_filho[link]
            cad.append(j)
            link = j.pai
        return cad[::-1]

    def resolver(self, q):
        """Completa o dicionario de juntas com as mimic e zero nas faltantes."""
        val = {}
        for j in self.juntas.values():
            if j.tipo == "fixed":
                continue
            if j.mimic is None:
                val[j.nome] = float(q.get(j.nome, 0.0))
        for j in self.juntas.values():
            if j.mimic is not None:
                mestre, mult, off = j.mimic
                val[j.nome] = mult * val.get(mestre, float(q.get(mestre, 0.0))) + off
        return val

    def T_junta(self, j, valor):
        T = j.T0.copy()
        if j.tipo in ("revolute", "continuous"):
            R = np.eye(4)
            R[:3, :3] = rodrigues(j.eixo, valor)
            T = T @ R
        elif j.tipo == "prismatic":
            P = np.eye(4)
            P[:3, 3] = np.asarray(j.eixo) / np.linalg.norm(j.eixo) * valor
            T = T @ P
        return T

    def fk(self, q):
        """Pose 4x4 de TODOS os links no referencial da raiz."""
        val = self.resolver(q)
        poses = {self.raiz: np.eye(4)}
        pendentes = list(self.juntas.values())
        while pendentes:
            resto = []
            for j in pendentes:
                if j.pai in poses:
                    poses[j.filho] = poses[j.pai] @ self.T_junta(j, val.get(j.nome, 0.0))
                else:
                    resto.append(j)
            pendentes = resto
        return poses

    def fk_lote(self, Q, link, ponto_local=None, nomes=None):
        """FK vetorizada: Q (N, n) com valores das juntas 'nomes' (padrao: ativas).
        Devolve (N,3) posicoes do 'ponto_local' (padrao: origem) do 'link'.
        Juntas mimic na cadeia sao resolvidas a partir das mestras."""
        nomes = nomes or self.ativas
        Q = np.asarray(Q, float)
        N = Q.shape[0]
        idx = {n: k for k, n in enumerate(nomes)}
        T = np.repeat(np.eye(4)[None], N, axis=0)
        for j in self.cadeia(link):
            T = T @ j.T0[None]
            if j.tipo in ("revolute", "continuous"):
                if j.mimic is None:
                    a = Q[:, idx[j.nome]] if j.nome in idx else np.zeros(N)
                else:
                    mestre, mult, off = j.mimic
                    a = mult * (Q[:, idx[mestre]] if mestre in idx else np.zeros(N)) + off
                R = np.repeat(np.eye(4)[None], N, axis=0)
                R[:, :3, :3] = rodrigues_lote(j.eixo, a)
                T = T @ R
        p = np.array([0, 0, 0, 1.0]) if ponto_local is None else np.r_[ponto_local, 1.0]
        return (T @ p)[:, :3]


# ----------------------------------------------------------------- malhas
def ler_stl(caminho):
    """Le STL binario -> (n,3,3) vertices dos triangulos."""
    with open(caminho, "rb") as f:
        f.read(80)
        n = struct.unpack("<I", f.read(4))[0]
        dados = np.frombuffer(f.read(50 * n), dtype=np.uint8).reshape(n, 50)
    tri = dados[:, 12:48].copy().view("<f4").reshape(n, 3, 3)
    return tri.astype(np.float64)


def resolver_package(uri, pasta_share):
    """package://servo6dof_description/meshes/x.stl -> <pasta_share>/servo6dof_description/meshes/x.stl"""
    if uri.startswith("package://"):
        return os.path.join(pasta_share, uri[len("package://"):])
    if uri.startswith("file://"):
        return uri[len("file://"):]
    return uri


def malhas_no_mundo(modelo, q, pasta_share, cache=None):
    """Lista de (triangulos (n,3,3) no mundo, rgba, nome_link) para a config q."""
    cache = {} if cache is None else cache
    poses = modelo.fk(q)
    saida = []
    for nome, link in modelo.links.items():
        for v in link.visuais:
            arq = resolver_package(v["arquivo"], pasta_share)
            if arq not in cache:
                cache[arq] = ler_stl(arq)
            tri = cache[arq] * np.asarray(v["escala"])[None, None, :]
            T = poses[nome] @ v["T"]
            pts = tri.reshape(-1, 3) @ T[:3, :3].T + T[:3, 3]
            saida.append((pts.reshape(-1, 3, 3), v["rgba"], nome))
    return saida


# ----------------------------------------------------------------- cameras
# Poses das cameras no mundo do estudio (estudio_hd.sdf). Camera do Gazebo:
# eixo x = direcao de visada, y = esquerda, z = cima.
CAMERAS = {
    "camera_frontal": {"xyz": [3.2, 0.4, 1.6], "rpy": [0.0, 0.215, 3.14159],
                        "hfov": 1.0472, "largura": 1280, "altura": 720},
    "camera_diagonal": {"xyz": [2.6, 2.6, 2.4], "rpy": [0.0, 0.414, -2.439],
                         "hfov": 1.0472, "largura": 1280, "altura": 720},
}


def intrinsecos(cam):
    fx = (cam["largura"] / 2.0) / math.tan(cam["hfov"] / 2.0)
    return fx, fx, cam["largura"] / 2.0, cam["altura"] / 2.0


def projetar(pts_mundo, nome_camera):
    """Projeta pontos (N,3) do mundo em pixels (N,2) da camera do estudio.
    Devolve tambem a profundidade ao longo do eixo optico (x da camera)."""
    cam = CAMERAS[nome_camera]
    Twc = T_de(cam["xyz"], cam["rpy"])
    Tcw = np.linalg.inv(Twc)
    P = np.c_[np.asarray(pts_mundo, float), np.ones(len(pts_mundo))] @ Tcw.T
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    fx, fy, cx, cy = intrinsecos(cam)
    u = cx - fx * y / x
    v = cy - fy * z / x
    return np.c_[u, v], x


if __name__ == "__main__":
    m = ModeloURDF()
    print("robo:", m.nome, "| raiz:", m.raiz, "| juntas ativas:", m.ativas)
    poses = m.fk({})
    for n in ["base_link", "primeiro_elo", "segundo_elo", "terceiro_elo", "quarto_elo", "base_garra"]:
        print("%-14s" % n, np.round(poses[n][:3, 3], 4))
