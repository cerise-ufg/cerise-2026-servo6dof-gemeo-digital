sudo docker run --rm -i -v ~/cerise2026/pose:/workspace/pose:ro cerise26_pose:latest python - <<'PY'
import numpy as np
d = np.load('/workspace/pose/dados/final/index.npz')
for k in d.keys():
    print(k, d[k].shape, d[k].dtype)
perm = np.random.default_rng(2026).permutation(np.arange(1, 5001))
teste = sorted(int(i) for i in perm[4500:])
print("teste[:10]", teste[:10], len(teste))
for k in d.keys():
    if 'teste' in k and ('id' in k):
        v = d[k]; print(k, v[:12])
PY
