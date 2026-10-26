ls ~/cerise2026/gemeo/repo/gemeo_digital/servidor/static/
du -sh ~/cerise2026/gemeo/repo/gemeo_digital/servidor/static/vendor
python3 - <<'PY'
import numpy as np
d = np.load('/home/energiainteligente/cerise2026/pose/dados/final/index.npz')
for k in d.keys():
    print(k, d[k].shape, d[k].dtype)
PY
sudo docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' | grep -E 'cerise26|playwright|servo6dof'
which ffmpeg; sudo docker run --rm cerise26_gemeo:latest bash -c 'which ffmpeg rviz2 Xvfb xvfb-run import xwd convert 2>&1; ls /opt/ros/humble/lib | grep -i rviz | head -3'
