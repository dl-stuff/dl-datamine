import sys
import os
import json
import pathlib
from collections import defaultdict

from loader.Database import DBViewIndex, DBView, check_target_path
from loader.AssetExtractor import Extractor
from exporter.Shared import MaterialData
from exporter.Adventurers import CharaData
from exporter.Dragons import DragonData
from exporter.Wyrmprints import AbilityCrest
from exporter.Weapons import WeaponBody, WeaponBodyBuildupGroup, WeaponBodyGroupSeries


IMAGE_PATTERNS = {
    'jp': {
        r'^images/icon/chara/l': '../chara',
        r'^images/icon/dragon/l': '../dragon',
        r'^images/icon/amulet/l': '../amulet',
        r'^images/icon/weapon/l': '../weapon',
        r'^images/icon/item/materialdata/l': '../material'
    }
}

def download_all_icons(out):
    ex = Extractor(ex_dir=None, ex_img_dir=out, stdout_log=False)
    ex.download_and_extract_by_pattern(IMAGE_PATTERNS)

def make_bv_id(res, view):
    return f'{res["_BaseId"]}_{res["_VariationId"]:02}'

def make_chara_json(res):
    return {
        'NameEN': res['_SecondName'] or res['_Name'],
        'NameJP': res['_SecondNameJP'] or res['_NameJP'],
        'NameCN': res['_SecondNameCN'] or res['_NameCN'],
        'Element': res['_ElementalType'],
        'Weapon': res['_WeaponType'],
        'Rarity': res['_Rarity'],
        'Spiral': bool(res['_MaxLimitBreakCount'] == 5)
    }

def make_dragon_json(res):
    return {
        'NameEN': res['_SecondName'] or res['_Name'],
        'NameJP': res['_SecondNameJP'] or res['_NameJP'],
        'NameCN': res['_SecondNameCN'] or res['_NameCN'],
        'Element': res['_ElementalType'],
        'Rarity': res['_Rarity']
    }

def make_id(res, view):
    return str(res['_Id'])

def make_base_id(res, view):
    return str(res['_BaseId'])

def make_amulet_json(res):
    return {
        'NameEN': res['_Name'],
        'NameJP': res['_NameJP'],
        'NameCN': res['_NameCN'],
        'Rarity': res['_Rarity']
    }

def make_material_json(res):
    return {
        'NameEN': res['_Name'],
        'NameJP': res['_NameJP'],
        'NameCN': res['_NameCN']
    }

def make_weapon_series_json(res):
    return {
        'NameEN': res['_GroupSeriesName'],
        'NameJP': res['_GroupSeriesNameJP'],
        'NameCN': res['_GroupSeriesNameCN']
    }

from urllib.parse import quote
import requests

MAX = 500
BASE_URL = 'https://dragalialost.gamepedia.com/api.php?action=cargoquery&format=json&limit={}'.format(MAX)

def get_api_request(offset, **kwargs):
    q = '{}&offset={}'.format(BASE_URL, offset)
    for key, value in kwargs.items():
        q += '&{}={}'.format(key, quote(value))
    return q

def get_data(**kwargs):
    offset = 0
    data = []
    while offset % MAX == 0:
        url = get_api_request(offset, **kwargs)
        r = requests.get(url).json()
        try:
            if len(r['cargoquery']) == 0:
                break
            data += r['cargoquery']
            offset += len(r['cargoquery'])
        except:
            raise Exception(url)
    return data

all_avail = {
    'Chara': set(),
    'Dragon': {'Gacha'},
    'Amulet': set(),
    'Weapon': set()
}

def process_avail(ak):
    def f(a):
        a = a.strip()
        all_avail[ak].add(a)
        return a
    return f

def chara_availability_data(data):
    for d in get_data(
            tables='Adventurers', 
            fields='Id,VariationId,Availability', 
            where='IsPlayable',
            order_by='Id ASC, VariationId ASC'):
        data[f'{d["title"]["Id"]}_{int(d["title"]["VariationId"]):02}']['Availability'] = list(map(process_avail('Chara'), d['title']['Availability'].split(',')))


GACHA_DEW = {
    3: '150',
    4: '2200',
    5: '8500'
}
def dragon_availability_data(data):
    for d in get_data(
            tables='Dragons', 
            fields='BaseId,VariationId,SellDewPoint,Availability', 
            where='IsPlayable',
            order_by='Id ASC, VariationId ASC'):
        bv_id = f'{d["title"]["BaseId"]}_{int(d["title"]["VariationId"]):02}'
        avail = list(map(process_avail('Dragon'), d['title']['Availability'].split(',')))
        if (d['title']['SellDewPoint'] == GACHA_DEW[data[bv_id]['Rarity']]):
            avail.append('Gacha')
        data[bv_id]['Availability'] = avail

def amulet_availability_data(data):
    for d in get_data(
            tables='Wyrmprints', 
            fields='BaseId,Availability', 
            where='IsPlayable',
            order_by='Id ASC, VariationId ASC'):
        data[d['title']['BaseId']]['Availability'] = list(map(process_avail('Amulet'), d['title']['Availability'].split(',')))

def make_json(out, outfile, view, id_fn, data_fn, avail_fn=None, where=None, order='_Id ASC', name_key='_Name'):
    all_res = view.get_all(exclude_falsy=False, where=where, order=order)
    data = {}
    for res in all_res:
        if not res[name_key]:
            continue
        data[id_fn(res, view)] = data_fn(res)
    if avail_fn:
        avail_fn(data)
        for d in data.copy():
            if 'Availability' not in data[d]:
                del data[d]
    check_target_path(out)
    with open(os.path.join(out, outfile), 'w') as f:
        json.dump(data, f)

# def make_wpn_id(res, view):
#     skin = view.index['WeaponSkin'].get(res['_WeaponSkinId'], exclude_falsy=False)
#     return f'{skin["_BaseId"]}_{skin["_VariationId"]:02}_{skin["_FormId"]}'


def make_wpn_id(skin):
    return f'{skin["_BaseId"]}_{skin["_VariationId"]:02}_{skin["_FormId"]}'

BUILDUP_PIECE = {
    1: 'Unbind',
    2: 'Refinement',
    3: 'Slots',
    5: 'Bonus',
    6: 'Copies'
}

def make_weapon_jsons(out, index):
    view = WeaponBodyBuildupGroup(index)
    all_res = view.get_all(exclude_falsy=True)
    processed = defaultdict(lambda: defaultdict(lambda: []))
    for res in all_res:
        mats = {}
        for i in range(1, 11):
            k1 = f'_BuildupMaterialId{i}'
            k2 = f'_BuildupMaterialQuantity{i}'
            try:
                mats[res[k1]] = res[k2]
            except KeyError:
                continue
        processed[res['_WeaponBodyBuildupGroupId']][res['_BuildupPieceType']].append({
            'Step': res['_Step'],
            'UnbindReq': res.get('_UnlockConditionLimitBreakCount', 0),
            'SkinId': res.get('_RewardWeaponSkinNo', 0),
            'Cost': res['_BuildupCoin'],
            'Mats': mats
        })
    processed = dict(processed)
    outfile = 'weaponbuild.json'
    check_target_path(out)
    with open(os.path.join(out, outfile), 'w') as f:
        json.dump(processed, f, indent=2)

    view = WeaponBody(index)
    all_res = view.get_all(exclude_falsy=True)
    processed = {}
    for res in all_res:
        if not res.get('_Name'):
            continue
        skins = {}
        for i, sid in enumerate(WeaponBody.WEAPON_SKINS):
            try:
                skin = index['WeaponSkin'].get(res[sid], exclude_falsy=True)
                skins[i] = make_wpn_id(skin)
            except (KeyError, TypeError):
                continue
        prereqcreate = [res.get(need) for need in ('_NeedCreateWeaponBodyId1', '_NeedCreateWeaponBodyId2') if res.get(need)]
        prereqfull = res.get('_NeedAllUnlockWeaponBodyId1')
        mats = {}
        for i in range(1, 6):
            k1 = f'_CreateEntityId{i}'
            k2 = f'_CreateEntityQuantity{i}'
            try:
                mats[res[k1]] = res[k2]
            except KeyError:
                continue
        processed[res['_Id']] = {
            'NameEN': res['_Name'],
            'NameJP': res['_NameJP'],
            'NameCN': res['_NameCN'],
            'Series': res['_WeaponSeriesId'],
            'Build': res.get('_WeaponBodyBuildupGroupId'),
            'Element': res['_ElementalType'],
            'Weapon': res['_WeaponType'],
            'Rarity': res['_Rarity'],
            'Unbind': (res.get('_MaxLimitOverCount', -1) + 1) * 4, # check WeaponBodyRarity
            'Prereq': {
                'Create': prereqcreate,
                'FullUp': prereqfull
            },
            'Cost': res.get('_CreateCoin', 0),
            'Mats': mats,
            'Skins': skins,
            'Bonus': any([res.get('_WeaponPassiveEffHp'), res.get('_WeaponPassiveEffAtk')]),
        }
    outfile = 'weapon.json'
    check_target_path(out)
    with open(os.path.join(out, outfile), 'w') as f:
        json.dump(processed, f, indent=2)


if __name__ == '__main__':
    all_avail = {
        'Chara': set(),
        'Dragon': {'Gacha'},
        'Amulet': set(),
        'Weapon': set()
    }
    outdir = os.path.join(pathlib.Path(__file__).parent.absolute(), '..', '..', 'dl-collection')
    # download_all_icons(os.path.join(outdir, 'public'))
    datadir = os.path.join(outdir, 'src', 'data')
    index = DBViewIndex()
    # make_json(datadir, 'chara.json', CharaData(index), make_bv_id, make_chara_json, chara_availability_data)
    # make_json(datadir, 'dragon.json', DragonData(index), make_bv_id, make_dragon_json, dragon_availability_data)
    # make_json(datadir, 'amulet.json', AbilityCrest(index), make_base_id, make_amulet_json, amulet_availability_data)
    # with open(os.path.join(datadir, 'availabilities.json'), 'w') as f:
    #     json.dump({k: sorted(list(v)) for k, v in all_avail.items()}, f)
    # make_json(datadir, 'material.json', MaterialData(index), make_id, make_material_json)
    # make_json(datadir, 'weaponseries.json', WeaponBodyGroupSeries(index), make_id, make_weapon_series_json, name_key='_GroupSeriesName')
    make_weapon_jsons(datadir, index)
