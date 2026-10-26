import json, os, sys
d = sys.argv[1]
ids = json.load(open(os.path.join(d, "amostra.json")))["poses"]
keep = {"amostra.json", "index_amostra.csv"}
for i in ids:
    keep.add("%06d.json" % i)
    for c in ("camera_frontal", "camera_diagonal"):
        for m in ("image", "depth", "segmentation_labels_map"):
            keep.add("%06d_%s_%s.png" % (i, c, m))
rm = [f for f in os.listdir(d) if f not in keep]
for f in rm:
    os.remove(os.path.join(d, f))
tot = sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d))
print("removidos", len(rm), "restam", len(os.listdir(d)), "bytes", tot, "poses", ids)
