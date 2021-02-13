import json
import os

from loader.Database import DBViewIndex, DBView, DBManager
from exporter.Shared import AbilityData, SkillData, PlayerAction

from exporter.Mappings import CLASS_TYPES


class AmuletData(DBView):
    """deprecated as of 2.0"""

    def __init__(self, index):
        super().__init__(
            index,
            "AmuletData",
            labeled_fields=["_Name", "_Text1", "_Text2", "_Text3", "_Text4", "_Text5"],
        )

    def process_result(self, res, exclude_falsy, full_query=True, full_abilities=False):
        if "_AmuletType" in res:
            res["_AmuletType"] = CLASS_TYPES.get(res["_AmuletType"], res["_AmuletType"])
        inner = (1, 2, 3) if full_abilities else (3,)
        outer = (1, 2, 3)
        for i in outer:
            for j in inner:
                k = f"_Abilities{i}{j}"
                if k in res and res[k]:
                    res[k] = self.index["AbilityData"].get(
                        res[k], full_query=True, exclude_falsy=exclude_falsy
                    )
        return res

    def get(
        self,
        pk,
        by="_Name",
        fields=None,
        exclude_falsy=False,
        full_query=True,
        full_abilities=False,
    ):
        res = super().get(pk, by=by, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        return self.process_result(res, exclude_falsy, full_query, full_abilities)

    @staticmethod
    def outfile_name(res, ext=".json"):
        name = "UNKNOWN" if "_Name" not in res else res["_Name"]
        return f'{res["_BaseId"]}_{res["_VariationId"]:02}_{name}{ext}'

    def export_all_to_folder(self, out_dir="./out", ext=".json", exclude_falsy=True):
        out_dir = os.path.join(out_dir, "wyrmprints")
        super().export_all_to_folder(
            out_dir,
            ext,
            exclude_falsy=exclude_falsy,
            full_query=True,
            full_abilities=False,
        )


class UnionAbility(DBView):
    def __init__(self, index):
        super().__init__(index, "UnionAbility", labeled_fields=["_Name"])

    def process_result(self, res, exclude_falsy):
        for i in (1, 2, 3, 4, 5):
            k = f"_AbilityId{i}"
            if (ab := res.get(k)) :
                res[k] = self.index["AbilityData"].get(
                    ab, full_query=True, exclude_falsy=exclude_falsy
                )
        return res

    def get(
        self,
        pk,
        by=None,
        fields=None,
        order=None,
        mode=DBManager.EXACT,
        exclude_falsy=True,
        expand_one=True,
    ):
        res = super().get(
            pk,
            by=by,
            fields=fields,
            order=order,
            mode=mode,
            exclude_falsy=exclude_falsy,
            expand_one=expand_one,
        )
        return self.process_result(res, exclude_falsy)

    def export_all_to_folder(self, out_dir="./out", ext=".json", exclude_falsy=True):
        processed_res = [
            self.process_result(res, exclude_falsy=exclude_falsy)
            for res in self.get_all(exclude_falsy=exclude_falsy)
        ]
        with open(
            os.path.join(out_dir, f"_union{ext}"), "w", newline="", encoding="utf-8"
        ) as fp:
            json.dump(processed_res, fp, indent=2, ensure_ascii=False, default=str)


class AbilityCrest(DBView):
    def __init__(self, index):
        super().__init__(
            index,
            "AbilityCrest",
            labeled_fields=["_Name", "_Text1", "_Text2", "_Text3", "_Text4", "_Text5"],
        )

    def process_result(self, res, exclude_falsy, full_abilities=False):
        inner = (1, 2, 3) if full_abilities else (3,)
        outer = (1, 2, 3)
        for i in outer:
            for j in inner:
                k = f"_Abilities{i}{j}"
                if k in res and res[k]:
                    res[k] = self.index["AbilityData"].get(
                        res[k], full_query=True, exclude_falsy=exclude_falsy
                    )
        if uab := res.get("_UnionAbilityGroupId"):
            res["_UnionAbilityGroupId"] = self.index["UnionAbility"].get(uab)
        return res

    def get(
        self,
        pk,
        by="_Name",
        fields=None,
        exclude_falsy=False,
        full_query=True,
        full_abilities=False,
    ):
        res = super().get(pk, by=by, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        return self.process_result(res, exclude_falsy, full_abilities)

    @staticmethod
    def outfile_name(res, ext=".json"):
        name = "UNKNOWN" if "_Name" not in res else res["_Name"]
        return f'{res["_BaseId"]}_{res["_VariationId"]:02}_{name}{ext}'

    def export_all_to_folder(self, out_dir="./out", ext=".json", exclude_falsy=True):
        out_dir = os.path.join(out_dir, "wyrmprints")
        super().export_all_to_folder(
            out_dir, ext, exclude_falsy=exclude_falsy, full_abilities=False
        )


if __name__ == "__main__":
    index = DBViewIndex()
    view = AbilityCrest(index)
    view.export_all_to_folder()
