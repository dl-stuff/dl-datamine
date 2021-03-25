from loader.Database import DBManager
from exporter.Mappings import ELEMENTS, WEAPON_TYPES

COUNT_WEAPON_BONUS = "SELECT _WeaponType, SUM(_WeaponPassiveEffAtk) AS _Bonus FROM WeaponBody GROUP BY _WeaponType"

COUNT_ADV_BY_MAX_LIMIT_BREAK = "SELECT _ElementalType, COUNT(_Id) as _Count FROM CharaData WHERE _MaxLimitBreakCount=? GROUP BY _ElementalType;"
COUNT_DRG = "SELECT _ElementalType, COUNT(_Id) as _Count FROM DragonData GROUP BY _ElementalType"

ALBUM_BONUS_ADV = {4: 0.2, 5: 0.3}
ALBUM_BONUS_DRG = 0.2

if __name__ == "__main__":
    dbm = DBManager()
    adv_ele_passives = {ele: 0 for ele in ELEMENTS.values()}
    for mlb, factor in ALBUM_BONUS_ADV.items():
        for res in dbm.query_many(COUNT_ADV_BY_MAX_LIMIT_BREAK, (mlb,), dict):
            try:
                elename = ELEMENTS[res["_ElementalType"]]
            except KeyError:
                continue
            adv_ele_passives[elename] += res["_Count"] * factor

    adv_wep_passives = {wep: 0 for wep in WEAPON_TYPES.values()}
    for res in dbm.query_many(COUNT_WEAPON_BONUS, tuple(), dict):
        try:
            wepname = WEAPON_TYPES[res["_WeaponType"]]
        except KeyError:
            continue
        adv_wep_passives[wepname] += res["_Bonus"]

    print("=Adventurer Bonus=")
    for ele, bonus in adv_ele_passives.items():
        print(f"{ele}:\t{bonus/100:.3f}")
    print("")
    for wep, bonus in adv_wep_passives.items():
        print(f"{wep}:\t{bonus/100:.3f}")

    drg_passives = {ele: 0 for ele in ELEMENTS.values()}
    for res in dbm.query_many(COUNT_DRG, tuple(), dict):
        try:
            elename = ELEMENTS[res["_ElementalType"]]
        except KeyError:
            continue
        drg_passives[elename] += res["_Count"] * ALBUM_BONUS_DRG

    print("")
    print("=Dragon Bonus=")
    for ele, bonus in drg_passives.items():
        print(f"{ele}:\t{bonus/100:.3f}")
