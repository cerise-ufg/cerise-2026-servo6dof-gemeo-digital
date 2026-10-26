# Artefatos grandes (GitHub Releases)

Os datasets completos e as saídas brutas da integração não são versionados no git (são dezenas de
milhares de PNGs, ~5 GB no total). Eles estão anexados ao Release **`dados-2026-10-26`** deste
repositório, em arquivos `.tar` sem compressão (os PNGs já são comprimidos), cada um com menos de 1,9 GB.

Cada parte de dataset é **independente**: contém uma faixa de ids e pode ser extraída sozinha. Os
arquivos auxiliares da pasta (`index.csv` e `poses_registradas_w0..7.csv`) vão nas duas partes; extrair as
duas partes na mesma pasta reconstrói a pasta original completa (35.009 arquivos).

| Arquivo | Tamanho | SHA-256 | Conteúdo |
|---|---|---|---|
| `dataset_cinza.part01.tar` | 1.288.212.480 B (1,29 GB) | `77b42478225b55654e7f01ab1250d5f5599f8f5403e9be2e216171996064034e` | dataset do relatório (braço cinza-alumínio), poses 000001–002500: 2.500 JSON + 15.000 PNG + 9 auxiliares |
| `dataset_cinza.part02.tar` | 1.285.918.720 B (1,29 GB) | `15adc58418dcdb515e41201745cfcc2afa07b97b1360b0c6ce562be24997db35` | dataset do relatório, poses 002501–005000: 2.500 JSON + 15.000 PNG + 9 auxiliares |
| `dataset_laranja.part01.tar` | 1.272.893.440 B (1,27 GB) | `6fbbf9d94a5d1f1eaaccbaa5f2c0d18ed17dbbb2faac32052e466a60148c3c6c` | variante com o braço laranja (mesmas poses), 000001–002500 |
| `dataset_laranja.part02.tar` | 1.271.121.920 B (1,27 GB) | `f72eea5eaed4853dffc58eecdb5eab5a95421e16c1ea2620ed94318eab11e8dd` | variante laranja, 002501–005000 |
| `gemeo_integracao_quadros_brutos.tar` | 35.153.920 B (35 MB) | `73f211a066637fe768e9e264149d95742a4aed168b4ae90fb7374050af77af85` | 148 quadros PNG capturados do front-end do gêmeo (A12): `varredura/` e `varredura_cam/` (72 + 72 quadros que geraram os MP4/GIF de `evidencias/`) e `teste_smoke/` (4) |
| `dataset_cinza.manifest.sha256` | 4.015.930 B | `ae052bcf91fd1e937bf939c99ace95ec48263f4d50a80787642274f8c65ab2e3` | SHA-256 de cada um dos 35.009 arquivos da pasta `dataset_cinza/` |
| `dataset_laranja.manifest.sha256` | 4.085.948 B | `ed95c3a8ddd27c72bfab5cdb0fde2c2d676b7a7e79b501b37ec0f43c17ffd5a1` | SHA-256 de cada um dos 35.009 arquivos da pasta `dataset_laranja/` |
| `SHA256SUMS.txt` | — | — | SHA-256 de todos os arquivos acima |

Cada `.tar` cria uma pasta de topo: `dataset_cinza/`, `dataset_laranja/` ou `quadros_brutos/`.
Formato dos arquivos do dataset: `docs/DATASET.md`. A versão **cinza** é a usada em todas as análises e
números do relatório; a **laranja** é uma segunda renderização das mesmas 5.000 poses
(`dataset_tools/variante_laranja/LEIAME.md`).

## Como baixar, conferir e extrair

```bash
# baixar (GitHub CLI; troque <org> pelo nome da organização)
gh release download dados-2026-10-26 -R <org>/cerise-2026-servo6dof-gemeo-digital -D dados
cd dados

# conferir a integridade dos arquivos baixados
sha256sum -c SHA256SUMS.txt          # Linux/WSL;  macOS: shasum -a 256 -c SHA256SUMS.txt

# extrair (cada parte é independente; as duas juntas formam a pasta completa)
tar -xf dataset_cinza.part01.tar
tar -xf dataset_cinza.part02.tar     # -> dataset_cinza/ com 35.009 arquivos

# conferir arquivo por arquivo depois de extrair
sha256sum -c dataset_cinza.manifest.sha256
```

No Windows, `tar -xf` funciona no PowerShell (bsdtar nativo) e `Get-FileHash -Algorithm SHA256 <arquivo>`
confere os hashes.

## Procedência e verificação

- Os dois datasets foram gerados no DGX Spark (`~/braco/dataset_cinza` e `~/braco/dataset`) e copiados para
  a estação de trabalho; antes do empacotamento, os SHA-256 dos 35.009 arquivos de cada pasta foram
  calculados nas duas máquinas e coincidiram integralmente.
- Depois do empacotamento, cada membro dos `.tar` foi relido e conferido contra o manifesto (35.009 de
  35.009 arquivos por dataset, sem divergência).
- Para regenerar o dataset em vez de baixá-lo: `README.md`, seção "Geração do dataset".
