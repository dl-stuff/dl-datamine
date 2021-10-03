import os
import json
from tqdm import tqdm

from loader.Database import DBViewIndex, DBView, check_target_path
from exporter.Shared import snakey
from exporter.Adventurers import CharaData
from exporter.Dragons import DragonData


class BattleRoyalCharaSkin(DBView):
    def __init__(self, index):
        super().__init__(index, "BattleRoyalCharaSkin")

    def process_result(self, res, **kwargs):
        self.link(res, "_BaseCharaId", "CharaData", full_query=False)
        self.index["CharaData"].set_animation_reference(res["_BaseCharaId"])
        self.link(res, "_SpecialSkillId", "SkillData", **kwargs)
        self.index["ActionParts"].animation_reference
        filtered_res = {}
        filtered_res["_Id"] = res["_Id"]
        for name_key in ("_Name", "_NameJP", "_NameCN"):
            filtered_res[name_key] = res["_BaseCharaId"][name_key]
        filtered_res["_SpecialSkillId"] = res["_SpecialSkillId"]
        return filtered_res

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        where = "_SpecialSkillId != 0"
        out_dir = os.path.join(out_dir, "_br")
        all_res = self.get_all(where=where)
        check_target_path(out_dir)
        sorted_res = {}
        for res in tqdm(all_res, desc="_br"):
            res = self.process_result(res)
            sorted_res[res["_Id"]] = res
        out_name = snakey(f"_chara_skin.json")
        output = os.path.join(out_dir, out_name)
        with open(output, "w", newline="", encoding="utf-8") as fp:
            json.dump(sorted_res, fp, indent=2, ensure_ascii=False, default=str)


class BattleRoyalUnit(DBView):
    def __init__(self, index):
        super().__init__(index, "BattleRoyalUnit")

    @staticmethod
    def outfile_name(res, ext=".json"):
        c_res = res["_BaseCharaDataId"]
        name = "UNKNOWN" if "_Name" not in c_res else c_res["_Name"] if "_SecondName" not in c_res else c_res["_SecondName"]
        return f'{res["_Id"]}_{name}{ext}'

    def process_result(self, res, **kwargs):
        self.link(res, "_BaseCharaDataId", "CharaData", condense=False)
        # self.link(res, "_DragonDataId", "DragonData", **kwargs)
        self.link(res, "_SkillId", "SkillData", **kwargs)
        for ab in range(1, 11):
            self.link(res, f"_ItemAbility{ab:02}", "AbilityData", **kwargs)
        return res

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        out_dir = os.path.join(out_dir, "_br")
        super().export_all_to_folder(out_dir, ext)


if __name__ == "__main__":
    index = DBViewIndex()
    view = BattleRoyalUnit(index)
    view.export_all_to_folder()
