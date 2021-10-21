import re
import os
from tqdm import tqdm

from exporter.Shared import snakey
from exporter.Dragons import DragonData
from exporter.Mappings import ELEMENTS

from exporter.conf.common import SkillProcessHelper, convert_all_hitattr, convert_fs, convert_x, hit_sr, hitattr_adj, remap_stuff, check_target_path, fmt_conf


class DrgConf(DragonData, SkillProcessHelper):
    EXTRA_DRAGONS = (
        20050102,
        20050202,
        20050302,
        20050402,
        20050502,
        20050507,
    )
    COMMON_ACTIONS = {"dodge": {}, "dodgeb": {}, "dshift": {}}
    COMMON_ACTIONS_DEFAULTS = {
        # recovery only
        "dodge": 0.66667,
        "dodgeb": 0.66667,
        "dshift": 0.69444,
    }

    def convert_skill(self, k, seq, skill, lv):
        conf, k, action = super().convert_skill(k, seq, skill, lv)
        conf["sp_db"] = skill.get("_SpLv2Dragon", 45)
        conf["uses"] = skill.get("_MaxUseNum", 1)
        if self.hitattrshift:
            del conf["attr"]
            hitattr_adj(action, conf["startup"], conf, pattern=re.compile(f".*\d_LV0{lv}.*"))
            hitattr_adj(action, conf["startup"], conf, pattern=re.compile(f".*\d(_HAS)?_LV0{lv}.*"), attr_key="attr_HAS")
        else:
            try:
                attr = conf["attr"]
                del conf["attr"]
                conf["attr"] = attr
            except KeyError:
                pass
        return conf, k, action

    def process_result(self, res, hitattrshift=False, mlvl=None, uniqueshift=False):
        self.reset_meta()
        self.hitattrshift = hitattrshift

        max_lb = res.get("_MaxLimitBreakCount", 4)
        att = res["_MaxAtk"]
        hp = res["_MaxHp"]
        if max_lb == 5:
            ab_seq = 6
            att = res.get("_AddMaxAtk1", 0)
            hp = res.get("_AddMaxHp1", 0)
        else:
            ab_seq = 5

        conf = {}
        if not uniqueshift:
            ablist = []
            self.set_ability_and_actcond_meta()
            for i in (1, 2):
                if (ab := res.get(f"_Abilities{i}{ab_seq}")) and (ability := self.index["AbilityConf"].get(ab, source=f"ability{i}")):
                    ablist.extend(ability)
            conf["d"] = {
                "name": res.get("_SecondName", res.get("_Name")),
                "icon": f'{res["_BaseId"]}_{res["_VariationId"]:02}',
                "att": att,
                "hp": hp,
                "ele": ELEMENTS.get(res["_ElementalType"]).lower(),
            }
            conf["d"]["abilities"] = ablist

        super().process_result(res)
        # if skipped:
        #     conf['d']['skipped'] = skipped

        for act, key in (
            ("dodgeb", "_AvoidActionBack"),
            ("dodge", "_AvoidActionFront"),
            ("dshift", "_Transform"),
        ):
            try:
                s, r, _ = hit_sr(res[key], startup=0.0, explicit_any=False)
            except KeyError:
                continue
                # try:
                #     DrgConf.COMMON_ACTIONS[act][tuple(actconf['attr'][0].items())].add(conf['d']['name'])
                # except KeyError:
                #     DrgConf.COMMON_ACTIONS[act][tuple(actconf['attr'][0].items())] = {conf['d']['name']}
            actconf = {}
            if DrgConf.COMMON_ACTIONS_DEFAULTS[act] != r:
                actconf = {"recovery": r}
            if act == "dshift":
                hitattrs = convert_all_hitattr(res[key])
                if hitattrs and (len(hitattrs) > 1 or hitattrs[0]["dmg"] != 2.0 or set(hitattrs[0].keys()) != {"dmg"}):
                    actconf["attr"] = hitattrs
                if hitattrshift:
                    if hitattrs := convert_all_hitattr(res[key], pattern=re.compile(r".*_HAS")):
                        actconf["attr_HAS"] = hitattrs
            if actconf:
                conf[act] = actconf

            self.action_ids[res[key]["_Id"]] = act

        if burst := res.get("_BurstAttack"):
            conf.update(convert_fs(burst, burst.get("_BurstMarkerId"), is_dragon=True))
            self.action_ids[burst["_Id"]] = "dfs"

        if "dodgeb" in conf:
            if "dodge" not in conf or conf["dodge"]["recovery"] > conf["dodgeb"]["recovery"]:
                conf["dodge"] = conf["dodgeb"]
                conf["dodge"]["backdash"] = True
            del conf["dodgeb"]

        dcombo = res["_DefaultSkill"]
        dcmax = res["_ComboMax"]
        for n, xn in enumerate(dcombo):
            n += 1
            xn_key = f"dx{n}"
            if dxconf := convert_x(xn, convert_follow=True, is_dragon=True):
                conf[xn_key] = dxconf
                self.action_ids[xn["_Id"]] = xn_key
            if hitattrshift:
                hitattr_adj(xn, conf[xn_key]["startup"], conf[xn_key], pattern=re.compile(r".*_HAS"), skip_nohitattr=True, attr_key="attr_HAS")

        for act, seq, key in (
            ("ds1", 1, "_Skill1"),
            ("ds2", 2, "_Skill2"),
        ):
            if not (dskill := res.get(key)):
                continue
            self.chara_skills[dskill["_Id"]] = (act, seq, dskill, None)
        dsfinal = res.get("_SkillFinalAttack")
        dsfinal_act = None
        if dsfinal:
            dsfinal_act = self.chara_skills.get(dsfinal["_Id"], (None,))[0]
            if dsfinal and not dsfinal_act:
                self.chara_skills[dsfinal["_Id"]] = ("ds99", 99, dsfinal, None)

        self.process_skill(res, conf, mlvl or {1: 2, 2: 2})
        if dsfinal_act:
            conf[dsfinal_act]["final"] = True

        if not uniqueshift:
            remap_stuff(conf, self.action_ids)
            self.unset_ability_and_actcond_meta()

        return conf

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        where_str = "_Rarity = 5 AND _IsPlayable = 1 AND (_SellDewPoint = 8500 OR _Id in (" + ",".join(map(str, DrgConf.EXTRA_DRAGONS)) + ")) AND _Id = _EmblemId"
        # where_str = '_IsPlayable = 1'
        all_res = self.get_all(where=where_str)
        out_dir = os.path.join(out_dir, "drg")
        check_target_path(out_dir)
        outdata = {ele.lower(): {} for ele in ELEMENTS.values()}
        # skipped = []
        for res in tqdm(all_res, desc=os.path.basename(out_dir)):
            conf = self.process_result(res)
            # outfile = snakey(conf['d']['ele']) + '.json'
            if conf:
                outdata[conf["d"]["ele"]][snakey(conf["d"]["name"])] = conf
        for ele, data in outdata.items():
            output = os.path.join(out_dir, f"{ele}.json")
            with open(output, "w", newline="", encoding="utf-8") as fp:
                fmt_conf(data, f=fp, lim=3)
                fp.write("\n")
        # pprint(DrgConf.COMMON_ACTIONS)

    def get(self, name, by=None, hitattrshift=False, mlvl=None, uniqueshift=False):
        res = super().get(name, by=by, full_query=False)
        if isinstance(res, list):
            res = res[0]
        return self.process_result(res, hitattrshift=hitattrshift, mlvl=mlvl, uniqueshift=uniqueshift)
