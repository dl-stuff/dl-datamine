import shutil
from glob import glob

from loader.Database import DBManager

SIM_TABLE_LIST = (
    "AbilityCrest",
    "AbilityData",
    "AbilityLimitedGroup",
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
    "TextLabel",
    "PlayerAction",
    "PlayerActionHitAttribute",
)


def transfer_sim_db(dl_sim_db):
    db = DBManager()
    db.transfer(dl_sim_db, SIM_TABLE_LIST)


def transfer_actions(actions_dir, dl_sim_act_dir):
    for filename in glob(actions_dir + "/PlayerAction*.json"):
        shutil.copy(filename, dl_sim_act_dir)


if __name__ == "__main__":
    transfer_sim_db("../dl9/conf.sqlite")
    transfer_actions("./_ex_sim/jp/actions", "../dl9/actions")