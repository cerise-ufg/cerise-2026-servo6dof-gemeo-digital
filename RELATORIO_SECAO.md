# Gêmeo digital do braço servo6dof: dataset, modelo digital e infraestrutura

**Atividades do Plano de Trabalho:** Objetivo 3, Atividade 7 (dataset estruturado e documentado);
Objetivo 4, Atividade 11 (modelo digital do braço robótico em ambiente virtual); Objetivo 4,
Atividade 12 (sistema de gêmeo digital, parte de infraestrutura).
**Repositório:** <https://github.com/EduardoCaixeta/cerise-2026-servo6dof-gemeo-digital> (privado; o
código está commitado no espelho local `E:\CERISE\FRENTES\ROBOTICA\SERVO6DOF_GEMEO`, e a criação do
repositório remoto e o *push* ficaram pendentes de autorização do Eduardo)
**Ambiente de execução:** DGX Spark (NVIDIA GB10, arm64, Ubuntu 24.04), containers Docker com ROS 2
Humble e Ignition Gazebo Fortress; data das execuções: 26/10/2026.

## 1. Objetivo

Esta seção registra três entregas encadeadas. A primeira é a consolidação, verificação e documentação
do dataset sintético do braço servo6dof gerado no Gazebo, com imagens RGB, de profundidade e de
segmentação rotuladas com os ângulos das juntas (A7). A segunda é a caracterização do modelo digital do
braço: estrutura física e cinemática extraída do URDF, cinemática direta validada, espaço de trabalho e
planejamento de movimento com MoveIt 2 (A11). A terceira é a infraestrutura do gêmeo digital: um
servidor que transmite quadros de teste do dataset e um visualizador 3D que compara o braço de
referência com o braço reconstruído por um estimador de pose plugável, além do desenho do nó ROS 2
correspondente (A12). A integração do modelo de estimação de pose, desenvolvido por outra frente,
fica para a etapa seguinte, e o ponto de encaixe já está implementado e testado.

## 2. Metodologia e implementação

### 2.1 Base de software e organização

O pacote ROS 2 do braço (`servo6dof_description`, `servo6dof_controller`, `servo6dof_moveit` e
`servo6dof_camera`), fornecido pelo Prof. Dr. Alisson Assis Cardoso e adaptado para o estúdio
fotográfico no Gazebo, foi copiado, sem alterações, para o repositório da frente, junto com os
scripts de geração do dataset e a documentação original. O braço tem cinco juntas de revolução
(`joint_1` a `joint_5`) e uma junta de garra (`joint_6`); as demais juntas da garra são `mimic` de
`joint_6`. Todo o processamento roda em containers com prefixo `cerise26_gemeo`. A imagem
`cerise26_gemeo:latest` deriva da imagem do gerador (`servo6dof:humble`) e acrescenta MoveIt 2 (move_group,
OMPL, KDL), as bibliotecas de análise e FastAPI. A pasta do dataset (`~/braco/dataset`) foi montada
sempre em modo somente leitura, e os metadados derivados foram gravados em `~/cerise2026/gemeo/dataset_meta`.

### 2.2 Dataset (A7)

A geração seguiu um plano fixo e reprodutível (`plano_poses.json`, semente 20260909) com 5.000 poses
sorteadas uniformemente em ±90° para `joint_1` a `joint_5` e em [-40°, 30°] para a garra, descontada
uma folga de 5 % em cada extremo. Para cada pose, o script de captura comanda a trajetória pelo
`FollowJointTrajectory` (3 s de tempo simulado mais 0,5 s de assentamento), descarta os quadros
anteriores e grava um JSON com as juntas comandadas, as juntas reais (lidas de `/joint_states` no
instante da foto) e a garra, além de seis PNGs 1280×720: RGB, profundidade (uint16 em milímetros) e
mapa de rótulos de segmentação das câmeras frontal e diagonal. A renderização usa o ogre2 com EGL da
NVIDIA, e a geração roda com oito instâncias isoladas do Gazebo em paralelo, retomando do disco o que
faltar a cada rodada.

Sobre essa saída, foram implementadas as ferramentas de `dataset_tools/analise/`:

- `indexar.py` gera um índice consolidado (`index.csv`, uma linha por pose) com ângulos, *split*
  recomendado, arquivo, tamanho e data de modificação de cada uma das seis imagens;
- `integridade.py` confere a existência dos arquivos, decodifica integralmente cada PNG e verifica
  dimensões, modo de cor, rótulos de segmentação, profundidade e duplicatas de quadros RGB entre poses;
- `estatisticas.py` calcula contagens, volumes, distribuições angulares frente aos limites, cobertura do
  espaço de juntas e correlações;
- `real_vs_comandado.py` confronta as juntas reais com as comandadas usando a cinemática direta do
  modelo digital;
- `grades.py` gera as grades de amostras e a amostra versionada; `linha_tempo.py` reconstrói a linha do
  tempo e a vazão da geração a partir dos arquivos e dos logs.

O *datasheet* completo está em `docs/DATASET.md`.

### 2.3 Modelo digital (A11)

O URDF foi gerado a partir do xacro dentro do container (`xacro servo6dof.urdf.xacro is_ignition:=true`),
o mesmo que o Gazebo recebe na geração do dataset. A partir dele foram produzidas a tabela de links e
juntas, a árvore cinemática (graphviz) e uma implementação própria de cinemática direta em Python e
numpy (`modelo_digital/cinematica.py`). Essa implementação lê o URDF, compõe as transformações das
origens (convenção RPY de eixos fixos) com as rotações de eixo-ângulo (Rodrigues), resolve as juntas
mimic e oferece uma versão vetorizada para lotes de configurações. A validação comparou essa FK com o TF
publicado pelo `robot_state_publisher` do ROS 2 para o mesmo URDF, em 300 configurações aleatórias e 11
links. O espaço de trabalho foi estimado por Monte Carlo com 100 mil configurações uniformes nos
limites. Também foi implementado um modelo pinhole das câmeras do estúdio (pose do SDF, campo de visão
horizontal de 60°, 1280×720) para projetar as malhas STL posicionadas pela FK sobre as imagens do
dataset e medir o IoU entre a silhueta do modelo e a máscara de segmentação do Gazebo. Por fim, o
MoveIt 2 foi executado sem interface gráfica: `move_group` com OMPL (RRTConnect) e KDL, mais
`ros2_control` com hardware falso (`mock_components/GenericSystem`, gerado por `urdf_fake.py`) e os
controladores originais. Um cliente da ação `/move_action` planejou e executou cinco objetivos.

### 2.4 Infraestrutura do gêmeo digital (A12)

O servidor (`gemeo_digital/servidor/app.py`, FastAPI com uvicorn) roda no container `cerise26_gemeo`,
publicado apenas em `127.0.0.1:8091` do Spark. Ele monta uma sequência de teste com 150 poses do
*split* de teste, ordenadas por vizinho mais próximo no espaço de juntas para que a animação fique
suave, e transmite por WebSocket, quadro a quadro, a imagem da câmera, as juntas de referência, as
juntas previstas, o erro por junta e o erro do efetuador calculado pela FK. A estimação é feita por um
`Predictor` plugável com a interface `predict(rgb, camera) -> {junta: rad}`
(`gemeo_digital/servidor/predictors.py`), que oferece estas implementações:

- `GroundTruthPredictor`: oráculo, devolve a verdade-base;
- `RuidoPredictor`: verdade-base com ruído gaussiano, usado só para demonstrar o painel de erro;
- `PosePredictorAdapter`: carrega `~/cerise2026/pose/inferencia/predict.py` (classe `PosePredictor`)
  quando a frente de pose publicar `~/cerise2026/pose/READY.json`;
- `HttpPredictor`: consulta um serviço de inferência externo.

O front-end, em three.js r160 com urdf-loader 0.13.1 servidos localmente, carrega o URDF e as malhas
STL (resolvendo `package://` para o pacote de descrição) duas vezes: "Braço — referência", em alumínio
sólido, e "Gêmeo digital", verde e translúcido, lado a lado ou sobrepostos. Uma das vistas reproduz a
pose e o campo de visão da câmera do dataset. O painel lateral mostra a imagem, os ângulos por junta e
um gráfico do erro ao longo da sequência. As capturas foram feitas com Playwright (Chromium headless
com WebGL via SwiftShader) no próprio Spark. A verificação de que as malhas aparecem combina o estado JS
da página (robôs e malhas carregados, erros, quadros recebidos), uma análise dos pixels do canvas e a
comparação entre a FK do three.js e a FK do servidor. Para o ecossistema ROS 2 foi desenhado e
implementado o nó `gemeo_twin_node` (imagem → `Predictor` → `/twin/joint_states`), com um segundo
`robot_state_publisher` de prefixo `twin/` e uma configuração de RViz com dois `RobotModel`
(`gemeo_digital/ros2/DESENHO_NO_ROS2.md`).

## 3. Resultados

### 3.1 Dataset (A7)

**Composição e volume.** A geração terminou com as **5.000 poses** do plano, o que dá **30.000
imagens** (10.000 de cada modalidade, metade por câmera) e **2,51 GB** no total: 1,10 GB de RGB, 1,30 GB
de profundidade, 0,11 GB de segmentação e 7,7 MB de JSON, ou 0,50 MB por pose. Os PNGs de profundidade
da câmera diagonal são os mais pesados (206 KB em média, contra 47 KB na frontal) porque o campo de
visão inclui o chão até cerca de 16 m, com gradiente contínuo. O *split* determinístico por id resultou
em 4.000 poses de treino, 500 de validação e 500 de teste.

| Modalidade | Câmera frontal | Câmera diagonal | Total |
|---|---|---|---|
| RGB (PNG 8 bits, 1280×720) | 0,60 GB (116 KB/img) | 0,50 GB (98 KB/img) | 1,10 GB |
| Profundidade (PNG inteiro, mm) | 0,24 GB (47 KB/img) | 1,05 GB (206 KB/img) | 1,30 GB |
| Segmentação (rótulos 0/1/2) | 0,05 GB (10 KB/img) | 0,05 GB (11 KB/img) | 0,11 GB |

![Figura: Amostras do dataset nas duas câmeras: RGB, profundidade colorizada e segmentação (laranja: rótulo 0, braço)](evidencias/a7_grade_amostras.png)

**Integridade.** O índice consolidado tem as 5.000 poses, com 30.000 PNGs referenciados, nenhum órfão,
nenhum faltante e nenhuma pose do plano sem arquivo. A verificação completa (decodificação integral das
30.000 imagens, em 86 s com 6 processos) não encontrou nenhum problema:

- todas as imagens têm 1280×720, no modo esperado (RGB, inteiro de 32 bits para profundidade e RGB com
  R = G = B para a segmentação);
- todas as 10.000 máscaras contêm exatamente os rótulos {0, 1, 2};
- não há nenhum quadro RGB duplicado entre poses diferentes, indicador de que não houve captura de quadro
  "velho".

O braço ocupa em média 8,8 % da imagem frontal (5,4 % a 14,0 %) e 6,0 % da diagonal (3,7 % a 8,9 %). A
câmera frontal não tem pixels sem retorno de profundidade; a diagonal tem 0,16 % (céu acima do fundo).

![Figura: Print do terminal com o índice e a verificação de integridade do dataset completo](evidencias/term_a7_integridade.png)

**Distribuição e cobertura.** Os ângulos comandados ocupam exatamente a faixa do plano
([−81,0°; 81,0°] nas cinco juntas do braço e [−36,5°; 26,5°] na garra), com média próxima de zero e
desvio-padrão entre 45,9° e 46,7°, compatível com a distribuição uniforme (46,8°). Todos os 10 pares de
juntas cobrem 100 % das células de uma grade 20×20 (8,1° por célula), a maior correlação de Pearson entre
juntas é |r| = 0,024 e a distância média ao vizinho mais próximo no espaço 5D normalizado (0,1265) é
praticamente igual à de uma amostra uniforme do mesmo tamanho (0,1262).

![Figura: Histogramas dos ângulos comandados frente aos limites do URDF e à folga de 5 % do plano](evidencias/a7_histogramas_angulos.png)

![Figura: Cobertura do espaço de juntas por pares e matriz de correlação entre juntas](evidencias/a7_cobertura_correlacao.png)

**Juntas reais × comandadas.** Em 34,1 % das poses, ao menos uma junta real difere da comandada por
mais de 0,01 rad, concentradas em `joint_1` a `joint_3` (19,8 %, 26,9 % e 21,9 % das poses), com 3,1 % em
`joint_4` e 0,1 % em `joint_5`. A análise pela FK do modelo digital explica a maior parte dos casos:

- 19,7 % das configurações comandadas levariam algum elo ou a ponta da garra abaixo do chão, e **100 %
  delas divergem**, enquanto nenhuma configuração real fica abaixo de −5 cm. O braço é barrado pelo chão,
  e o JSON registra onde ele parou;
- entre as poses comandadas acima do chão, 18,0 % também divergem, o que é compatível com movimento não
  concluído ou contato durante a trajetória.

As imagens confirmam que o rótulo correto é a junta real: nas 670 imagens de poses divergentes avaliadas,
o IoU médio da silhueta do modelo com a máscara do Gazebo foi de 0,930 usando as juntas reais e de 0,547
usando as comandadas.

![Figura: Divergência entre juntas reais e comandadas por junta e em função da altura mínima do braço na configuração comandada](evidencias/a7_real_vs_comandado.png)

**Linha do tempo e vazão.** A primeira pose foi gravada às 00:41:38 e a última às 04:19:45 (3,64 h de
parede, média de 0,38 pose/s, ou 2,3 imagens/s, com 8 workers). A mediana do intervalo entre poses de um
mesmo worker foi de 12,8 s, cerca de 0,63 pose/s em regime com os 8 workers. Nas primeiras 1,3 h, as
janelas de 5 min chegaram a 45 poses/min. A vazão caiu depois para 12 a 26 poses/min, com o host
compartilhado com jobs de outras frentes (load average medido entre 28 e 46 nesse período). A primeira
rodada (iniciada às 00:40:33) gravou 4.747 poses, e alguns Gazebos degradaram no fim (capturas puladas
por falta de quadro, cerca de 20 min sem novas poses). Uma segunda rodada, iniciada às 04:02:59 pela
própria lógica de retomada, completou as 253 poses faltantes (253 → 15 → 0) às 04:19:46. Cada worker
terminou com exatamente 625 poses.

![Figura: Poses acumuladas, vazão em janelas de 5 minutos e poses por worker durante a geração no DGX Spark](evidencias/a7_linha_tempo_geracao.png)

### 3.2 Modelo digital (A11)

**Estrutura física e cinemática.** O URDF gerado tem 13 links e 12 juntas: 11 de revolução, das quais
6 são ativas (`joint_1` a `joint_6`) e 5 são mimic de `joint_6`, e 1 junta fixa (`world`→`base_link`).
O braço tem 5 graus de liberdade e a garra, 1. As malhas STL são aplicadas com fator de escala 6.

| Junta | Pai → filho | Origem xyz (m) | Eixo | Limites (graus) |
|---|---|---|---|---|
| joint_1 | base_link → primeiro_elo | (0; −0,23; −0,01) | z | [−90; 90] |
| joint_2 | primeiro_elo → segundo_elo | (−0,05; −0,03; 0,57) | x | [−90; 90] |
| joint_3 | segundo_elo → terceiro_elo | (0,06; 0; 0,63) | x | [−90; 90] |
| joint_4 | terceiro_elo → quarto_elo | (0; 0,78; 0) | x | [−90; 90] |
| joint_5 | quarto_elo → base_garra | (0,02; 0,36; 0) | y | [−90; 90] |
| joint_6 (garra) | base_garra → garra_elo1 | (−0,072; 0,12; 0,01) | z | [−40; 30] |

As distâncias entre origens consecutivas da cadeia (base_link → base_garra) são 0,23, 0,57, 0,63, 0,78
e 0,36 m. As massas do URDF somam 1,51 kg e todas as inércias são o valor de preenchimento
(Ixx = Iyy = Izz = 1 kg·m²). O modelo é, portanto, cinematicamente completo, mas não dinamicamente
calibrado. As tabelas completas estão em `resultados/modelo_juntas.md` e `resultados/modelo_links.md`.

![Figura: Árvore cinemática do servo6dof extraída do URDF gerado (azul: juntas ativas com eixo e limites; laranja: juntas mimic da garra)](evidencias/a11_arvore_cinematica.png)

![Figura: Modelo digital renderizado por software nas quatro poses nomeadas do SRDF, com as malhas STL posicionadas pela cinemática direta própria e a cadeia de referenciais em laranja](evidencias/a11_render_modelo_poses.png)

**Validação da cinemática direta.** Nas 3.300 comparações (300 configurações × 11 links), a FK própria
coincidiu com o TF do `robot_state_publisher` com erro máximo de posição de 1,9×10⁻¹⁵ m e de orientação
de 4,2×10⁻⁸ rad, ou seja, no nível do arredondamento numérico, inclusive nos links mimic da garra. A
FK do front-end (three.js/urdf-loader) coincidiu com a do servidor com diferença de até 7,6×10⁻⁷ m, a
precisão de float32.

![Figura: Erro da cinemática direta própria em relação ao TF do robot_state_publisher, por link (300 configurações)](evidencias/a11_validacao_fk_tf.png)

**Espaço de trabalho.** Com 100 mil configurações (FK vetorizada em 0,3 a 0,6 s), a ponta da garra
alcança até 2,05 m de distância horizontal do eixo de `joint_1`, com z entre −0,82 e 2,58 m. O fecho
convexo tem 27,8 m³ e o volume efetivamente ocupado, medido em voxels de 5 cm, é de 7,9 m³. Cerca de
20 % das configurações dentro dos limites levariam a garra abaixo do plano do chão. Essa propriedade
do modelo explica parte das divergências entre juntas comandadas e reais observadas no dataset.

![Figura: Espaço de trabalho da ponta da garra (100 mil configurações): nuvem 3D, vista de topo e vista lateral radial](evidencias/a11_espaco_trabalho.png)

**Modelo × imagens do simulador.** A projeção das malhas, posicionadas pela FK com as juntas registradas
no JSON, sobre as imagens do Gazebo coincide visualmente com o braço renderizado. Isso valida, ao mesmo
tempo, o modelo cinemático, o modelo de câmera e os rótulos do dataset. Em 1.000 poses sorteadas (2.000 imagens), o IoU entre a silhueta projetada do modelo e a máscara do
braço (rótulo 0 com profundidade válida) foi de 0,950 em média na câmera frontal (mediana 0,965,
percentil 5 de 0,896; precisão 0,961 e revocação 0,985) e de 0,938 na diagonal (mediana 0,951,
percentil 5 de 0,889). A diferença residual concentra-se na garra, cuja geometria no Gazebo não segue
o mimic do URDF (seção 4). Em 2,05 % das imagens (41 de 2.000), o IoU ficou abaixo de 0,8: o braço na
imagem aparece numa configuração diferente tanto das juntas reais quanto das comandadas (só 1 desses
casos é consistente com as comandadas), o que indica rótulo suspeito. Esses casos devem ser filtrados
para treino; a lista da amostra está em `resultados/validacao_projecao_n1000.csv`.

![Figura: Modelo digital (verde translúcido) e cadeia cinemática (laranja) projetados sobre imagens do dataset nas duas câmeras](evidencias/a11_sobreposicao_modelo_dataset.png)

![Figura: IoU entre a silhueta do modelo digital e a máscara de segmentação do Gazebo, com o caso mediano e o pior caso](evidencias/a11_iou_silhueta_n1000.png)

**MoveIt 2 headless.** A configuração do MoveIt 2 do pacote define o grupo `arm` (cadeia base_link →
base_garra) e o grupo `gripper` (`joint_6`), os estados nomeados `home`, `recolhido` e `estendido`
(braço) e `aberta` e `fechada` (garra), o efetuador `garra` e a matriz de colisões desabilitadas. Usa
KDL com IK só de posição (`position_only_ik`, adequada a um braço de 5 GDL) e controladores
`FollowJointTrajectory` para `arm_controller` e `gripper_controller`. Com hardware falso, os cinco
objetivos (três em espaço de juntas, um alvo cartesiano de posição para `base_garra` e o retorno a
`home`) foram planejados e executados com sucesso, e os três controladores ficaram ativos. Em 10
pedidos de planejamento por objetivo:

| Objetivo | Planejamentos com sucesso | Tempo médio (mín.–máx.) | Pontos da trajetória executada | Duração (s) |
|---|---|---|---|---|
| recolhido | 10/10 | 14,5 ms (13,5–15,9) | 23 | 2,18 |
| giro_esquerda | 10/10 | 13,0 ms (3,2–23,7) | 28 | 2,63 |
| estendido | 10/10 | 15,9 ms (13,3–24,6) | 23 | 2,19 |
| alvo_cartesiano | 10/10 | 17,0 ms (12,5–24,3) | 21 | 1,98 |
| home | 10/10 | 12,9 ms (2,1–17,3) | 17 | 1,56 |

No alvo cartesiano, a posição final de `base_garra` (calculada pela FK) ficou a 1,6 cm do alvo, dentro
da região de tolerância esférica de 2 cm especificada no pedido.

![Figura: Trajetórias de juntas planejadas pelo MoveIt 2 (OMPL RRTConnect) e executadas pelo ros2_control com hardware falso](evidencias/a11_moveit_trajetoria.png)

![Figura: Print do terminal da execução headless do MoveIt 2 no Spark](evidencias/term_a11_moveit_headless.png)

### 3.3 Infraestrutura do gêmeo digital (A12)

O servidor responde em `/saude`, `/api/info`, `/api/quadro/{idx}` e `/ws` e serve o URDF e as malhas do
pacote de descrição. Em todos os cenários capturados, os dois robôs carregaram 12 malhas cada, sem
erros de carregamento, e o WebSocket entregou quadros continuamente (a 2 e 10 quadros/s). O WebGL rodou
em SwiftShader, por software, e a página ficou pronta (URDF e 24 malhas carregados) entre 0,84 e 1,01 s
nas capturas finais. Com o preditor oráculo, o erro exibido é nulo, como esperado. Com o preditor de
demonstração (ruído gaussiano de 4° por junta, sem nenhum modelo envolvido), o painel mostra erro médio
de alguns graus por quadro e erros do efetuador da ordem de centímetros a decímetros, o que exercita o
gráfico e a tabela.

![Figura: Print do terminal do servidor do gêmeo: container publicado só no loopback do Spark, saúde, metadados e um quadro](evidencias/term_a12_servidor.png)

![Figura: Front-end do gêmeo digital (three.js + urdf-loader): braço de referência e gêmeo digital lado a lado, imagem da câmera, ângulos por junta e gráfico de erro](evidencias/a12_gemeo_lado_a_lado.png)

![Figura: Gêmeo sobreposto como fantasma ao braço de referência, na vista da câmera frontal do dataset](evidencias/a12_gemeo_sobreposto_vista_camera.png)

![Figura: Demonstração do painel de erro com o preditor sintético (verdade-base mais ruído gaussiano de 4°), sem modelo de pose](evidencias/a12_gemeo_demo_predictor_ruido.png)

O nó ROS 2 foi testado de ponta a ponta sem Gazebo, reproduzindo poses do *split* de teste. Os tópicos
e nós esperados apareceram, e a pose do efetuador do gêmeo (`twin/base_garra`, descontado o
deslocamento) coincidiu com a da referência no mesmo carimbo de tempo com erro de 4,6×10⁻¹⁶ m. A taxa
observada em `/twin/joint_states` foi de 1,0 a 1,3 Hz para 2 Hz publicados, por perda de quadros de
imagens 1280×720 sem compressão com QoS *best effort* sob carga alta do host.

![Figura: Print do terminal do teste do nó ROS 2 do gêmeo (imagem → /twin/joint_states → TF com prefixo twin/)](evidencias/term_a12_no_ros2_twin.png)

**Como plugar o modelo de pose.** Basta que a frente de pose publique `~/cerise2026/pose/READY.json` e
`~/cerise2026/pose/inferencia/predict.py` com a classe `PosePredictor` cujo método
`predict(rgb, camera)` devolva os ângulos em radianos, e que o servidor seja subido em modo `auto` ou
`pose`. Se o modelo exigir torch e GPU, o servidor deve rodar na imagem da frente de pose
(`IMAGEM=cerise26_pose:latest GPU=1 bash gemeo_digital/subir_servidor.sh pose`). O gráfico de erro e o
erro do efetuador passam então a medir o modelo real.

## 4. Limitações

- **Rótulos do dataset.** As juntas comandadas não são verdade-base em 34,1 % das poses (principalmente
  pelo contato com o chão); deve-se usar `juntas_reais`. Cerca de 2 % das imagens (estimativa em 1.000
  poses) têm silhueta incompatível com as juntas registradas e devem ser filtradas por IoU (o script
  `validar_projecao.py --n 5000` gera a lista completa).
- **Domínio sintético.** Iluminação, materiais e fundo do estúdio são fixos e simplificados, e as malhas
  estão em escala 6. A transferência para o braço físico exigirá randomização de domínio ou ajuste fino
  com imagens reais.
- **Logs da geração.** O reinício para a segunda rodada sobrescreveu `gen_main.log` e `gen_logs/`; a
  linha do tempo foi reconstruída pelos mtimes dos arquivos, e os eventos da primeira rodada vêm das
  observações feitas durante a execução.
- **Dinâmica não calibrada.** O URDF tem massas simbólicas e inércias de preenchimento (1 kg·m²);
  servem para cinemática e visualização, não para simulação dinâmica fiel.
- **Garra no Gazebo.** O Fortress não implementa `mimic` do URDF; só `joint_6` e `joint_7` são
  acionadas, as pinças têm limites [0, 0] e os elos intermediários ficam passivos. A geometria da garra
  nas imagens, portanto, difere da do modelo mimic. O urdf-loader, por sua vez, satura as pinças em 0
  por causa desses limites. Essa diferença responde por parte do erro de silhueta na região da garra.
- **Segmentação.** O braço sai com rótulo 0, o mesmo de regiões sem objeto (céu sem retorno de
  profundidade na câmera diagonal), porque o plugin `Label` no URDF quebrava os controladores. A máscara
  do braço deve ser obtida como rótulo 0 com profundidade válida, critério adotado aqui.
- **Infraestrutura sem modelo.** As capturas e métricas do gêmeo foram obtidas com o oráculo e com o
  preditor sintético. O desempenho do gêmeo com estimação de pose real depende do modelo da outra
  frente.
- **Acesso.** O servidor está restrito ao loopback do Spark e é acessado por túnel SSH local. A exposição
  pública é decisão pendente do Eduardo e não foi feita.

## 5. Próximos passos

1. Integrar o `PosePredictor` assim que a frente de pose publicar `READY.json`, medir o erro por junta e
   do efetuador na sequência de teste e repetir as capturas.
2. Regerar ou filtrar as poses do plano que atravessam o chão, ou incluir o chão como objeto de colisão
   no planejamento, para que juntas comandadas e reais coincidam; manter as juntas reais como rótulo.
3. Corrigir o rótulo de segmentação do braço (por exemplo, `Label` no SDF gerado em vez do URDF) e
   calibrar massas e inércias a partir do CAD ou de medições do braço físico.
4. Conectar o nó ROS 2 do gêmeo ao Gazebo ao vivo (e depois ao braço real), com `image_transport`
   comprimido, e gravar sessões em rosbag para avaliação.
5. Se for decidido expor o visualizador, adotar proxy com autenticação na rede do laboratório em vez de
   abrir portas do Spark.
