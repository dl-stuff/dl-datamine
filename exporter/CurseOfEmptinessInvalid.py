from collections import defaultdict
from pprint import pprint

from loader.Database import DBViewIndex

from exporter.Shared import ActionCondition
from exporter.Mappings import AFFLICTION_TYPES


METADATA_FIELDS = (
    "_Id",
    "_Text",
    "_TextJP",
    "_TextCN",
    "_TextEx",
    "_TextExJP",
    "_TextExCN",
    "_Type",
    "_BlockExaustFlag",
    "_InternalFlag",
    "_UniqueIcon",
    "_ResistBuffReset",
    "_ResistDebuffReset",
    "_UnifiedManagement",
    "_Overwrite",
    "_OverwriteIdenticalOwner",
    "_OverwriteGroupId",
    "_MaxDuplicatedCount",
    "_UsePowerUpEffect",
    "_NotUseStartEffect",
    "_StartEffectCommon",
    "_StartEffectAdd",
    "_LostOnDragon",
    "_RestoreOnReborn",
    "_EfficacyType",
    "_DebuffCategory",
    "_RemoveDebuffCategory",
    "_Rate",
    "_DurationSec",
    "_DurationNum",
    "_MinDurationSec",
    "_DurationTimeScale",
    "_IsAddDurationNum",
    "_MaxDurationNum",
    "_CoolDownTimeSec",
    "_RemoveAciton",
    "_LevelUpId",
    "_LevelDownId",
    "_ExcludeFromBuffExtension",
    "_CurseOfEmptinessInvalid",
    "_SlipDamageIntervalSec",
    "_ValidSlipHp",
    "_AdditionAttackHitEffect",
)


def get_identifying_name(res, value=0):
    if isinstance(value, float):
        value = round(value, 2)
    idx = res["_Id"]
    if (text := res.get("_Text")) :
        return f"{idx}-{text}: {value}"
    elif (text := res.get("_TextEx")) :
        return f"{idx}-{text}: {value}"
    elif (text := AFFLICTION_TYPES.get(res.get("_Type"))) :
        return f"{idx}-{text}: {value}"
    return f"{idx}: {value}"


if __name__ == "__main__":
    index = DBViewIndex()
    view = ActionCondition(index)
    all_res = view.get_all(exclude_falsy=True)
    counters = defaultdict(lambda: {0: [], 1: []})
    for res in all_res:
        flag = res.get("_CurseOfEmptinessInvalid", 0)
        for key, value in res.items():
            if key not in METADATA_FIELDS:
                counters[key][flag].append(get_identifying_name(res, value))
    # pprint(dict(counters))
    for key, data in counters.items():
        print(f"=========={key}==========")
        print(f"Not Invalid: {len(data[0])}")
        pprint(data[0])
        print(f"Invalid: {len(data[1])}")
        pprint(data[1])
