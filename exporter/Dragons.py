import json
import os
from tabulate import tabulate

from loader.Database import DBViewIndex, DBView, DBDict, DBManager
from exporter.Shared import AbilityData, SkillData, PlayerAction


class DragonMotion(DBView):
    def __init__(self, index):
        super().__init__(index, "DragonMotion")

    def get_by_state_ref(self, state, ref):
        tbl = self.database.check_table(self.name)
        query = f"SELECT {tbl.named_fields} FROM {self.name} WHERE {self.name}.state=? AND {self.name}.ref=?;"
        return self.database.query_many(query=query, param=(state, ref), d_type=DBDict)


class DragonData(DBView):
    ACTIONS = ["_AvoidActionFront", "_AvoidActionBack", "_Transform"]

    def __init__(self, index):
        super().__init__(
            index,
            "DragonData",
            labeled_fields=["_Name", "_SecondName", "_Profile", "_CvInfo", "_CvInfoEn"],
        )

    def process_result(self, res, full_abilities=False):
        if "_AnimFileName" in res and res["_AnimFileName"]:
            anim_key = int(res["_AnimFileName"][1:].replace("_", ""))
        else:
            anim_key = int(f'{res["_BaseId"]}{res["_VariationId"]:02}')
        self.index["ActionParts"].animation_reference = ("DragonMotion", anim_key)
        for s in ("_Skill1", "_Skill2", "_SkillFinalAttack"):
            try:
                res[s] = self.index["SkillData"].get(res[s], full_abilities=full_abilities)
            except:
                pass
        inner = (1, 2, 3, 4, 5) if full_abilities else (5,)
        outer = (1, 2)
        for i in outer:
            for j in inner:
                k = f"_Abilities{i}{j}"
                if k in res and res[k]:
                    res[k] = self.index["AbilityData"].get(res[k], full_query=True)
        for act in self.ACTIONS:
            if act in res:
                res[act] = self.index["PlayerAction"].get(res[act])
        if "_DefaultSkill" in res and res["_DefaultSkill"]:
            base_action_id = res["_DefaultSkill"]
            res["_DefaultSkill"] = [self.index["PlayerAction"].get(base_action_id + i) for i in range(0, res["_ComboMax"])]
        self.index["ActionParts"].animation_reference = None
        return res

    def get(self, pk, by=None, fields=None, full_query=True, full_abilities=False):
        if by is None:
            res = super().get(pk, by="_SecondName", fields=fields, mode=DBManager.LIKE)
            if not res:
                res = super().get(pk, by="_Name", fields=fields, mode=DBManager.LIKE)
                if not res:
                    res = super().get(pk, by="_Id", fields=fields, mode=DBManager.LIKE)
        else:
            res = super().get(pk, by=by, fields=fields, mode=DBManager.LIKE)
        if not full_query:
            return res
        return self.process_result(res, full_abilities=full_abilities)

    @staticmethod
    def outfile_name(res, ext=".json"):
        name = "UNKNOWN" if "_Name" not in res else res["_Name"] if "_SecondName" not in res else res["_SecondName"]
        if (emblem := res.get("_EmblemId")) and emblem != res["_Id"]:
            return f'{res["_Id"]:02}_{name}{ext}'
        return f'{res["_BaseId"]}_{res["_VariationId"]:02}_{name}{ext}'

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        out_dir = os.path.join(out_dir, "dragons")
        super().export_all_to_folder(out_dir, ext, full_abilities=False)


if __name__ == "__main__":
    index = DBViewIndex()
    view = DragonData(index)
    view.export_all_to_folder()
