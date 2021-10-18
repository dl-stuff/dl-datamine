import re
import os
from tqdm import tqdm
from collections import defaultdict

from loader.Database import check_target_path

from exporter.Weapons import WeaponType
from exporter.Adventurers import CharaData, ExAbilityData
from exporter.Shared import snakey
from exporter.Mappings import ELEMENTS, WEAPON_TYPES

from exporter.conf.common import SkillProcessHelper, AbilityConf, convert_fs, convert_x, convert_misc, convert_all_hitattr, fr, fmt_conf, remap_stuff


class BaseConf(WeaponType):
    LABEL_MAP = {
        "AXE": "axe",
        "BOW": "bow",
        "CAN": "staff",
        "DAG": "dagger",
        "KAT": "blade",
        "LAN": "lance",
        "ROD": "wand",
        "SWD": "sword",
        "GUN": "gun",
    }
    GUN_MODES = (40, 41, 42)

    def __init__(self, index):
        self.action_ids = {}
        return super().__init__(index)

    def process_result(self, res, full_query=True):
        conf = {"lv2": {}}
        if res["_Label"] != "GUN":
            fs_id = res["_BurstPhase1"]
            res = super().process_result(res, full_query=True)
            # fs_delay = {}
            fsconf = convert_fs(res["_BurstPhase1"], res["_ChargeMarker"], res["_ChargeCancel"])
            # startup = fsconf["fs"]["startup"]
            # for x, delay in fs_delay.items():
            #     fsconf['fs'][x] = {'startup': fr(startup+delay)}
            if fsconf:
                self.action_ids[res["_BurstPhase1"]["_Id"]] = "fs"
            conf.update(fsconf)
            for n in range(1, 6):
                try:
                    xn = res[f"_DefaultSkill0{n}"]
                except KeyError:
                    break
                conf[f"x{n}"] = convert_x(xn)
                # for part in xn['_Parts']:
                #     if part['commandType'] == 'ACTIVE_CANCEL' and part.get('_actionId') == fs_id and part.get('_seconds'):
                #         fs_delay[f'x{n}'] = part.get('_seconds')
                self.action_ids[xn["_Id"]] = f"x{n}"
                if hitattrs := convert_all_hitattr(xn, re.compile(r".*H0\d_LV02$")):
                    for attr in hitattrs:
                        attr["iv"] = fr(attr["iv"] - conf[f"x{n}"]["startup"])
                        if attr["iv"] == 0:
                            del attr["iv"]
                    conf["lv2"][f"x{n}"] = {"attr": hitattrs}
        else:
            # gun stuff
            self.action_ids[res["_BurstPhase1"]] = "fs"
            for mode in BaseConf.GUN_MODES:
                mode = self.index["CharaModeData"].get(mode, full_query=True)
                mode_name = f'gun{mode["_GunMode"]}'
                if burst := mode.get("_BurstAttackId"):
                    marker = burst.get("_BurstMarkerId")
                    for fs, fsc in convert_fs(burst, marker).items():
                        conf[f"{fs}_{mode_name}"] = fsc
                        self.action_ids[burst["_Id"]] = "fs"
                if (xalt := mode.get("_UniqueComboId")) and isinstance(xalt, dict):
                    for prefix in ("", "Ex"):
                        if xalt.get(f"_{prefix}ActionId"):
                            for n, xn in enumerate(xalt[f"_{prefix}ActionId"]):
                                n += 1
                                xn_key = f"x{n}_{mode_name}{prefix.lower()}"
                                if xaltconf := convert_x(xn):
                                    conf[xn_key] = xaltconf
                                self.action_ids[xn["_Id"]] = f"x{n}"
                                if hitattrs := convert_all_hitattr(xn, re.compile(r".*H0\d_LV02$")):
                                    for attr in hitattrs:
                                        attr["iv"] = fr(attr["iv"] - conf[xn_key]["startup"])
                                        if attr["iv"] == 0:
                                            del attr["iv"]
                                    conf["lv2"][xn_key] = {"attr": hitattrs}

        remap_stuff(conf, self.action_ids)

        return conf

    @staticmethod
    def outfile_name(res, ext):
        return BaseConf.LABEL_MAP[res["_Label"]] + ext

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        out_dir = os.path.join(out_dir, "base")
        all_res = self.get_all()
        check_target_path(out_dir)
        for res in tqdm(all_res, desc=os.path.basename(out_dir)):
            out_name = self.outfile_name(res, ext)
            res = self.process_result(res)
            output = os.path.join(out_dir, out_name)
            with open(output, "w", newline="", encoding="utf-8") as fp:
                # json.dump(res, fp, indent=2, ensure_ascii=False)
                fmt_conf(res, f=fp)
                fp.write("\n")


class ExAbilityConf(ExAbilityData, AbilityConf):
    def process_result(self, res, source=None):
        conf = {"category": res["_Category"]}
        if not (conflist := super().process_result(res, source=source)):
            return
        conf.update(conflist[0])
        return conf


class AdvConf(CharaData, SkillProcessHelper):
    SERVANT_TO_DACT = (
        (1, "dx1"),
        (2, "dx2"),
        (3, "dx3"),
        (4, "dx4"),
        (5, "dx5"),
        (6, "ds1"),
        (7, "ds2"),
    )

    def process_result(self, res, condense=True, force_50mc=False):
        self.set_animation_reference(res)
        self.reset_meta()

        if force_50mc:
            res = dict(res)
            res["_MaxLimitBreakCount"] = 4
        spiral = res["_MaxLimitBreakCount"] == 5

        res = self.condense_stats(res)
        conf = {
            "c": {
                "name": res.get("_SecondName", res.get("_Name")),
                "icon": f'{res["_BaseId"]:06}_{res["_VariationId"]:02}_r{res["_Rarity"]:02}',
                "att": res["_MaxAtk"],
                "hp": res["_MaxHp"],
                "ele": ELEMENTS[res["_ElementalType"]].lower(),
                "wt": WEAPON_TYPES[res["_WeaponType"]].lower(),
                "spiral": spiral,
            }
        }
        # hecc
        if res["_Id"] == 10450404:
            conf["c"]["name"] = "Sophie (Persona)"
        if conf["c"]["wt"] == "gun":
            conf["c"]["gun"] = set()
        self.name = conf["c"]["name"]

        if avoid_on_c := res.get("_AvoidOnCombo"):
            actdata = self.index["PlayerAction"].get(avoid_on_c)
            conf["dodge_on_x"] = convert_misc(actdata)
            self.action_ids[actdata["_Id"]] = "dodge"
        for dodge in map(res.get, ("_Avoid", "_BackAvoidOnCombo")):
            if dodge:
                actdata = self.index["PlayerAction"].get(dodge)
                if dodgeconf := convert_misc(actdata):
                    conf["dodge"] = dodgeconf
                self.action_ids[dodge] = "dodge"

        if burst := res.get("_BurstAttack"):
            burst = self.index["PlayerAction"].get(res["_BurstAttack"])
            if burst and (marker := burst.get("_BurstMarkerId")):
                conf.update(convert_fs(burst, marker))
                self.action_ids[burst["_Id"]] = "fs"

        if conf["c"]["spiral"]:
            mlvl = {1: 4, 2: 3}
        else:
            mlvl = {1: 3, 2: 2}

        for s in (1, 2):
            if sdata := res.get(f"_Skill{s}"):
                skill = self.index["SkillData"].get(sdata, full_query=True)
                self.chara_skills[sdata] = (f"s{s}", s, skill, None)

        self.index["AbilityConf"].set_meta(self)
        ablist = []
        for i in (1, 2, 3):
            found = 1
            for j in (3, 2, 1):
                if ab := res.get(f"_Abilities{i}{j}"):
                    if force_50mc and found > 0:
                        found -= 1
                        continue
                    if ability := self.index["AbilityConf"].get(ab, source=f"ability{i}"):
                        ablist.extend(ability)
                    break
        if self.utp_chara is not None:
            conf["c"]["utp"] = self.utp_chara
        if self.cp1_gauge is not None:
            conf["c"]["cp"] = self.cp1_gauge
        conf["c"]["abilities"] = ablist

        if udrg := res.get("_UniqueDragonId"):
            udform_key = "dservant" if self.utp_chara and self.utp_chara[0] == 2 else "dragonform"
            conf[udform_key] = self.index["DrgConf"].get(udrg, by="_Id", uniqueshift=True, hitattrshift=self.hitattrshift, mlvl=mlvl if res.get("_IsConvertDragonSkillLevel") else None)
            self.action_ids.update(self.index["DrgConf"].action_ids)
            # dum
            self.set_animation_reference(res)

        base_mode_burst, base_mode_x = None, None
        for m in range(1, 5):
            if mode := res.get(f"_ModeId{m}"):
                if not isinstance(mode, dict):
                    mode = self.index["CharaModeData"].get(mode, full_query=True)
                    if not mode:
                        continue
                if gunkind := mode.get("_GunMode"):
                    conf["c"]["gun"].add(gunkind)
                    if mode["_Id"] in BaseConf.GUN_MODES:
                        continue
                    # if not any([mode.get(f'_Skill{s}Id') for s in (1, 2)]):
                    #     continue
                if not (mode_name := self.chara_modes.get(m)):
                    if m == 2 and self.utp_chara is not None and self.utp_chara[0] != 1:
                        mode_name = "_ddrive"
                    else:
                        try:
                            mode_name = "_" + snakey(mode["_ActionId"]["_Parts"][0]["_actionConditionId"]["_Text"].split(" ")[0].lower())
                        except:
                            if m == 1:
                                mode_name = ""
                            else:
                                mode_name = f"_mode{m}"
                for s in (1, 2):
                    if skill := mode.get(f"_Skill{s}Id"):
                        self.chara_skills[skill.get("_Id")] = (
                            f"s{s}{mode_name}",
                            s,
                            skill,
                            None,
                        )
                if (burst := mode.get("_BurstAttackId")) and base_mode_burst != burst["_Id"]:
                    marker = burst.get("_BurstMarkerId")
                    if not marker:
                        marker = self.index["PlayerAction"].get(burst["_Id"] + 4)
                    fs = None
                    for fs, fsc in convert_fs(burst, marker).items():
                        conf[f"{fs}{mode_name}"] = fsc
                    if fs:
                        self.action_ids[burst["_Id"]] = "fs"
                    if not mode_name:
                        base_mode_burst = burst["_Id"]
                if ((xalt := mode.get("_UniqueComboId")) and isinstance(xalt, dict)) and base_mode_x != xalt["_Id"]:
                    xalt_pattern = re.compile(r".*H0\d_LV02$") if conf["c"]["spiral"] else None
                    for prefix in ("", "Ex"):
                        if xalt.get(f"_{prefix}ActionId"):
                            for n, xn in enumerate(xalt[f"_{prefix}ActionId"]):
                                n += 1
                                if not mode_name and prefix:
                                    xn_key = f"x{n}_{prefix.lower()}"
                                else:
                                    xn_key = f"x{n}{mode_name}{prefix.lower()}"
                                if xaltconf := convert_x(xn, pattern=xalt_pattern):
                                    conf[xn_key] = xaltconf
                                    self.action_ids[xn["_Id"]] = xn_key
                                elif xalt_pattern is not None and (xaltconf := convert_x(xn)):
                                    conf[xn_key] = xaltconf
                                    self.action_ids[xn["_Id"]] = xn_key
                    if not mode_name:
                        base_mode_x = xalt["_Id"]
                        if xalt["_MaxComboNum"] < 5:
                            conf["default"] = {"x_max": xalt["_MaxComboNum"]}
        try:
            conf["c"]["gun"] = list(conf["c"]["gun"])
        except KeyError:
            pass

        # self.abilities = self.last_abilities(res, as_mapping=True)
        # pprint(self.abilities)
        # for k, seq, skill in self.chara_skills.values():

        if edit := res.get("_EditSkillId"):
            if edit not in self.chara_skills:
                skill = self.index["SkillData"].get(edit, full_query=True)
                self.chara_skills[edit] = (f"s99", 99, skill, None)
                res["_EditSkillId"] = skill
            else:
                res["_EditSkillId"] = self.chara_skills[edit][2]

        self.process_skill(res, conf, mlvl)

        if ss_conf := self.skillshare_data(res):
            conf["c"]["skillshare"] = ss_conf

        try:
            self.action_ids.update(self.base_conf.action_ids)
        except AttributeError:
            pass
        servant_attrs = None
        if self.utp_chara and self.utp_chara[0] == 2:
            # build fake servant attrs
            servant_attrs = {}
            for servant_id, dact in self.SERVANT_TO_DACT:
                if not (dact_conf := conf["dservant"].get(dact)) or not (dact_attrs := dact_conf.get("attr")):
                    continue
                servant_attrs[servant_id] = []
                for attr in dact_attrs:
                    try:
                        del attr["sp"]
                    except KeyError:
                        pass
                    attr = dict(attr)
                    if servant_id == 6:
                        # man i fucking hate cykagames
                        attr["gluca"] = 1
                    attr["msl"] = dact_conf.get("startup") + attr.get("iv", 0.0) + attr.get("msl", 0.0)
                    servant_attrs[servant_id].append(attr)
        remap_stuff(conf, self.action_ids, servant_attrs=servant_attrs)

        self.index["AbilityConf"].set_meta(None)

        return conf

    def get(self, name, exss=False):
        res = super().get(name, full_query=False)
        if isinstance(res, list):
            res = res[0]
        conf = self.process_result(res)
        if exss:
            if ex_res := self.exability_data(res):
                conf["DEBUG_COAB"] = ex_res
        return conf

    @staticmethod
    def outfile_name(conf, ext, variant=None):
        if variant is not None:
            return snakey(conf["c"]["name"]) + "." + variant + ext
        return snakey(conf["c"]["name"]) + ext

    def skillshare_data(self, res):
        ss_conf = {}
        if res["_HoldEditSkillCost"] != 10:
            ss_conf["limit"] = res["_HoldEditSkillCost"]
        if res["_EditSkillRelationId"] > 1:
            modifiers = self.index["EditSkillCharaOffset"].get(res["_EditSkillRelationId"], by="_EditSkillRelationId")[0]
            if modifiers["_SpOffset"] > 1:
                ss_conf["mod_sp"] = modifiers["_SpOffset"]
            if modifiers["_StrengthOffset"] != 0.699999988079071:
                ss_conf["mod_att"] = modifiers["_StrengthOffset"]
            if modifiers["_BuffDebuffOffset"] != 1:
                ss_conf["mod_buff"] = modifiers["_BuffDebuffOffset"]
        if res.get("_EditSkillCost", 0) > 0 and (skill := res.get("_EditSkillId")):
            # skill = self.index["SkillData"].get(res["_EditSkillId"])
            # ss_conf["s"] = self.
            ss_conf["src"] = self.all_chara_skills[skill["_Id"]][0]
            ss_conf["cost"] = res["_EditSkillCost"]
            if res["_MaxLimitBreakCount"] >= 5:
                sp_lv = 4
            else:
                sp_lv = 3
            if res["_EditSkillLevelNum"] == 2:
                sp_lv -= 1
            # ss_conf["type"] = skill["_SkillType"]
            ss_conf["sp"] = skill[f"_SpLv{sp_lv}Edit"]
        return ss_conf

    def exability_data(self, res):
        ex_ab = self.index["ExAbilityConf"].get(res["_ExAbilityData5"], source="coab")
        chain_ab = self.index["AbilityConf"].get(res.get("_ExAbility2Data5"), source="chain")
        entry = {
            "ex": ex_ab,
            "chain": chain_ab,
        }
        return entry

    def sort_exability_data(self, exability_data):
        ex_by_ele = defaultdict(set)
        ex_by_category = {}
        catagorized_names = defaultdict(set)
        all_ele_chains = {}
        for ele, exabs in exability_data.items():
            for name, entry in exabs.items():
                cat = entry["category"]
                ex_by_ele[ele].add(cat)
                if cat not in ex_by_category or (entry["ex"] and ex_by_category[cat]["ex"][0][1] < entry["ex"][0][1]):
                    ex_by_category[cat] = {
                        "category": cat,
                        "ex": entry["ex"],
                        "chain": [],
                    }
                catagorized_names[cat].add(name)
                if entry.get("ALL_ELE_CHAIN"):
                    del entry["ALL_ELE_CHAIN"]
                    all_ele_chains[name] = entry
        extra_data = {}
        extra_data["generic"] = {}
        extra_data["any"] = {}
        for cat, entry in ex_by_category.items():
            if cat not in catagorized_names:
                continue
            catname = sorted(catagorized_names[cat])[0]
            if len(catagorized_names[cat]) > 1:
                print(f"More than 1 name for EX category {cat}: {catagorized_names[cat]}, picked {catname}")
            entry["category"] = catname
            if all((cat in eleset for eleset in ex_by_ele.values())):
                extra_data["generic"][catname] = entry
                for name in catagorized_names[cat]:
                    for exabs in exability_data.values():
                        try:
                            if not exabs[name]["chain"]:
                                del exabs[name]
                            else:
                                exabs[name]["category"] = catname
                        except KeyError:
                            pass
            else:
                if entry["ex"] and not entry["ex"][0][0].startswith("ele_"):
                    extra_data["any"][catname] = entry
                for name in catagorized_names[cat]:
                    for exabs in exability_data.values():
                        try:
                            exabs[name]["category"] = catname
                        except KeyError:
                            pass
        extra_data["any"].update(all_ele_chains)
        exability_data.update(extra_data)

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        # do this here in order to have the action ids from generic weapon
        self.base_conf = BaseConf(self.index)
        self.base_conf.export_all_to_folder(out_dir=out_dir)

        all_res = self.get_all(where="_ElementalType != 99 AND _IsPlayable = 1")
        # ref_dir = os.path.join(out_dir, '..', 'adv')
        skillshare_out = os.path.join(out_dir, f"skillshare{ext}")
        exability_out = os.path.join(out_dir, f"exability{ext}")
        advout_dir = os.path.join(out_dir, "adv")
        check_target_path(advout_dir)
        exability_data = {ele.lower(): {} for ele in ELEMENTS.values()}

        for res in tqdm(all_res, desc=os.path.basename(advout_dir)):
            try:
                if res.get("_UniqueGrowMaterialId1") and res.get("_UniqueGrowMaterialId2"):
                    outconf = self.process_result(res, force_50mc=True)
                    out_name = self.outfile_name(outconf, ext, variant="50MC")
                    output = os.path.join(advout_dir, out_name)
                    with open(output, "w", newline="", encoding="utf-8") as fp:
                        fmt_conf(outconf, f=fp)
                        fp.write("\n")
                outconf = self.process_result(res)
                out_name = self.outfile_name(outconf, ext)
                if ex_res := self.exability_data(res):
                    exability_data[snakey(outconf["c"]["ele"])][snakey(outconf["c"]["name"])] = ex_res
                output = os.path.join(advout_dir, out_name)
                with open(output, "w", newline="", encoding="utf-8") as fp:
                    fmt_conf(outconf, f=fp)
                    fp.write("\n")
            except Exception as e:
                print(res["_Id"], res.get("_SecondName", res.get("_Name")), flush=True)
                raise e
        if AdvConf.MISSING_ENDLAG:
            print("Missing endlag for:", AdvConf.MISSING_ENDLAG)
        self.sort_exability_data(exability_data)
        with open(exability_out, "w", newline="") as fp:
            fmt_conf(exability_data, f=fp, lim=3, sortlim=2)
            fp.write("\n")