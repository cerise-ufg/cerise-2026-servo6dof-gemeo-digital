import numpy as np, json
from PIL import Image
for i in [1, 2, 3]:
    for cam in ["camera_frontal", "camera_diagonal"]:
        for mod in ["image", "depth", "segmentation_labels_map"]:
            p = "/dataset/%06d_%s_%s.png" % (i, cam, mod)
            im = Image.open(p)
            a = np.asarray(im)
            info = (im.mode, a.shape, a.dtype, int(a.min()), int(a.max()))
            if mod == "segmentation_labels_map":
                u, c = np.unique(a.reshape(-1, a.shape[-1]) if a.ndim == 3 else a.reshape(-1), axis=0, return_counts=True)
                info += (list(zip([tuple(x) if np.ndim(x) else x for x in u.tolist()], c.tolist()))[:8],)
            if mod == "depth":
                nz = a[a > 0]
                info += ("nz frac %.3f" % (nz.size / a.size), int(nz.min()) if nz.size else 0, int(np.median(nz)) if nz.size else 0)
            print(i, cam, mod, info)
d = json.load(open("/dataset/000002.json")); print(d["juntas_comandadas"], d["juntas_reais"])
