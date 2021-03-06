from loader.Database import DBViewIndex, DBView
from exporter.Adventurers import CharaData

import re
import json
from unidecode import unidecode
def snakey(name):
    return re.sub(r'[^0-9a-zA-Z ]', '', unidecode(name)).replace(' ', '_').replace('_amp', '_and')

KEEP_LOWER_SP = {
    101502021
}
def same(lst, idx):
    if lst[1:] == lst[:-1]:
        return lst[0]
    elif idx in KEEP_LOWER_SP:
        return min(lst)
    else:
        return lst[-1]

SPECIAL_EDIT_SKILL = {
    103505044: 2,
    105501025: 1
}
def export_skill_share_json():
    index = DBViewIndex()
    view = CharaData(index)
    all_res = view.get_all(exclude_falsy=False)
    skill_share_data = {}
    for res in all_res:
        res_data = {}
        if res['_HoldEditSkillCost'] != 10:
            res_data['limit'] = res['_HoldEditSkillCost']
        if res['_EditSkillRelationId'] > 1:
            modifiers = index['EditSkillCharaOffset'].get(res['_EditSkillRelationId'], by='_EditSkillRelationId')[0]
            if modifiers['_SpOffset'] > 1:
                res_data['mod_sp'] = modifiers['_SpOffset']
            if modifiers['_StrengthOffset'] != 0.699999988079071:
                res_data['mod_att'] = modifiers['_StrengthOffset']
            if modifiers['_BuffDebuffOffset'] != 1:
                res_data['mod_buff'] = modifiers['_BuffDebuffOffset']
        try:
            name = snakey(res['_Name']) if not res['_SecondName'] else snakey(res['_SecondName'])
        except:
            continue
        if res['_EditSkillId'] > 0 and res['_EditSkillCost'] > 0:
            skill = index['SkillData'].get(res['_EditSkillId'], exclude_falsy=False)
            if res['_EditSkillId'] == res['_Skill1']:
                res_data['s'] = 1
            elif res['_EditSkillId'] == res['_Skill2']:
                res_data['s'] = 2
            else:
                try:
                    res_data['s'] = SPECIAL_EDIT_SKILL[res['_EditSkillId']]
                except:
                    res_data['s'] = 99
            if res['_MaxLimitBreakCount'] >= 5:
                sp_lv = 4
            else:
                sp_lv = 3
            if res['_EditSkillLevelNum'] == 2:
                sp_lv -= 1
            # res_data['name'] = snakey(skill['_Name'])
            res_data['cost'] = res['_EditSkillCost']
            res_data['type'] = skill['_SkillType']
            # sp_s_list = [
            #     skill['_SpEdit'],
            #     skill['_SpLv2Edit'],
            #     skill['_SpLv3Edit'],
            #     skill['_SpLv4Edit'],
            # ]
            res_data['sp'] = skill[f'_SpLv{sp_lv}Edit']
        else:
            continue

        skill_share_data[name] = res_data

    with open('../dl/conf/skillshare.json', 'w', newline='') as f:
        json.dump(skill_share_data, f, indent=2, default=str)


if __name__ == '__main__':
    export_skill_share_json()