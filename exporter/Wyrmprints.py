import json
import os

from loader.Database import DBManager, DBView
from exporter.Shared import AbilityData, SkillData, PlayerAction

from exporter.Mappings import CLASS_TYPES

class AmuletData(DBView):
    def __init__(self, db):
        super().__init__(db, 'AmuletData', labeled_fields=['_Name', '_Text1', '_Text2', '_Text3', '_Text4', '_Text5'])
        self.abilities = AbilityData(db)

    def process_result(self, res, exclude_falsy, full_query=True, full_abilities=False):
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

    @staticmethod
    def outfile_name(res, ext='.json'):
        name = 'UNKNOWN' if '_Name' not in res else res['_Name']
        return f'{res["_BaseId"]}_{res["_VariationId"]:02}_{name}{ext}'

    def export_all_to_folder(self, out_dir='./out', ext='.json', exclude_falsy=True):
        out_dir = os.path.join(out_dir, 'wyrmprints')
        super().export_all_to_folder(out_dir, ext, exclude_falsy=exclude_falsy, full_query=True, full_abilities=False)

if __name__ == '__main__':
    db = DBManager()
    view = AmuletData(db)
    view.export_all_to_folder()