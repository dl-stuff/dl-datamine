import re
import os
from tqdm import tqdm
from collections import defaultdict

from loader.Database import DBView, check_target_path
from loader.Enums import AbilityStat, AbilityTargetAction

from exporter.Weapons import WeaponType
from exporter.Adventurers import CharaData
from exporter.Shared import snakey
from exporter.Mappings import ELEMENTS, WEAPON_TYPES

from exporter.conf.common import ActCondConf, SDat, SkillProcessHelper, AbilityConf, convert_fs, convert_x, convert_misc, convert_all_hitattr, fr, fmt_conf, remap_stuff


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
    GUN_FS = {
        1: 900015,
        2: 900105,
        3: 900205,
    }
    GUN_X = {
        1: 30,
        2: 31,
        3: 32,
    }

    def __init__(self, index):
        self.action_ids = {}
        return super().__init__(index)

    def process_result(self, res):
        conf = {"lv2": {}}
        if res["_Label"] != "GUN":
            fs_id = res["_BurstPhase1"]
            res = super().process_result(res)
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
                conf[f"x{n}"] = convert_x(xn, pattern=re.compile(r".*H0\d$"))
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
                                if xaltconf := convert_x(xn, pattern=re.compile(r".*H0\d$")):
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
            outname = self.outfile_name(res, ext)
            res = self.process_result(res)
            output = os.path.join(out_dir, outname)
            with open(output, "w", newline="", encoding="utf-8") as fp:
                # json.dump(res, fp, indent=2, ensure_ascii=False)
                fmt_conf(res, f=fp)


class ExAbilityConf(AbilityConf):
    def __init__(self, index):
        DBView.__init__(self, index, "ExAbilityData", labeled_fields=["_Name", "_Details"])
        self.meta = None
        self.source = None
        self.use_ablim_groups = False
        self.use_shift_groups = False

    def at_BuffExtension(self, res, i):
        return self._at_mod(res, i, "bufftime", "ex")

    def at_StatusUp(self, res, i):
        if AbilityStat(self._varid_a(res, i)) == AbilityStat.Atk:
            return self._at_mod(res, i, "att", "ex")
        return super().at_StatusUp(res, i)

    def at_ActDamageUp(self, res, i):
        if AbilityTargetAction(res[f"_TargetAction{i}"]) == AbilityTargetAction.SKILL_ALL:
            res[f"_TargetAction{i}"] = 0
            at = self._at_upval("actdmg", res, i)
            at.append("-t:s")
            at.append("ex")
            return at
        return super().at_ActDamageUp(res, i)

    def process_result(self, res, source=None):
        if conflist := super().process_result(res, source=source):
            exability = conflist[0]
            exability["category"] = res["_Category"]
            return exability
        return {"category": res["_Category"]}


class AdvConf(CharaData, SkillProcessHelper):
    SERVANT_TO_DACT = (
        (-1, "dshift"),  # not actuall a thing irl
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
        self.set_ability_and_actcond_meta()

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
            mlvl = {"s1": 4, "s2": 3}
        else:
            mlvl = {"s1": 3, "s2": 2}

        for s in (1, 2):
            if sid := res.get(f"_Skill{s}"):
                self.chara_skills[sid] = SDat(sid, f"s{s}", None)

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
        if self.cp1_gauge > 0:
            conf["c"]["cp"] = self.cp1_gauge
        conf["c"]["abilities"] = ablist

        if udrg := res.get("_UniqueDragonId"):
            udform_key = "dservant" if self.utp_chara and self.utp_chara[0] == 2 else "dragonform"
            if res.get("_IsConvertDragonSkillLevel"):
                dmlvl = {"ds1": mlvl["s1"], "ds2": mlvl["s2"]}
            else:
                dmlvl = None
            conf[udform_key] = self.index["DrgConf"].get(udrg, by="_Id", uniqueshift=True, hitattr_shift=self.hitattr_shift, mlvl=dmlvl)
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
                    self.chara_modes[m] = mode_name
                for s in (1, 2):
                    if skill := mode.get(f"_Skill{s}Id"):
                        self.chara_skills[skill["_Id"]] = SDat(skill["_Id"], f"s{s}", mode_name.strip("_") or None, skill)
                if (burst := mode.get("_BurstAttackId")) and burst["_Id"] not in (base_mode_burst, BaseConf.GUN_FS.get(gunkind, 0)):
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
                if ((xalt := mode.get("_UniqueComboId")) and isinstance(xalt, dict)) and xalt["_Id"] not in (base_mode_x, BaseConf.GUN_X.get(gunkind, 0)):
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
                if dashondodge := mode.get("_DashOnAvoid"):
                    if dashconf := convert_misc(dashondodge):
                        conf["dash"] = dashconf
                        self.action_ids[dashondodge["_Id"]] = "dash"

                if self.utp_chara and (mode_act := mode.get("_ActionId")):
                    if mode_act_conf := convert_misc(mode_act):
                        if not "dragonform" in conf:
                            conf["dragonform"] = {}
                        conf["dragonform"]["dshift"] = mode_act_conf

        try:
            conf["c"]["gun"] = list(conf["c"]["gun"])
        except KeyError:
            pass

        if edit := res.get("_EditSkillId"):
            if edit not in self.chara_skills:
                self.chara_skills[edit] = SDat(edit, "s99", None)

        self.process_skill(res, conf, mlvl)

        if self.combo_shift:
            i = 1
            while (xn := f"x{i}") in conf:
                conf[f"{xn}_{self.combo_shift}"] = conf[xn]
                del conf[xn]
                i += 1

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
                    # if servant_id == 6:
                    #     # man i fucking hate cykagames
                    #     attr["gluca"] = 1
                    attr["msl"] = dact_conf.get("startup", 0.0) + attr.get("iv", 0.0) + attr.get("msl", 0.0)
                    servant_attrs[servant_id].append(attr)
        remap_stuff(conf, self.action_ids, servant_attrs=servant_attrs, chara_modes=self.chara_modes)
        self.unset_ability_and_actcond_meta(conf)

        return conf

    def get(self, name, exss=False):
        res = super().get(name, full_query=False)
        if isinstance(res, list):
            res = res[0]
        conf = self.process_result(res)
        if exss:
            conf["DEBUG_COAB"] = {
                "ex": self.index["ExAbilityConf"].get(res["_ExAbilityData5"], source="ex"),
                "chain": self.index["AbilityConf"].get(res["_ExAbility2Data5"], source="ex"),
            }
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
        if res.get("_EditSkillCost", 0) > 0 and (edit := res.get("_EditSkillId")):
            sdat = self.all_chara_skills[edit]
            ss_conf["src"] = sdat.base
            ss_conf["cost"] = res["_EditSkillCost"]
            if res["_MaxLimitBreakCount"] >= 5:
                sp_lv = 4
            else:
                sp_lv = 3
            if res["_EditSkillLevelNum"] == 2:
                sp_lv -= 1
            ss_conf["sp"] = sdat.skill[f"_SpLv{sp_lv}Edit"]
        return ss_conf

    def process_exability_data(self, exability_data):
        exability_conf = {
            "actconds": {},
            "coab": {},
            "chain": {},
            "lookup": {},
        }
        self.set_ability_and_actcond_meta()
        for coab, chain_data in sorted(exability_data.items()):
            exability_conf["coab"][coab] = self.index["ExAbilityConf"].get(coab, source="ex")
            for chain, charas in sorted(chain_data.items()):
                exability_conf["chain"][chain] = self.index["AbilityConf"].get(chain, source="ex")
                for chara in charas:
                    exability_conf["lookup"][chara] = [str(coab), str(chain)]
        self.unset_ability_and_actcond_meta(exability_conf)
        return exability_conf

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        # do this here in order to have the action ids from generic weapon
        self.base_conf = BaseConf(self.index)
        self.base_conf.export_all_to_folder(out_dir=out_dir)

        all_res = self.get_all(where="_ElementalType != 99 AND _IsPlayable = 1")
        # ref_dir = os.path.join(out_dir, '..', 'adv')
        # skillshare_out = os.path.join(out_dir, f"skillshare{ext}")
        exability_out = os.path.join(out_dir, f"exability{ext}")
        advout_dir = os.path.join(out_dir, "adv")
        # exability_data = {ele.lower(): {} for ele in ELEMENTS.values()}
        exability_data = defaultdict(lambda: defaultdict(list))

        for res in tqdm(all_res, desc=os.path.basename(advout_dir)):
            name = res.get("_SecondName", res.get("_Name", res.get("_Id")))
            try:
                if res.get("_UniqueGrowMaterialId1") and res.get("_UniqueGrowMaterialId2"):
                    outconf = self.process_result(res, force_50mc=True)
                    outname = self.outfile_name(outconf, ext, variant="50MC")
                    output = os.path.join(advout_dir, outconf["c"]["ele"], outname)
                    check_target_path(os.path.dirname(output))
                    with open(output, "w", newline="", encoding="utf-8") as fp:
                        fmt_conf(outconf, f=fp)
                outconf = self.process_result(res)
                outname = self.outfile_name(outconf, ext)
                # if ex_res := self.exability_data(res):
                #     exability_data[snakey(outconf["c"]["ele"])][snakey(outconf["c"]["name"])] = ex_res
                exability_data[res["_ExAbilityData5"]][res["_ExAbility2Data5"]].append(snakey(outconf["c"]["name"]))
                output = os.path.join(advout_dir, outconf["c"]["ele"], outname)
                check_target_path(os.path.dirname(output))
                with open(output, "w", newline="", encoding="utf-8") as fp:
                    fmt_conf(outconf, f=fp)
            except Exception as e:
                print()
                print(res["_Id"], name, flush=True)
                raise e
        exability_data = self.process_exability_data(exability_data)
        with open(exability_out, "w", newline="") as fp:
            fmt_conf(exability_data, f=fp, lim=2, sortlim=0)
