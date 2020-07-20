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

def make_id(res):
    return str(res["_BaseId"])

def make_amulet_json(res):
    return {
        'NameEN': res['_Name'],
        'NameJP': res['_NameJP'],
        'NameCN': res['_NameCN'],
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
        'Weapon': res['_Type'],
        'Rarity': res['_Rarity'],
        'Craft': res['_CraftSeriesId']
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

def weapon_availability_data(data):
    for d in get_data(
            tables='Weapons', 
            fields='BaseId,VariationId,FormId,Availability', 
            where='IsPlayable',
            order_by='Id ASC, VariationId ASC'):
        data[f'{d["title"]["BaseId"]}_{int(d["title"]["VariationId"]):02}_{d["title"]["FormId"]}']['Availability'] = list(map(process_avail('Weapon'), d['title']['Availability'].split(',')))

def make_json(out, outfile, view, id_fn, data_fn, avail_fn, where=None, order='_BaseId ASC, _VariationId ASC'):
    all_res = view.get_all(exclude_falsy=False, where=where, order=order)
    data = {}
    for res in all_res:
        if not res['_Name']:
            continue
        data[id_fn(res)] = data_fn(res)
    avail_fn(data)
    for d in data.copy():
        if 'Availability' not in data[d]:
            del data[d]
    check_target_path(out)
    with open(os.path.join(out, outfile), 'w') as f:
        json.dump(data, f)

if __name__ == '__main__':
    all_avail = {
        'Chara': set(),
        'Dragon': {'Gacha'},
        'Amulet': set(),
        'Weapon': set()
    }
    outdir = os.path.join(pathlib.Path(__file__).parent.absolute(), '..', '..', 'dl-collection')
    download_all_icons(os.path.join(outdir, 'public'))
    datadir = os.path.join(outdir, 'src', 'data')
    index = DBViewIndex()
    make_json(datadir, 'chara.json', CharaData(index), make_bv_id, make_chara_json, chara_availability_data)
    make_json(datadir, 'dragon.json', DragonData(index), make_bv_id, make_dragon_json, dragon_availability_data)
    make_json(datadir, 'amulet.json', AmuletData(index), make_id, make_amulet_json, amulet_availability_data)
    make_json(datadir, 'weapon.json', WeaponData(index), make_wpn_id, make_weapon_json, weapon_availability_data)
    with open(os.path.join(datadir, 'availabilities.json'), 'w') as f:
        json.dump({k: sorted(list(v)) for k, v in all_avail.items()}, f)
