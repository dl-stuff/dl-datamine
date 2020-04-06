import os
import json
import re
from collections import defaultdict

from loader.Database import DBManager, DBView, DBDict, check_target_path
from exporter.Shared import ActionCondition, get_valid_filename
from exporter.Mappings import AFFLICTION_TYPES, TRIBE_TYPES, ELEMENTS

class EnemyAbility(DBView):
    def __init__(self, db):
        super().__init__(db, 'EnemyAbility', labeled_fields=['_Name'])

class EnemyList(DBView):
    def __init__(self, db):
        super().__init__(db, 'EnemyList', labeled_fields=['_Name'])

    def process_result(self, res, exclude_falsy=False):
        if '_TribeType' in res and res['_TribeType']:
            res['_TribeType'] = TRIBE_TYPES.get(res['_TribeType'], res['_TribeType'])
        return res

    # def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, exclude_falsy=False):
    def get(self, pk, fields=None, exclude_falsy=True, full_query=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        res = self.process_result(res, exclude_falsy=exclude_falsy)
        return res

class EnemyData(DBView):
    def __init__(self, db):
        super().__init__(db, 'EnemyData')
        self.enemy_list = EnemyList(db)

    def process_result(self, res, exclude_falsy=False):
        if '_BookId' in res and res['_BookId']:
            if (data := self.enemy_list.get(res['_BookId'], exclude_falsy=exclude_falsy)):
                res['_BookId'] = data
        if '_ElementalType' in res and res['_ElementalType']:
            res['_ElementalType'] = ELEMENTS.get(res['_ElementalType'], res['_ElementalType'])
        return res

    # def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, exclude_falsy=False):
    def get(self, pk, fields=None, exclude_falsy=True, full_query=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        res = self.process_result(res, exclude_falsy=exclude_falsy)
        return res

class EnemyActionHitAttribute(DBView):
    def __init__(self, db):
        super().__init__(db, 'EnemyActionHitAttribute')
        self.action_condition = ActionCondition(db)

    def process_result(self, res, exclude_falsy=True):
        res_list = [res] if isinstance(res, dict) else res
        for r in res_list:
            if '_ActionCondition' in r and r['_ActionCondition']:
                act_cond = self.action_condition.get(r['_ActionCondition'], exclude_falsy=exclude_falsy)
                if act_cond:
                    r['_ActionCondition'] = act_cond
        return res

    def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, exclude_falsy=False):
        res = super().get(pk, by, fields, order, mode, exclude_falsy)
        return self.process_result(res, exclude_falsy=exclude_falsy)

class EnemyHitDifficulty(DBView):
    def __init__(self, db):
        super().__init__(db, 'EnemyHitDifficulty')
        self.enemy_hitattr = EnemyActionHitAttribute(db)

    def process_result(self, res, exclude_falsy=True):
        for k in res:
            if k == '_Id':
                continue
            res[k] = self.enemy_hitattr.get(res[k], exclude_falsy=exclude_falsy)
        return res

    def get(self, pk, fields=None, exclude_falsy=True, full_query=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        return self.process_result(res, exclude_falsy=exclude_falsy)

class EnemyAction(DBView):
    def __init__(self, db):
        super().__init__(db, 'EnemyAction', labeled_fields=['_NameFire', '_NameWater', '_NameWind', '_NameLight', '_NameDark'])
        self.enemy_hit_difficulty = EnemyHitDifficulty(db)

    def process_result(self, res, exclude_falsy=True):
        if '_ActionGroupName' in res and res['_ActionGroupName'] and (hitdiff := self.enemy_hit_difficulty.get(res['_ActionGroupName'], exclude_falsy=exclude_falsy)):
            res['_ActionGroupName'] = hitdiff
        return res

    def get(self, pk, fields=None, exclude_falsy=True, full_query=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        return self.process_result(res, exclude_falsy=exclude_falsy)

class EnemyActionSet(DBView):
    def __init__(self, db):
        super().__init__(db, 'EnemyActionSet')
        self.enemy_action = EnemyAction(db)

    def process_result(self, res, exclude_falsy=True):
        for k in res:
            if k == '_Id':
                continue
            res[k] = self.enemy_action.get(res[k], exclude_falsy=exclude_falsy)
        return res

    def get(self, pk, fields=None, exclude_falsy=True, full_query=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        return self.process_result(res, exclude_falsy=exclude_falsy)

class EnemyParam(DBView):
    DP_PATTERN = {
        1: 'On Death',
        2: 'Every 10% HP'
    }
    def __init__(self, db):
        super().__init__(db, 'EnemyParam')
        self.enemy_data = EnemyData(db)
        self.enemy_ability = EnemyAbility(db)
        self.enemy_actions = EnemyActionSet(db)

    def process_result(self, res, exclude_falsy=True, full_actions=False):
        if '_DataId' in res and res['_DataId']:
            if (data := self.enemy_data.get(res['_DataId'], exclude_falsy=exclude_falsy)):
                res['_DataId'] = data
        if full_actions:
            if '_ActionSet' in res and res['_ActionSet']:
                res['_ActionSet'] = self.enemy_actions.get(res['_ActionSet'], exclude_falsy=exclude_falsy)
        for ab in ('_Ability01', '_Ability02'):
            if ab in res and res[ab] and (data := self.enemy_ability.get(res[ab], exclude_falsy=exclude_falsy)):
                res[ab] = data
        resists = {}
        for k, v in AFFLICTION_TYPES.items():
            resist_key = f'_RegistAbnormalRate{k:02}'
            if resist_key in res:
                resists[v] = res[resist_key]
                del res[resist_key]
            else:
                resists[v] = 0
        res['_AfflictionResist'] = resists
        if '_DropDpPattern' in res:
            res['_DropDpPattern'] = self.DP_PATTERN.get(res['_DropDpPattern'], res['_DropDpPattern'])
        return res

    # @staticmethod
    # def remove_falsy_fields(res):
    #     return DBDict(filter(lambda x: bool(x[1]) or x[0].startswith('_RegistAbnormalRate'), res.items()))

    # def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, exclude_falsy=False):
    def get(self, pk, fields=None, exclude_falsy=True, full_query=True, full_actions=False):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        res = self.process_result(res, exclude_falsy=exclude_falsy, full_actions=full_actions)
        return res

    # @staticmethod
    # def outfile_name(res, ext='.json'):
    #     name = res.get('_ParamGroupName', 'UNKNOWN')
    #     return get_valid_filename(f'{res["_Id"]:02}_{name}{ext}')

    PARAM_GROUP = re.compile(r'([^\d]+)_\d{2}_\d{2}_E_?\d{2}')
    def export_all_to_folder(self, out_dir='./out', ext='.json', exclude_falsy=True):
        # super().export_all_to_folder(out_dir, ext, fn_mode='a', exclude_falsy=exclude_falsy, full_actions=False)
        out_dir = os.path.join(out_dir, 'enemies')
        all_res = self.get_all(exclude_falsy=exclude_falsy)
        check_target_path(out_dir)
        sorted_res = defaultdict(lambda: [])
        for res in all_res:
            if '_ParamGroupName' in res:
                if (match := self.PARAM_GROUP.match(res['_ParamGroupName'])):
                    sorted_res[match.group(1)].append(self.process_result(res, exclude_falsy=exclude_falsy))
                else:
                    sorted_res[res['_ParamGroupName'].split('_', 1)[0]].append(self.process_result(res, exclude_falsy=exclude_falsy))
        for group_name, res_list in sorted_res.items():
            out_name = get_valid_filename(f'{group_name}{ext}')
            output = os.path.join(out_dir, out_name)
            with open(output, 'w', newline='', encoding='utf-8') as fp:
                json.dump(res_list, fp, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    db = DBManager()
    view = EnemyParam(db)
    view.export_all_to_folder()