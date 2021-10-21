import os
from collections import defaultdict
from tqdm import tqdm

from loader.Database import check_target_path
from exporter.Shared import snakey
from exporter.Wyrmprints import AbilityCrest

from exporter.conf.common import fmt_conf


# CREATE TABLE UnionAbility (_Id INTEGER PRIMARY KEY,_Name TEXT,_IconEffect TEXT,_SortId INTEGER,_CrestGroup1Count1 INTEGER,_AbilityId1 INTEGER,_PartyPower1 INTEGER,_CrestGroup1Count2 INTEGER,_AbilityId2 INTEGER,_PartyPower2 INTEGER,_CrestGroup1Count3 INTEGER,_AbilityId3 INTEGER,_PartyPower3 INTEGER,_CrestGroup1Count4 INTEGER,_AbilityId4 INTEGER,_PartyPower4 INTEGER,_CrestGroup1Count5 INTEGER,_AbilityId5 INTEGER,_PartyPower5 INTEGER)


class WpConf(AbilityCrest):
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
        # union
        union_abilities = self.index["UnionAbility"].get_all()
        union_names = {res["_Id"]: res["_Name"] for res in union_abilities}

        all_res = self.get_all()
        check_target_path(out_dir)
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
                    dupe["name"] = f"{dupe['name']} ({union_names[dupe['union']]})"
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

        union_conf = {}
        for res in tqdm(union_abilities, desc="wp"):
            union_tiers = {}
            for i in range(1, 6):
                if (abid := res.get(f"_AbilityId{i}")) and (ability := self.index["AbilityConf"].get(abid, source="union")):
                    union_tiers[res[f"_CrestGroup1Count{i}"]] = ability
            union_conf[res["_Id"]] = union_tiers

    def get(self, name):
        res = super().get(name, full_query=False)
        if isinstance(res, list):
            res = res[0]
        return self.process_result(res)
