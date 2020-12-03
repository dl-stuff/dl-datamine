import argparse
from time import monotonic
from tqdm import tqdm

from loader.Database import DBManager, DBViewIndex
from exporter.Adventurers import CharaData
from exporter.Dragons import DragonData
from exporter.Enemy import EnemyParam
from exporter.Weapons import WeaponBody, WeaponType
from exporter.Wyrmprints import AbilityCrest, UnionAbility
from exporter.Shared import ActionCondition, PlayerActionHitAttribute, PlayerAction, AbilityData

CLASSES = [
    CharaData,
    DragonData,
    EnemyParam,
    WeaponBody,
    AbilityCrest,
    WeaponType,
    # PlayerActionHitAttribute,
    # PlayerAction,
    # AbilityData,
    UnionAbility,
]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Export data from database.')
    parser.add_argument('-o', type=str, help='output directory', default='out')
    args = parser.parse_args()

    start = monotonic()
    index = DBViewIndex()
    views = {}
    for view_class in CLASSES:
        view = view_class(index)
        view.export_all_to_folder(out_dir=args.o)
    print(f'\ntotal: {monotonic()-start:.4f}s', flush=True)