from UnityPy.export.SpriteHelper import get_triangles
from UnityPy.classes.Sprite import SpritePackingRotation, SpritePackingMode
from UnityPy.enums import TextureFormat
import json
import os
import errno

import aiohttp
import asyncio

import urllib.request
import multiprocessing

import re
from tqdm import tqdm
from queue import SimpleQueue
from collections import defaultdict

from PIL import Image, ImageDraw
from UnityPy import AssetsManager


MANIFESTS = {
    'jp': 'manifest/assetbundle.manifest.json',
    'en': 'manifest/assetbundle.en_us.manifest.json',
    'cn': 'manifest/assetbundle.zh_cn.manifest.json',
    'tw': 'manifest/assetbundle.zh_tw.manifest.json'
}


class ParsedManifestFlat(dict):
    def __init__(self, manifest):
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
        return list(filter(lambda x: x[0] not in other.keys() or x[1] != other[x[0]], self.items()))


class AssetEntry:
    URL_FORMAT = 'http://dragalialost.akamaized.net/dl/assetbundles/Android/{h}/{hash}'

    def __init__(self, asset):
        self.name = asset['name']
        self.hash = asset['hash']
        self.url = AssetEntry.URL_FORMAT.format(
            h=self.hash[0:2], hash=self.hash)
        if 'dependencies' in asset and asset['dependencies']:
            self.dependencies = asset['dependencies']
        else:
            self.dependencies = None
        self.size = asset['size']
        self.group = asset['group']
        self.dependents = None

    def map_dependencies(self, pm):
        if self.dependencies:
            mapped = []
            for dep in self.dependencies:
                mapped.append(pm[dep])
                if pm[dep].dependents:
                    pm[dep].dependents.append(self)
                else:
                    pm[dep].dependents = [self]
            self.dependencies = mapped

    def __repr__(self):
        if self.dependencies:
            return f'{self.name} ({self.hash})\n-> {self.dependencies}'
        else:
            return f'{self.name} ({self.hash})'

    def __eq__(self, other):
        return self.hash == other.hash

    def __ne__(self, other):
        return self.hash != other.hash


class ParsedManifest(dict):
    def __init__(self, manifest):
        super().__init__({})
        self.path = manifest
        with open(manifest) as f:
            tree = json.load(f)
        for category in tree['categories']:
            for asset in category['assets']:
                self[asset['name']] = AssetEntry(asset)
        for asset in tree['rawAssets']:
            self[asset['name']] = AssetEntry(asset)
        for asset in self.values():
            asset.map_dependencies(self)

    DO_NOT_EXPAND = {'shader'}

    @staticmethod
    def expand_dependencies(targets):
        q = SimpleQueue()
        seen = set()
        results = {}
        for k, v in targets:
            q.put((k, v))
        while not q.empty():
            k, v = q.get()
            if k not in ParsedManifest.DO_NOT_EXPAND and v.name not in seen:
                seen.add(v.name)
                try:
                    results[k].append(v.url)
                except:
                    results[k] = [v.url]
                if v.dependencies:
                    for dep in v.dependencies:
                        q.put((k, dep))
        return list(results.items())

    @staticmethod
    def link_dependencies(targets):
        results = {}
        has_dep = []
        for k, v in targets:
            if v.dependents:
                has_dep.append(v)
            else:
                results[k] = [v.url]
        for v in has_dep:
            found = False
            for dep in v.dependents:
                if dep.name in results:
                    results[dep.name].append(v.url)
                    found = True
            if not found:
                results[v.name] = [v.url]
        return list(results.items())

    @staticmethod
    def flatten(targets):
        return [(k, [v.url]) for k, v in targets]

    @staticmethod
    def _get_by(targets, mode):
        if mode == 2:
            return ParsedManifest.expand_dependencies(targets)
        elif mode == 1:
            return ParsedManifest.link_dependencies(targets)
        else:
            return ParsedManifest.flatten(targets)

    def get_by_pattern(self, pattern, mode=0):
        if not isinstance(pattern, re.Pattern):
            pattern = re.compile(pattern, flags=re.IGNORECASE)
        targets = filter(lambda x: pattern.search(x[0]), self.items())
        return ParsedManifest._get_by(targets, mode)

    def get_by_diff(self, other, mode=0):
        targets = filter(lambda x: x[0] not in other.keys() or x[1] != other[x[0]], self.items())
        return ParsedManifest._get_by(targets, mode)

    def get_by_pattern_diff(self, pattern, other, mode=0):
        if not isinstance(pattern, re.Pattern):
            pattern = re.compile(pattern, flags=re.IGNORECASE)
        targets = filter(lambda x: pattern.search(x[0]) and (x[0] not in other.keys() or x[1] != other[x[0]]), self.items())
        return ParsedManifest._get_by(targets, mode)


def check_target_path(target):
    if not os.path.exists(os.path.dirname(target)):
        try:
            os.makedirs(os.path.dirname(target))
        except OSError as exc:  # Guard against race condition
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
    data.read_type_tree()
    tree = data.type_tree
    json.dump(process_json(tree), f, indent=2)


def unpack_Texture2D(data, dest, texture_2d, stdout_log=False):
    if stdout_log:
        print('Texture2D', dest, flush=True)
    try:
        tpl = (dest, data.image, data.m_TextureFormat)
        try:
            texture_2d[data.path_id]['root'] = tpl
        except KeyError:
            texture_2d[data.path_id] = {}
            texture_2d[data.path_id]['root'] = tpl
    except:
        pass


SPRITE_ROTATION = {
    SpritePackingRotation.kSPRFlipHorizontal: Image.FLIP_TOP_BOTTOM,
    SpritePackingRotation.kSPRFlipVertical: Image.FLIP_LEFT_RIGHT,
    SpritePackingRotation.kSPRRotate180: Image.ROTATE_180,
    SpritePackingRotation.kSPRRotate90: Image.ROTATE_270
}


def unpack_Sprite(data, dest, texture_2d, stdout_log=False):
    if stdout_log:
        print('Sprite', dest, flush=True)

    m_Sprite = data
    atlas = None
    if m_Sprite.m_SpriteAtlas:
        atlas = m_Sprite.m_SpriteAtlas.read()
    elif m_Sprite.m_AtlasTags:
        # looks like the direct pointer is empty, let's try to find the Atlas via its name
        for obj in m_Sprite.assets_file.objects.values():
            if obj.type == "SpriteAtlas":
                atlas = obj.read()
                if atlas.name == m_Sprite.m_AtlasTags[0]:
                    break
                atlas = None
    if atlas:
        sprite_atlas_data = atlas.render_data_map[m_Sprite.m_RenderDataKey]
    else:
        sprite_atlas_data = m_Sprite.m_RD

    rect = sprite_atlas_data.textureRect
    rect_size = (int(rect.right - rect.left), int(rect.bottom - rect.top))

    rotation = None
    settings_raw = sprite_atlas_data.settingsRaw
    if settings_raw.packed == 1:
        try:
            rotation = SPRITE_ROTATION[settings_raw.packingRotation]
        except:
            pass

    mask = None
    if settings_raw.packingMode == SpritePackingMode.kSPMTight:
        mask = Image.new('1', rect_size, color=0)
        draw = ImageDraw.ImageDraw(mask)
        for triangle in get_triangles(m_Sprite):
            draw.polygon(triangle, fill=1)

    s_tuple = (dest, rect, rotation, mask)
    try:
        texture_2d[sprite_atlas_data.texture.path_id]['sprites'].append(
            s_tuple)
    except KeyError:
        try:
            texture_2d[sprite_atlas_data.texture.path_id]['sprites'] = [s_tuple]
        except KeyError:
            texture_2d[sprite_atlas_data.texture.path_id] = {}
            texture_2d[sprite_atlas_data.texture.path_id]['sprites'] = [s_tuple]


def unpack_MonoBehaviour(data, dest, stdout_log=False):
    if stdout_log:
        print('MonoBehaviour', dest, flush=True)
    dest, _ = os.path.splitext(dest)
    dest += '.json'
    check_target_path(dest)

    with open(dest, 'w', encoding='utf8', newline='') as f:
        write_json(f, data)


def unpack_TextAsset(data, dest, stdout_log=False):
    if stdout_log:
        print('TextAsset', dest, flush=True)
    check_target_path(dest)

    try:
        with open(dest, 'w', encoding='utf8', newline='') as f:
            f.write(data.text)
    except UnicodeDecodeError:
        with open(dest, 'wb') as f:
            f.write(data.script)


def unpack_GameObject(data, destination_folder, stdout_log):
    dest = os.path.join(destination_folder, os.path.splitext(data.name)[0])
    if stdout_log:
        print('GameObject', dest, flush=True)
    dest += '.json'
    mono_list = []
    for idx, obj in enumerate(data.components):
        obj_type_str = str(obj.type)
        if obj_type_str == 'MonoBehaviour':
            subdata = obj.read()
            if stdout_log:
                print('- MonoBehaviour', subdata.name, flush=True)
            subdata.read_type_tree()
            json_data = subdata.type_tree
            if json_data:
                mono_list.append(json_data)
        elif obj_type_str == 'GameObject':
            subdata = obj.read()
            UNPACK[obj_type_str](
                subdata, os.path.join(dest, '{:02}'.format(idx)))
        # elif stdout_log:
        #     print(f'Unsupported type {obj_type_str}')
    if len(mono_list) > 0:
        check_target_path(dest)
        with open(dest, 'w', encoding='utf8', newline='') as f:
            json.dump(mono_list, f, indent=2)


IMAGE_TYPES = {'Texture2D', 'Sprite'}


def unpack(obj, ex_target, ex_dir, ex_img_dir, texture_2d, stdout_log=False):
    obj_type_str = str(obj.type)
    if (ex_dir is None and obj_type_str not in IMAGE_TYPES) or (ex_img_dir is None and obj_type_str in IMAGE_TYPES):
        if stdout_log:
            print(f'Skipped {ex_target}')
        return None
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
            if obj_type_str in IMAGE_TYPES:
                dest = os.path.join(ex_img_dir, dest)
                method(data, dest, texture_2d, stdout_log)
            else:
                dest = os.path.join(ex_dir, dest)
                method(data, dest, stdout_log)
    # elif stdout_log:
    #     print(f'Unsupported type {obj_type_str}')


UNPACK = {
    'Texture2D': unpack_Texture2D,
    'Sprite': unpack_Sprite,
    'MonoBehaviour': unpack_MonoBehaviour,
    'TextAsset': unpack_TextAsset,
    'GameObject': unpack_GameObject,
    'AnimationClip': unpack_MonoBehaviour,
    'AnimatorOverrideController': unpack_MonoBehaviour
}

wyrmprint_alpha = Image.new('RGBA', (1024, 1024), color=(0, 0, 0, 255))
ImageDraw.Draw(wyrmprint_alpha).rectangle(
    [212, 26, 811, 997], fill=(255, 255, 255, 255), outline=None)
wyrmprint_alpha = wyrmprint_alpha.convert('L')


def merge_YCbCr(Y_img, Cb_img, Cr_img):
    _, _, _, Y = Y_img.convert('RGBA').split()
    Cb = Cb_img.convert('L').resize(Y_img.size, Image.ANTIALIAS)
    Cr = Cr_img.convert('L').resize(Y_img.size, Image.ANTIALIAS)
    return Image.merge('YCbCr', (Y, Cb, Cr)).convert('RGBA')


def merge_categorized(all_categorized_images, stdout_log=False):
    for dest, sorted_images in tqdm(all_categorized_images.items(), desc='merge_categorized'):
        try:
            image = None
            if 'color' in sorted_images:
                image = sorted_images['color']
                a = None
                for alpha in ('alpha', 'A', 'alphaA8'):
                    try:
                        alpha_img = sorted_images[alpha]
                        if alpha_img.mode == 'RGB' or alpha_img.getextrema()[3][0] == 255:
                            a = alpha_img.convert('L')
                        else:
                            _, _, _, a = alpha_img.split()
                    except KeyError:
                        continue
                if a:
                    image.putalpha(a)
                dest = os.path.splitext(dest)[0] + '.png'
                check_target_path(dest)
                image.save(dest)
                if stdout_log:
                    print(f'Merged RGBA {dest}')

            if 'Y' in sorted_images:
                image = merge_YCbCr(
                    sorted_images['Y'], sorted_images['Cb'], sorted_images['Cr'])
                if 'alpha' in sorted_images:
                    a = sorted_images['alpha'].convert('L')
                # elif sorted_images['Y'].size == (1024, 1024):
                #     a = wyrmprint_alpha
                else:
                    a = None
                if a:
                    image.putalpha(a)
                check_target_path(dest)
                dest = os.path.splitext(dest)[0] + '.png'
                image.save(dest)
                if stdout_log:
                    print(f'Merged YCbCr {dest}')
            if image is not None:
                try:
                    flipped = image.transpose(Image.FLIP_TOP_BOTTOM)
                    for s_dest, s_box, flip, mask in sorted_images['sprites']:
                        s_img = flipped.crop(
                            (s_box.left, s_box.top, s_box.right, s_box.bottom))
                        if flip is not None:
                            s_img = s_img.transpose(flip)
                        s_img = s_img.transpose(Image.FLIP_TOP_BOTTOM)
                        if mask is not None:
                            s_img = Image.composite(s_img, Image.new(
                                s_img.mode, s_img.size, color=0), mask)
                        s_dest = os.path.splitext(s_dest)[0] + '.png'
                        check_target_path(s_dest)
                        s_img.save(s_dest)
                        if stdout_log:
                            print(f'Merged Sprite {s_dest}')
                except KeyError:
                    pass
        except Exception as e:
            print(dest, sorted_images.keys())
            print(str(e))


def merge_indexed(all_indexed_images, stdout_log=False, combine_all=True):
    for dest, images in tqdm(all_indexed_images.items(), desc='merge_categorized'):
        alpha = images['a']
        color = images['c']
        dest = os.path.splitext(dest)[0]
        try:
            with open(dest + '.json', 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            continue
        mapping = data['partsTextureIndexTable']
        position = data['partsDataTable'][0]['position']
        size = data['partsDataTable'][0]['size']
        box = [int(position['x']-size['x']/2), int(position['y']-size['y']/2),
               int(position['x']+size['x']/2), int(position['y']+size['y']/2)]
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
            if a_idx <= 0:
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
                merged_dest = os.path.join(os.path.dirname(
                    dest), 'merged', f'{os.path.basename(dest)}_{l1_key}_{l2_key}.png')
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


IMAGE_CATEGORY = re.compile(r'(.+?)_(sprite|C|alpha|alphaA8|A|Y|Cb|Cr)$')
IMAGE_ALPHA_INDEX = re.compile(
    r'(.+?)_parts_([a-z])(\d{3})_(sprite|alpha|alphaA8|A|Y|Cb|Cr)$')


def merge_images(image_list, stdout_log=False, do_indexed=True):
    all_categorized_images = defaultdict(lambda: {})
    all_indexed_images = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: {})))
    for images in tqdm(image_list, desc='images'):
        if images is None:
            continue
        for _, data in images.items():
            dest, img, tx_format = data['root']
            res = IMAGE_ALPHA_INDEX.match(dest)
            if res:
                dest, designation, index, category = res.groups()
                all_indexed_images[dest][designation][int(
                    index)][category] = img
                continue
            res = IMAGE_CATEGORY.match(dest)
            if res:
                destination, category = res.groups()
                if category == 'C':
                    category = 'color'
                if category in ('alphaA8', 'A') and tx_format not in (TextureFormat.Alpha8, TextureFormat.ETC_RGB4):
                    destination = dest
                    category = 'color'
                all_categorized_images[destination][category] = img
                continue
            all_categorized_images[dest]['color'] = img
            if 'sprites' in data:
                all_categorized_images[dest]['sprites'] = data['sprites']

    if all_categorized_images:
        merge_categorized(all_categorized_images, stdout_log=stdout_log)
    if do_indexed and all_indexed_images:
        merge_indexed(all_indexed_images, stdout_log=stdout_log)

### multiprocessing ###
def mp_download_extract(target, source_list, extract, region, dl_dir, overwrite, ex_dir, ex_img_dir, stdout_log):
    base_dl_target = os.path.join(dl_dir, region, target)
    check_target_path(base_dl_target)

    downloaded = []
    for idx, source in enumerate(source_list):
        if len(source_list) > 1:
            dl_target = base_dl_target + str(idx)
        else:
            dl_target = base_dl_target
        if overwrite or not os.path.exists(dl_target):
            if stdout_log:
                print(f'Download {dl_target} from {source}', flush=True)
            try:
                urllib.request.urlretrieve(source, dl_target)
            except Exception as e:
                print(str(e))
                continue
        downloaded.append(dl_target)
        print('.', end='', flush=True)

#     return target, extract, region, downloaded
# def mp_extract(target, extract, downloaded, region, ex_dir, ex_img_dir, stdout_log):

    if extract is None:
        extract = os.path.dirname(target).replace('/', '_')
    ex_target = os.path.join(region, extract)
    texture_2d = {}
    for dl_target in downloaded:
        am = AssetsManager(dl_target)
        for asset in am.assets.values():
            for obj in asset.objects.values():
                unpack(obj, ex_target, ex_dir, ex_img_dir, texture_2d, stdout_log=stdout_log)
        print('-', end='', flush=True)
    return texture_2d
### multiprocessing ###

class Extractor:
    def __init__(self, dl_dir='./_download', ex_dir='./_extract', ex_img_dir='./_images', mf_mode=0, overwrite=False, stdout_log=False):
        self.pm = {}
        self.pm_old = {}
        for region, manifest in MANIFESTS.items():
            self.pm[region] = ParsedManifest(manifest)
            self.pm_old[region] = ParsedManifest(f'{manifest}.old')
        self.dl_dir = dl_dir
        self.ex_dir = ex_dir
        self.ex_img_dir = ex_img_dir
        self.extract_list = []
        self.stdout_log = stdout_log
        self.mf_mode = mf_mode
        self.overwrite = overwrite

    ### multiprocessing ###
    def pool_download_and_extract(self, download_list, extract=None, region=None):
        if not download_list:
            return
        NUM_WORKERS = multiprocessing.cpu_count()
        EX_RE = len(download_list[0]) == 2

        print(f'Processing {len(download_list)}', flush=True)
        pool = multiprocessing.Pool(processes=NUM_WORKERS)
        if EX_RE:
            dl_args = [
                (target, source, extract, region, self.dl_dir, self.overwrite, self.ex_dir, self.ex_img_dir, self.stdout_log) 
                for target, source in download_list
            ]
        else:
            dl_args = [
                (target, source, extract, region, self.dl_dir, self.overwrite, self.ex_dir, self.ex_img_dir, self.stdout_log)
                for target, source, extract, region in download_list
            ]
        results = list(filter(None, pool.starmap(mp_download_extract, dl_args)))
        pool.close()
        pool.join()
        print('\n', flush=True)

        if results:
            merge_images(results, self.stdout_log)
    ### multiprocessing ###

    def download_and_extract_by_pattern_diff(self, label_patterns):
        download_list = []
        for region, label_pat in label_patterns.items():
            for pat, extract in label_pat.items():
                download_list.extend([(*ts, extract, region) 
                for ts in self.pm[region].get_by_pattern_diff(pat, self.pm_old[region], mode=self.mf_mode)])
        self.pool_download_and_extract(download_list)

    def download_and_extract_by_pattern(self, label_patterns):
        download_list = []
        for region, label_pat in label_patterns.items():
            for pat, extract in label_pat.items():
                download_list.extend([(*ts, extract, region) for ts in self.pm[region].get_by_pattern(pat, mode=self.mf_mode)])
        self.pool_download_and_extract(download_list)

    def download_and_extract_by_diff(self, region='jp'):
        download_list = self.pm[region].get_by_diff(self.pm_old[region], mode=self.mf_mode)
        self.pool_download_and_extract(download_list, region=region)

    def extract_target(self, dl_target, ex_target, texture_2d):
        am = AssetsManager(dl_target)
        for asset in am.assets.values():
            for obj in asset.objects.values():
                unpack(obj, ex_target, self.ex_dir, self.ex_img_dir,
                       texture_2d, stdout_log=self.stdout_log)

    def local_extract(self, input_dir):
        result = []
        for root, _, files in os.walk(input_dir):
            for file_name in tqdm(files, desc='local'):
                _, ext = os.path.splitext(file_name)
                if len(ext) > 0:
                    if self.stdout_log:
                        print('Skipped', file_name)
                    continue
                texture_2d = {}
                self.extract_target(os.path.join(root, file_name), 'local', texture_2d)
                if texture_2d:
                    result.append(texture_2d)
        merge_images(result, self.stdout_log)


if __name__ == '__main__':
    import sys
    IMAGE_PATTERNS = {
        'jp': {
            r'^raid/model': None
        }
    }

    if len(sys.argv) > 1:
        if sys.argv[1] == 'diff':
            ex = Extractor(dl_dir='./_dl_diff', ex_dir=None)
            if len(sys.argv) > 2:
                region = sys.argv[2]
                print(f'{region}: ', flush=True, end='')
                ex.download_and_extract_by_diff(region=region)
            else:
                for region, manifest in MANIFESTS.items():
                    ex.download_and_extract_by_diff(region=region)
        else:
            ex = Extractor(ex_dir='./_images', mf_mode=1)
            ex.download_and_extract_by_pattern({'jp': {sys.argv[1]: None}})
    else:
        ex = Extractor(stdout_log=False, overwrite=False, mf_mode=1)
        ex.download_and_extract_by_pattern(IMAGE_PATTERNS)
        # ex.local_extract('_apk')
