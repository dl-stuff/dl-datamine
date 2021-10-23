import collections
import json
import os
from tqdm import tqdm

from loader.Database import DBViewIndex, DBView, DBManager, check_target_path
from exporter.Shared import AbilityData, SkillData, PlayerAction, snakey

from exporter.Mappings import CLASS_TYPES


class UnionAbility(DBView):
    def __init__(self, index):
        super().__init__(index, "UnionAbility", labeled_fields=["_Name"])

    def process_result(self, res):
        for i in (1, 2, 3, 4, 5):
            self.link(res, f"_AbilityId{i}", "AbilityData")
        return res

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        processed_res = [self.process_result(res) for res in self.get_all()]
        with open(os.path.join(out_dir, f"_union{ext}"), "w", newline="", encoding="utf-8") as fp:
            json.dump(processed_res, fp, indent=2, ensure_ascii=False, default=str)


class AbilityCrestBuildupGroup(DBView):
    def __init__(self, index):
        super().__init__(index, "AbilityCrestBuildupGroup")


class AbilityCrestBuildupLevel(DBView):
    def __init__(self, index):
        super().__init__(index, "AbilityCrestBuildupLevel")


class AbilityCrestRarity(DBView):
    def __init__(self, index):
        super().__init__(index, "AbilityCrestRarity")


class AbilityCrestTrade(DBView):
    def __init__(self, index):
        super().__init__(index, "AbilityCrestTrade")


class AbilityCrest(DBView):
    def __init__(self, index):
        super().__init__(
            index,
            "AbilityCrest",
            labeled_fields=["_Name", "_Text1", "_Text2", "_Text3", "_Text4", "_Text5"],
        )

    def process_result(self, res, full_abilities=False):
        inner = (1, 2, 3) if full_abilities else (3,)
        outer = (1, 2, 3)
        for i in outer:
            for j in inner:
                k = f"_Abilities{i}{j}"
                if k in res and res[k]:
                    res[k] = self.index["AbilityData"].get(res[k], full_query=True)
        if uab := res.get("_UnionAbilityGroupId"):
            res["_UnionAbilityGroupId"] = self.index["UnionAbility"].get(uab)
        if trade_data := self.index["AbilityCrestTrade"].get(res["_Id"], by="_AbilityCrestId"):
            res["_TradeData"] = trade_data
        return res

    def get(self, pk, by="_Name", fields=None, full_query=True, full_abilities=False):
        res = super().get(pk, by=by, fields=fields)
        if not full_query:
            return res
        return self.process_result(res, full_abilities)

    @staticmethod
    def outfile_name(res, ext=".json"):
        name = "UNKNOWN" if "_Name" not in res else res["_Name"]
        # FIXME: do better name sanitation here
        return snakey(f'{res["_BaseId"]}_{res["_VariationId"]:02}_{name}{ext}')

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        out_dir = os.path.join(out_dir, "wyrmprints")
        all_res = self.get_all()
        check_target_path(out_dir)
        duplicates = collections.defaultdict(list)
        for res in all_res:
            duplicates[self.outfile_name(res, ext)].append(res)
        for out_name, res_list in tqdm(duplicates.items(), desc=os.path.basename(out_dir)):
            res_list = [self.process_result(res) for res in res_list]
            main_res = res_list[0]
            main_res_id = main_res["_Id"]
            if len(res_list) > 1:
                keys_that_differ = set()
                id_to_sub_res = {}
                for sub_res in res_list[1:]:
                    id_to_sub_res[sub_res["_Id"]] = sub_res
                    for key in sub_res:
                        if sub_res[key] != main_res[key]:
                            keys_that_differ.add(key)
                for key in keys_that_differ:
                    main_res[key] = {main_res_id: main_res[key]}
                    for sub_res_id, sub_res in id_to_sub_res.items():
                        main_res[key][sub_res_id] = sub_res[key]
            output = os.path.join(out_dir, out_name)
            with open(output, "w", newline="", encoding="utf-8") as fp:
                json.dump(main_res, fp, indent=2, ensure_ascii=False, default=str)


if __name__ == "__main__":
    index = DBViewIndex()
    view = AbilityCrest(index)
    view.export_all_to_folder()
