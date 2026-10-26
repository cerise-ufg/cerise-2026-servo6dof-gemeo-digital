// Front-end do Gemeo Digital do servo6dof (three.js + urdf-loader).
// Dois bracos carregados do MESMO URDF: "referencia" (juntas da verdade-base)
// e "gemeo digital" (juntas previstas pelo Predictor do servidor).
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js';
import URDFLoader from 'urdf-loader';

const ESTADO = window.__gemeo = {
  pronto: false, robos: 0, malhas: { ref: 0, gemeo: 0 }, erros: [], quadros: 0, ultimo: null, ws: 'fechado',
};
const JUNTAS = ['joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5', 'joint_6'];
const SEPARACAO = 3.0;            // m, distancia (eixo y do ROS) no modo lado a lado
const graus = r => r * 180 / Math.PI;
const $ = id => document.getElementById(id);

// ---------------------------------------------------------------- cena
const vp = $('viewport');
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true;
vp.appendChild(renderer.domElement);
const rotulos = new CSS2DRenderer();
rotulos.domElement.style.position = 'absolute';
rotulos.domElement.style.inset = '0';
rotulos.domElement.style.pointerEvents = 'none';
vp.appendChild(rotulos.domElement);

const cena = new THREE.Scene();
cena.background = new THREE.Color(0x2c3037);
const camera = new THREE.PerspectiveCamera(40, 1, 0.05, 200);
camera.position.set(7.5, 4.2, 5.5);
const orbita = new OrbitControls(camera, renderer.domElement);
orbita.target.set(0, 1.0, -SEPARACAO / 2);
orbita.enableDamping = true;

cena.add(new THREE.HemisphereLight(0xf2f4f8, 0x30333a, 1.1));
const sol = new THREE.DirectionalLight(0xffffff, 1.6);
sol.position.set(6, 10, 4);
sol.castShadow = true;
sol.shadow.mapSize.set(2048, 2048);
Object.assign(sol.shadow.camera, { left: -6, right: 6, top: 6, bottom: -6 });
cena.add(sol);
const preench = new THREE.DirectionalLight(0xcfd8ff, 0.5);
preench.position.set(-5, 4, -6);
cena.add(preench);
const chao = new THREE.Mesh(new THREE.PlaneGeometry(40, 40),
  new THREE.MeshStandardMaterial({ color: 0x3a3e46, roughness: 0.95 }));
chao.rotation.x = -Math.PI / 2;
chao.receiveShadow = true;
cena.add(chao);
const grade = new THREE.GridHelper(20, 40, 0x59606b, 0x464b54);
grade.position.y = 0.002;
cena.add(grade);

// ROS (z para cima) -> three.js (y para cima)
const ros2three = (x, y, z) => new THREE.Vector3(x, z, -y);

function grupoRobo(nome) {
  const g = new THREE.Group();
  g.name = nome;
  cena.add(g);
  return g;
}
const gRef = grupoRobo('referencia');
const gGem = grupoRobo('gemeo');

function rotulo(texto, classe) {
  const d = document.createElement('div');
  d.className = 'rotulo3d ' + classe;
  d.textContent = texto;
  return new CSS2DObject(d);
}
const rotRef = rotulo('Braço — referência', 'ref');
const rotGem = rotulo('Gêmeo digital', 'gemeo');
rotRef.position.set(0, 2.85, 0);
rotGem.position.set(0, 2.85, 0);
gRef.add(rotRef);
gGem.add(rotGem);

const matRef = new THREE.MeshStandardMaterial({ color: 0xc9ccd3, metalness: 0.35, roughness: 0.42 });
const matGem = new THREE.MeshStandardMaterial({
  color: 0x1baf7a, metalness: 0.05, roughness: 0.55, transparent: true, opacity: 0.38, depthWrite: false,
});

let INFO = null;
let roboRef = null;
let roboGem = null;

function carregarRobo(tipo, grupo, material) {
  return new Promise((ok, falha) => {
    const manager = new THREE.LoadingManager();
    const loader = new URDFLoader(manager);
    loader.packages = INFO.pacotes;
    let robo = null;
    // aplica o material e conta as malhas no momento em que cada STL chega
    // (o FileLoader do three.js deduplica pedidos simultaneos da mesma URL, entao
    // nao se pode confiar so no onLoad do LoadingManager de cada robo)
    loader.loadMeshCb = (caminho, mgr, matUrdf, pronto, tentativa = 0) => {
      loader.defaultMeshLoader(caminho, mgr, material, (obj, err) => {
        if (err && tentativa < 2) {   // nova tentativa (servidor ocupado)
          setTimeout(() => loader.loadMeshCb(caminho, mgr, matUrdf, pronto, tentativa + 1), 600);
          return;
        }
        if (obj) {
          obj.traverse(o => {
            if (o.isMesh) {
              o.material = material;
              o.castShadow = tipo === 'ref';
              o.receiveShadow = tipo === 'ref';
              o.renderOrder = tipo === 'ref' ? 0 : 1;
              ESTADO.malhas[tipo]++;
            }
          });
        }
        if (err) ESTADO.erros.push('malha ' + caminho + ': ' + err);
        pronto(obj, err);
      });
    };
    manager.onError = url => ESTADO.erros.push('falha ao carregar ' + url);
    manager.onLoad = () => {
      if (!robo) return;
      ESTADO.robos++;
      ok(robo);
    };
    loader.load(INFO.urdf, r => {
      robo = r;
      r.rotation.x = -Math.PI / 2;     // URDF z-up -> cena y-up
      grupo.add(r);
    }, undefined, e => { ESTADO.erros.push(String(e)); falha(e); });
  });
}

function posRos(robo, grupo) {
  // posicao de base_garra no referencial do robo, em coordenadas ROS (z para cima)
  if (!robo || !robo.links || !robo.links.base_garra) return null;
  robo.updateMatrixWorld(true);
  const p = new THREE.Vector3();
  robo.links.base_garra.getWorldPosition(p);
  p.sub(grupo.position);
  return [p.x, -p.z, p.y];
}

function aplicarJuntas(robo, juntas) {
  if (!robo || !juntas) return;
  for (const j of JUNTAS) if (j in juntas) robo.setJointValue(j, juntas[j]);
}

// ---------------------------------------------------------------- disposicao / vista
function aplicarModo() {
  const modo = $('sel-modo').value;
  if (modo === 'lado') {
    gGem.position.copy(ros2three(0, SEPARACAO, 0));
    rotRef.element.textContent = 'Braço — referência';
    rotGem.visible = true;
    rotGem.element.style.display = '';
  } else {
    gGem.position.set(0, 0, 0);
    rotRef.element.textContent = 'Referência (sólido) + gêmeo (fantasma)';
    rotGem.element.style.display = 'none';
  }
  aplicarVista();
}

function aplicarVista() {
  const vista = $('sel-vista').value;
  const modo = $('sel-modo').value;
  if (vista === 'camera' && INFO) {
    // camera do Gazebo: x = visada, y = esquerda, z = cima (rpy fixos, Rz*Ry*Rx)
    const c = INFO.cameras[$('sel-camera').value];
    const [r, p, y] = c.rpy;
    const R = new THREE.Matrix4().makeRotationZ(y).multiply(new THREE.Matrix4().makeRotationY(p))
      .multiply(new THREE.Matrix4().makeRotationX(r));
    const d = new THREE.Vector3(1, 0, 0).applyMatrix4(R);
    const u = new THREE.Vector3(0, 0, 1).applyMatrix4(R);
    camera.position.copy(ros2three(...c.xyz));
    camera.up.copy(ros2three(u.x, u.y, u.z));
    const alvo = ros2three(c.xyz[0] + d.x * 3, c.xyz[1] + d.y * 3, c.xyz[2] + d.z * 3);
    orbita.target.copy(alvo);
    // mesmo campo de visao HORIZONTAL da camera do dataset quando o canvas e' mais
    // estreito que 16:9 (mostra todo o enquadramento da imagem)
    const asp = Math.min(camera.aspect, c.largura / c.altura);
    camera.fov = 2 * Math.atan(Math.tan(c.hfov / 2) / asp) * 180 / Math.PI;
    camera.updateProjectionMatrix();
  } else {
    // camera distante e teleobjetiva: pouca diferenca de perspectiva entre os dois bracos
    camera.up.set(0, 1, 0);
    camera.fov = 26;
    camera.updateProjectionMatrix();
    if (modo === 'lado') {
      camera.position.set(12.5, 5.0, -SEPARACAO / 2 + 1.2);
      orbita.target.set(0, 1.0, -SEPARACAO / 2);
    } else {
      camera.position.set(8.6, 4.4, 3.6);
      orbita.target.set(0, 1.0, -0.2);
    }
  }
  orbita.update();
}

function redimensionar() {
  const w = vp.clientWidth, h = vp.clientHeight;
  renderer.setSize(w, h);
  rotulos.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  if (INFO) aplicarVista();
}
window.addEventListener('resize', redimensionar);

function animar() {
  requestAnimationFrame(animar);
  orbita.update();
  renderer.render(cena, camera);
  rotulos.render(cena, camera);
}

// ---------------------------------------------------------------- painel
function montarTabela() {
  $('tab-juntas').innerHTML = JUNTAS.map(j => `
    <tr><td class="nome">${j}${j === 'joint_6' ? ' (garra)' : ''}</td>
    <td id="gt-${j}">—</td><td id="pr-${j}">—</td><td id="er-${j}">—</td>
    <td><div class="barra-erro"><i id="bar-${j}" style="width:0%"></i></div></td></tr>`).join('');
}

const fmt = (v, nd = 1) => (v === null || v === undefined || Number.isNaN(v)) ? '—' : v.toFixed(nd);

function atualizarPainel(q) {
  $('img-camera').src = q.imagem;
  $('img-legenda').textContent = `pose ${String(q.id).padStart(6, '0')} · ${q.camera.replace('_', ' ')}`;
  $('chip-quadro').textContent = `quadro ${q.idx + 1}/${q.total} · id ${q.id}`;
  $('chip-predictor').textContent = 'predictor: ' + q.predictor;
  for (const j of JUNTAS) {
    $('gt-' + j).textContent = fmt(graus(q.gt[j]));
    $('pr-' + j).textContent = fmt(graus(q.pred[j]));
    const e = q.erro_graus[j];
    $('er-' + j).textContent = (e >= 0 ? '+' : '') + fmt(e);
    $('bar-' + j).style.width = Math.min(100, Math.abs(e) / 10 * 100) + '%';
  }
  $('v-mae').textContent = fmt(q.mae_graus, 2) + '°';
  $('v-max').textContent = fmt(q.max_graus, 2) + '°';
  $('v-ee').textContent = fmt(100 * q.erro_efetuador_m, 1) + ' cm';
  $('v-lat').textContent = fmt(q.latencia_predictor_ms, 1) + ' ms';
}

// ---------------------------------------------------------------- grafico de erro
const HIST = [];
const canv = $('graf-erro');
const ctx = canv.getContext('2d');
let hoverX = null;

function desenharGrafico() {
  const dpr = window.devicePixelRatio || 1;
  const W = canv.clientWidth, H = canv.clientHeight;
  canv.width = W * dpr; canv.height = H * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  const css = getComputedStyle(document.documentElement);
  const cTexto = css.getPropertyValue('--texto3').trim();
  const cGrade = css.getPropertyValue('--borda').trim();
  const s1 = css.getPropertyValue('--serie1').trim();
  const s2 = css.getPropertyValue('--serie2').trim();
  const m = { e: 34, d: 10, t: 8, b: 20 };
  const dados = HIST.slice(-60);
  const ymax = Math.max(1, ...dados.map(d => d.max)) * 1.15;
  const x = i => m.e + (W - m.e - m.d) * (dados.length <= 1 ? 0 : i / 59);
  const y = v => H - m.b - (H - m.t - m.b) * (v / ymax);
  ctx.font = '11px Segoe UI, Arial';
  ctx.fillStyle = cTexto;
  ctx.strokeStyle = cGrade;
  ctx.lineWidth = 1;
  const passo = ymax > 8 ? Math.ceil(ymax / 4) : (ymax > 2 ? 1 : 0.5);
  for (let v = 0; v <= ymax; v += passo) {
    ctx.beginPath(); ctx.moveTo(m.e, y(v)); ctx.lineTo(W - m.d, y(v)); ctx.stroke();
    ctx.fillText(v.toFixed(passo < 1 ? 1 : 0) + '°', 2, y(v) + 4);
  }
  if (dados.length) {
    ctx.fillText('#' + dados[0].n, m.e, H - 4);
    const t = '#' + dados[dados.length - 1].n + ' (quadros recebidos)';
    ctx.fillText(t, W - m.d - ctx.measureText(t).width, H - 4);
  }
  for (const [chave, cor] of [['max', s2], ['mae', s1]]) {
    ctx.strokeStyle = cor; ctx.lineWidth = 2; ctx.beginPath();
    dados.forEach((d, i) => (i ? ctx.lineTo(x(i), y(d[chave])) : ctx.moveTo(x(i), y(d[chave]))));
    ctx.stroke();
  }
  if (hoverX !== null && dados.length) {
    const i = Math.max(0, Math.min(dados.length - 1, Math.round((hoverX - m.e) / ((W - m.e - m.d) / 59))));
    const d = dados[i];
    ctx.strokeStyle = cTexto; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x(i), m.t); ctx.lineTo(x(i), H - m.b); ctx.stroke();
    for (const [chave, cor] of [['max', s2], ['mae', s1]]) {
      ctx.fillStyle = cor; ctx.beginPath(); ctx.arc(x(i), y(d[chave]), 4, 0, 7); ctx.fill();
    }
    const dica = $('dica');
    dica.style.display = 'block';
    dica.innerHTML = `#${d.n} · pose ${d.id}<br>médio ${d.mae.toFixed(2)}° · máx ${d.max.toFixed(2)}°`;
    dica.style.left = Math.min(W - 150, x(i) + 8) + 'px';
    dica.style.top = '4px';
  } else {
    $('dica').style.display = 'none';
  }
}
canv.addEventListener('mousemove', ev => { hoverX = ev.offsetX; desenharGrafico(); });
canv.addEventListener('mouseleave', () => { hoverX = null; desenharGrafico(); });

// ---------------------------------------------------------------- websocket
let ws = null;
let rodando = true;
let idxAtual = 0;

function enviar(o) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(o)); }

function conectar() {
  const url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
  ws = new WebSocket(url);
  ws.onopen = () => {
    ESTADO.ws = 'aberto';
    $('chip-conexao').className = 'chip on';
    $('chip-conexao').lastElementChild.textContent = 'conectado';
    enviar({ cmd: 'fps', valor: Number($('sel-fps').value) });
    enviar({ cmd: 'camera', valor: $('sel-camera').value });
  };
  ws.onclose = () => {
    ESTADO.ws = 'fechado';
    $('chip-conexao').className = 'chip off';
    $('chip-conexao').lastElementChild.textContent = 'desconectado — tentando de novo';
    setTimeout(conectar, 2000);
  };
  ws.onmessage = ev => {
    const q = JSON.parse(ev.data);
    if (q.tipo !== 'quadro') { ESTADO.erros.push(q.mensagem || 'mensagem desconhecida'); return; }
    idxAtual = q.idx;
    ESTADO.quadros++;
    ESTADO.ultimo = { idx: q.idx, id: q.id, mae: q.mae_graus };
    aplicarJuntas(roboRef, q.gt);
    aplicarJuntas(roboGem, q.pred);
    // FK do proprio three.js (urdf-loader) para conferencia com a FK do servidor (Python)
    ESTADO.efetuador = { ref: posRos(roboRef, gRef), gemeo: posRos(roboGem, gGem),
                         servidor_gt: q.efetuador_gt_m, servidor_pred: q.efetuador_pred_m };
    atualizarPainel(q);
    if (!HIST.length || HIST[HIST.length - 1].idx1 !== q.idx + 1) {
      HIST.push({ idx1: q.idx + 1, n: ESTADO.quadros, id: q.id, mae: q.mae_graus || 0, max: q.max_graus || 0 });
      if (HIST.length > 600) HIST.shift();
    }
    desenharGrafico();
  };
}

$('bt-play').onclick = () => {
  rodando = !rodando;
  enviar({ cmd: rodando ? 'continuar' : 'pausar' });
  $('bt-play').textContent = rodando ? '❚❚ pausar' : '▶ continuar';
};
$('bt-prox').onclick = () => enviar({ cmd: 'ir', idx: idxAtual + 1 });
$('bt-ant').onclick = () => enviar({ cmd: 'ir', idx: idxAtual - 1 });
$('sel-fps').onchange = e => enviar({ cmd: 'fps', valor: Number(e.target.value) });
$('sel-camera').onchange = e => { enviar({ cmd: 'camera', valor: e.target.value }); aplicarVista(); };
$('sel-modo').onchange = aplicarModo;
$('sel-vista').onchange = aplicarVista;

// parametros de URL (usados nas capturas): ?modo=sobreposto&vista=camera&camera=camera_diagonal&fps=5
const P = new URLSearchParams(location.search);
for (const [k, id] of [['modo', 'sel-modo'], ['vista', 'sel-vista'], ['camera', 'sel-camera'], ['fps', 'sel-fps']]) {
  if (P.get(k)) $(id).value = P.get(k);
}

async function iniciar() {
  montarTabela();
  redimensionar();
  animar();
  INFO = await (await fetch('/api/info')).json();
  if (INFO.aviso_predictor) console.warn(INFO.aviso_predictor);
  $('chip-predictor').textContent = 'predictor: ' + INFO.predictor;
  // carga sequencial: o segundo robo reaproveita o cache HTTP das mesmas malhas
  roboRef = await carregarRobo('ref', gRef, matRef);
  roboGem = await carregarRobo('gemeo', gGem, matGem);
  aplicarModo();
  $('carregando').classList.add('oculto');
  ESTADO.pronto = true;
  conectar();
}
iniciar().catch(e => { ESTADO.erros.push(String(e)); $('carregando').textContent = 'erro: ' + e; });
