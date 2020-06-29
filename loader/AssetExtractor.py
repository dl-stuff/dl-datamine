import json
import os
import errno
import aiohttp
import asyncio
import re
import concurrent
from tqdm import tqdm
from queue import SimpleQueue
from collections import defaultdict

from PIL import Image, ImageDraw
from UnityPy import AssetsManager

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
        self.url = AssetEntry.URL_FORMAT.format(h=self.hash[0:2], hash=self.hash)
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

    def get_by_pattern(self, pattern, mode=0):
        if not isinstance(pattern, re.Pattern):
            pattern = re.compile(pattern, flags=re.IGNORECASE)
        targets = filter(lambda x: pattern.search(x[0]), self.items())
        if mode == 2:
            return ParsedManifest.expand_dependencies(targets)
        elif mode == 1:
            return ParsedManifest.link_dependencies(targets)
        else:
            return ParsedManifest.flatten(targets)

    def get_by_diff(self, other, mode=0):
        targets = filter(lambda x: x[0] not in other.keys() or x[1] != other[x[0]], self.items())
        if mode == 2:
            return ParsedManifest.expand_dependencies(targets)
        elif mode == 1:
            return ParsedManifest.link_dependencies(targets)
        else:
            return ParsedManifest.flatten(targets)


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

def unpack_Texture2D(data, dest, texture_2d, stdout_log=False):
    if stdout_log:
        print('Texture2D', dest, flush=True)
    try:
        tpl = (dest, data.image)
        try:
            texture_2d[data.path_id]['root'] = tpl
        except KeyError:
            texture_2d[data.path_id] = {}
            texture_2d[data.path_id]['root'] = tpl
    except:
        pass


from UnityPy.classes.Sprite import SpritePackingRotation, SpritePackingMode
from UnityPy.export.SpriteHelper import get_triangles
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
        texture_2d[sprite_atlas_data.texture.path_id]['sprites'].append(s_tuple)
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
        subdata = obj.read()
        if obj_type_str == 'MonoBehaviour':
            json_data = subdata.read_type_tree()
            if json_data:
                mono_list.append(json_data)
        elif obj_type_str == 'GameObject':
            UNPACK[obj_type_str](subdata, os.path.join(dest, '{:02}'.format(idx)))
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
ImageDraw.Draw(wyrmprint_alpha).rectangle([212, 26, 811, 997], fill=(255, 255, 255, 255), outline=None)
wyrmprint_alpha = wyrmprint_alpha.convert('L')

def merge_YCbCr(Y_img, Cb_img, Cr_img):
    _, _, _, Y = Y_img.convert('RGBA').split()
    Cb = Cb_img.convert('L').resize(Y_img.size, Image.ANTIALIAS)
    Cr = Cr_img.convert('L').resize(Y_img.size, Image.ANTIALIAS)
    return Image.merge('YCbCr', (Y, Cb, Cr)).convert('RGBA')

def merge_categorized(all_categorized_images, stdout_log=False):
    for dest, sorted_images in all_categorized_images.items():
        try:
            image = None
            if 'color' in sorted_images:
                image = sorted_images['color']
                a = None
                for alpha in ('alpha', 'A', 'alphaA8'):
                    try:
                        alpha_img = sorted_images[alpha]
                        if alpha_img.mode == 'RGB':
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
                image = merge_YCbCr(sorted_images['Y'], sorted_images['Cb'], sorted_images['Cr'])
                if 'alpha' in sorted_images:
                    a = sorted_images['alpha'].convert('L')
                elif sorted_images['Y'].size == (1024, 1024):
                    a = wyrmprint_alpha
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
                        s_img = flipped.crop((s_box.left, s_box.top, s_box.right, s_box.bottom))
                        if flip is not None:
                            s_img = s_img.transpose(flip)
                        s_img = s_img.transpose(Image.FLIP_TOP_BOTTOM)
                        if mask is not None:
                            s_img = Image.composite(s_img, Image.new(s_img.mode, s_img.size, color=0), mask)
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
    for dest, images in all_indexed_images.items():
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

IMAGE_CATEGORY = re.compile(r'(.+?)_(sprite|C|alpha|alphaA8|A|Y|Cb|Cr)$')
IMAGE_ALPHA_INDEX = re.compile(r'(.+?)_parts_([a-z])(\d{3})_(sprite|alpha|alphaA8|A|Y|Cb|Cr)$')
def merge_images(image_list, stdout_log=False, do_indexed=True):
    all_categorized_images = defaultdict(lambda: {})
    all_indexed_images = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {})))
    for images in image_list:
        if images is None:
            continue
        for _, data in images.items():
            dest, img = data['root']
            res = IMAGE_ALPHA_INDEX.match(dest)
            if res:
                dest, designation, index, category = res.groups()
                all_indexed_images[dest][designation][int(index)][category] = img
                continue
            res = IMAGE_CATEGORY.match(dest)
            if res:
                dest, category = res.groups()
                if category == 'C':
                    category = 'color'
                all_categorized_images[dest][category] = img
                continue
            all_categorized_images[dest]['color'] = img
            if 'sprites' in data:
                all_categorized_images[dest]['sprites'] = data['sprites']

    merge_categorized(all_categorized_images, stdout_log=stdout_log)
    if do_indexed:
        merge_indexed(all_indexed_images, stdout_log=stdout_log)

class Extractor:
    def __init__(self, manifests, dl_dir='./_download', ex_dir='./_extract', ex_img_dir='./_images', mf_mode=0, stdout_log=True):
        self.pm = {}
        for region, manifest in manifests.items():
            self.pm[region] = ParsedManifest(manifest)
        self.dl_dir = dl_dir
        self.ex_dir = ex_dir
        self.ex_img_dir = ex_img_dir
        self.extract_list = []
        self.stdout_log = stdout_log
        self.mf_mode = mf_mode

    async def down_ex(self, session, source_list, region, target, extract):
        base_dl_target = os.path.join(self.dl_dir, region, target)
        check_target_path(base_dl_target)

        texture_2d = {}
        for idx, source in enumerate(source_list):
            if len(source_list) > 1:
                dl_target = base_dl_target + str(idx)
            else:
                dl_target = base_dl_target            
            if self.stdout_log:
                print(f'Download {dl_target} from {source}', flush=True)

            try:
                async with session.get(source, timeout=60) as resp:
                    assert resp.status == 200
                    if os.path.exists(dl_target) and os.path.isdir(dl_target):
                        dl_target = os.path.join(dl_target, os.path.basename(dl_target))
                    with open(dl_target, 'wb') as f:
                        f.write(await resp.read())
            except asyncio.TimeoutError:
                print('Timeout', dl_target)
                continue
            except Exception as e:
                print(str(e))
                continue

            _, ext = os.path.splitext(dl_target)
            if len(ext) > 0:
                if self.stdout_log:
                    print('Skipped', dl_target)
                return None
            if extract is None:
                extract = os.path.dirname(target).replace('/', '_')
            ex_target = os.path.join(region, extract)
            self.extract_target(dl_target, ex_target, texture_2d)
        if len(texture_2d) > 0:
            return texture_2d

    def extract_target(self, dl_target, ex_target, texture_2d):
        am = AssetsManager(dl_target)
        for asset in am.assets.values():
            for obj in asset.objects.values():
                unpack(obj, ex_target, self.ex_dir, self.ex_img_dir, texture_2d, stdout_log=self.stdout_log)

    async def download_and_extract(self, download_list, extract, region='jp'):
        async with aiohttp.ClientSession(headers={'Connection': 'close'}) as session:
            result = [await f for f in tqdm(asyncio.as_completed([
                self.down_ex(session, source, region, target, extract)
                for target, source in download_list
            ]), desc=region, total=len(download_list))]
            merge_images(result, self.stdout_log)

    def download_and_extract_by_pattern(self, label_patterns, region='jp'):
        download_list = []
        for pat, extract in label_patterns.items():
            download_list = self.pm[region].get_by_pattern(pat, mode=self.mf_mode)
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.download_and_extract(download_list, extract, region))

    def download_and_extract_by_diff(self, old_manifest, region='jp'):
        old_manifest = ParsedManifest(old_manifest)
        download_list = self.pm[region].get_by_diff(old_manifest, mode=self.mf_mode)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.download_and_extract(download_list, None, region))

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
        r'^images/icon/others': None,
        # r'^images/outgame': None
        # r'_gluonresources/meshes/weapon': None
        # r'^prefabs/outgame/fort/facility': None

        # r'^characters/motion/axe': 'characters_motion',
        # r'^characters/motion/bow': 'characters_motion',
        # r'^characters/motion/can': 'characters_motion',
        # r'^characters/motion/dag': 'characters_motion',
        # r'^characters/motion/kat': 'characters_motion',
        # r'^characters/motion/lan': 'characters_motion',
        # r'^characters/motion/rod': 'characters_motion',
        # r'^characters/motion/swd': 'characters_motion',
        # r'characters/motion/animationclips$': 'characters_motion',

        # r'^dragon/motion': 'dragon_motion',
    }

    MANIFESTS = {
        'jp': 'manifest/assetbundle.manifest.json',
        'en': 'manifest/assetbundle.en_us.manifest.json',
        'cn': 'manifest/assetbundle.zh_cn.manifest.json',
        'tw': 'manifest/assetbundle.zh_tw.manifest.json'
    }

    if len(sys.argv) > 1:
        if sys.argv[1] == 'diff':
            ex = Extractor(MANIFESTS, ex_dir=None, stdout_log=False)
            if len(sys.argv) > 2:
                region = sys.argv[2]
                print(f'{region}: ', flush=True, end='')
                ex.download_and_extract_by_diff(f'{MANIFESTS[region]}.old', region=region)
            else:
                for region, manifest in MANIFESTS.items():
                    ex.download_and_extract_by_diff(f'{manifest}.old', region=region)
        else:
            ex = Extractor(MANIFESTS, ex_dir='./_images', stdout_log=False)
            ex.download_and_extract_by_pattern({sys.argv[1]: None}, region='jp')
    else:
        ex = Extractor(MANIFESTS, stdout_log=False, mf_mode=1)
        ex.download_and_extract_by_pattern(IMAGE_PATTERNS, region='jp')
        # ex.local_extract('_apk')