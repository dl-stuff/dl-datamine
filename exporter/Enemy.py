from loader.Database import DBManager, DBView, DBDict
from exporter.Mappings import AFFLICTION_TYPES, TRIBE_TYPES, ELEMENTS

class EnemyAbility(DBView):
    def __init__(self, db):
        super().__init__(db, 'EnemyAbility', labeled_fields=['_Name'])

class EnemyList(DBView):
    def __init__(self, db):
        super().__init__(db, 'EnemyList', labeled_fields=['_Name'])

    def process_res(self, res, exclude_falsy=False):
        if '_TribeType' in res and res['_TribeType']:
            res['_TribeType'] = TRIBE_TYPES.get(res['_TribeType'], res['_TribeType'])
        return res

    # def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, exclude_falsy=False):
    def get(self, pk, fields=None, exclude_falsy=True, full_query=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        res = self.process_res(res, exclude_falsy=exclude_falsy)
        return res

class EnemyData(DBView):
    def __init__(self, db):
        super().__init__(db, 'EnemyData')
        self.enemy_list = EnemyList(db)

    def process_res(self, res, exclude_falsy=False):
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
        res = self.process_res(res, exclude_falsy=exclude_falsy)
        return res

class EnemyParam(DBView):
    def __init__(self, db):
        super().__init__(db, 'EnemyParam')
        self.enemy_data = EnemyData(db)
        self.enemy_ability = EnemyAbility(db)

    def process_res(self, res, exclude_falsy=False):
        if '_DataId' in res and res['_DataId']:
            if (data := self.enemy_data.get(res['_DataId'], exclude_falsy=exclude_falsy)):
                res['_DataId'] = data
        # for child in ('_Child01Param', '_Child02Param', '_Child03Param'):
        #     if child in res and res[child]:
        #         if (data := self.get(res[child], exclude_falsy=exclude_falsy)):
        #             res[child] = data
        resists = {}
        for k, v in AFFLICTION_TYPES.items():
            resist_key = f'_RegistAbnormalRate{k:02}'
            if resist_key in res:
                resists[v] = res[resist_key]
                del res[resist_key]
            else:
                resists[v] = 0
        res['_AfflictionResist'] = resists
        return res

    # @staticmethod
    # def remove_falsy_fields(res):
    #     return DBDict(filter(lambda x: bool(x[1]) or x[0].startswith('_RegistAbnormalRate'), res.items()))

    # def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, exclude_falsy=False):
    def get(self, pk, fields=None, exclude_falsy=True, full_query=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        res = self.process_res(res, exclude_falsy=exclude_falsy)
        return res

if __name__ == '__main__':
    db = DBManager()
    view = EnemyParam(db)
    res = view.get(219010101)
    # 219010101 volk
    print(res)
