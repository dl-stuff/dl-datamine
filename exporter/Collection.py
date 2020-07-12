import sys
import os
import json
import pathlib

from loader.Database import DBViewIndex, DBView, check_target_path
from loader.AssetExtractor import Extractor
from exporter.Adventurers import CharaData
from exporter.Dragons import DragonData
from exporter.Wyrmprints import AmuletData
from exporter.Weapons import WeaponData


IMAGE_PATTERNS = {
    r'^images/icon/chara/l': '../chara',
    r'^images/icon/dragon/l': '../dragon',
    r'^images/icon/amulet/l': '../amulet',
    r'^images/icon/weapon/l': '../weapon'
}

MANIFESTS = {
    'jp': 'manifest/assetbundle.manifest.json',
    'en': 'manifest/assetbundle.en_us.manifest.json',
    'cn': 'manifest/assetbundle.zh_cn.manifest.json',
    'tw': 'manifest/assetbundle.zh_tw.manifest.json'
}

def download_all_icons(out):
    ex = Extractor(MANIFESTS, ex_dir=None, ex_img_dir=out, stdout_log=False)
    ex.download_and_extract_by_pattern(IMAGE_PATTERNS, region='jp')

def make_bv_id(res):
    return f'{res["_BaseId"]}_{res["_VariationId"]:02}'

def make_chara_json(res):
    return {
        'NameEN': res['_SecondName'] or res['_Name'],
        'NameJP': res['_SecondNameJP'] or res['_NameJP'],
        'NameCN': res['_SecondNameCN'] or res['_NameCN'],
        'Element': res['_ElementalType'],
        'Weapon': res['_WeaponType'],
        'Rarity': res['_Rarity'],
        'Spiral': bool(res['_MaxLimitBreakCount'] == 5),
        'SkillShare': res['_EditSkillLevelNum'] * (-1 if res['_DefaultIsUnlockEditSkill'] else 1)
    }

def make_dragon_json(res):
    return {
        'NameEN': res['_SecondName'] or res['_Name'],
        'NameJP': res['_SecondNameJP'] or res['_NameJP'],
        'NameCN': res['_SecondNameCN'] or res['_NameCN'],
        'Element': res['_ElementalType'],
        'Rarity': res['_Rarity'],
        'Gift': res['_FavoriteType']
    }

def make_id(res):
    return str(res["_BaseId"])

def make_amulet_json(res):
    return {
        'NameEN': res['_Name'],
        'NameJP': res['_NameJP'],
        'NameCN': res['_NameCN'],
        'Type': res['_AmuletType'],
        'Rarity': res['_Rarity']
    }

def make_wpn_id(res):
    return f'{res["_BaseId"]}_{res["_VariationId"]:02}_{res["_FormId"]}'

def make_weapon_json(res):
    return {
        'NameEN': res['_Name'],
        'NameJP': res['_NameJP'],
        'NameCN': res['_NameCN'],
        'Element': res['_ElementalType'],
        'Type': res['_Type'],
        'Rarity': res['_Rarity'],
        'Craftable': bool(res['_CraftSeriesId'])
    }


def make_json(out, outfile, view, id_fn, data_fn, where=None):
    all_res = view.get_all(exclude_falsy=False, where=where)
    data = {}
    for res in all_res:
        if not res['_IsPlayable']:
            continue
        data[id_fn(res)] = data_fn(res)
    check_target_path(out)
    with open(os.path.join(out, outfile), 'w') as f:
        json.dump(data, f)

if __name__ == '__main__':
    outdir = os.path.join(pathlib.Path(__file__).parent.absolute(), '..', '..', 'dl-collection')
    download_all_icons(os.path.join(outdir, 'public'))
    datadir = os.path.join(outdir, 'src', 'data')
    index = DBViewIndex()
    make_json(datadir, 'chara.json', CharaData(index), make_bv_id, make_chara_json)
    make_json(datadir, 'dragon.json', DragonData(index), make_bv_id, make_dragon_json)
    make_json(datadir, 'amulet.json', AmuletData(index), make_id, make_amulet_json)
    make_json(datadir, 'weapon.json', WeaponData(index), make_wpn_id, make_weapon_json)
