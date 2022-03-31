import itertools
import json
import os
import errno
import sys
import glob
import shutil
import subprocess
from pprint import pprint
from tqdm import tqdm

import requests
import multiprocessing

import re

# from tqdm import tqdm
from collections import defaultdict
from functools import partial

from PIL import Image, ImageDraw
from UnityPy import Environment

from UnityPy.export.SpriteHelper import get_triangles, SpritePackingRotation, SpritePackingMode
from UnityPy.enums.ClassIDType import ClassIDType


def get_latest_manifests():
    manifest_dirs = sorted(glob.glob("manifest/*/"))
    latest = manifest_dirs[-1]
    previous = manifest_dirs[-2]
    return get_manifests(latest, previous)


def get_manifests(latest, previous):
    def lp_m_tuple(manifest_name):
        return (os.path.join(latest, manifest_name), os.path.join(previous, manifest_name))

    return {
        "jp": lp_m_tuple("assetbundle.manifest.json"),
        "en": lp_m_tuple("assetbundle.en_us.manifest.json"),
        "cn": lp_m_tuple("assetbundle.zh_cn.manifest.json"),
        "tw": lp_m_tuple("assetbundle.zh_tw.manifest.json"),
    }


MANIFESTS = get_latest_manifests()

IMG_EXT = ".png"
IMG_ARGS = {
    ".png": {"optimize": False},
    ".webp": {"lossless": True, "quality": 0},
}


# https://github.com/vgmstream/vgmstream/blob/master/src/meta/hca_keys.h
CRI_A = "e7889cad"
CRI_B = "000002b2"

# 00000000
# 0030D9E8


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
                sae = SimpleAssetEntry()
                sae.name = label
                sae.hash = os.path.basename(url)
                sae.url = url
                _, ext = os.path.splitext(sae.name)
                sae.raw = bool(ext)
                self[label] = sae

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
        if not type(other) == AssetEntry:
            return False
        return self.hash == other.hash

    def __ne__(self, other):
        if not type(other) == AssetEntry:
            return True
        return self.hash != other.hash


class SimpleAssetEntry:
    def __init__(self, asset_entry=None):
        if asset_entry:
            self.name = asset_entry.name
            self.hash = asset_entry.hash
            self.size = asset_entry.size
            self.url = asset_entry.url
            self.raw = asset_entry.raw
        else:
            self.name = None
            self.hash = None
            self.size = None
            self.url = None
            self.raw = None
        self.ver = None


class ParsedManifest(dict):
    def __init__(self, manifest):
        super().__init__({})
        self.assets = {}
        self.raw_assets = {}
        self.path = manifest
        with open(manifest) as f:
            mtree = json.load(f)
            self["assets"] = self.assets
            for category in mtree["categories"]:
                for asset in category["assets"]:
                    self.assets[asset["name"]] = AssetEntry(asset)
            self["raw_assets"] = self.raw_assets
            for asset in mtree["rawAssets"]:
                self.raw_assets[asset["name"]] = AssetEntry(asset, raw=True)

    def asset_items(self):
        return itertools.chain(self.assets.items(), self.raw_assets.items())

    @staticmethod
    def flatten(targets):
        return [(k, SimpleAssetEntry(v)) for k, v in targets]

    def get_by_pattern(self, pattern):
        if not isinstance(pattern, re.Pattern):
            pattern = re.compile(pattern, flags=re.IGNORECASE)
        targets = filter(lambda x: pattern.search(x[0]), self.asset_items())
        return ParsedManifest.flatten(targets)

    def get_by_diff(self, other):
        targets = filter(lambda x: other.get_entry(x[0]) != x[1], self.asset_items())
        return ParsedManifest.flatten(targets)

    def get_entry(self, key):
        if key in self.assets:
            return self.assets[key]
        if key in self.raw_assets:
            return self.raw_assets[key]
        return None

    def get_by_pattern_diff(self, pattern, other):
        if not isinstance(pattern, re.Pattern):
            pattern = re.compile(pattern, flags=re.IGNORECASE)
        targets = filter(
            lambda x: pattern.search(x[0]) and other.get_entry(x[0]) != x[1],
            self.asset_items(),
        )
        return ParsedManifest.flatten(targets)

    def report_diff(self, other):
        added_keys = set()
        changed_keys = set()
        removed_keys = set()
        for key, value in self.asset_items():
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


class AllParsedManifests:
    def __init__(self, basename) -> None:
        self.path = None
        self.manifests = {}
        for mpath in tqdm(sorted(glob.glob(f"manifest/*/{basename}")), desc="manifests"):
            self.manifests[os.path.basename(os.path.dirname(mpath))] = ParsedManifest(mpath)

    def get_by_pattern(self, pattern):
        if not isinstance(pattern, re.Pattern):
            pattern = re.compile(pattern, flags=re.IGNORECASE)
        targets = {}
        for ver, pm in self.manifests.items():
            # filter(lambda x: pattern.search(x[0]), self.asset_items())
            for name, entry in pm.asset_items():
                if pattern.search(name) and entry.hash not in targets:
                    sae = SimpleAssetEntry(entry)
                    sae.ver = ver
                    targets[entry.hash] = (sae.name, sae)
        return list(targets.values())

    def asset_items(self):
        # return itertools.chain((pm.asset_items() for pm in self.manifests.values()))
        seen_hash = set()
        for pm in self.manifests.values():
            for name, entry in pm.asset_items():
                if entry.hash not in seen_hash:
                    seen_hash.add(entry.hash)
                    yield name, entry


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
        name = obj.type.name + "." + data.name.replace("/", "_")
    except AttributeError:
        print(result)
        pass
    dest = os.path.join(dest, name + ".json")
    save_json(result, dest)


def unpack_MonoBehaviour(obj, dest, ex_paths, obj_by_pathid, name=None, process=True):
    data = obj.read()
    if data.path_id in ex_paths:
        return
    try:
        name = name or data.name or data.m_Script.get_obj().read().name
    except AttributeError:
        return
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
        if component.type == ClassIDType.MonoBehaviour:
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
    obj_type_str = obj.type.name
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
                if other_pathid in ex_paths or other_obj.type != ClassIDType.Texture2D:
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
                if other_obj.type != ClassIDType.Texture2D:
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


IMAGE_TYPES = (ClassIDType.Texture2D, ClassIDType.Material, ClassIDType.Sprite, ClassIDType.AssetBundle)
UNPACK_PRIORITY = {
    ClassIDType.GameObject: 10,
    ClassIDType.Material: 9,
    # ClassIDType.AssetBundle: 8,
}


def get_unpack_priority(obj):
    return UNPACK_PRIORITY.get(obj.type, 0)


UNPACK = {
    ClassIDType.MonoBehaviour: unpack_MonoBehaviour,
    ClassIDType.GameObject: unpack_GameObject,
    ClassIDType.TextAsset: unpack_TextAsset,
    ClassIDType.AnimationClip: unpack_Animation,
    ClassIDType.AnimatorController: unpack_Animation,
    ClassIDType.AnimatorOverrideController: unpack_Animation,
    ClassIDType.Texture2D: unpack_Texture2D,
    ClassIDType.Sprite: unpack_Sprite,
    ClassIDType.Material: unpack_Material,
    # ClassIDType.AssetBundle: unpack_TypeTree,
    # ClassIDType.MonoScript: unpack_TypeTree,
}


### multiprocessing ###
def mp_extract(ex_dir, ex_img_dir, ex_target, dl_filelist):
    unity_env = Environment(*[os.path.abspath(f) for f in dl_filelist])
    ex_paths = set()

    obj_by_pathid = {}
    for asset in unity_env.assets:
        for obj in asset.get_objects():
            # print(obj.type, obj.read().name, obj.read().path_id)
            if UNPACK.get(obj.type):
                obj_by_pathid[obj.read().path_id] = obj
            # else:
            #     print(obj.type, obj.read().name, obj.read().path_id)

    ex_dest = None if ex_dir is None else os.path.join(ex_dir, ex_target)
    img_dest = None if ex_img_dir is None else os.path.join(ex_img_dir, ex_target)
    print_counter = 0
    for obj in sorted(obj_by_pathid.values(), key=get_unpack_priority, reverse=True):
        if (dest := img_dest if obj.type in IMAGE_TYPES else ex_dest) is None:
            continue
        method = UNPACK[obj.type]
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


def requests_download(url, target):
    check_target_path(target)
    trials = 3
    while trials > 0:
        trials -= 1
        try:
            # with requests.get(url, stream=True) as req:
            #     if req.status_code != 200:
            #         return False
            #     with open(target, "wb") as fn:
            #         for chunk in req:
            #             fn.write(chunk)
            with requests.get(url) as req:
                if req.status_code != 200:
                    return False
                with open(target, "wb") as fn:
                    fn.write(req.content)
            return True
        except requests.exceptions.ConnectionError:
            continue
        except Exception as e:
            print(e, url)
            return False
    print(url)
    return False


def mp_download_to_hash(source, dl_dir):
    dl_target = os.path.join(dl_dir, source.hash)
    if not os.path.exists(dl_target) or source.size != os.stat(dl_target).st_size:
        if os.path.exists(dl_target):
            os.remove(dl_target)
        if requests_download(source.url, dl_target):
            # print("-", end="", flush=True)
            pass


def mp_download(target, source, extract, region, dl_dir, overwrite, local_mirror):
    # dl_target = os.path.join(dl_dir, region, target.replace("/", "_"))
    if source.raw:
        if source.ver:
            dl_target = os.path.join(dl_dir, source.ver, target.replace("/", "_"))
        else:
            dl_target = os.path.join(dl_dir, region, target.replace("/", "_"))
    else:
        dl_target = os.path.join(dl_dir, source.hash)

    if overwrite or not os.path.exists(dl_target):
        if local_mirror is not None:
            link_src = os.path.join(local_mirror, source.hash)
            if overwrite or not os.path.exists(link_src):
                if not requests_download(source.url, link_src):
                    return
            if source.raw:
                check_target_path(dl_target)
                # symlink is no good with wine stuff
                os.link(link_src, dl_target)
            else:
                dl_target = link_src
        else:
            if not requests_download(source.url, dl_target):
                return
        print("-", end="", flush=True)
    else:
        print(".", end="", flush=True)

    if extract is None:
        extract = os.path.dirname(target).replace("/", "_")
        if source.ver:
            extract = os.path.join(source.ver, extract)
    ex_target = os.path.join(region, extract)
    return (source, ex_target, dl_target)


### multiprocessing ###


def deretore_acb(source, ex_target, dl_target):
    # https://github.com/OpenCGSS/DereTore
    cmds = []
    if sys.platform != "win32":
        # needs wine-mono
        cmds.append("wine")
    cmds.extend(("bin/deretore/acb2wavs.exe", "-a", CRI_A, "-b", CRI_B))
    cmds.append(dl_target)
    # print(" ".join(cmds))
    try:
        subprocess.call(cmds, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        return False
    out_folder = os.path.join(os.path.dirname(dl_target), "_acb_{}".format(os.path.basename(dl_target)))
    # if not os.path.exists(out_folder):
    #     return True
    check_target_path(ex_target, is_dir=True)
    use_infix = len(os.listdir(out_folder)) > 1
    if use_infix:
        use_infix = all((bool(os.listdir(subdir)) for subdir in glob.glob(out_folder + "/*")))
    for subdir in os.listdir(out_folder):
        infix = subdir + "_" if use_infix else ""
        out_sub = os.path.join(out_folder, subdir)
        for wav_file in os.listdir(out_sub):
            shutil.move(
                os.path.join(out_sub, wav_file),
                os.path.join(
                    ex_target,
                    f"{os.path.splitext(os.path.basename(source.name))[0]}_{infix}{wav_file[4:]}",
                ),
            )
    shutil.rmtree(out_folder)
    return True


def crid_mod_usm(source, ex_target, dl_target):
    # https://mega.nz/file/TJQniYwL#Dp_D-KvzVlVgTwqzVJc1n3vslBZsHdy8pdDqzhRtsOI
    cmds = []
    if sys.platform != "win32":
        cmds.append("wine")
    src_basename = os.path.splitext(os.path.basename(source.name))[0]
    ex_basename = os.path.join(ex_target, f"{src_basename}")
    check_target_path(ex_target, is_dir=True)
    check_target_path(ex_basename)
    audio_chno = "0"
    cmds.extend(("bin/crid_mod.exe", "-a", CRI_A, "-b", CRI_B, "-o", ex_basename, "-s", audio_chno, "-v", "-x"))
    cmds.append(dl_target)
    # print(" ".join(cmds))
    try:
        subprocess.call(cmds, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        return False
    m2v_file = f"{ex_basename}.m2v"
    cmds = ["ffmpeg", "-y", "-i", m2v_file]
    if os.path.exists(adx_file := f"{ex_basename}__{audio_chno}.adx"):
        cmds.extend(("-i", adx_file, "-c:a", "aac"))
    else:
        adx_file = None
    cmds.extend(("-c:v", "copy", f"{ex_basename}.mp4"))
    try:
        subprocess.call(cmds, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        return False
    finally:
        os.remove(m2v_file)
        if adx_file:
            os.remove(adx_file)
    return True


class Extractor:
    def __init__(self, dl_dir="./_download", ex_dir="./_extract", ex_img_dir="./_images", ex_media_dir="./_media", overwrite=False, manifest_override=MANIFESTS, local_mirror="../archives/cdn"):
        self.pm = {}
        self.pm_old = {}
        if manifest_override == "ALLTIME":
            for region, manifests in MANIFESTS.items():
                self.pm[region] = AllParsedManifests(os.path.basename(manifests[0]))
                self.pm_old[region] = None
        elif manifest_override == "OLDSTYLE":
            self.pm["jp"] = ParsedManifestFlat("jpmanifest_with_asset_labels.txt")
            self.pm_old["jp"] = None
        else:
            for region, manifests in manifest_override.items():
                latest, previous = manifests
                self.pm[region] = ParsedManifest(manifest=latest)
                if latest == previous:
                    self.pm_old[region] = None
                else:
                    self.pm_old[region] = ParsedManifest(manifest=previous)
        self.dl_dir = dl_dir
        self.ex_dir = ex_dir
        self.ex_img_dir = ex_img_dir
        self.ex_media_dir = ex_media_dir
        self.extract_list = []
        self.overwrite = overwrite
        self.local_mirror = local_mirror

    def raw_extract(self, source, ex_target, dl_target):
        if self.ex_media_dir:
            ex_target = os.path.join(self.ex_media_dir, ex_target)
            if source.name.endswith(".acb"):
                if deretore_acb(source, ex_target, dl_target):
                    return
            if source.name.endswith(".awb"):
                return
            if source.name.endswith(".usm"):
                if crid_mod_usm(source, ex_target, dl_target):
                    return
        if self.ex_dir:
            ex_target = os.path.join(self.ex_dir, ex_target)
            check_target_path(ex_target, is_dir=True)
            shutil.copy(dl_target, ex_target)

    ### multiprocessing ###
    def pool_download_and_extract(self, download_list, region=None):
        if not download_list:
            return
        NUM_WORKERS = multiprocessing.cpu_count()
        pool = multiprocessing.Pool(processes=NUM_WORKERS)
        if region is None:
            dl_args = [(target, source, extract, region, self.dl_dir, self.overwrite, self.local_mirror) for region, extract, matched in download_list for target, source in matched]
        else:
            dl_args = [(target, source, extract, region, self.dl_dir, self.overwrite, self.local_mirror) for extract, matched in download_list for target, source in matched]
        print(f"Download {len(dl_args)}", flush=True)  # tqdm(dl_args, desc="download", total=len(dl_args))
        downloaded = list(filter(None, pool.starmap(mp_download, dl_args)))
        pool.close()
        pool.join()

        raw_extract_args = []
        sorted_downloaded = defaultdict(list)
        for source, ex_target, dl_target in downloaded:
            if source.raw:
                raw_extract_args.append((source, ex_target, dl_target))
            else:
                sorted_downloaded[ex_target.replace("s_images", "images")].append(dl_target)

        if raw_extract_args:
            print("\nRaw")
            print_counter = 0
            for args in raw_extract_args:
                self.raw_extract(*args)
                if print_counter == 0:
                    print("=", end="", flush=True)
                    print_counter = 10
                print_counter -= 1

        if sorted_downloaded:
            pool = multiprocessing.Pool(processes=NUM_WORKERS)
            ex_args = [(self.ex_dir, self.ex_img_dir, ex_target, dl_targets) for ex_target, dl_targets in sorted_downloaded.items()]
            print(f"\nExtract {tuple(sorted_downloaded.keys())}", flush=True)
            # tqdm(ex_args, desc="extract", total=len(ex_args))
            pool.starmap(mp_extract, ex_args)
            pool.close()
            pool.join()

        print("", flush=True)

    def mirror_files(self, mirror_dir="../archives/cdn"):
        dl_args = []
        check_target_path(mirror_dir, is_dir=True)
        for region_pm in self.pm.values():
            # mirror_dir = os.path.join(mirror_prefix, os.path.basename(os.path.dirname(region_pm.path)))
            for _, source in region_pm.asset_items():
                dl_args.append((source, mirror_dir))
        # print(f"Download {len(dl_args)}", flush=True)
        # NUM_WORKERS = multiprocessing.cpu_count()
        # pool = multiprocessing.Pool(processes=NUM_WORKERS)
        # list(filter(None, pool.starmap(mp_download_to_hash, dl_args)))
        # pool.close()
        # pool.join()
        for args in tqdm(dl_args, desc="download"):
            mp_download_to_hash(*args)

    ### multiprocessing ###

    def download_and_extract_by_pattern_diff(self, label_patterns):
        download_list = []
        for region, label_pat in label_patterns.items():
            if not self.pm_old[region]:
                continue
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
        if not self.pm_old[region]:
            return
        download_list = self.pm[region].get_by_diff(self.pm_old[region])
        self.pool_download_and_extract(((None, download_list),), region=region)

    def report_diff(self, region="jp"):
        if not self.pm_old[region]:
            return
        self.pm[region].report_diff(self.pm_old[region])

    def apk_assets_extract(self, asset_folder):
        # for use with apk
        acb_files = []
        usm_files = []
        # unity_files = []
        # globalgamemanagers = []
        # deretore_acb(source, ex_target, dl_target)
        for root, _, files in os.walk(asset_folder):
            for filename in files:
                _, ext = os.path.splitext(filename)
                source = SimpleAssetEntry()
                source.name = filename
                filepath = os.path.join(root, filename)
                args = (
                    source,
                    os.path.join(self.ex_media_dir, "apk", root.replace(asset_folder, "").replace("/", "_")),
                    filepath,
                )
                if ext in (".acb", ".awb"):
                    acb_files.append(args)
                elif ext in (".usm",):
                    usm_files.append(args)
                # elif "assets/bin/Data" in root:
                #     if os.path.basename(filename).startswith("globalgamemanagers"):
                #         globalgamemanagers.append(filepath)
                #     else:
                #         unity_files.append(filepath)

        for args in acb_files:
            deretore_acb(*args)

        for args in usm_files:
            crid_mod_usm(*args)

        # print("\nExtract")

        # mp_extract(self.ex_dir, self.ex_img_dir, "bin_Data", [*globalgamemanagers, *unity_files])

        # ex_target = "bin_Data"
        # bin_data_path = os.path.abspath(os.path.join(asset_folder, "bin/Data"))

        # unity_env = Environment(bin_data_path)
        # ex_paths = set()

        # obj_by_pathid = {}
        # for asset in unity_env.assets:
        #     for obj in asset.get_objects():
        #         # print(obj.type, obj.read().path_id)
        #         if UNPACK.get(obj.type):
        #             obj_by_pathid[obj.read().path_id] = obj
        #         # else:
        #         #     print(obj.type, obj.read().name, obj.read().path_id)

        # ex_dest = None if self.ex_dir is None else os.path.join(self.ex_dir, ex_target)
        # img_dest = None if self.ex_img_dir is None else os.path.join(self.ex_img_dir, ex_target)
        # print_counter = 0
        # for obj in sorted(obj_by_pathid.values(), key=get_unpack_priority, reverse=True):
        #     if (dest := img_dest if obj.type in IMAGE_TYPES else ex_dest) is None:
        #         continue
        #     method = UNPACK[obj.type]
        #     check_target_path(dest, is_dir=True)
        #     method(obj, dest, ex_paths, obj_by_pathid)
        #     if print_counter == 0:
        #         print("=", end="", flush=True)
        #         print_counter = 10
        #     print_counter -= 1

        # path_id_to_string = {pathid: sprite for pathid, sprite in obj_by_pathid.items() if isinstance(sprite, str)}
        # if path_id_to_string:
        #     with open(os.path.join(img_dest, "_path_id.json"), "w") as fn:
        #         json.dump(path_id_to_string, fn, indent=2)
