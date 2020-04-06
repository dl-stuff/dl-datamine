import argparse

from loader.Database import DBManager
from exporter.Adventurers import CharaData
from exporter.Dragons import DragonData
from exporter.Enemy import EnemyParam
from exporter.Weapons import WeaponData
from exporter.Wyrmprints import AmuletData


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Export data from database.')
    parser.add_argument('-o', type=str, help='output directory', default='out')
    parser.add_argument('-mode', type=str, help='output mode', default='json')
    args = parser.parse_args()

    db = DBManager()
    views = {}
    for view_class in (CharaData, DragonData, EnemyParam, WeaponData, AmuletData):
        views[view_class.__name__] = view_class(db)
    if args.mode == 'json':
        for view in views.values():
            view.export_all_to_folder(out_dir=args.o)