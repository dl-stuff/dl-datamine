import os
from glob import glob
import json

from loader.AssetExtractor import Extractor

GEN = "./out/gen"
DST = "../dl/www/dl-sim/pic"
OUTPUT = "../dl/www/dl-sim/pic/index.json"

if __name__ == "__main__":
    pic_index = {
        "Weapon": {"name": "Weapon", "icon": "icons/weaponskill.png", "link": "<NO>"},
        "Axe2": {"name": "Critical Damage +30%", "icon": "coabs/Axe2.png", "link": "Critical_Damage_+30%_(Co-ability)"},
        "Blade": {"name": "Strength +10%", "icon": "coabs/Blade.png", "link": "Strength_+10%_(Co-ability)"},
        "Bow": {"name": "Skill Haste +15%", "icon": "coabs/Bow.png", "link": "Skill_Haste_+15%_(Co-ability)"},
        "Dagger": {"name": "Critical Rate +10%", "icon": "coabs/Dagger.png", "link": "Critical_Rate_+10%_(Co-ability)"},
        "Dagger2": {"name": "Standard Attack Damage +20%", "icon": "coabs/Dagger2.png", "link": "Standard_Attack_Damage_+20%"},
        "Lance": {"name": "HP +15%", "icon": "coabs/Lance.png", "link": "HP_+15%_(Co-ability)"},
        "Gun": {"name": "Gauge Accelerator +20%", "icon": "coabs/Gun.png", "link": "Gauge_Accelerator_+20%_(Co-ability)"},
        "Sword": {"name": "Dragon Haste +15%", "icon": "coabs/Sword.png", "link": "Dragon_Haste_+15%_(Co-ability)"},
        "Staff": {"name": "Recovery Potency +20%", "icon": "coabs/Staff.png", "link": "Recovery_Potency_+20%_(Co-ability)"},
        "Wand": {"name": "Skill Damage +15%", "icon": "coabs/Wand.png", "link": "Skill_Damage_+15%_(Co-ability)"},
        "Wand2": {
            "name": "Overdrive Punisher +15%\nGauge Accelerator +10%",
            "icon": "coabs/Wand2.png",
            "link": "Overdrive_Punisher_&_Gauge_Accelerator_VIII",
        },
        "Empty_6": {"name": "Empty 6", "icon": "icons/formC.png", "link": "<NO>"},
        "Empty_7": {"name": "Empty 7", "icon": "icons/formC.png", "link": "<NO>"},
    }
    ex = Extractor(ex_dir=None, ex_img_dir=DST)
    patterns = {"jp": {}}
    icon_set = set()
    with open(os.path.join(GEN, "wyrmprints.json"), "r") as fn:
        for wp, data in json.load(fn).items():
            pic_index[wp] = {"name": data["name"], "icon": f"amulet/{data['icon']}.png"}
            if data["union"] > 0:
                pic_index[wp]["deco"] = f"union/{data['union']:02}.png"
            icon_set.add(data["icon"])
    patterns["jp"]["^images/icon/amulet/l/" + "(?:" + "|".join(map(str, icon_set)) + ")"] = f"../amulet"

    icon_set = set()
    for data_path in glob(GEN + "/drg/*/*.json"):
        with open(data_path, "r") as fn:
            data = json.load(fn)
            name = os.path.splitext(os.path.basename(data_path))[0]
            pic_index[name] = {"name": data["d"]["name"], "icon": f"dragon/{data['d']['icon']}.png"}
            icon_set.add(data["d"]["icon"])
    patterns["jp"]["^images/icon/dragon/l/" + "(?:" + "|".join(map(str, icon_set)) + ")"] = f"../dragon"

    icon_set = set()
    for data_path in glob(GEN + "/wep/*.json"):
        with open(data_path, "r") as fn:
            for elewt in json.load(fn).values():
                for wep, data in elewt.items():
                    pic_index[f"{data['w']['wt']}-{data['w']['ele']}-{wep}"] = {"name": data["w"]["name"], "icon": f"weapon/{data['w']['icon']}.png"}
                    icon_set.add(data["w"]["icon"])
    patterns["jp"]["^images/icon/weapon/l/" + "(?:" + "|".join(map(str, icon_set)) + ")"] = f"../weapon"

    icon_set = set()
    for data_path in glob(GEN + "/adv/*/*.json"):
        with open(data_path, "r") as fn:
            data = json.load(fn)
            name = os.path.splitext(os.path.basename(data_path))[0]
            name = name.split(".")[0]
            pic_index[name] = {"name": data["c"]["name"], "icon": f"character/{data['c']['icon']}.png"}
            icon_set.add(data["c"]["icon"])
    patterns["jp"]["^images/icon/chara/l/" + "(?:" + "|".join(map(str, icon_set)) + ")"] = f"../character"

    with open(OUTPUT, "w") as fn:
        json.dump(pic_index, fn, separators=(",", ":"))
    ex.download_and_extract_by_pattern(patterns)
