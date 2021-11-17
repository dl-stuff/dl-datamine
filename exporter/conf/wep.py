import os
from tqdm import tqdm

from loader.Database import check_target_path
from exporter.Weapons import WeaponBody
from exporter.Shared import snakey
from exporter.Mappings import ELEMENTS, WEAPON_TYPES

from exporter.conf.common import SDat, SkillProcessHelper, remap_stuff, fmt_conf


class WepConf(WeaponBody, SkillProcessHelper):
    def process_result(self, res):
        self.reset_meta()
        self.set_ability_and_actcond_meta()
        self.set_animation_reference(res)

        ablist = []
        for i in (1, 2, 3):
            for j in (3, 2, 1):
                ab = res.get(f"_Abilities{i}{j}")
                if ability := self.index["AbilityConf"].get(ab, source=f"ability{i}"):
                    ablist.extend(ability)
                break

        self.link(res, "_WeaponSkinId", "WeaponSkin")
        skin = res["_WeaponSkinId"]
        tier = res.get("_MaxLimitOverCount", 0) + 1
        try:
            ele_type = ELEMENTS.get(res["_ElementalType"], res["_ElementalType"]).lower()
        except (AttributeError, TypeError):
            ele_type = "any"
        self.link(res, "_WeaponSeriesId", "WeaponBodyGroupSeries")
        conf = {
            "w": {
                "name": res["_Name"],
                "icon": f'{skin["_BaseId"]}_{skin["_VariationId"]:02}_{skin["_FormId"]}',
                "att": res.get(f"_MaxAtk{tier}", 0),
                "hp": res.get(f"_MaxHp{tier}", 0),
                "ele": ele_type,
                "wt": WEAPON_TYPES[res["_WeaponType"]].lower(),
                "series": res["_WeaponSeriesId"]["_GroupSeriesName"].replace(" Weapons", ""),
                # 'crest': {
                #     5: res.get('_CrestSlotType1MaxCount', 0),
                #     4: res.get('_CrestSlotType2MaxCount', 0)
                # },
                "tier": tier,
                "abilities": ablist
                # 'skipped': skipped
            }
        }

        for base, group, key in (("s3", None, "_ChangeSkillId3"),):
            if not (sid := res.get(key)):
                continue
            self.chara_skills[sid] = SDat(sid, base, group)

        self.process_skill(res, conf, {})

        remap_stuff(conf, self.action_ids)
        self.unset_ability_and_actcond_meta(conf)
        self.index["ActionParts"].animation_reference = None

        return conf

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        all_res = self.get_all(where="_IsPlayable = 1")
        out_dir = os.path.join(out_dir, "wep")
        check_target_path(out_dir)
        outdata = {wt.lower(): {ele.lower(): {} for ele in ("any", *ELEMENTS.values())} for wt in WEAPON_TYPES.values()}
        # skipped = []
        for res in tqdm(all_res, desc=os.path.basename(out_dir)):
            conf = self.process_result(res)
            # outfile = snakey(conf['d']['ele']) + '.json'
            if conf:
                outdata[conf["w"]["wt"]][conf["w"]["ele"]][snakey(conf["w"]["series"]).lower()] = conf
        for wt, data in outdata.items():
            output = os.path.join(out_dir, f"{wt}.json")
            with open(output, "w", newline="", encoding="utf-8") as fp:
                fmt_conf(data, f=fp, lim=4)
        #     else:
        #         skipped.append(res["_Name"])
        # print('Skipped:', ','.join(skipped))
