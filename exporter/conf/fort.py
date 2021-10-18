import os

from loader.Database import DBViewIndex, DBManager
from exporter.Shared import FortPlantData
from exporter.Mappings import ELEMENTS, WEAPON_TYPES

from exporter.conf.common import fmt_conf

# dum
FortPlantData(DBViewIndex())

COUNT_WEAPON_BONUS = "SELECT _WeaponType, SUM(_WeaponPassiveEffAtk) AS _Bonus FROM WeaponBody GROUP BY _WeaponType"

COUNT_ADV_BY_MAX_LIMIT_BREAK = "SELECT _ElementalType, COUNT(_Id) as _Count FROM CharaData WHERE _MaxLimitBreakCount=? AND _IsPlayable GROUP BY _ElementalType"
COUNT_DRG_BY_MAX_LIMIT_BREAK = "SELECT _ElementalType, COUNT(_Id) as _Count FROM DragonData WHERE _MaxLimitBreakCount=? AND _IsPlayable GROUP BY _ElementalType"

COUNT_HALIDOM = """SELECT View_FortPlantData._Name,
FortPlantDetail._AssetGroup, FortPlantDetail._EffectId, FortPlantDetail._EffType1, FortPlantDetail._EffType2,
MAX(FortPlantDetail._EffArgs1) AS _EffArgs1, MAX(FortPlantDetail._EffArgs2) AS _EffArgs2, MAX(FortPlantDetail._EffArgs3) AS _EffArgs3
FROM FortPlantDetail
INNER JOIN View_FortPlantData ON View_FortPlantData._Id=FortPlantDetail._AssetGroup
WHERE _EffectId=1 OR _EffectId=2 OR _EffectId=6
GROUP BY (_AssetGroup)"""

ALBUM_BONUS_ADV = {4: 0.2, 5: 0.3}
ALBUM_BONUS_DRG = {4: {"hp": 0.2, "atk": 0.2}, 5: {"hp": 0.3, "atk": 0.2}}

# SELECT View_FortPlantData._Name, FortPlantDetail._EffectId, FortPlantDetail._EffType1, FortPlantDetail._EffType2, FortPlantDetail._EffArgs1, FortPlantDetail._EffArgs2, FortPlantDetail._EffArgs3
# FROM View_FortPlantData
# INNER JOIN FortPlantDetail ON View_FortPlantData._DetailId=FortPlantDetail._Id


def count_fort_passives(include_album=True):
    dbm = DBManager()
    adv_ele_passives = {(idx, ele): [0, 0] for idx, ele in ELEMENTS.items()}
    if include_album:
        for mlb, factor in ALBUM_BONUS_ADV.items():
            for res in dbm.query_many(COUNT_ADV_BY_MAX_LIMIT_BREAK, (mlb,), dict):
                try:
                    eletype = res["_ElementalType"]
                    elename = ELEMENTS[eletype]
                except KeyError:
                    continue
                adv_ele_passives[(eletype, elename)][0] += round(res["_Count"] * factor, 1)
                adv_ele_passives[(eletype, elename)][1] += round(res["_Count"] * factor, 1)

    adv_wep_passives = {(idx, wep): [0, 0] for idx, wep in WEAPON_TYPES.items()}
    for res in dbm.query_many(COUNT_WEAPON_BONUS, tuple(), dict):
        try:
            weptype = res["_WeaponType"]
            wepname = WEAPON_TYPES[weptype]
        except KeyError:
            continue
        adv_wep_passives[(weptype, wepname)][0] += res["_Bonus"]
        adv_wep_passives[(weptype, wepname)][1] += res["_Bonus"]

    drg_passives = {(idx, ele): [0, 0] for idx, ele in ELEMENTS.items()}
    if include_album:
        for mlb, factor in ALBUM_BONUS_DRG.items():
            for res in dbm.query_many(COUNT_DRG_BY_MAX_LIMIT_BREAK, (mlb,), dict):
                try:
                    eletype = res["_ElementalType"]
                    elename = ELEMENTS[eletype]
                except KeyError:
                    continue
                drg_passives[(eletype, elename)][0] += round(res["_Count"] * factor["hp"], 1)
                drg_passives[(eletype, elename)][1] += round(res["_Count"] * factor["atk"], 1)

    for res in dbm.query_many(COUNT_HALIDOM, (), dict):
        if res["_EffectId"] == 1:
            passive_dict = adv_wep_passives
            passive_types = WEAPON_TYPES
        elif res["_EffectId"] == 2:
            passive_dict = adv_ele_passives
            passive_types = ELEMENTS
        elif res["_EffectId"] == 6:
            passive_dict = drg_passives
            passive_types = ELEMENTS
        mult = 1
        if "Altar" in res["_Name"] or "Dojo" in res["_Name"]:
            mult = 2
        for eff in (res["_EffType1"], res["_EffType2"]):
            if not eff:
                continue
            passive_dict[(eff, passive_types[eff])][0] += res["_EffArgs1"] * mult
            passive_dict[(eff, passive_types[eff])][1] += res["_EffArgs2"] * mult

    return adv_ele_passives, adv_wep_passives, drg_passives


def to_jsonable(passives):
    jsonable = {"hp": {}, "att": {}}
    for key, bonus in passives.items():
        jsonable["hp"][key[1].lower()] = bonus[0]
        jsonable["att"][key[1].lower()] = bonus[1]
    return jsonable


def write_fort_passives(out_dir):
    fort_passives = {}
    for key, album in (("album_true", True), ("album_false", False)):
        adv_ele_passives, adv_wep_passives, drg_passives = count_fort_passives(include_album=album)
        fort_passives[key] = {
            "ele": to_jsonable(adv_ele_passives),
            "wep": to_jsonable(adv_wep_passives),
            "drg": to_jsonable(drg_passives),
        }
        out_path = os.path.join(out_dir, "fort.json")
        with open(out_path, "w") as fn:
            fmt_conf(fort_passives, f=fn)
            fn.write("\n")
