import json
import os
from tabulate import tabulate

from loader.Database import DBViewIndex, DBView, DBDict, DBManager
from exporter.Shared import AbilityData, SkillData, PlayerAction


class DragonMotion(DBView):
    def __init__(self, index):
        super().__init__(index, 'DragonMotion')

    def get_by_state_ref(self, state, ref, exclude_falsy=True):
        tbl = self.database.check_table(self.name)
        query = f'SELECT {tbl.named_fields} FROM {self.name} WHERE {self.name}.state=? AND {self.name}.ref=?;'
        return self.database.query_many(
            query=query,
            param=(state, ref),
            d_type=DBDict
        )


class DragonData(DBView):
    ACTIONS = ['_AvoidActionFront', '_AvoidActionBack', '_Transform']

    def __init__(self, index):
        super().__init__(index, 'DragonData', labeled_fields=[
            '_Name', '_SecondName', '_Profile', '_CvInfo', '_CvInfoEn'])

    def process_result(self, res, exclude_falsy, full_query=True, full_abilities=False):
        if '_AnimFileName' in res and res['_AnimFileName']:
            anim_key = int(res['_AnimFileName'][1:].replace('_', ''))
        else:
            anim_key = int(f'{res["_BaseId"]}{res["_VariationId"]:02}')
        self.index['ActionParts'].animation_reference = (
            'DragonMotion', anim_key)
        for s in ('_Skill1', '_Skill2'):
            try:
                res[s] = self.index['SkillData'].get(
                    res[s], exclude_falsy=exclude_falsy, full_abilities=full_abilities)
            except:
                pass
        inner = (1, 2, 3, 4, 5) if full_abilities else (5,)
        outer = (1, 2)
        for i in outer:
            for j in inner:
                k = f'_Abilities{i}{j}'
                if k in res and res[k]:
                    res[k] = self.index['AbilityData'].get(
                        res[k], full_query=True, exclude_falsy=exclude_falsy)
        for act in self.ACTIONS:
            if act in res:
                res[act] = self.index['PlayerAction'].get(
                    res[act], exclude_falsy=exclude_falsy)
        if '_DefaultSkill' in res and res['_DefaultSkill']:
            base_action_id = res['_DefaultSkill']
            res['_DefaultSkill'] = [self.index['PlayerAction'].get(
                base_action_id+i, exclude_falsy=exclude_falsy) for i in range(0, res['_ComboMax'])]
        self.index['ActionParts'].animation_reference = None
        return res

    def get(self, pk, by=None, fields=None, exclude_falsy=False, full_query=True, full_abilities=False):
        if by is None:
            res = super().get(pk, by='_SecondName', fields=fields, mode=DBManager.LIKE, exclude_falsy=exclude_falsy)
            if not res:
                res = super().get(pk, by='_Name', fields=fields, mode=DBManager.LIKE, exclude_falsy=exclude_falsy)
        else:
            res = super().get(pk, by=by, fields=fields, mode=DBManager.LIKE, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        return self.process_result(res, exclude_falsy, full_query, full_abilities)

    @staticmethod
    def outfile_name(res, ext='.json'):
        name = 'UNKNOWN' if '_Name' not in res else res[
            '_Name'] if '_SecondName' not in res else res['_SecondName']
        return f'{res["_BaseId"]}_{res["_VariationId"]:02}_{name}{ext}'

    def export_all_to_folder(self, out_dir='./out', ext='.json', exclude_falsy=True):
        out_dir = os.path.join(out_dir, 'dragons')
        super().export_all_to_folder(out_dir, ext, exclude_falsy=exclude_falsy,
                                     full_query=True, full_abilities=False)

    def simplified_combos(self):
        all_data = self.get_all(exclude_falsy=False)
        for res in all_data:
            if '_AnimFileName' in res and res['_AnimFileName']:
                anim_key = int(res['_AnimFileName'][1:].replace('_', ''))
            else:
                anim_key = int(f'{res["_BaseId"]}{res["_VariationId"]:02}')
            self.index['ActionParts'].animation_reference = (
                'DragonMotion', anim_key)
            print('\n'+res['_Name'], '-', res['_SecondName'] or '')
            base_action_id = res['_DefaultSkill']
            default_skill = [self.index['PlayerAction'].get(
                base_action_id+i, exclude_falsy=False) for i in range(0, res['_ComboMax'])]
            for combo in default_skill:
                if not combo:
                    continue
                combo_parts = []
                for part in sorted(combo['_Parts'], key=lambda ds: ds['_seconds']):
                    command_type = part['commandType']
                    seconds = part['_seconds']
                    duration = part['_duration']
                    speed = part['_speed']

                    if command_type == 'PARTS_MOTION':
                        try:
                            duration = part['_animation'][0]['duration']
                        except:
                            pass
                    elif command_type == 'SEND_SIGNAL' or command_type == 'ACTIVE_CANCEL':
                        command_type = f'{command_type}_{part["_actionId"] % 100:02}'
                    elif command_type == 'BULLET':
                        duration = part['_delayTime']

                    combo_data = [
                        command_type,
                        seconds,
                        round(seconds*60),
                        duration,
                        round(duration*60),
                        speed
                    ]
                    combo_parts.append(combo_data)

                print(combo['_Id'] % 100)
                print(tabulate(combo_parts, headers=[
                      'Type', 'seconds', '(f)', 'duration', '(f)', 'speed'], floatfmt=".4f"))
            self.index['ActionParts'].animation_reference = None


if __name__ == '__main__':
    index = DBViewIndex()
    view = DragonData(index)
    # view.export_all_to_folder()
    view.simplified_combos()
