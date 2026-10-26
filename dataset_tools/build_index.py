import csv,glob,json,os,sys
d=sys.argv[1]
js=sorted(glob.glob(os.path.join(d,"[0-9]"*6+".json")))
rows=[]
for f in js:
    a=json.load(open(f))
    jc=a.get("juntas_comandadas",{}); g=a.get("garra_comandada",{})
    row={"id":a["id"]}
    for j in ["joint_1","joint_2","joint_3","joint_4","joint_5"]:
        row[j]=jc.get(j,"")
    row["joint_6"]=list(g.values())[0] if g else ""
    row["imagens"]=";".join(sorted(c["arquivo"] for c in a.get("cameras",{}).values()))
    rows.append(row)
rows.sort(key=lambda r:r["id"])
with open(os.path.join(d,"index.csv"),"w",newline="") as fo:
    w=csv.DictWriter(fo,fieldnames=["id","joint_1","joint_2","joint_3","joint_4","joint_5","joint_6","imagens"])
    w.writeheader(); w.writerows(rows)
print("index.csv reconstruido:",len(rows),"poses")
