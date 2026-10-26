# Datasheet: dataset sintético multimodal do braço servo6dof (CERISE 2026)

*Formato inspirado em "Datasheets for Datasets" (Gebru et al.). Todos os números foram medidos sobre os
arquivos em 26/10/2026 pelos scripts de `dataset_tools/analise/`; os valores brutos estão em
`resultados/dataset_*.json`.*

## 1. Motivação

- **Para que foi criado.** Para treinar e avaliar modelos de estimação da pose articular do braço
  servo6dof a partir de imagens (os ângulos das juntas a partir de RGB e, opcionalmente, de
  profundidade e segmentação), insumo do gêmeo digital do braço (Plano de Trabalho CERISE 2026,
  Objetivo 3, Atividade 7, e Objetivo 4, Atividades 11 e 12).
- **Quem criou.** Eduardo Martins de Carvalho Caixeta (bolsista), com o pacote ROS 2 do braço do
  Prof. Dr. Alisson Assis Cardoso (CERISE/EMC/UFG).
- **Financiamento e infraestrutura.** Projeto CERISE/EMC/UFG; geração no DGX Spark do laboratório.

## 2. Composição

⟨COMPOSICAO⟩

## 3. Processo de coleta (geração)

- **Plano de poses.** `dataset_tools/gerar_plano.py` sorteia 5.000 poses com `random.Random(20260909)`,
  uniformes em [−90°; 90°] para `joint_1` a `joint_5` e em [−40°; 30°] para a garra, descontada uma folga
  de 5 % em cada extremo (faixa efetiva de ±81° nas juntas do braço). Cada pose tem um id fixo, o que
  torna a geração retomável e reprodutível.
- **Simulação.** ROS 2 Humble + Ignition Gazebo Fortress (container `servo6dof:humble`,
  `docker/Dockerfile.spark`), mundo `estudio_hd.sdf`: chão (rótulo 1), fundo (rótulo 2), duas luzes
  direcionais e duas câmeras estáticas (RGB, profundidade e segmentação semântica, 1280×720, hfov 60°,
  5 Hz). Câmera frontal em (3,2; 0,4; 1,6) m com rpy (0; 0,215; π); câmera diagonal em (2,6; 2,6; 2,4) m
  com rpy (0; 0,414; −2,439). Renderização ogre2 por GPU (EGL da NVIDIA, headless).
- **Pipeline por pose** (`servo6dof_camera/scripts/tirar_fotos.py`): objetivo `FollowJointTrajectory`
  para o braço e a garra (3 s de tempo simulado), espera de 3 s + 0,5 s de assentamento medida em tempo
  de simulação, descarte do buffer de quadros, captura do quadro seguinte de cada um dos 6 tópicos,
  gravação dos 6 PNGs e do JSON (juntas comandadas, juntas reais de `/joint_states` e garra).
- **Paralelismo.** `dataset_tools/gerar_hd_spark.sh` com 8 workers, cada um com Gazebo isolado
  (`ROS_DOMAIN_ID` 90–97, `IGN_PARTITION` próprio); o worker *w* faz as poses com `id % 8 == w`. Ao fim de
  cada rodada, o script recalcula o que falta no disco e repete até zerar. `dataset_tools/finalizar.sh`
  corrige o dono dos arquivos e religa os serviços de produção do Spark ao término.
- **Período e vazão.** ⟨GERACAO⟩

## 4. Pré-processamento e formato

Não há pré-processamento além da conversão no momento da gravação:

- **RGB** (`*_image.png`): PNG RGB 8 bits, 1280×720;
- **profundidade** (`*_depth.png`): PNG inteiro (lido pelo Pillow como modo `I`), em **milímetros**
  (metros × 1000, truncado em 65.535); 0 = sem retorno (fora do plano de corte);
- **segmentação** (`*_segmentation_labels_map.png`): PNG RGB com R = G = B = rótulo; 0 = braço (e regiões
  sem objeto), 1 = chão, 2 = fundo. **Máscara do braço recomendada: rótulo 0 e profundidade > 0**;
- **anotação** (`NNNNNN.json`): `id`, `pose`, `juntas_comandadas` e `juntas_reais` (rad, 4–5 casas),
  `garra_comandada.joint_6` (rad), `juntas_graus` (das comandadas) e `cameras` (arquivo, tipo, largura e
  altura de cada imagem);
- **índice** (`dataset_meta/index.csv`, gerado por `indexar.py`): uma linha por pose com ângulos, *split*,
  e arquivo, bytes e mtime de cada imagem;
- **intrínsecos** (pinhole, sem distorção): fx = fy = 640 / tan(30°) ≈ 1108,5 px, cx = 640, cy = 360.
  A convenção da câmera do Gazebo é x para a frente, y para a esquerda e z para cima;
  `modelo_digital/cinematica.py:projetar` implementa a projeção.

## 5. Splits recomendados

Divisão determinística por id, independente da ordem de geração: `id % 10` de 0 a 7 → **treino**,
8 → **validação**, 9 → **teste**. ⟨SPLITS⟩ O servidor do gêmeo digital usa o *split* de teste. Como as
poses foram sorteadas de forma independente e uniforme, não há vazamento temporal; para avaliar a
generalização entre câmeras, recomenda-se também treinar numa câmera e testar na outra.

## 6. Usos

- **Previstos:** regressão de ângulos de junta a partir de imagem (estimação de pose articular), detecção
  de pontos-chave por projeção da FK, segmentação do braço, estimação de profundidade monocular e
  avaliação do gêmeo digital.
- **Rótulo correto:** use **`juntas_reais`** como verdade-base da imagem, não `juntas_comandadas` (seção 8).
- **Não recomendados sem adaptação:** transferência direta para o braço físico (domínio sintético, malhas
  em escala 6, materiais e luz simplificados) e estudos de dinâmica (inércias de preenchimento no URDF).

## 7. Distribuição, licença e manutenção

- **Onde está:** dataset completo no DGX Spark em `~/braco/dataset` (somente leitura para as frentes);
  metadados em `~/cerise2026/gemeo/dataset_meta`; amostra de 8 poses do *split* de teste em
  `amostra_dataset/` deste repositório.
- **Licença:** uso interno do projeto CERISE/EMC/UFG até deliberação dos coordenadores (proposta: CC BY 4.0
  para os dados sintéticos, mantendo os créditos do modelo do braço ao Prof. Alisson).
- **Manutenção:** regenerável a partir de `plano_poses.json` com `gerar_hd_spark.sh`; a retomada
  verifica o disco pose a pose.

## 8. Limitações conhecidas

⟨LIMITACOES⟩
