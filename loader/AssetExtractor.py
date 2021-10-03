import json
import os
import errno
import sys
from time import monotonic
from pprint import pprint
import shutil

import urllib.request
import multiprocessing

import re

# from tqdm import tqdm
from queue import SimpleQueue
from collections import defaultdict
from itertools import chain
from functools import partial

from PIL import Image, ImageDraw
from UnityPy import Environment

from UnityPy.export.SpriteHelper import get_triangles, SpritePackingRotation, SpritePackingMode

MANIFESTS = {
    "jp": "manifest/assetbundle.manifest.json",
    "en": "manifest/assetbundle.en_us.manifest.json",
    "cn": "manifest/assetbundle.zh_cn.manifest.json",
    "tw": "manifest/assetbundle.zh_tw.manifest.json",
}

IMG_EXT = ".png"
IMG_ARGS = {
    ".png": {"optimize": False},
    ".webp": {"lossless": True, "quality": 0},
}


def save_img(img, dest):
    check_target_path(dest)
    img.save(dest, **IMG_ARGS[IMG_EXT])


def save_json(data, dest):
    check_target_path(dest)
    with open(dest, "w", encoding="utf8", newline="") as fn:
        json.dump(data, fn, indent=2)


class ParsedManifestFlat(dict):
    def __init__(self, manifest):
        super().__init__({})
        with open(manifest) as f:
            for line in f:
                url, label = [l.strip() for l in line.split("|")]
                self[label] = url

    def get_by_pattern(self, pattern):
        if not isinstance(pattern, re.Pattern):
            pattern = re.compile(pattern, flags=re.IGNORECASE)
        return list(filter(lambda x: pattern.search(x[0]), self.items()))

    def get_by_diff(self, other):
        return list(filter(lambda x: x[0] not in other.keys() or x[1] != other[x[0]], self.items()))


class AssetEntry:
    URL_FORMAT = "http://dragalialost.akamaized.net/dl/assetbundles/Android/{h}/{hash}"

    def __init__(self, asset, raw=False):
        self.name = asset["name"]
        self.hash = asset["hash"]
        self.url = AssetEntry.URL_FORMAT.format(h=self.hash[0:2], hash=self.hash)
        if "dependencies" in asset and asset["dependencies"]:
            self.dependencies = asset["dependencies"]
        else:
            self.dependencies = None
        self.size = asset["size"]
        self.group = asset["group"]
        self.dependents = None
        self.raw = raw

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
            return f"{self.name} ({self.hash})\n-> {self.dependencies}"
        else:
            return f"{self.name} ({self.hash})"

    def __eq__(self, other):
        return self.hash == other.hash

    def __ne__(self, other):
        return self.hash != other.hash


class SimpleAssetEntry:
    def __init__(self, asset_entry):
        self.name = asset_entry.name
        self.hash = asset_entry.hash
        self.url = asset_entry.url
        self.raw = asset_entry.raw


class ParsedManifest(dict):
    def __init__(self, manifest):
        super().__init__({})
        self.path = manifest
        with open(manifest) as f:
            tree = json.load(f)
        for category in tree["categories"]:
            for asset in category["assets"]:
                self[asset["name"]] = AssetEntry(asset)
        for asset in tree["rawAssets"]:
            self[asset["name"]] = AssetEntry(asset, raw=True)

    @staticmethod
    def flatten(targets):
        return [(k, SimpleAssetEntry(v)) for k, v in targets]

    def get_by_pattern(self, pattern):
        if not isinstance(pattern, re.Pattern):
            pattern = re.compile(pattern, flags=re.IGNORECASE)
        targets = filter(lambda x: pattern.search(x[0]), self.items())
        return ParsedManifest.flatten(targets)

    def get_by_diff(self, other):
        targets = filter(lambda x: x[0] not in other.keys() or x[1] != other[x[0]], self.items())
        return ParsedManifest.flatten(targets)

    def get_by_pattern_diff(self, pattern, other):
        if not isinstance(pattern, re.Pattern):
            pattern = re.compile(pattern, flags=re.IGNORECASE)
        targets = filter(
            lambda x: pattern.search(x[0]) and (x[0] not in other.keys() or x[1] != other[x[0]]),
            self.items(),
        )
        return ParsedManifest.flatten(targets)

    def report_diff(self, other):
        added_keys = set()
        changed_keys = set()
        removed_keys = set()
        for key, value in self.items():
            if key not in other:
                added_keys.add(key)
            elif value != other[key]:
                changed_keys.add(key)
        for key in other.keys():
            if key not in self:
                removed_keys.add(key)

        print("===========ADDED===========")
        pprint(added_keys)
        print("==========CHANGED==========")
        pprint(changed_keys)
        print("==========REMOVED==========")
        pprint(removed_keys)


def check_target_path(target, is_dir=False):
    if not is_dir:
        target = os.path.dirname(target)
    try:
        os.makedirs(target, exist_ok=True)
    except OSError as exc:  # Guard against race condition
        if exc.errno != errno.EEXIST:
            raise


def merge_path_dir(path):
    new_dir = os.path.dirname(path).replace("/", "_")
    return os.path.join(new_dir, os.path.basename(path))


def process_json(tree):
    while isinstance(tree, dict):
        if "dict" in tree:
            tree = tree["dict"]
        elif "list" in tree:
            tree = tree["list"]
        elif "entriesValue" in tree and "entriesKey" in tree:
            return {k: process_json(v) for k, v in zip(tree["entriesKey"], tree["entriesValue"])}
        else:
            return tree
    return tree


def serialize_memoryview(value):
    try:
        return str(value.hex())
    except AttributeError:
        return str(value)


def unpack_TypeTree(obj, dest, ex_paths, obj_by_pathid, name=None):
    data = obj.read()
    result = data.type_tree.to_dict()
    try:
        name = str(obj.type) + "." + data.name.replace("/", "_")
    except AttributeError:
        print(result)
        pass
    dest = os.path.join(dest, name + ".json")
    save_json(result, dest)


def unpack_MonoBehaviour(obj, dest, ex_paths, obj_by_pathid, name=None, process=True):
    data = obj.read()
    if data.path_id in ex_paths:
        return
    name = name or data.name or data.m_Script.get_obj().read().name
    result = data.type_tree.to_dict()
    if process:
        result = process_json(result)
        if not result:
            return
    dest = os.path.join(dest, name + ".json")
    save_json(result, dest)
    ex_paths.add(data.path_id)


def unpack_TextAsset(obj, dest, ex_paths, obj_by_pathid):
    data = obj.read()
    if data.path_id in ex_paths:
        return
    dest = os.path.join(dest, data.name)
    check_target_path(dest)
    try:
        with open(dest, "w", encoding="utf8", newline="") as f:
            f.write(data.text)
    except UnicodeDecodeError:
        with open(dest, "wb") as f:
            f.write(data.script)
    ex_paths.add(data.path_id)


def unpack_GameObject(obj, dest, ex_paths, obj_by_pathid):
    data = obj.read()
    component_monos = []
    for component in data.m_Components:
        if component.type == "MonoBehaviour":
            mono_data = component.read()
            mono_json_data = mono_data.type_tree.to_dict().get("_data")
            if not mono_json_data:
                try:
                    mono_name = mono_data.m_Script.get_obj().read().name
                    if data.name != mono_name:
                        mono_name = f"{data.name}.{mono_name}"
                    elif not mono_name:
                        mono_name = data.name
                except AttributeError:
                    mono_name = data.name
                unpack_MonoBehaviour(component, dest, ex_paths, obj_by_pathid, name=mono_name, process=False)
                continue
            component_monos.append(mono_json_data)
            ex_paths.add(mono_data.path_id)
        # else:
        #     unpack_TypeTree(component, dest, ex_paths, obj_by_pathid, name=data.name)
    if component_monos:
        dest = os.path.join(dest, data.name + ".json")
        save_json(component_monos, dest)


# def find_ref(container):
#     ref = os.path.splitext(os.path.basename(container))[0]
#     if len(ref) < 4:
#         ref = None
#     elif ref[3] == "_":
#         ref = ref.split("_")[-1]
#         if len(ref) != 8:
#             ref = None
#     elif ref[0] == "d":
#         parts = ref.split("_")
#         if len(parts[0]) == 9:
#             ref = parts[0]
#         else:
#             ref = parts[0] + parts[1]
#     return ref


def unpack_Animation(obj, dest, ex_paths, obj_by_pathid):
    data = obj.read()
    if data.path_id in ex_paths:
        return
    obj_type_str = str(obj.type)
    # ref = None
    # if obj.container is not None:
    #     ref = find_ref(obj.container)
    # else:
    #     for asset in obj.assets_file.objects.values():
    #         if asset.container is not None:
    #             ref = find_ref(asset.container)
    #             if ref is not None:
    #                 break
    dest = f"{dest}/{obj_type_str}.{data.name}.json"
    tree = data.type_tree.to_dict()
    tree["pathID"] = data.path_id
    # tree["ref"] = ref
    save_json(tree, dest)
    ex_paths.add(data.path_id)


def other_tex_env(material, mat_paths):
    for key, tex_env in material.m_SavedProperties.m_TexEnvs.items():
        try:
            data = tex_env.m_Texture.get_obj().read()
            if data.path_id not in mat_paths:
                yield key, data.image, data.name
        except AttributeError:
            continue


def tex_env_img(obj_by_pathid, material, mat_paths, ex_paths, key, image_only=True):
    try:
        # this will work 1day i belieeeeeve
        # data = material.m_SavedProperties.m_TexEnvs[key].m_Texture.get_obj().read()
        path_id = material.m_SavedProperties.m_TexEnvs[key].m_Texture.path_id
        if path_id in ex_paths:
            return None
        data = obj_by_pathid[path_id].read()
        if not data.m_Width or not data.m_Height:
            return None
        mat_paths.add(path_id)
        if image_only:
            return data.image
        return data
    except (KeyError, AttributeError):
        return None


def merge_Alpha(m_img, a_img):
    if a_img.mode == "RGB" or a_img.getextrema()[3][0] == 255:
        alpha = a_img.convert("L")
    else:
        _, _, _, alpha = a_img.split()
    m_img.putalpha(alpha)
    return m_img


def merge_YCbCr(y_img, cb_img, cr_img, a_img=None):
    # Sometimes MonoBehaviour can carry the mapping instead of Material
    # print(y_img, cb_img, cr_img, a_img)
    _, _, _, Y = y_img.convert("RGBA").split()
    Cb = cb_img.convert("L").resize(y_img.size, Image.ANTIALIAS)
    Cr = cr_img.convert("L").resize(y_img.size, Image.ANTIALIAS)
    ycbcr_img = Image.merge("YCbCr", (Y, Cb, Cr)).convert("RGBA")
    if a_img:
        merge_Alpha(ycbcr_img, a_img)
    return ycbcr_img


def unpack_Material(obj, dest, ex_paths, obj_by_pathid):
    data = obj.read()
    mat_paths = set()

    # unpack_TypeTree(obj, dest, ex_paths, obj_by_pathid)

    get_tex = partial(tex_env_img, obj_by_pathid, data, mat_paths, ex_paths)

    if (y_img := get_tex("_TexY")) and (cb_img := get_tex("_TexCb")) and (cr_img := get_tex("_TexCr")):
        save_img(merge_YCbCr(y_img, cb_img, cr_img, a_img=get_tex("_TexA")), os.path.join(dest, f"{data.m_Name}{IMG_EXT}"))
    else:
        m_data = get_tex("_MainTex", image_only=False)
        if not m_data:
            return
        m_img, m_name = m_data.image, m_data.name
        # _MaskAlphaTex is probably always path_id = 0
        if (a_img := get_tex("_AlphaTex")) or (a_img := get_tex("_MaskAlphaTex")):
            merge_Alpha(m_img, a_img)
        save_img(m_img, os.path.join(dest, f"{m_name}{IMG_EXT}"))
        obj_by_pathid[m_data.path_id] = m_img

    # for key, env_img, env_img_name in other_tex_env(data, mat_paths):
    #     save_img(env_img, os.path.join(dest, f"{data.name}{key}.{env_img_name}{IMG_EXT}"))

    ex_paths.update(mat_paths)


YCBCR_PATTERN = re.compile(r"(.*)_(Y|Cb|Cr)")


def unpack_Texture2D(obj, dest, ex_paths, obj_by_pathid):
    data = obj.read()
    if data.path_id in ex_paths:
        return
    if not data.m_Width or not data.m_Height:
        return
    if obj.assets_file:
        # try to find ycbcr
        if res := YCBCR_PATTERN.match(data.name):
            img_name = res.group(1)
            found_ycbcr = {res.group(2): data}
            for other_pathid, other_obj in obj.assets_file.objects.items():
                if other_pathid in ex_paths or str(other_obj.type) != "Texture2D":
                    continue
                other_data = other_obj.read()
                if (res := YCBCR_PATTERN.match(other_data.name)) and res.group(1) == img_name and res.group(2) not in found_ycbcr:
                    found_ycbcr[res.group(2)] = other_data
                if len(found_ycbcr) == 3:
                    img_name = f"{img_name}{IMG_EXT}"
                    save_img(merge_YCbCr(found_ycbcr["Y"].image, found_ycbcr["Cb"].image, found_ycbcr["Cr"].image), os.path.join(dest, img_name))
                    for ycbcr_data in found_ycbcr.values():
                        ex_paths.add(ycbcr_data.path_id)
                    return
        if len(obj.assets_file.container_) == 2:
            # try to find alpha
            for other_container, other_ptr in obj.assets_file.container_.items():
                if other_container == obj.container:
                    continue
                other_obj = other_ptr.get_obj()
                if str(other_obj.type) != "Texture2D":
                    continue
                other_data = other_obj.read()
                if data.name in other_data.name:
                    img_name = f"{data.name}{IMG_EXT}"
                    m_img, a_img = data.image, other_data.image
                elif other_data.name in data.name:
                    img_name = f"{other_data.name}{IMG_EXT}"
                    m_img, a_img = other_data.image, data.image
                else:
                    continue
                save_img(merge_Alpha(m_img, a_img), os.path.join(dest, img_name))
                ex_paths.add(data.path_id)
                ex_paths.add(other_data.path_id)
                return
    save_img(data.image, os.path.join(dest, f"{data.name}{IMG_EXT}"))
    ex_paths.add(data.path_id)


SPRITE_ROTATION = {
    SpritePackingRotation.kSPRFlipHorizontal: Image.FLIP_TOP_BOTTOM,
    SpritePackingRotation.kSPRFlipVertical: Image.FLIP_LEFT_RIGHT,
    SpritePackingRotation.kSPRRotate180: Image.ROTATE_180,
    SpritePackingRotation.kSPRRotate90: Image.ROTATE_270,
}


def unpack_Sprite(obj, dest, ex_paths, obj_by_pathid):
    # see UnityPy.SpriteHelper.get_image_from_sprite
    data = obj.read()
    if data.path_id in ex_paths:
        return

    atlas = data.m_RD
    texture = obj_by_pathid[atlas.texture.path_id]
    if not isinstance(texture, Image.Image):
        return
    texture_rect = atlas.textureRect
    settings_raw = atlas.settingsRaw

    texture = texture.transpose(Image.FLIP_TOP_BOTTOM)
    sprite_img = texture.crop((texture_rect.x, texture_rect.y, texture_rect.x + texture_rect.width, texture_rect.y + texture_rect.height))

    if settings_raw.packed == 1:
        # DL sprites are pmuch never packed=1
        sprite_img = sprite_img.transpose(SPRITE_ROTATION[settings_raw.packingRotation])

    if settings_raw.packingMode == SpritePackingMode.kSPMTight:
        mask = Image.new("1", sprite_img.size, color=0)
        draw = ImageDraw.ImageDraw(mask)
        for triangle in get_triangles(data):
            draw.polygon(triangle, fill=1)
        if sprite_img.mode == "RGBA":
            empty_img = Image.new(sprite_img.mode, sprite_img.size, color=0)
            sprite_img = Image.composite(sprite_img, empty_img, mask)
        else:
            sprite_img.putalpha(mask)

    sprite_img = sprite_img.transpose(Image.FLIP_TOP_BOTTOM)
    save_img(sprite_img, os.path.join(dest, f"{data.name}{IMG_EXT}"))
    ex_paths.add(data.path_id)
    obj_by_pathid[data.path_id] = data.name


IMAGE_TYPES = ("Texture2D", "Material", "Sprite", "AssetBundle")
UNPACK_PRIORITY = {
    "GameObject": 10,
    "Material": 9,
    # "AssetBundle": 8,
}


def get_unpack_priority(obj):
    return UNPACK_PRIORITY.get(str(obj.type), 0)


UNPACK = {
    "MonoBehaviour": unpack_MonoBehaviour,
    "GameObject": unpack_GameObject,
    "TextAsset": unpack_TextAsset,
    "AnimationClip": unpack_Animation,
    "AnimatorController": unpack_Animation,
    "AnimatorOverrideController": unpack_Animation,
    "Texture2D": unpack_Texture2D,
    "Sprite": unpack_Sprite,
    "Material": unpack_Material,
    # "AssetBundle": unpack_TypeTree,
    # "MonoScript": unpack_TypeTree,
}


### multiprocessing ###
def mp_extract(ex_dir, ex_img_dir, ex_target, dl_filelist):
    unity_env = Environment()
    unity_env.load_files(dl_filelist)
    ex_paths = set()

    obj_by_pathid = {}
    for asset in unity_env.assets:
        for obj in asset.get_objects():
            # print(obj.type, obj.read().name, obj.read().path_id)
            if UNPACK.get(str(obj.type)):
                obj_by_pathid[obj.read().path_id] = obj
            # else:
            #     print(obj.type, obj.read().name, obj.read().path_id)

    ex_dest = None if ex_dir is None else os.path.join(ex_dir, ex_target)
    img_dest = None if ex_img_dir is None else os.path.join(ex_img_dir, ex_target)
    print_counter = 0
    for obj in sorted(obj_by_pathid.values(), key=get_unpack_priority, reverse=True):
        if (dest := img_dest if obj.type in IMAGE_TYPES else ex_dest) is None:
            continue
        method = UNPACK[str(obj.type)]
        check_target_path(dest, is_dir=True)
        method(obj, dest, ex_paths, obj_by_pathid)
        if print_counter == 0:
            print("=", end="", flush=True)
            print_counter = 10
        print_counter -= 1

    path_id_to_string = {pathid: sprite for pathid, sprite in obj_by_pathid.items() if isinstance(sprite, str)}
    if path_id_to_string:
        with open(os.path.join(img_dest, "_path_id.json"), "w") as fn:
            json.dump(path_id_to_string, fn, indent=2)


def mp_download(target, source, extract, region, dl_dir, overwrite):
    dl_target = os.path.join(dl_dir, region, target.replace("/", "_"))
    check_target_path(dl_target)

    if overwrite or not os.path.exists(dl_target):
        try:
            urllib.request.urlretrieve(source.url, dl_target)
            print("-", end="", flush=True)
        except Exception as e:
            print(f"\n{e}")
            return
    else:
        print(".", end="", flush=True)

    if extract is None:
        extract = os.path.dirname(target).replace("/", "_")
    ex_target = os.path.join(region, extract)
    return (source, ex_target, dl_target)


### multiprocessing ###


class Extractor:
    def __init__(self, dl_dir="./_download", ex_dir="./_extract", ex_img_dir="./_images", overwrite=False):
        self.pm = {}
        self.pm_old = {}
        for region, manifest in MANIFESTS.items():
            self.pm[region] = ParsedManifest(manifest)
            self.pm_old[region] = ParsedManifest(f"{manifest}.old")
        self.dl_dir = dl_dir
        self.ex_dir = ex_dir
        self.ex_img_dir = ex_img_dir
        self.extract_list = []
        self.overwrite = overwrite

    ### multiprocessing ###
    def pool_download_and_extract(self, download_list, region=None):
        if not download_list:
            return
        NUM_WORKERS = multiprocessing.cpu_count()
        pool = multiprocessing.Pool(processes=NUM_WORKERS)
        if region is None:
            dl_args = [
                (
                    target,
                    source,
                    extract,
                    region,
                    self.dl_dir,
                    self.overwrite,
                )
                for region, extract, matched in download_list
                for target, source in matched
            ]
        else:
            dl_args = [
                (
                    target,
                    source,
                    extract,
                    region,
                    self.dl_dir,
                    self.overwrite,
                )
                for extract, matched in download_list
                for target, source in matched
            ]
        print(f"Download {len(dl_args)}", flush=True)  # tqdm(dl_args, desc="download", total=len(dl_args))
        downloaded = list(filter(None, pool.starmap(mp_download, dl_args)))
        pool.close()
        pool.join()

        sorted_downloaded = defaultdict(list)
        for source, ex_target, dl_target in downloaded:
            if source.raw:
                if self.ex_dir:
                    ex_target = os.path.join(self.ex_dir, ex_target)
                    check_target_path(ex_target, is_dir=True)
                    shutil.copy(dl_target, ex_target)
                continue
            sorted_downloaded[ex_target.replace("s_images", "images")].append(dl_target)

        pool = multiprocessing.Pool(processes=NUM_WORKERS)
        ex_args = [(self.ex_dir, self.ex_img_dir, ex_target, dl_targets) for ex_target, dl_targets in sorted_downloaded.items()]
        print(f"\nExtract {tuple(sorted_downloaded.keys())}", flush=True)
        # tqdm(ex_args, desc="extract", total=len(ex_args))
        pool.starmap(mp_extract, ex_args)
        pool.close()
        pool.join()
        print("", flush=True)

    ### multiprocessing ###

    def download_and_extract_by_pattern_diff(self, label_patterns):
        download_list = []
        for region, label_pat in label_patterns.items():
            for pat, extract in label_pat.items():
                matched = self.pm[region].get_by_pattern_diff(pat, self.pm_old[region])
                if not matched:
                    continue
                download_list.append((region, extract, matched))
        self.pool_download_and_extract(download_list)

    def download_and_extract_by_pattern(self, label_patterns):
        download_list = []
        for region, label_pat in label_patterns.items():
            for pat, extract in label_pat.items():
                matched = self.pm[region].get_by_pattern(pat)
                if not matched:
                    continue
                download_list.append((region, extract, matched))
        self.pool_download_and_extract(download_list)

    def download_and_extract_by_diff(self, region="jp"):
        download_list = self.pm[region].get_by_diff(self.pm_old[region])
        self.pool_download_and_extract(((None, download_list),), region=region)

    def report_diff(self, region="jp"):
        self.pm[region].report_diff(self.pm_old[region])


def cmd_line_extract():
    EX_PATTERNS = {
        "jp": {
            r"^emotion/story/chara/110334_02": None,
        },
    }

    if len(sys.argv) > 1:
        if sys.argv[1] == "diff":
            ex = Extractor(ex_dir=None)
            if len(sys.argv) > 2:
                region = sys.argv[2]
                print(f"{region}: ", flush=True, end="")
                ex.download_and_extract_by_diff(region=region)
            else:
                for region in MANIFESTS.keys():
                    ex.download_and_extract_by_diff(region=region)
        elif sys.argv[1] == "report":
            ex = Extractor()
            ex.report_diff()
        else:
            ex = Extractor()
            ex.download_and_extract_by_pattern({"jp": {sys.argv[1]: None}})
    else:
        # ex_dir="./_ex_sim",
        ex = Extractor(ex_dir=None, overwrite=False)
        ex.ex_dir = ex.ex_img_dir
        ex.download_and_extract_by_pattern(EX_PATTERNS)


if __name__ == "__main__":
    cmd_line_extract()
    # pm = ParsedManifest(MANIFESTS["jp"])
    # pprint(pm.get_by_pattern(r"images/icon/form/m/", mode=1))
