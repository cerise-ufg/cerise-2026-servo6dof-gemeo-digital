# CERISE 2026 · servo6dof: dataset, modelo digital e gêmeo digital

**Autor:** Eduardo Martins de Carvalho Caixeta (CERISE/EMC/UFG)
**Plano de Trabalho:** "Pesquisa, Desenvolvimento e Inovação em Gêmeos Digitais, Tecnologias Imersivas,
Robótica e Navegação Autônoma no escopo do CERISE/EMC/UFG" (2026). Coordenação: Prof. Dr. Alisson Assis
Cardoso (Navegação Autônoma / Gêmeos Digitais) e Prof. Dr. Carlos Galvão Pinheiro Junior (Realidade
Aumentada).

Este repositório reúne o trabalho do braço robótico **servo6dof** nas seguintes atividades do plano:

- **Objetivo 3, Atividade 7:** dataset estruturado e documentado do braço (imagens sintéticas RGB,
  profundidade e segmentação de duas câmeras, rotuladas com os ângulos das juntas), gerado no Gazebo;
- **Objetivo 4, Atividade 11:** modelo digital do braço em ambiente virtual (características físicas e
  cinemáticas, cinemática direta validada, espaço de trabalho, planejamento com MoveIt 2);
- **Objetivo 4, Atividade 12:** gêmeo digital (servidor FastAPI + WebSocket + front-end three.js, e nó
  ROS 2 com RViz) com `Predictor` plugável, **integrado ao modelo de estimação de pose** do repositório
  `cerise-2026-pose-servo6dof` (mesma organização): o braço "gêmeo" segue as juntas previstas **só a
  partir da imagem** e é avaliado contra a verdade-base no conjunto de teste.

O braço e o pacote ROS 2 original (`servo6dof_*`) são do Prof. Dr. Alisson Assis Cardoso. A execução de
2026 roda em ROS 2 Humble + Ignition Gazebo Fortress, em contêineres Docker no DGX Spark (NVIDIA GB10,
arm64). As seções de relatório estão em `RELATORIO_SECAO.md` (A7, A11 e infraestrutura da A12) e
`RELATORIO_SECAO_A12.md` (integração e avaliação do gêmeo com o modelo de pose); a ficha do dataset, em
`docs/DATASET.md`.

## Estrutura

```
ros2_ws/src/servo6dof/          pacotes ROS 2 (description, controller, moveit, camera) usados na geração
docker/                         Dockerfile.spark (gerador do dataset, imagem servo6dof:humble),
                                Dockerfile.gemeo (MoveIt 2, análise, FastAPI), Dockerfile.playwright
                                (capturas headless), Dockerfile.rviz (RViz 2 em Xvfb)
dataset_tools/                  geração: gerar_plano.py, plano_poses.json (5.000 poses), gerar_hd_spark.sh,
                                cams_hd.yaml, finalizar.sh, build_index.py, status_dataset.py
  analise/                      índice, integridade, estatísticas, grades, linha do tempo, reais x comandadas
  variante_laranja/             segunda renderização (braço laranja): xacro, finalização, LEIAME
  legado_wsl/                   scripts da geração anterior em WSL2
modelo_digital/                 URDF gerado, cinematica.py (FK numpy + câmera pinhole), tabelas, árvore,
                                validação FK x TF, espaço de trabalho, renders, IoU modelo x imagens,
                                moveit_headless/
gemeo_digital/
  servidor/                     FastAPI + WebSocket, predictors.py, static/ (three.js r160 + urdf-loader 0.13.1)
  ros2/                         nó imagem -> /twin/joint_states, launch, RViz headless, testes
  capturas/                     capturas Playwright e verificação das malhas
  integracao/                   avaliação do gêmeo com o modelo de pose (driver Playwright, análise, figuras)
    sessao_2026-10-26/          roteiro executado na avaliação de 26/10/2026 (LEIAME.md)
amostra_dataset/                8 poses do split de teste (48 PNG + JSON, ~4 MB)
docs/                           DATASET.md (datasheet), README e guia MoveIt originais, slides
evidencias/                     figuras, prints de terminal e animações (MP4/GIF) do relatório
resultados/                     métricas medidas (.json/.csv/.log)
  dataset_meta/                 index.csv (uma linha por pose) e integridade_por_imagem.csv (30.000 imagens)
  a12_integracao/               métricas, quadros, piores casos, logs JSONL das sessões, saídas de terminal
  geracao_laranja/              logs da segunda renderização
  logs_spark/                   builds das imagens Docker e logs auxiliares
scripts/                        rodar_container.sh, final_dataset.sh; spark_aux/ (scripts auxiliares)
legado/                         pasta original do projeto do braço (ago.-set./2026), ver legado/LEIAME.md
RELEASES.md                     datasets completos e saídas brutas (Releases), SHA-256 e instruções
```

## Como reproduzir (DGX Spark, arm64, Docker com nvidia-container-toolkit)

Os scripts assumem o repositório em `~/cerise2026/gemeo/repo`, a pasta do gerador em `~/braco` (com o
dataset em `~/braco/dataset`, montado sempre como somente leitura nas análises) e os metadados em
`~/cerise2026/gemeo/dataset_meta`; os caminhos podem ser trocados pelas variáveis dos scripts.

### Imagens Docker

```bash
cd ~/cerise2026/gemeo/repo
sudo docker build -f docker/Dockerfile.spark -t servo6dof:humble docker                     # gerador (ROS 2 + Fortress + EGL)
sudo docker build -f docker/Dockerfile.gemeo -t cerise26_gemeo:latest docker                # ferramentas, MoveIt 2, FastAPI
sudo docker build -f docker/Dockerfile.playwright -t cerise26_gemeo_playwright:latest docker
sudo docker build -f docker/Dockerfile.rviz -t cerise26_gemeo_rviz:latest docker            # (também feito pelo rodar_rviz_pose.sh)
```

### Geração do dataset (A7)

A pasta de trabalho do gerador (`~/braco`, montada em `/ws`) contém `src/` (= `ros2_ws/src`),
`plano_poses.json`, `cams_hd.yaml` e `gerar_hd_spark.sh` (de `dataset_tools/`).

```bash
python3 dataset_tools/gerar_plano.py --saida ~/braco/plano_poses.json   # 5.000 poses, semente 20260909
sudo docker run --rm -v ~/braco:/ws servo6dof:humble bash -lc \
  "source /opt/ros/humble/setup.bash && cd /ws && colcon build --packages-up-to servo6dof_camera"
sudo docker run -d --name braco_gen --gpus all -v ~/braco:/ws servo6dof:humble \
  bash -lc "bash /ws/gerar_hd_spark.sh 8 > /ws/gen_main.log 2>&1"       # 8 workers Gazebo, retomável
python3 dataset_tools/build_index.py ~/braco/dataset                    # index.csv da pasta
```

Para a variante laranja, o `servo6dof.urdf.xacro` de `dataset_tools/variante_laranja/` substitui o do
pacote de descrição antes do `colcon build`.

### Análise do dataset e modelo digital (A7, A11)

```bash
bash dataset_tools/analise/rodar_analise.sh 0          # índice, integridade (0 = decodifica todas), estatísticas
sudo docker run --rm -v $PWD:/repo cerise26_gemeo:latest bash /repo/modelo_digital/gerar_urdf.sh
bash scripts/rodar_container.sh tab  "python3 modelo_digital/tabela_modelo.py"
bash scripts/rodar_container.sh fk   "python3 modelo_digital/validar_fk_tf.py --n 300"
bash scripts/rodar_container.sh ws   "python3 modelo_digital/espaco_trabalho.py --n 100000"
bash scripts/rodar_container.sh rend "python3 modelo_digital/render_modelo.py --ids 1 2 7"
bash scripts/rodar_container.sh iou  "python3 modelo_digital/validar_projecao.py --n 1000"   # ou --n 5000
bash scripts/rodar_container.sh moveit "bash modelo_digital/moveit_headless/rodar_moveit_headless.sh"
```

### Servidor do gêmeo digital (A12)

```bash
bash gemeo_digital/subir_servidor.sh auto               # auto | gt | ruido | pose | http (só 127.0.0.1:8091)
bash gemeo_digital/derrubar_servidor.sh
# acesso de outra máquina por encaminhamento SSH local:
#   ssh -N -L 127.0.0.1:18091:localhost:8091 <host-do-spark>  ->  http://127.0.0.1:18091
bash gemeo_digital/capturas/sessao_capturas.sh          # capturas Playwright + verificação das malhas
```

**Plugar o modelo de pose.** O servidor carrega `~/cerise2026/pose/inferencia/predict.py` (classe
`PosePredictor`) quando `~/cerise2026/pose/READY.json` existe (modo `auto` ou `pose`). Contrato:
`PosePredictor(**READY.json["kwargs"]).predict(rgb: np.ndarray HxWx3 uint8 RGB, camera: str)` devolvendo
`{"joint_1": rad, ..., "joint_5": rad[, "joint_6": rad]}` (também aceita lista/array em ordem, ou graus
se `READY.json` tiver `"unidade": "graus"`). Se o modelo precisar de torch/GPU, o servidor sobe com a
imagem do modelo de pose: `IMAGEM=cerise26_pose:latest GPU=1 bash gemeo_digital/subir_servidor.sh pose`.
Alternativa desacoplada: `GEMEO_PREDICTOR_URL=<url>` e modo `http` (POST JSON `{"camera", "png_b64"}`).

**Integração com o modelo de pose e avaliação** (roteiro completo em
`gemeo_digital/integracao/sessao_2026-10-26/LEIAME.md`):

```bash
IMAGEM=cerise26_pose:latest GPU=1 N_QUADROS=0 LOGS=$HOME/cerise2026/gemeo/integracao/logs \
  bash gemeo_digital/subir_servidor.sh pose
GL=gpu bash gemeo_digital/integracao/rodar_playwright.sh avaliar      # teste inteiro, 2 câmeras + fps fixos
bash gemeo_digital/integracao/rodar_playwright.sh capturas             # quadros de baixo erro e de falha
bash gemeo_digital/integracao/rodar_playwright.sh varredura --inicio 0 --n 72 --modo lado --vista livre --pasta /integ/varredura
EXTRA="-v $HOME/cerise2026/gemeo/integracao:/integ -v $HOME/cerise2026/pose:/pose:ro" \
  bash scripts/rodar_container.sh analise "python3 gemeo_digital/integracao/analisar_gemeo.py"
bash gemeo_digital/ros2/rodar_rviz_pose.sh                             # nó ROS 2 (predictor=http) + RViz em Xvfb
```

- A sequência do servidor usa o mesmo split de teste do modelo de pose (80/10/10 por pose, semente 2026,
  lido de `~/cerise2026/pose/dados/final/index.npz`): 500 poses × 2 câmeras, nenhuma vista no treino.
- O WebSocket aceita `fps=0` (malha fechada: o próximo quadro só sai quando o front-end confirma que
  desenhou o anterior) e o front-end devolve um `ack` com o instante em que o gêmeo atualizado está nos
  pixels do canvas; a latência ponta a ponta é gravada por quadro em JSONL (`GEMEO_LOG_DIR`).
- `POST /api/prever` expõe o predictor a outros clientes (o nó ROS 2 usa essa rota); `GET /api/recursos`
  mostra a memória de GPU do torch, RSS e cgroup.

## Resultados principais (medidos em 26/10/2026)

| Item | Resultado |
|---|---|
| Dataset | 5.000 poses, 30.000 imagens 1280×720 (RGB, profundidade, segmentação × 2 câmeras), 2,51 GB; splits 4.000/500/500 |
| Integridade (todas as 30.000 imagens) | 0 problemas, 0 órfãos, 0 faltantes, 0 quadros duplicados; rótulos {0,1,2} em todas as máscaras |
| Cobertura do espaço de juntas | 100 % das células 20×20 em todos os pares; correlação máx. entre juntas 0,024 |
| Juntas reais × comandadas | 34,1 % das poses divergem (> 0,01 rad), 100 % das que atravessariam o chão; usar `juntas_reais` |
| Geração | 3,64 h no DGX Spark, 8 workers Gazebo, 12,8 s/pose por worker (mediana) |
| Variante laranja (mesmas 5.000 poses) | 1,86 h (10:47–12:38), 8 workers; 35.009 arquivos |
| Modelo × imagens (IoU silhueta, 1.000 poses) | 0,950 (frontal) e 0,938 (diagonal); 2,05 % das imagens abaixo de 0,8 |
| Modelo × imagens (IoU silhueta, 5.000 poses) | 0,949 (frontal) e 0,937 (diagonal); 247 de 10.000 imagens (2,47 %) abaixo de 0,8 |
| URDF | 13 links, 12 juntas (11 de revolução, 1 fixa), 5 GDL no braço + 1 na garra, 5 juntas mimic |
| FK própria × TF do `robot_state_publisher` | 300 configurações × 11 links: erro máx. 1,9e-15 m e 4,2e-8 rad |
| FK do front-end (three.js/urdf-loader) × FK Python | ≤ 7,6e-7 m (precisão float32) |
| Espaço de trabalho (100 mil configurações) | alcance horizontal máx. 2,05 m; z da ponta da garra em [-0,82; 2,58] m; 20 % das configurações levariam a garra abaixo do chão |
| MoveIt 2 headless (OMPL RRTConnect, hardware falso) | 5/5 objetivos executados; 50/50 planejamentos com sucesso, 12,9 a 17,0 ms em média por objetivo |
| Nó ROS 2 do gêmeo | imagem → `/twin/joint_states` → TF `twin/`: erro 4,6e-16 m com oráculo |
| Front-end | 2 × 12 malhas STL carregadas, sem erros, verificado por Playwright (pixels e estado JS) |
| **A12 – gêmeo com o modelo de pose** (teste, 500 poses × 2 câmeras = 1.000 quadros, só imagem) | erro médio das juntas 1–4: 5,41° (j1 4,19 · j2 3,04 · j3 3,91 · j4 10,52); j5 (rotação da garra) 41,7°; média das 5 juntas 12,68°, idêntica à avaliação offline do modelo de pose |
| A12 – erro do efetuador (FK das juntas previstas × verdade) | mediana 76 mm, média 107 mm, p95 275 mm, máx. 991 mm; 64,5 % dos quadros abaixo de 100 mm |
| A12 – latência imagem → predição → gêmeo desenhado | mediana 99,6 ms (p95 217 ms); modelo 77,7 ms; render no navegador (WebGL na GPU) 14,1 ms |
| A12 – FPS sustentado | 9,8 (malha fechada, GPU livre) e 5,9 (GPU disputada); taxas-alvo 2/5/10 mantidas (2,00/5,00/9,97); SwiftShader (CPU) 0,42 |
| A12 – memória | pico 2,94 GB alocados / 3,18 GB reservados de GPU (torch), teto de 4 GB |
| A12 – ROS 2 + RViz headless | `/twin/joint_states` a 2,00 Hz, 79/80 pares casados; atraso imagem → gêmeo 255 ms (mediana); erro das juntas compatível com o do servidor |

Fontes: `resultados/dataset_*.json`, `resultados/validacao_projecao_n1000.json`,
`resultados/validacao_projecao_n5000.json`, `resultados/modelo_resumo.json`,
`resultados/validacao_fk_tf.json`, `resultados/espaco_trabalho.json`, `resultados/moveit_planejamento.json`,
`resultados/ros2_twin_tf.json`, `resultados/capturas_verificacao.json`,
`resultados/a12_integracao/metricas_gemeo_integracao.json`, `resultados/a12_integracao/ros2_twin_pose.json`
e `resultados/geracao_laranja/gen_main.log`.

## Artefatos em Releases

Os datasets completos (versão cinza, do relatório, e variante laranja; duas partes `.tar` independentes
de ~1,3 GB por versão) e os 148 quadros brutos das varreduras do gêmeo estão no Release
`dados-2026-10-26`. Tamanhos, SHA-256, manifestos por arquivo e comandos para baixar, conferir e extrair:
[`RELEASES.md`](RELEASES.md). A amostra `amostra_dataset/` (8 poses) fica no próprio git.

## O que não está aqui e por quê

| Item | Motivo | Como obter |
|---|---|---|
| Imagens Docker (`servo6dof:humble`, `cerise26_gemeo*`, `cerise26_pose`) | muitos GB; regeneráveis | `docker/Dockerfile.*` e comandos acima; `cerise26_pose` vem do repositório `cerise-2026-pose-servo6dof` |
| Imagens base de terceiros (`ros:humble-ros-base`, `mcr.microsoft.com/playwright/python:v1.49.1-noble`) | distribuídas pelos registros oficiais | `docker pull` (feito pelo `docker build`) |
| `build/`, `install/`, `log/` do colcon, `__pycache__/` | artefatos regeneráveis | `colcon build` |
| Modelo de pose (HPE + Depth Anything V2) e seus pesos | pertencem a outro repositório; os pesos do Depth Anything V2 são de terceiros (Hugging Face) | repositório `cerise-2026-pose-servo6dof` |
| Pacotes npm completos de three.js 0.160.0 e urdf-loader 0.13.1 | terceiros; só os módulos usados estão em `gemeo_digital/servidor/static/vendor/` (three.js: MIT, licença incluída; urdf-loader: Apache-2.0, G. Johnson, github.com/gkjohnson/urdf-loaders) | `registry.npmjs.org` (ver `scripts/spark_aux/vendor.sh`) |
| Pacotes de transferência temporários do Spark (`codigo*.tgz`, `saidas*.tgz`, `repo_base.tgz`) | cópias intermediárias; o conteúdo está no histórico do git (exceto rascunhos de uma figura e do texto do relatório, substituídos pelas versões finais) | — |
| Script de religamento dos serviços de produção do Spark (`dataset_run_restore.sh`, chamado por `dataset_tools/finalizar.sh`) | configuração operacional da máquina, fora do escopo do projeto | — |
| Segredos (chaves, tokens, senhas) | segurança; nenhum é usado por este repositório | — |

**Licença:** não há arquivo `LICENSE` neste repositório, por decisão do autor. Os componentes de
terceiros mantêm as licenças indicadas acima; a ficha do dataset (`docs/DATASET.md`) registra a proposta de
licença dos dados, pendente de deliberação da coordenação.

## Segurança

O servidor do gêmeo é publicado só em `127.0.0.1:8091` do Spark. Nada é exposto à internet; o acesso é
feito por encaminhamento SSH local. A eventual exposição pública é uma decisão pendente (ver
`RELATORIO_SECAO.md`, Limitações).
