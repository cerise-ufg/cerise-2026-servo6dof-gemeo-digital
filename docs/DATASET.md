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

- **Instâncias:** 5.000 poses do braço servo6dof (ids 000001 a 005000), cada uma com 6 imagens
  1280×720 e 1 anotação JSON. Total: **30.000 imagens** (10.000 RGB, 10.000 de profundidade e 10.000 de
  segmentação; 15.000 por câmera) e **2,51 GB** (RGB 1,10 GB; profundidade 1,30 GB; segmentação 0,11 GB;
  JSON 7,7 MB; 0,50 MB por pose).
- **Rótulos por pose:** 5 ângulos de junta do braço (rad), comandados e reais, e o ângulo comandado da garra.
  Da segmentação deriva a máscara do braço; da profundidade, a geometria por pixel; da FK do modelo
  digital, as poses 3D dos elos e a projeção 2D de pontos-chave.
- **Distribuição dos ângulos comandados:** uniforme em [−81°; 81°] nas juntas do braço (desvio-padrão
  medido de 45,9° a 46,7°, contra 46,8° teóricos) e em [−36,5°; 26,5°] na garra; correlação máxima entre
  juntas |r| = 0,024; 100 % das células 20×20 cobertas em todos os pares de juntas.
- **Conteúdo das imagens:** um único braço sobre chão cinza e fundo liso, iluminação fixa, sem oclusores.
  O braço ocupa em média 8,8 % da imagem frontal (5,4 % a 14,0 %) e 6,0 % da diagonal (3,7 % a 8,9 %).
  Profundidade mínima por imagem: 1,22 a 3,02 m (frontal) e 2,00 a 3,43 m (diagonal).
- **Integridade (verificação completa):** 30.000 de 30.000 arquivos existem e decodificam, todos em
  1280×720 e no modo esperado; as 10.000 máscaras contêm exatamente os rótulos {0, 1, 2}; nenhum quadro
  RGB duplicado entre poses; nenhum PNG órfão; nenhuma pose do plano faltando.
- **Arquivos auxiliares na pasta:** `poses_registradas_w0..7.csv` (registro por worker do script de
  captura).

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
- **Período e vazão.** primeira pose às 00:41:38 e última às 04:19:45 de 26/10/2026 (3,64 h; média de 0,38 pose/s,
  ou 2,3 imagens/s). Em regime, cada worker levou em mediana 12,8 s por pose (cerca de 0,63 pose/s com 8
  workers), com pico de 45 poses/min em janelas de 5 min; a vazão caiu à metade quando o host passou a
  ser compartilhado com jobs de outras frentes. A primeira rodada gravou 4.747 poses; a segunda
  (04:02:59) completou as 253 faltantes, e cada worker terminou com 625 poses.

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
- **índice** (`resultados/dataset_meta/index.csv`, gerado por `indexar.py`): uma linha por pose com ângulos, *split*,
  e arquivo, bytes e mtime de cada imagem;
- **intrínsecos** (pinhole, sem distorção): fx = fy = 640 / tan(30°) ≈ 1108,5 px, cx = 640, cy = 360.
  A convenção da câmera do Gazebo é x para a frente, y para a esquerda e z para cima;
  `modelo_digital/cinematica.py:projetar` implementa a projeção.

## 5. Splits recomendados

Divisão determinística por id, independente da ordem de geração: `id % 10` de 0 a 7 → **treino**,
8 → **validação**, 9 → **teste**. Resultado: **4.000 / 500 / 500** poses (24.000 / 3.000 / 3.000 imagens). O servidor do gêmeo digital usa o *split* de teste. Como as
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

- **Onde está:** dataset completo nos Releases deste repositório (`dataset_cinza.part01.tar` e
  `.part02.tar`, com SHA-256 e instruções em `RELEASES.md`); na execução, ficou no DGX Spark em
  `~/braco/dataset` (hoje `~/braco/dataset_cinza`). Metadados (`index.csv`, integridade por imagem) em
  `resultados/dataset_meta/`; amostra de 8 poses do *split* de teste em `amostra_dataset/`.
- **Variante laranja:** as mesmas 5.000 poses renderizadas de novo com o braço em laranja
  (`dataset_laranja.part01.tar` e `.part02.tar`; procedimento em `dataset_tools/variante_laranja/`). As
  estatísticas desta ficha referem-se à versão cinza, usada no relatório.
- **Licença:** uso interno do projeto CERISE/EMC/UFG até deliberação dos coordenadores (proposta: CC BY 4.0
  para os dados sintéticos, mantendo os créditos do modelo do braço ao Prof. Alisson).
- **Manutenção:** regenerável a partir de `plano_poses.json` com `gerar_hd_spark.sh`; a retomada
  verifica o disco pose a pose.

## 8. Limitações conhecidas

1. **Juntas comandadas ≠ reais em 34,1 % das poses** (> 0,01 rad em alguma junta, sobretudo `joint_1` a
   `joint_3`). 19,7 % das configurações do plano atravessariam o chão, e todas elas divergem, porque o
   braço é barrado pelo chão. **Use `juntas_reais` como rótulo.** Medido pela silhueta: IoU médio de 0,930
   com as juntas reais contra 0,547 com as comandadas nas poses divergentes.
2. **Cerca de 2 % de imagens com rótulo suspeito:** em 1.000 poses avaliadas, 2,05 % das imagens têm IoU
   abaixo de 0,8 entre a silhueta do modelo (com as juntas reais) e a máscara do Gazebo, ou seja, o braço
   na imagem não corresponde às juntas registradas (provável captura antes do assentamento ou contato).
   Recomenda-se filtrar com `modelo_digital/validar_projecao.py --n 5000`; essa execução, sobre as 5.000
   poses, está em `resultados/validacao_projecao_n5000.csv` (247 de 10.000 imagens, 2,47 %, abaixo de 0,8).
3. **Segmentação:** o braço tem rótulo 0, o mesmo de regiões sem objeto (céu na câmera diagonal, 0,16 % dos
   pixels). Use rótulo 0 com profundidade > 0. Não há rótulos por elo.
4. **Garra:** o Gazebo Fortress não aplica o `mimic` do URDF; os dedos da garra nas imagens não seguem
   exatamente o modelo cinemático (só `joint_6` e `joint_7` são acionadas). O ângulo da garra no JSON é
   o comandado, sem leitura real.
5. **Domínio:** cena fixa (duas câmeras, luz, fundo e materiais constantes) e malhas em escala 6; sem ruído
   de sensor nem borrão de movimento. O uso em imagens reais exige randomização de domínio ou ajuste fino.
6. **Dinâmica:** o URDF tem inércias de preenchimento; as poses são quasi-estáticas (assentamento de
   0,5 s em tempo simulado).
