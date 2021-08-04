from tqdm import tqdm
import json

from loader.Database import DBViewIndex
from exporter.Enemy import EnemyParam
from exporter.Shared import snakey


def find_enemy_actionset_data(output_name, check_condition, res_where=None):
    index = DBViewIndex()
    view = EnemyParam(index)
    all_data = {}
    all_res = view.get_all(where=res_where)
    for res in tqdm(all_res, desc="enemies"):
        res = view.process_result(res)
        sub_data = {}
        for as_key in EnemyParam.ACTION_SETS:
            if not (action_set := res.get(as_key)):
                continue
            if isinstance(action_set, int):
                if not (action_set := index["EnemyActionSet"].get(as_key)):
                    continue
            for key, value in action_set.items():
                if not isinstance(value, dict):
                    continue
                if not isinstance((action_group := value.get("_ActionGroupName")), dict):
                    continue
                is_data = False
                for hitattr in action_group.values():
                    if not isinstance(hitattr, dict) or not (act_cond := hitattr.get("_ActionCondition")):
                        continue
                    if check_condition(act_cond):
                        is_data = True
                if is_data:
                    sub_data[f"{as_key}{key}"] = value
        if sub_data:
            key = snakey(f'{res.get("_ParamGroupName", "UNKNOWN")}_{res.get("_Name")}')
            all_data[key] = sub_data
    with open(f"{output_name}.json", "w") as fn:
        json.dump(all_data, fn, indent=2, ensure_ascii=False)


def export_nihility_data():
    find_enemy_actionset_data("nihility", lambda act_cond: act_cond.get("_CurseOfEmptiness"))


def export_corrosion_data():
    # res_where="_ParamGroupName LIKE 'DIABOLOS_%'"
    find_enemy_actionset_data("corrosion", lambda act_cond: act_cond.get("_UniqueIcon") == 96)


if __name__ == "__main__":
    export_nihility_data()
    export_corrosion_data()

# "_Id": 1602,
# "_Text": "Creeping Corrosion",
# "_TextJP": "侵蝕",
# "_TextCN": "侵蚀",
# "_UniqueIcon": 96,
# "_UnifiedManagement": 2,
# "_Rate": 100,
# "_DebuffCategory": 1,
# "_SlipDamageIntervalSec": 3.0,
# "_SlipDamageRatio": 0.09000000357627869,
# "_SlipDamageGroup": 1,
# "_RateIncreaseByTime": 0.30000001192092896,
# "_RateIncreaseDuration": 12.199999809265137,
# "_ValidSlipHp": -1.0,
# "_RequiredRecoverHp": 4500,
# "_RateGetHpRecovery": -0.30000001192092896
