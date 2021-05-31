import os
import itertools
from glob import glob
from tqdm import tqdm
import shutil

from loader.Database import DBManager, DBTableMetadata, DBViewIndex
from exporter.Shared import AbnormalStatusType
from exporter.FortPassives import count_fort_passives

AbnormalStatusType(DBViewIndex())  # just to create the view bolb

SIM_TABLE_LIST = (
    "AbilityCrest",
    "AbilityData",
    "ExAbilityData",
    "ActionCondition",
    "ActionGrant",
    "AuraData",
    "CharaData",
    "CharaModeData",
    "CharaUniqueCombo",
    "DragonData",
    "SkillData",
    "WeaponBody",
    "WeaponType",
    "PlayerAction",
    "PlayerActionHitAttribute",
    "UnionAbility",
    "EnemyParam",
    "MotionData",
    "BuffCountData",
    "AbnormalStatusType",
)

DL9_DB = "../dl9/core/conf.sqlite"


def transfer_sim_db(dl_sim_db):
    db = DBManager()
    db.transfer(dl_sim_db, SIM_TABLE_LIST)
    db = DBManager(DL9_DB)
    adv_ele_passives, adv_wep_passives, drg_passives = count_fort_passives(include_album=True)
    halidom_data = []
    for elebonus, wepbonus in itertools.product(adv_ele_passives.items(), adv_wep_passives.items()):
        halidom_data.append(
            {
                "form": 1,
                "ele": elebonus[0][0],
                "wep": wepbonus[0][0],
                "hp": elebonus[1][0] + wepbonus[1][0],
                "atk": elebonus[1][1] + wepbonus[1][1],
            }
        )
    for drgbonus in drg_passives.items():
        halidom_data.append(
            {
                "form": 2,
                "ele": drgbonus[0][0],
                "wep": None,
                "hp": drgbonus[1][0],
                "atk": drgbonus[1][1],
            }
        )
    meta = DBTableMetadata("HalidomBonus")
    meta.init_from_row(halidom_data[0], auto_pk=True)
    db.create_table(meta)
    db.insert_many(meta.name, halidom_data)


def transfer_actions_json(output_dir, actions_dir):
    for filename in tqdm(glob(actions_dir + "/PlayerAction_*.json"), desc="copy_actions"):
        shutil.copy(filename, os.path.join(output_dir, os.path.basename(filename)))


if __name__ == "__main__":
    if os.path.exists(DL9_DB):
        os.remove(DL9_DB)
    transfer_sim_db(DL9_DB)
    transfer_actions_json("../dl9/action/data", "./_ex_sim/jp/actions")
