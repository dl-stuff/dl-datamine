from loader.Database import DBManager
from exporter.Mappings import ELEMENTS, WEAPON_TYPES

COUNT_WEAPON_BONUS = "SELECT _WeaponType, SUM(_WeaponPassiveEffAtk) AS _Bonus FROM WeaponBody GROUP BY _WeaponType"

COUNT_ADV_BY_MAX_LIMIT_BREAK = "SELECT _ElementalType, COUNT(_Id) as _Count FROM CharaData WHERE _MaxLimitBreakCount=? AND _IsPlayable GROUP BY _ElementalType"
COUNT_DRG = "SELECT _ElementalType, COUNT(_Id) as _Count FROM DragonData WHERE _IsPlayable GROUP BY _ElementalType"

COUNT_HALIDOM = """SELECT View_FortPlantData._Name,
FortPlantDetail._AssetGroup, FortPlantDetail._EffectId, FortPlantDetail._EffType1, FortPlantDetail._EffType2,
MAX(FortPlantDetail._EffArgs1) AS _EffArgs1, MAX(FortPlantDetail._EffArgs2) AS _EffArgs2, MAX(FortPlantDetail._EffArgs3) AS _EffArgs3
FROM FortPlantDetail
INNER JOIN View_FortPlantData ON View_FortPlantData._Id=FortPlantDetail._AssetGroup
WHERE _EffectId=1 OR _EffectId=2 OR _EffectId=6
GROUP BY (_AssetGroup)"""

ALBUM_BONUS_ADV = {4: 0.2, 5: 0.3}
ALBUM_BONUS_DRG = 0.2

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
                adv_ele_passives[(eletype, elename)][0] += res["_Count"] * factor
                adv_ele_passives[(eletype, elename)][1] += res["_Count"] * factor

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
        for res in dbm.query_many(COUNT_DRG, tuple(), dict):
            try:
                eletype = res["_ElementalType"]
                elename = ELEMENTS[eletype]
            except KeyError:
                continue
            drg_passives[(eletype, elename)][0] += res["_Count"] * ALBUM_BONUS_DRG
            drg_passives[(eletype, elename)][1] += res["_Count"] * ALBUM_BONUS_DRG

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


if __name__ == "__main__":
    adv_ele_passives, adv_wep_passives, drg_passives = count_fort_passives(include_album=True)

    print("===Adventurer Bonus===")
    for ele, bonus in adv_ele_passives.items():
        hp, atk = bonus
        print(f"{ele[1]}:\t{hp:.1f}% {atk:.1f}%")
    print()
    for wep, bonus in adv_wep_passives.items():
        hp, atk = bonus
        print(f"{wep[1]}:\t{hp:.1f}% {atk:.1f}%")
    print("")
    print("===Dragon Bonus===")
    for ele, bonus in drg_passives.items():
        hp, atk = bonus
        print(f"{ele[1]}:\t{hp:.1f}% {atk:.1f}%")
