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
    "TextLabel",
    "ActionParts",
    "ActionPartsHitLabel",
    "PlayerAction",
    "PlayerActionHitAttribute",
)


def transfer_sim_db(dl_sim_db):
    db = DBManager()
    db.transfer(dl_sim_db, SIM_TABLE_LIST)


if __name__ == "__main__":
    transfer_sim_db("../dl9/conf.sqlite")