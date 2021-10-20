import os
from collections import defaultdict
from tqdm import tqdm

from loader.Database import check_target_path
from exporter.Shared import snakey
from exporter.Wyrmprints import AbilityCrest

from exporter.conf.common import fmt_conf


class WpConf(AbilityCrest):
    def __init__(self, index):
        super().__init__(index)
        self.boon_names = {res["_Id"]: res["_Name"] for res in self.index["UnionAbility"].get_all()}

    def process_result(self, res):
        self.index["AbilityConf"].set_meta(None, use_ablim_groups=True)
        ablist = []
        for i in (1, 2, 3):
            ab = res.get(f"_Abilities{i}3")
            if ability := self.index["AbilityConf"].get(ab, source=f"ability{i}"):
                ablist.extend(ability)

        boon = res.get("_UnionAbilityGroupId", 0)
        if not boon and not ablist:
            return

        if res.get("_IsHideChangeImage"):
            icon = f'{res["_BaseId"]}_01'
        else:
            icon = f'{res["_BaseId"]}_02'
        conf = {
            "name": res["_Name"].strip(),
            "icon": icon,
            "att": res["_MaxAtk"],
            "hp": res["_MaxHp"],
            "rarity": res["_CrestSlotType"],
            "union": boon,
            "abilities": ablist,
        }

        self.index["AbilityConf"].set_meta(None, use_ablim_groups=False)
        return conf

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        all_res = self.get_all()
        check_target_path(out_dir)
        self.index["ActionCondition"].set_kind("wyrmprints")
        outdata = {}
        skipped = []
        collisions = defaultdict(list)
        for res in tqdm(all_res, desc="wp"):
            conf = self.process_result(
                res,
            )
            if conf:
                qual_name = snakey(res["_Name"])
                if qual_name in outdata:
                    collisions[qual_name].append(outdata[qual_name])
                    collisions[qual_name].append(conf)
                else:
                    outdata[qual_name] = conf
            else:
                skipped.append((res["_BaseId"], res["_Name"]))
                # skipped.append(res["_Name"])
        for qual_name, duplicates in collisions.items():
            if len({dupe["union"] for dupe in duplicates}) == len(duplicates):
                for dupe in duplicates:
                    dupe["name"] = f"{dupe['name']} ({self.boon_names[dupe['union']]})"
                    outdata[snakey(dupe["name"].replace("'s Boon", ""))] = dupe
                del outdata[qual_name]
            else:
                print(f"Check dupe {qual_name}")
        output = os.path.join(out_dir, "wyrmprints.json")
        with open(output, "w", newline="", encoding="utf-8") as fp:
            # json.dump(res, fp, indent=2, ensure_ascii=False)
            fmt_conf(outdata, f=fp)
            fp.write("\n")
        # print('Skipped:', skipped)
        self.index["ActionCondition"].export_all_to_folder(out_dir)

    def get(self, name):
        res = super().get(name, full_query=False)
        if isinstance(res, list):
            res = res[0]
        return self.process_result(res)
