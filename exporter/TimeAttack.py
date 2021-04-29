from PIL import Image
import os
import json
import requests
from tqdm import tqdm
from collections import defaultdict

from loader.AssetExtractor import Extractor
from loader.Database import DBManager

TIMEATTACK_URL = "https://dragalialost.com/api/index.php?lang=en_us&type=event_web&action=ranking_data&quest_id={quest_id}"
OUTPUT_DIR = "_timeattack"
ICON_PATTERNS = {
    "jp": {
        r"^images/icon/chara/m/.+r05$": "../resources/chara",
        r"^images/icon/dragon/m": "../resources/dragon",
        r"^images/icon/amulet/m": "../resources/amulet",
    }
}
QUERY_CHARA_NAME = "SELECT _Name, _SecondName FROM View_CharaData WHERE _BaseId=? AND _VariationId=?"
QUERY_DRAGON_NAME = "SELECT _Name, _SecondName FROM View_DragonData WHERE _BaseId=? AND _VariationId=?"
QUERY_AMULET_NAME = "SELECT _Name FROM View_AbilityCrest WHERE _BaseId=?"


def calculate_percent_difference(i1, i2):
    if i1.mode != i2.mode:
        return 100
    if i1.size != i2.size:
        return 100

    pairs = zip(i1.getdata(), i2.getdata())
    if len(i1.getbands()) == 1:
        # for gray-scale jpegs
        dif = sum(abs(p1 - p2) for p1, p2 in pairs)
    else:
        dif = sum(abs(c1 - c2) for p1, p2 in pairs for c1, c2 in zip(p1, p2))

    ncomponents = i1.size[0] * i1.size[1] * 3
    return (dif / 255.0 * 100) / ncomponents


def compare_remote_to_local(img_url, category):
    i1 = Image.open(requests.get(img_url, stream=True).raw)
    category_dir = os.path.join(OUTPUT_DIR, "resources", category)
    for target in os.listdir(category_dir):
        i2 = Image.open(os.path.join(category_dir, target))
        if calculate_percent_difference(i1, i2) < 5:
            return target
    raise RuntimeError(f"no match found for {img_url}")


def query_name_from_icon(img_url, category, query, dbm, seen_icons):
    icon = compare_remote_to_local(img_url, category)
    icon_name, _ = os.path.splitext(icon)
    parts = icon_name.split("_")
    if category == "amulet":
        base_id = parts[0]
        query_res = dbm.query_one(query, (base_id,), dict)
        if not query_res:
            raise RuntimeError(f"{base_id} not found in {category}")
        name = query_res["_Name"]
    else:
        base_id = parts[0]
        var_id = parts[1]
        query_res = dbm.query_one(query, (base_id, var_id), dict)
        if not query_res:
            raise RuntimeError(f"{base_id, var_id} not found in {category}")
        name = query_res["_SecondName"] or query_res["_Name"]
    seen_icons[img_url] = name
    return name


def convert_player_slots(player_slots, dbm, seen_icons):
    chara_img = player_slots["chara_img"]
    try:
        player_slots["chara_name"] = seen_icons[chara_img]
    except KeyError:
        player_slots["chara_name"] = query_name_from_icon(chara_img, "chara", QUERY_CHARA_NAME, dbm, seen_icons)

    dragon_img = player_slots["dragon_img"]
    try:
        player_slots["dragon_name"] = seen_icons[dragon_img]
    except KeyError:
        player_slots["dragon_name"] = query_name_from_icon(dragon_img, "dragon", QUERY_DRAGON_NAME, dbm, seen_icons)

    for amulet_slot in player_slots["amulet"]:
        amulet_img = amulet_slot["img"]
        try:
            amulet_slot["name"] = seen_icons[amulet_img]
        except KeyError:
            amulet_slot["name"] = query_name_from_icon(amulet_img, "amulet", QUERY_AMULET_NAME, dbm, seen_icons)


def get_timeattack_data(quest_id):
    response = requests.get(TIMEATTACK_URL.format(quest_id=quest_id))
    if response.status_code != 200:
        return
    res_json = response.json()
    if res_json["data_headers"]["result_code"] == 0:
        return
    data = res_json["data"]
    timestamp = data["ranking"]["update_time"]
    raw_outfile = os.path.join(OUTPUT_DIR, f"{quest_id}_raw_{timestamp}.json")
    with open(raw_outfile, "w") as fn:
        json.dump(data, fn, indent=2, ensure_ascii=False, sort_keys=True)
    print(f"Wrote {raw_outfile}")
    dbm = DBManager()
    iconmap_outfile = os.path.join(OUTPUT_DIR, f"iconmap_{timestamp}.json")
    if os.path.isfile(iconmap_outfile):
        with open(iconmap_outfile, "r") as fn:
            seen_icons = json.load(fn)
    else:
        seen_icons = {"": "Empty"}
    for entry in tqdm(data["ranking"]["ranking_data"], desc="icon to names"):
        for player_slots in entry["player_list"]:
            convert_player_slots(player_slots, dbm, seen_icons)
    converted_outfile = os.path.join(OUTPUT_DIR, f"{quest_id}_converted_{timestamp}.json")
    with open(converted_outfile, "w") as fn:
        json.dump(data, fn, indent=2, ensure_ascii=False, sort_keys=True)
    print(f"Wrote {converted_outfile}")

    with open(iconmap_outfile, "w") as fn:
        json.dump(seen_icons, fn, indent=2, sort_keys=True)
    print(f"Wrote {iconmap_outfile}")
    dbm.close()

    return timestamp


def prepare_icons():
    ex = Extractor(ex_dir=OUTPUT_DIR, ex_img_dir=OUTPUT_DIR, stdout_log=False, overwrite=False, mf_mode=0)
    ex.download_and_extract_by_pattern(ICON_PATTERNS)


def value_sort(item):
    return -item[1]


def weighted_usage_data(quest_id, timestamp, weigh_by_rank=True):
    with open(os.path.join(OUTPUT_DIR, f"{quest_id}_converted_{timestamp}.json"), "r") as fn:
        data = json.load(fn)
    chara_usage = defaultdict(float)
    dragon_usage = defaultdict(float)
    amulet_usage = defaultdict(float)
    total_rank = len(data["ranking"]["ranking_data"])
    for entry in data["ranking"]["ranking_data"]:
        rank = int(entry["rank"])
        if weigh_by_rank:
            weight = (total_rank + 1 - rank) / total_rank
        else:
            weight = 1
        for player in entry["player_list"]:
            chara_usage[player["chara_name"]] += weight
            dragon_usage[player["dragon_name"]] += weight
            for amulet in player["amulet"]:
                amulet_usage[amulet["name"]] += weight
    weighted = {
        "chara": dict(sorted(chara_usage.items(), key=value_sort)),
        "dragon": dict(sorted(dragon_usage.items(), key=value_sort)),
        "amulet": dict(sorted(amulet_usage.items(), key=value_sort)),
    }
    prefix = "weighted" if weigh_by_rank else "usage"
    weighted_outfile = os.path.join(OUTPUT_DIR, f"{quest_id}_{prefix}_{timestamp}.json")
    with open(weighted_outfile, "w") as fn:
        json.dump(weighted, fn, indent=2, ensure_ascii=False)
    print(f"Wrote {weighted_outfile}")


# 227030104 tart solo
# 227030105 tart coop
if __name__ == "__main__":
    quest_id = 227030105
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # prepare_icons()
    timestamp = get_timeattack_data(quest_id)
    weighted_usage_data(quest_id, timestamp)
    weighted_usage_data(quest_id, timestamp, weigh_by_rank=False)
