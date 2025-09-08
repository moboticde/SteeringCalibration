import os
import yaml

config_path = os.path.join(os.path.dirname(__file__), "..", "resources", "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

def find_config(unit_id):
    folder = os.path.normpath(config["paths"]["product_base"])

    sub_folders = [name for name in os.listdir(folder) if os.path.isdir(os.path.join(folder, name))]
    unit_id1 = unit_id.replace("-", "")
    os.chdir(folder)
    lis = []
    for i in sub_folders:
        j = i.replace("-", "")
        if unit_id1[0] == "D":
            if unit_id1.find(j[0:]) == 0:
                lis.append(i)
        elif "STO" in unit_id1:
            if unit_id1.find(j[0:]) == 0:
                lis.append(i)
        elif "ST" in unit_id1:
            if unit_id1.find(j[0:]) == 0:
                lis.append(i)
        elif unit_id1[0] == "S":  
            if unit_id1.find(j[0:]) == 0:
                lis.append(i)
        else:
            if unit_id1.find(j[2:]) == 0:
                lis.append(i)

    if not lis:                           
        return None

    fol1 = max(lis, key=len)

    os.chdir(fol1)
    curd = os.getcwd()
    sub_folders1 = [name for name in os.listdir(curd) if os.path.isdir(os.path.join(curd, name))]
    unit_id2 = unit_id.replace("-", "")

    for f in sub_folders1:
        k = f.replace("-", "")
        if unit_id2.find(k[2:]) == 0:
            os.chdir(f)
            return os.getcwd()
        elif unit_id[0] == "D":
            if unit_id2.find(k[0:]) == 0:
                os.chdir(f)
                return os.getcwd()
        elif "STO" in unit_id:
            if unit_id2.find(k[0:]) == 0:
                os.chdir(f)
                return os.getcwd()
        elif "ST" in unit_id:
            if unit_id2.find(k[0:]) == 0:
                os.chdir(f)
                return os.getcwd()
        elif unit_id[0] == "S":          
            if unit_id2.find(k[0:]) == 0:
                os.chdir(f)
                return os.getcwd()

    return curd  # fallback if no subfolder matches
