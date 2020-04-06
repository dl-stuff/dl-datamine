import json
import os
import errno
import aiohttp
import asyncio
import re
import concurrent
from collections import defaultdict

from PIL import Image, ImageDraw
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

    def get_by_diff(self, other):
        return list(filter(lambda x: x[0] not in other.keys(), self.items()))


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
    # dest, _ = os.path.splitext(dest)
    # dest = dest + '.png'
    # check_target_path(dest)
    # img = data.image
    # img.save(dest)
    return data.image

def unpack_MonoBehaviour(data, dest, stdout_log=False):
    if stdout_log:
        print('MonoBehaviour', dest, flush=True)
    dest, _ = os.path.splitext(dest)
    dest += '.json'
    check_target_path(dest)

    with open(dest, 'w', encoding='utf8', newline='') as f:
        write_json(f, data)
    return None

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
    return None

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
            return dest, method(data, dest, stdout_log)
            

UNPACK = {
    'Texture2D': unpack_Texture2D, 
    'MonoBehaviour': unpack_MonoBehaviour,
    'GameObject': unpack_GameObject,
    'AnimationClip': unpack_MonoBehaviour,
    'AnimatorOverrideController': unpack_MonoBehaviour
}

wyrmprint_alpha = Image.new('RGBA', (1024, 1024), color=(0, 0, 0, 255))
ImageDraw.Draw(wyrmprint_alpha).rectangle([212, 26, 811, 997], fill=(255, 255, 255, 255), outline=None)
wyrmprint_alpha = wyrmprint_alpha.convert('L')

def merge_YCbCr(Y_img, Cb_img, Cr_img):
    _, _, _, Y = Y_img.convert('RGBA').split()
    Cb = Cb_img.convert('L').resize(Y_img.size, Image.ANTIALIAS)
    Cr = Cr_img.convert('L').resize(Y_img.size, Image.ANTIALIAS)
    return Image.merge('YCbCr', (Y, Cb, Cr)).convert('RGBA')

def merge_categorized(all_categorized_images, stdout_log=False):
    for dest, sorted_images in all_categorized_images.items():
        if len(sorted_images) == 1:
            image = next(iter(sorted_images.values()))
            dest = os.path.splitext(dest)[0] + '.png'
            check_target_path(dest)
            image.save(dest)
            if stdout_log:
                print(f'Saved {dest}')
            continue
        if 'sprite' in sorted_images:
            base = sorted_images['sprite']
            if 'alphaA8' in sorted_images:
                _, _, _, a = sorted_images['alphaA8'].split()
            elif (alpha := 'alpha') in sorted_images or (alpha := 'A') in sorted_images:
                a = sorted_images[alpha].convert('L')
            base.putalpha(a)
            dest = os.path.splitext(dest)[0] + '.png'
            check_target_path(dest)
            base.save(dest)
            if stdout_log:
                print(f'Merged RGBA {dest}')
        if 'Y' in sorted_images:
            merged = merge_YCbCr(sorted_images['Y'], sorted_images['Cb'], sorted_images['Cr'])
            if 'alpha' in sorted_images:
                a = sorted_images['alpha'].convert('L')
            elif sorted_images['Y'].size == (1024, 1024):
                a = wyrmprint_alpha
            else:
                a = None
            if a is not None:
                merged.putalpha(a)
            dest = os.path.splitext(dest)[0] + '.png'
            check_target_path(dest)
            merged.save(dest)
            if stdout_log:
                print(f'Merged YCbCr {dest}')

def merge_indexed(all_indexed_images, stdout_log=False, combine_all=False):
    for dest, images in all_indexed_images.items():
        alpha = images['a']
        color = images['c']
        dest = os.path.splitext(dest)[0]
        with open(dest + '.json', 'r') as f:
            data = json.load(f)
        mapping = data['partsTextureIndexTable']
        position = data['partsDataTable'][0]['position']
        size = data['partsDataTable'][0]['size']
        box = [int(position['x']-size['x']/2), int(position['y']-size['y']/2), int(position['x']+size['x']/2), int(position['y']+size['y']/2)]
        layer1 = {}
        layer2 = {}
        for entry in mapping:
            c_idx = entry['colorIndex']
            a_idx = entry['alphaIndex']
            c_dict = color[c_idx]
            a_dict = alpha[a_idx]
            merged = merge_YCbCr(c_dict['Y'], c_dict['Cb'], c_dict['Cr'])
            # merged.putalpha(a_dict['alpha'].convert('L'))
            if 'alpha' in a_dict:
                mask = a_dict['alpha'].convert('L')
            else:
                mask = None
            if a_idx == 0:
                layer1[f'{c_idx:03}{a_idx:03}'] = merged, mask
            else:
                layer2[f'{c_idx:03}{a_idx:03}'] = merged, mask
            # merged.save(f'{dest}_c{c_idx:03}a{a_idx:03}.png')
        if combine_all:
            base = Image.open(f'{dest}_base.png')
            # for l1_key, l1_img in layer1.items():
            #     for l2_key, l2_img in layer2.items():
            #         base.paste(l1_img[0], box=box, mask=l1_img[1])
            #         base.paste(l2_img[0], box=box, mask=l2_img[1])
            #         base.save(f'{dest}_{l1_key}_{l2_key}.png')
            for l1, l2 in zip(layer1.items(), layer2.items()):
                l1_key, l1_img = l1
                l2_key, l2_img = l2
                base.paste(l1_img[0], box=box, mask=l1_img[1])
                base.paste(l2_img[0], box=box, mask=l2_img[1])
                merged_dest = os.path.join(os.path.dirname(dest), 'merged', f'{os.path.basename(dest)}_{l1_key}_{l2_key}.png')
                check_target_path(merged_dest)
                base.save(merged_dest)
            if stdout_log:
                print(f'Merged expressions {dest}')
        for layer in (layer1, layer2):
            for key, img in layer.items():
                if img[1]:
                    img[0].putalpha(img[1])
                img[0].save(f'{dest}_{key}.png')
                if stdout_log:
                    print(f'Saved {dest}_{key}')

IMAGE_CATEGORY = re.compile(r'(.+?)_(sprite|alpha|alphaA8|Y|Cb|Cr)$')
IMAGE_ALPHA_INDEX = re.compile(r'(.+?)_parts_([a-z])(\d{3})_(sprite|alpha|alphaA8|Y|Cb|Cr)$')
def merge_images(image_list, stdout_log=False, do_indexed=False):
    all_categorized_images = defaultdict(lambda: {})
    all_indexed_images = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {})))
    for images in image_list:
        if images is None:
            continue
        for dest, img in images.items():
            res = IMAGE_ALPHA_INDEX.match(dest)
            if res:
                dest, designation, index, category = res.groups()
                all_indexed_images[dest][designation][int(index)][category] = img
                continue
            res = IMAGE_CATEGORY.match(dest)
            if res:
                dest, category = res.groups()
                all_categorized_images[dest][category] = img
                continue
            all_categorized_images[dest]['sprite'] = img

    merge_categorized(all_categorized_images, stdout_log=stdout_log)
    if do_indexed:
        merge_indexed(all_indexed_images, stdout_log=stdout_log)


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
                print(f'Download {dl_target} from {source}')
            with open(dl_target, 'wb') as f:
                f.write(await resp.read())
            
            if extract is None:
                extract = os.path.dirname(target).replace('/', '_')
            ex_target = os.path.join(self.ex_dir, region, extract)
            am = AssetsManager(dl_target)
            texture_2d = {}
            for asset in am.assets.values():
                for obj in asset.objects.values():
                    result = unpack(obj, ex_target, self.stdout_log)
                    if result and result[1]:
                        texture_2d[result[0]] = result[1]
            if len(texture_2d) > 0:
                return texture_2d

    async def download_and_extract(self, download_list, extract, region='jp'):
        async with aiohttp.ClientSession() as session:
            result = await asyncio.gather(*[
                self.down_ex(session, source, region, target, extract)
                for target, source in download_list
            ])
            merge_images(result, self.stdout_log)

    def download_and_extract_by_pattern(self, label_patterns, region='jp'):
        for pat, extract in label_patterns.items():
            download_list = self.pm[region].get_by_pattern(pat)
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.download_and_extract(download_list, extract, region))

    def download_and_extract_by_diff(self, old_manifest, region='jp'):
        old_manifest = ParsedManifest(old_manifest)
        download_list = self.pm[region].get_by_diff(old_manifest)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.download_and_extract(download_list, None, region))

if __name__ == '__main__':
    ex = Extractor('jpmanifest_with_asset_labels.txt', 'enmanifest_with_asset_labels.txt', ex_dir='_images', stdout_log=False)
    IMAGE_PATTERNS = {
        # r'^images/icon/': None,
        # r'^images/outgame': None

        r'^images/icon/ability/l': '../icon/ability',
        r'^images/icon/amulet/l': '../icon/wyrmprint',
        r'^images/icon/chara/l': '../icon/character',
        r'^images/icon/element/m': '../icon/element',
        r'^images/icon/weapontype/m': '../icon/weapontype',
        r'^images/icon/skill/l': '../icon/skill',
        r'^images/icon/stamp/l/framed': '../icon/stamp',
        r'^images/icon/status': '../icon/status',
        r'^images/icon/weapon/l': '../icon/weapon',
        r'^images/outgame/unitdetail/amulet': '../portrait/amulet',
        r'^images/outgame/unitdetail/chara': '../portrait/character',
        r'^images/outgame/unitdetail/dragon': '../portrait/dragon',
    }

    ex.download_and_extract_by_pattern(IMAGE_PATTERNS, region='jp')
