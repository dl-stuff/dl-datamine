import json
import os
import errno
import aiohttp
import asyncio
import re
import concurrent

from UnityPy import AssetsManager

class ParsedManifest(dict):
    def __init__(self, manifest=None):
        super().__init__({})
        with open(manifest) as f:
            for line in f:
                url, label = [l.strip() for l in line.split('|')]
                self[label] = url

    def get_by_pattern(self, pattern):
        if not isinstance(pattern, re.Pattern):
            pattern = re.compile(pattern, flags=re.IGNORECASE)
        return list(filter(lambda x: pattern.search(x[0]), self.items()))


def check_target_path(target):
    if not os.path.exists(os.path.dirname(target)):
        try:
            os.makedirs(os.path.dirname(target))
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise

def merge_path_dir(path):
    new_dir = os.path.dirname(path).replace('/', '_')
    return os.path.join(new_dir, os.path.basename(path))

def process_json(tree):
    while isinstance(tree, dict):
        if 'dict' in tree:
            tree = tree['dict']
        elif 'list' in tree:
            tree = tree['list']
        elif 'entriesValue' in tree and 'entriesHashCode' in tree:
            return {k: process_json(v) for k, v in zip(tree['entriesHashCode'], tree['entriesValue'])}
        else:
            return tree
    return tree

def write_json(f, data):
    tree = data.read_type_tree()
    json.dump(process_json(tree), f, indent=2)

def unpack_Texture2D(data, dest, stdout_log=False):
    if stdout_log:
        print('Texture2D', dest, flush=True)
    dest, _ = os.path.splitext(dest)
    dest = dest + '.png'
    check_target_path(dest)
    img = data.image
    img.save(dest)

def unpack_MonoBehaviour(data, dest, stdout_log=False):
    if stdout_log:
        print('MonoBehaviour', dest, flush=True)
    dest, _ = os.path.splitext(dest)
    dest += '.json'
    check_target_path(dest)

    with open(dest, 'w', encoding='utf8', newline='') as f:
        write_json(f, data)

def unpack_GameObject(data, destination_folder, stdout_log):
    dest = os.path.join(destination_folder, os.path.splitext(data.name)[0])
    if stdout_log:
        print('GameObject', dest, flush=True)
    dest += '.json'
    mono_list = []
    for idx, obj in enumerate(data.components):
        obj_type_str = str(obj.type)
        if obj_type_str in UNPACK:
            subdata = obj.read()
            if obj_type_str == 'MonoBehaviour':
                json_data = subdata.read_type_tree()
                if json_data:
                    mono_list.append(json_data)
            elif obj_type_str == 'GameObject':
                UNPACK[obj_type_str](subdata, os.path.join(dest, '{:02}'.format(idx)))
    if len(mono_list) > 0:
        check_target_path(dest)
        with open(dest, 'w', encoding='utf8', newline='') as f:
            json.dump(mono_list, f, indent=2)

def unpack(obj, ex_target, stdout_log=False):
    obj_type_str = str(obj.type)
    if obj_type_str in UNPACK:
        data = obj.read()
        method = None
        if obj_type_str == 'GameObject':
            dest = ex_target
            method = UNPACK[obj_type_str]
        elif data.name:
            dest = os.path.join(ex_target, data.name)
            method = UNPACK[obj_type_str]
        if method:
            method(data, dest, stdout_log)

UNPACK = {
    'Texture2D': unpack_Texture2D, 
    'MonoBehaviour': unpack_MonoBehaviour,
    'GameObject': unpack_GameObject,
    'AnimationClip': unpack_MonoBehaviour,
    'AnimatorOverrideController': unpack_MonoBehaviour
}

class Extractor:
    def __init__(self, jp_manifest, en_manifest, dl_dir='./_download', ex_dir='./_extract', stdout_log=True):
        self.pm = {
            'jp': ParsedManifest(jp_manifest),
            'en': ParsedManifest(en_manifest)
        }
        self.dl_dir = dl_dir
        self.ex_dir = ex_dir
        self.extract_list = []
        self.stdout_log = stdout_log

    async def down_ex(self, session, source, region, target, extract):
        dl_target = os.path.join(self.dl_dir, region, target)
        check_target_path(dl_target)
        async with session.get(source) as resp:
            assert resp.status == 200
            if self.stdout_log:
                print(f'Download {dl_target}, {source}')
            with open(dl_target, 'wb') as f:
                f.write(await resp.read())
            
            ex_target = os.path.join(self.ex_dir, region, extract)
            am = AssetsManager(dl_target)
            for asset in am.assets.values():
                for obj in asset.objects.values():
                    unpack(obj, ex_target, self.stdout_log)

    async def download_and_extract(self, download_list, extract, region='jp'):
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(*[
                self.down_ex(session, source, region, target, extract)
                for target, source in download_list
            ])

    def download_and_extract_all(self, label_patterns, region='jp'):
        for pat, extract in label_patterns.items():
            download_list = self.pm[region].get_by_pattern(pat)
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.download_and_extract(download_list, extract, region))