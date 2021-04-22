import os
import json
from tqdm import tqdm

from loader.Database import DBViewIndex, DBView, check_target_path
from exporter.Shared import get_valid_filename
from exporter.Adventurers import CharaData
from exporter.Dragons import DragonData


class BattleRoyalCharaSkin(DBView):
    def __init__(self, index):
        super().__init__(index, "BattleRoyalCharaSkin")

    def process_result(self, res, **kwargs):
        self.link(res, "_BaseCharaId", "CharaData", full_query=False)
        self.link(res, "_SpecialSkillId", "SkillData", **kwargs)
        filtered_res = {}
        filtered_res["_Id"] = res["_Id"]
        for name_key in ("_Name", "_NameJP", "_NameCN"):
            filtered_res[name_key] = res["_BaseCharaId"][name_key]
        filtered_res["_SpecialSkillId"] = res["_SpecialSkillId"]
        return filtered_res

    def get(self, *args, **kwargs):
        return self.process_result(super().get(*args, **kwargs), exclude_falsy=True)

    def export_all_to_folder(self, out_dir="./out", ext=".json", exclude_falsy=True):
        where = "_SpecialSkillId != 0"
        out_dir = os.path.join(out_dir, "_br")
        all_res = self.get_all(exclude_falsy=exclude_falsy, where=where)
        check_target_path(out_dir)
        sorted_res = {}
        for res in tqdm(all_res, desc="_br"):
            res = self.process_result(res, exclude_falsy=exclude_falsy)
            sorted_res[res["_Id"]] = res
        out_name = get_valid_filename(f"_chara_skin.json")
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
        self.link(res, "_BaseCharaDataId", "CharaData", **kwargs)
        # self.link(res, "_DragonDataId", "DragonData", **kwargs)
        self.link(res, "_SkillId", "SkillData", **kwargs)
        for ab in range(1, 11):
            self.link(res, f"_ItemAbility{ab:02}", "AbilityData", **kwargs)
        return res

    def get(self, *args, **kwargs):
        return self.process_result(super().get(*args, **kwargs), exclude_falsy=True)

    def export_all_to_folder(self, out_dir="./out", ext=".json", exclude_falsy=True):
        out_dir = os.path.join(out_dir, "_br")
        super().export_all_to_folder(out_dir, ext, exclude_falsy=exclude_falsy)


if __name__ == "__main__":
    index = DBViewIndex()
    view = BattleRoyalUnit(index)
    view.export_all_to_folder()
