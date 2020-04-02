import json
import os

from loader.Database import DBManager, DBView
from exporter.Shared import AbilityData, SkillData, PlayerAction, check_target_path

from exporter.Mappings import CLASS_TYPES

class AmuletData(DBView):
    def __init__(self, db):
        super().__init__(db, 'AmuletData', labeled_fields=['_Name', '_Text1', '_Text2', '_Text3', '_Text4', '_Text5'])
        self.abilities = AbilityData(db)

    def process_result(self, res, exclude_falsy, full_query, full_abilities):
        if not full_query:
            return res
        if '_AmuletType' in res:
            res['_AmuletType'] = CLASS_TYPES.get(res['_AmuletType'], res['_AmuletType'])
        inner = (1, 2, 3) if full_abilities else (3,)
        outer = (1, 2, 3)
        for i in outer:
            for j in inner:
                k = f'_Abilities{i}{j}'
                if k in res and res[k]:
                    res[k] = self.abilities.get(res[k], full_query=True, exclude_falsy=exclude_falsy)
        return res

    def get(self, pk, fields=None, exclude_falsy=False, full_query=True, full_abilities=False):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        return self.process_result(res, exclude_falsy, full_query, full_abilities)

    def export_all_to_folder(self, out_dir=None, ext='.json', exclude_falsy=True):
        if not out_dir:
            out_dir = f'./out/wyrmprints'
        all_res = self.get_all(exclude_falsy=exclude_falsy)
        check_target_path(out_dir)
        for res in all_res:
            res = self.process_result(res, exclude_falsy, True, False)
            name = 'UNKNOWN' if '_Name' not in res else res['_Name']
            output = os.path.join(out_dir, f'{res["_BaseId"]}_{res["_VariationId"]:02}_{name}{ext}')
            with open(output, 'w', newline='', encoding='utf-8') as fp:
                json.dump(res, fp, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    db = DBManager()
    view = AmuletData(db)
    view.export_all_to_folder()