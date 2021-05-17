import sys
import os
import json
import pathlib
from collections import defaultdict
from datetime import datetime

from loader.Database import DBViewIndex, DBView, check_target_path
from loader.AssetExtractor import Extractor
from exporter.Shared import (
    SkillData,
    AbilityData,
    MaterialData,
    FortPlantData,
    FortPlantDetail,
)
from exporter.Adventurers import CharaData, ManaCircle, CharaLimitBreak
from exporter.Dragons import DragonData
from exporter.Wyrmprints import (
    AbilityCrest,
    AbilityCrestRarity,
    AbilityCrestBuildupGroup,
    AbilityCrestBuildupLevel,
)
from exporter.Weapons import (
    WeaponBody,
    WeaponBodyRarity,
    WeaponBodyBuildupGroup,
    WeaponBodyBuildupLevel,
    WeaponBodyGroupSeries,
    WeaponPassiveAbility,
)


IMAGE_PATTERNS = {
    "jp": {
        r"^images/icon/chara/l": "../chara",
        r"^images/icon/dragon/l": "../dragon",
        r"^images/icon/amulet/l": "../amulet",
        r"^images/icon/weapon/l": "../weapon",
        r"^images/icon/manacircle": "../manacircle",
        # r'^images/icon/ability/l/': '../ability',
        # r'^images/icon/material/l/': '../material',
        # r'^images/fort/': '../fort',
        # r'^images/icon/skill/ingamel/': '../skill'
    }
}

ability_icons = set()
skill_icons = set()
material_icons = set()
fort_icons = set()


def download_all_icons(out, set_icons=None):
    ex = Extractor(ex_dir=None, ex_img_dir=out)
    ex.download_and_extract_by_pattern(IMAGE_PATTERNS)
    if not set_icons:
        return
    patterns = {"jp": {}}
    for icon_set, prefix, dest in set_icons:
        patterns["jp"][prefix + "(?:" + "|".join(map(str, icon_set)) + ")"] = dest
    ex.download_and_extract_by_pattern(patterns)


def make_bv_id(res, view):
    return f'{res["_BaseId"]}_{res["_VariationId"]:02}'


def make_chara_json(res, index):
    result = {
        "NameEN": res.get("_SecondName") or res.get("_Name"),
        "NameJP": res.get("_SecondNameJP") or res.get("_NameJP"),
        "NameCN": res.get("_SecondNameCN") or res.get("_NameCN"),
        "Element": res.get("_ElementalType"),
        "Weapon": res.get("_WeaponType"),
        "Rarity": res.get("_Rarity"),
        "MaxLimitBreak": res.get("_MaxLimitBreakCount"),
        "LimitBreak": res["_CharaLimitBreak"],
        "MCName": res["_ManaCircleName"],
        "MCEle": res["_PieceMaterialElementId"],
        "Skills": {},
        "Abilities": {},
    }
    result["DefaultLv"] = {
        "Abilities": {i: res.get(f"_DefaultAbility{i}Level") for i in (1, 2, 3)},
        "FS": res.get("_DefaultBurstAttackLevel"),
    }
    for i in (1, 2, 3):
        result["Abilities"][i] = {}
        for j in (1, 2, 3):
            ab_key = f"_Abilities{i}{j}"
            if ab := res.get(ab_key):
                ab = index["AbilityData"].get(ab)
                ab_icon = ab["_AbilityIconName"]
                result["Abilities"][i][j] = ab_icon
                ability_icons.add(ab_icon.lower())
    exability = index["ExAbilityData"].get(res["_ExAbilityData5"])
    result["ExAbility"] = exability["_AbilityIconName"]
    ability_icons.add(exability["_AbilityIconName"].lower())
    for i in (1, 2):
        result["Skills"][i] = {}
        s_key = f"_Skill{i}"
        skill = index["SkillData"].get(res.get(s_key))
        for j in (1, 2, 3, 4):
            s_icon = skill[f"_SkillLv{j}IconName"]
            result["Skills"][i][j] = s_icon
            skill_icons.add(s_icon.lower())
    if (growmat := res.get("_GrowMaterialId")) :
        result["Grow"] = growmat
        growend = res.get("_GrowMaterialOnlyEndDate")
        if growend:
            result["GrowEnd"] = datetime.strptime(growend + " UTC", "%Y/%m/%d %H:%M:%S %Z").timestamp()

        material_icons.add(growmat)
    if (unique1 := res.get("_UniqueGrowMaterialId1")) :
        result["Unique1"] = unique1
        material_icons.add(unique1)
    if (unique2 := res.get("_UniqueGrowMaterialId2")) :
        result["Unique2"] = unique2
        material_icons.add(unique2)
    return result


def make_dragon_json(res, index):
    return {
        "NameEN": res.get("_SecondName") or res.get("_Name"),
        "NameJP": res.get("_SecondNameJP") or res.get("_NameJP"),
        "NameCN": res.get("_SecondNameCN") or res.get("_NameCN"),
        "Element": res.get("_ElementalType"),
        "Rarity": res.get("_Rarity"),
    }


def make_id(res, view):
    return str(res["_Id"])


def make_base_id(res, view):
    return str(res["_BaseId"])


def make_amulet_json(res, index):
    result = {
        "BaseId": res["_BaseId"],
        "NameEN": res.get("_Name"),
        "NameJP": res.get("_NameJP"),
        "NameCN": res.get("_NameCN"),
        "Rarity": res.get("_Rarity"),
        "Form": res["_CrestSlotType"],
        "Cost": res.get("_TradeData", {"_NeedDewPoint": 0})["_NeedDewPoint"],
        "Build": res.get("_AbilityCrestBuildupGroupId"),
        "AbIcon": res["_Abilities13"]["_AbilityIconName"],
    }
    ability_icons.add(res["_Abilities13"]["_AbilityIconName"].lower())
    if uab := res.get("_UnionAbilityGroupId"):
        result["Union"] = uab.get("_Id")
    if res.get("_UniqueBuildupMaterialId"):
        material_icons.add(res.get("_UniqueBuildupMaterialId"))
        result["Unique"] = res.get("_UniqueBuildupMaterialId")
    if res.get("_IsHideChangeImage"):
        result["NoRefine"] = res.get("_IsHideChangeImage")
    return result


def make_material_json(res, index):
    return {
        "NameEN": res.get("_Name"),
        "NameJP": res.get("_NameJP"),
        "NameCN": res.get("_NameCN"),
        "SortId": res.get("_SortId"),
    }


def make_weapon_series_json(res, index):
    return {
        "NameEN": res.get("_GroupSeriesName"),
        "NameJP": res.get("_GroupSeriesNameJP"),
        "NameCN": res.get("_GroupSeriesNameCN"),
    }


from urllib.parse import quote
import requests

MAX = 500
BASE_URL = "https://dragalialost.wiki/api.php?action=cargoquery&format=json&limit={}".format(MAX)


def get_api_request(offset, **kwargs):
    q = "{}&offset={}".format(BASE_URL, offset)
    for key, value in kwargs.items():
        q += "&{}={}".format(key, quote(value))
    return q


def get_data(**kwargs):
    offset = 0
    data = []
    while offset % MAX == 0:
        url = get_api_request(offset, **kwargs)
        r = requests.get(url).json()
        try:
            if len(r["cargoquery"]) == 0:
                break
            data += r["cargoquery"]
            offset += len(r["cargoquery"])
        except:
            raise Exception(url)
    return data


all_avail = {"Chara": set(), "Dragon": {"Gacha"}, "Amulet": set(), "Weapon": set()}


def process_avail(ak):
    def f(a):
        a = a.strip()
        all_avail[ak].add(a)
        return a

    return f


def chara_availability_data(data):
    for d in get_data(
        tables="Adventurers",
        fields="Id,VariationId,Availability",
        where="IsPlayable",
        order_by="Id ASC, VariationId ASC",
    ):
        data[f'{d["title"]["Id"]}_{int(d["title"]["VariationId"]):02}']["Availability"] = list(map(process_avail("Chara"), d["title"]["Availability"].split(",")))


GACHA_DEW = {3: "150", 4: "2200", 5: "8500"}


def dragon_availability_data(data):
    for d in get_data(
        tables="Dragons",
        fields="BaseId,VariationId,SellDewPoint,Availability",
        where="IsPlayable",
        order_by="Id ASC, VariationId ASC",
    ):
        bv_id = f'{d["title"]["BaseId"]}_{int(d["title"]["VariationId"]):02}'
        avail = list(map(process_avail("Dragon"), d["title"]["Availability"].split(",")))
        if d["title"]["SellDewPoint"] == GACHA_DEW[data[bv_id]["Rarity"]]:
            avail.append("Gacha")
        data[bv_id]["Availability"] = avail


def amulet_availability_data(data):

    for d in get_data(
        tables="Wyrmprints",
        fields="Id,Availability",
        where="IsPlayable",
        order_by="Id ASC, VariationId ASC",
    ):
        data[d["title"]["Id"]]["Availability"] = list(map(process_avail("Amulet"), d["title"]["Availability"].split(",")))


def make_json(
    out,
    outfile,
    view,
    id_fn,
    data_fn,
    avail_fn=None,
    where=None,
    order="_Id ASC",
    name_key="_Name",
    process=False,
):
    all_res = view.get_all(where=where, order=order)
    data = {}
    for res in all_res:
        if not res[name_key]:
            continue
        if process:
            res = view.process_result(res)
        data[id_fn(res, view)] = data_fn(res, view.index)
    if avail_fn:
        avail_fn(data)
        for d in data.copy():
            if "Availability" not in data[d]:
                del data[d]
    with open(os.path.join(out, outfile), "w") as f:
        json.dump(data, f)


def make_wpn_id(skin):
    return f'{skin["_BaseId"]}_{skin["_VariationId"]:02}_{skin["_FormId"]}'


BUILDUP_PIECE = {1: "Unbind", 2: "Refine", 3: "Slots", 5: "Bonus", 6: "Copies"}


def get_mats_dict(res, idx_range, k1_fmt, k2_fmt):
    mats = {}
    for i in idx_range:
        k1 = k1_fmt.format(i)
        k2 = k2_fmt.format(i)
        try:
            mats[res[k1]] = res[k2]
            material_icons.add(res[k1])
        except KeyError:
            continue
    return mats


def make_weapon_jsons(out, index):
    rarity_level_mats = defaultdict(dict)
    for row in WeaponBodyBuildupLevel(index).get_all():
        rarity_level_mats[row["_RarityGroup"]][row["_Level"]] = get_mats_dict(row, range(1, 4), "_BuildupMaterialId{}", "_BuildupMaterialQuantity{}")
    rarity_level_mats = dict(rarity_level_mats)
    for rarity, level_mats in rarity_level_mats.items():
        cumulative_mats = {}
        for level in sorted(level_mats.keys()):
            for mat_id, mat_num in level_mats[level].items():
                try:
                    cumulative_mats[mat_id] += mat_num
                except KeyError:
                    cumulative_mats[mat_id] = mat_num
            rarity_level_mats[rarity][level] = dict(cumulative_mats)

    rarity_unbind_level = defaultdict(dict)
    for row in WeaponBodyRarity(index).get_all():
        rarity = row["_Id"]
        if rarity not in rarity_level_mats:
            continue
        for i in range(row["_MaxLimitBreakCountByLimitOver2"] + 1):
            key = f"_MaxLimitLevelByLimitBreak{i}"
            if not row.get(key):
                continue
            rarity_unbind_level[rarity][i] = {
                "Level": row[key],
                "Mats": rarity_level_mats[rarity][row[key]],
            }
    outfile = "weaponlevel.json"
    with open(os.path.join(out, outfile), "w") as f:
        json.dump(dict(rarity_unbind_level), f)

    view = WeaponBodyBuildupGroup(index)
    all_res = view.get_all()
    processed = defaultdict(lambda: defaultdict(list))
    for res in all_res:
        mats = get_mats_dict(res, range(1, 11), "_BuildupMaterialId{}", "_BuildupMaterialQuantity{}")
        # a hack for 7slot
        if res.get("_BuildupPieceType") == 9:
            res["_BuildupPieceType"] = 3
            res["_Step"] += 1
        # lv_req = res.get("_UnlockConditionLevel", 0)
        # ub_req = res.get("_UnlockConditionLimitBreakCount", 0)
        # rf_req = res.get("_UnlockConditionLimitOverCount", 0)
        processed[res.get("_WeaponBodyBuildupGroupId")][res.get("_BuildupPieceType")].append(
            {
                "Step": res.get("_Step"),
                "UnbindReq": res.get("_UnlockConditionLimitBreakCount", 0),
                "SkinId": res.get("_RewardWeaponSkinNo", 0),
                "Cost": res.get("_BuildupCoin"),
                "Mats": mats,
            }
        )
    processed = dict(processed)
    outfile = "weaponbuild.json"
    with open(os.path.join(out, outfile), "w") as f:
        json.dump(processed, f)

    view = WeaponBody(index)
    all_res = view.get_all()
    processed = {}
    for res in all_res:
        if not res.get("_Name") or (not res.get("_WeaponBodyBuildupGroupId") and not res.get("_WeaponPassiveAbilityGroupId")):
            continue

        skins = {}
        for i, sid in enumerate(WeaponBody.WEAPON_SKINS):
            try:
                skin = index["WeaponSkin"].get(res[sid])
                skins[i] = make_wpn_id(skin)
            except (KeyError, TypeError):
                continue
        prereqcreate = [res.get(need) for need in ("_NeedCreateWeaponBodyId1", "_NeedCreateWeaponBodyId2") if res.get(need)]
        prereqfull = res.get("_NeedAllUnlockWeaponBodyId1")
        mats = get_mats_dict(res, range(1, 6), "_CreateEntityId{}", "_CreateEntityQuantity{}")
        passive = None
        if res.get("_WeaponPassiveAbilityGroupId"):
            passive_ab_group = index["WeaponPassiveAbility"].get(
                res.get("_WeaponPassiveAbilityGroupId"),
                by="_WeaponPassiveAbilityGroupId",
            )
            passive = {}
            for p in passive_ab_group:
                ab = index["AbilityData"].get(p.get("_AbilityId"), full_query=False)
                ability_icons.add(ab.get("_AbilityIconName").lower())
                ab_skins = {}
                for i in (1, 2):
                    sid = f"_RewardWeaponSkinId{i}"
                    try:
                        skin = index["WeaponSkin"].get(p[sid])
                        ab_skins[i] = make_wpn_id(skin)
                    except (KeyError, TypeError):
                        continue
                ab_mats = get_mats_dict(p, range(1, 6), "_UnlockMaterialId{}", "_UnlockMaterialQuantity{}")
                ability_val0 = int(ab.get("_AbilityType1UpValue", 0))
                ability_info = {
                    "Icon": ab.get("_AbilityIconName"),
                    "NameEN": ab.get("_Name").format(ability_val0=ability_val0).strip(),
                    "NameJP": ab.get("_NameJP").format(ability_val0=ability_val0).strip(),
                    "NameCN": ab.get("_NameCN").format(ability_val0=ability_val0).strip(),
                }

                passive[p.get("_WeaponPassiveAbilityNo")] = {
                    "UnbindReq": p.get("_UnlockConditionLimitBreakCount", 0),
                    "Ability": ability_info,
                    "Cost": p.get("_UnlockCoin", 0),
                    "Mats": ab_mats,
                    "Skins": ab_skins,
                }

        processed[res.get("_Id")] = {
            "NameEN": res.get("_Name"),
            "NameJP": res.get("_NameJP"),
            "NameCN": res.get("_NameCN"),
            "Series": res.get("_WeaponSeriesId"),
            "Build": res.get("_WeaponBodyBuildupGroupId"),
            "Passive": passive,
            "Element": res.get("_ElementalType"),
            "Weapon": res.get("_WeaponType"),
            "Rarity": res.get("_Rarity"),
            "Prereq": {"Create": prereqcreate, "FullUp": prereqfull},
            "Cost": res.get("_CreateCoin", 0),
            "Mats": mats,
            "Skins": skins,
            # 'Bonus': any([res.get('_WeaponPassiveEffHp'), res.get('_WeaponPassiveEffAtk')]),
        }
    outfile = "weapon.json"
    with open(os.path.join(out, outfile), "w") as f:
        json.dump(processed, f)


def make_fort_jsons(out, index):
    view = FortPlantData(index)
    all_res = view.get_all()
    processed = {}
    for res in all_res:
        res = view.process_result(res)
        flattened_detail = []
        detail = res.get("_DetailId")
        while isinstance(detail, dict):
            if not detail.get("_Level"):
                break
            mats = get_mats_dict(detail, range(1, 6), "_MaterialsId{}", "_MaterialsNum{}")
            flattened_detail.append(
                {
                    "Icon": detail.get("_ImageUiName"),
                    "Level": detail.get("_Level"),
                    "Time": detail.get("_Time", 0),
                    "Cost": detail.get("_Cost", 0),
                    "Mats": mats,
                }
            )
            fort_icons.add(detail.get("_ImageUiName").lower())
            detail = detail.get("_NextAssetGroup")
        if not flattened_detail:
            continue
        processed[res.get("_Id")] = {
            "NameEN": res.get("_Name"),
            "NameJP": res.get("_NameJP"),
            "NameCN": res.get("_NameCN"),
            "Type": res.get("_Type"),
            "Detail": flattened_detail,
        }
    outfile = "fort.json"
    with open(os.path.join(out, outfile), "w") as f:
        json.dump(processed, f)


def make_amulet_jsons(out, index):
    make_json(
        out,
        "amulet.json",
        AbilityCrest(index),
        make_id,
        make_amulet_json,
        amulet_availability_data,
        process=True,
    )

    rarity_level_mats = defaultdict(dict)
    for row in AbilityCrestBuildupLevel(index).get_all():
        mats = get_mats_dict(row, range(1, 4), "_BuildupMaterialId{}", "_BuildupMaterialQuantity{}")
        if uniqc := row.get("_UniqueBuildupMaterialCount"):
            mats["Unique"] = uniqc
        rarity = 9 if row.get("_RarityGroup") == 901 else row.get("_RarityGroup")
        rarity_level_mats[rarity][row.get("_Level")] = mats
    rarity_level_mats = dict(rarity_level_mats)
    for rarity, level_mats in rarity_level_mats.items():
        cumulative_mats = {}
        for level in sorted(level_mats.keys()):
            for mat_id, mat_num in level_mats[level].items():
                try:
                    cumulative_mats[mat_id] += mat_num
                except KeyError:
                    cumulative_mats[mat_id] = mat_num
            rarity_level_mats[rarity][level] = dict(cumulative_mats)

    rarity_level = defaultdict(dict)
    for row in AbilityCrestRarity(index).get_all():
        rarity = row.get("_Id")
        if rarity not in rarity_level_mats:
            continue
        for i in range(5):
            key = f"_MaxLimitLevelByLimitBreak{i}"
            if row[key] == 0:
                continue
            rarity_level[rarity][i] = {
                "Level": row[key],
                "Mats": rarity_level_mats[rarity][row[key]],
            }
    outfile = "amuletlevel.json"
    with open(os.path.join(out, outfile), "w") as f:
        json.dump(dict(rarity_level), f)

    view = AbilityCrestBuildupGroup(index)
    all_res = view.get_all()
    processed = defaultdict(lambda: defaultdict(list))
    for res in all_res:
        mats = get_mats_dict(res, range(1, 4), "_BuildupMaterialId{}", "_BuildupMaterialQuantity{}")
        if uniqc := res.get("_UniqueBuildupMaterialCount"):
            mats["Unique"] = uniqc
        processed[res.get("_AbilityCrestBuildupGroupId")][res.get("_BuildupPieceType")].append(
            {
                "Step": res.get("_Step"),
                # "UnbindReq": res.get("_UnlockConditionLimitBreakCount", 0),
                "Cost": res.get("_BuildupDewPoint", 0),
                "Mats": mats,
            }
        )
    processed = dict(processed)
    outfile = "amuletbuild.json"
    with open(os.path.join(out, outfile), "w") as f:
        json.dump(processed, f)


# class ManaPieceType(Enum):
#     NONE = 0
#     HP = 10101
#     ATK = 10102
#     HP_ATK = 10103
#     BURSTATTACK = 10201
#     ABILITY_1 = 10301
#     ABILITY_2 = 10302
#     ABILITY_3 = 10303
#     SKILL_1 = 10401
#     SKILL_2 = 10402
#     EXABILITY = 10501
#     ITEM_1 = 10601
#     ITEM_2 = 10602
#     COMBO_1 = 10701
#     MAX_LEVEL_5 = 10801


def make_manacircle_jsons(out, index):
    mc_data = defaultdict(dict)
    for row in ManaCircle(index).get_all(where="_Seq != 0"):
        mcn = row["_ManaCircleName"]
        mcs = row["_Seq"]
        if mcs not in mc_data[mcn]:
            mats = {}
            if (unique1 := row.get("_UniqueGrowMaterialCount1")) :
                mats["Unique1"] = unique1
            if (unique2 := row.get("_UniqueGrowMaterialCount2")) :
                mats["Unique2"] = unique2
            mc_data[mcn][mcs] = {
                "Piece": row["_ManaPieceType"],
                "Story": row.get("_IsReleaseStory", 0),
                "Mana": row.get("_NecessaryManaPoint", 0),
                "Hierarchy": row.get("_Hierarchy", 0),
                "No": row.get("_No", 0),
                "Step": row.get("_Step", 0),
                "Mats": mats,
                "Ele": {},
            }
            if (grow := row.get("_GrowMaterialCount")) :
                mc_data[mcn][mcs]["Grow"] = grow
        if mce := row.get("_ElementId"):
            eldwater = row.get("_DewPoint", 0)
            mats = get_mats_dict(row, range(1, 4), "_MaterialId{}", "_MaterialQuantity{}")
            if eldwater or mats:
                mc_data[mcn][mcs]["Ele"][mce] = {
                    "Eldwater": row.get("_DewPoint", 0),
                    "Mats": get_mats_dict(row, range(1, 4), "_MaterialId{}", "_MaterialQuantity{}"),
                }
    mc_data = dict(mc_data)
    outfile = "manacircle.json"
    with open(os.path.join(out, outfile), "w") as f:
        json.dump(mc_data, f)

    chara_lb = {}
    for row in CharaLimitBreak(index).get_all():
        chara_lb[row["_Id"]] = {}
        for i in range(1, 6):
            clb = {}
            clb["Mats"] = get_mats_dict(row, range(1, 6), "_OrbData{}Id" + str(i), "_OrbData{}Num" + str(i))
            if (grow := row.get(f"_GrowMaterialNum{i}")) :
                clb["Grow"] = grow
            chara_lb[row["_Id"]][i] = clb
    outfile = "charalimitbreak.json"
    with open(os.path.join(out, outfile), "w") as f:
        json.dump(chara_lb, f)


if __name__ == "__main__":
    all_avail = {"Chara": set(), "Dragon": {"Gacha"}, "Amulet": set(), "Weapon": set()}
    outdir = os.path.join(pathlib.Path(__file__).parent.absolute(), "..", "..", "dl-collection")
    imgdir = os.path.join(outdir, "public")
    datadir = os.path.join(outdir, "src", "data")
    index = DBViewIndex()

    check_target_path(outdir)

    playable = "_ElementalType != 99 AND _IsPlayable = 1"
    make_json(
        datadir,
        "chara.json",
        CharaData(index),
        make_bv_id,
        make_chara_json,
        chara_availability_data,
        where=playable,
    )
    make_json(
        datadir,
        "dragon.json",
        DragonData(index),
        make_bv_id,
        make_dragon_json,
        dragon_availability_data,
        where=playable,
    )
    make_json(datadir, "material.json", MaterialData(index), make_id, make_material_json)

    make_json(
        datadir,
        "weaponseries.json",
        WeaponBodyGroupSeries(index),
        make_id,
        make_weapon_series_json,
        name_key="_GroupSeriesName",
    )

    make_weapon_jsons(datadir, index)
    make_fort_jsons(datadir, index)
    make_amulet_jsons(datadir, index)
    make_manacircle_jsons(datadir, index)

    with open(os.path.join(datadir, "availabilities.json"), "w") as f:
        json.dump({k: sorted(list(v)) for k, v in all_avail.items()}, f)

    download_all_icons(
        imgdir,
        set_icons=(
            (ability_icons, "images/icon/ability/l/", "../ability"),
            (skill_icons, "images/icon/skill/l/", "../skill"),
            (material_icons, "images/icon/item/materialdata/l/", "../material"),
            (fort_icons, "images/fort/", "../fort"),
        ),
    )
