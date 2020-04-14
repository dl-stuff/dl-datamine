import argparse

from loader.Database import DBManager, DBViewIndex
from exporter.Adventurers import CharaData
from exporter.Dragons import DragonData
from exporter.Enemy import EnemyParam
from exporter.Weapons import WeaponData
from exporter.Wyrmprints import AmuletData
from exporter.Shared import ActionCondition, PlayerActionHitAttribute


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Export data from database.')
    parser.add_argument('-o', type=str, help='output directory', default='out')
    parser.add_argument('-mode', type=str, help='output mode', default='json')
    args = parser.parse_args()

    index = DBViewIndex()
    views = {}
    for view_class in (CharaData, DragonData, EnemyParam, WeaponData, AmuletData, ActionCondition, PlayerActionHitAttribute):
        views[view_class.__name__] = view_class(index)
    if args.mode == 'json':
        for view in views.values():
            view.export_all_to_folder(out_dir=args.o)