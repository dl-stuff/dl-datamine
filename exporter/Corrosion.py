from tqdm import tqdm
import json

from loader.Database import DBViewIndex
from exporter.Enemy import EnemyParam
from exporter.Shared import snakey


def export_corrosion_data():
    index = DBViewIndex()
    view = EnemyParam(index)
    all_corrosion_data = {}
    all_res = view.get_all(where="_ParamGroupName LIKE 'DIABOLOS_%'")
    for res in tqdm(all_res, desc="enemies"):
        res = view.process_result(res)
        action_set = res["_ActionSet"]
        corrosion_data = {}
        for key, value in action_set.items():
            if not isinstance(value, dict):
                continue
            if not isinstance((action_group := value.get("_ActionGroupName")), dict):
                continue
            is_corrosion = False
            for hitattr in action_group.values():
                if not isinstance(hitattr, dict) or not (act_cond := hitattr.get("_ActionCondition")):
                    continue
                if act_cond.get("_UniqueIcon") == 96:
                    is_corrosion = True
            if is_corrosion:
                corrosion_data[key] = value
        if corrosion_data:
            key = snakey(f'{res.get("_ParamGroupName", "UNKNOWN")}_{res.get("_Name")}')
            all_corrosion_data[key] = corrosion_data
    with open("corrosion.json", "w") as fn:
        json.dump(all_corrosion_data, fn, indent=2, ensure_ascii=False)


if __name__ == "__main__":
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
