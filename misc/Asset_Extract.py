import os
import argparse
import errno
import json
from UnityPy import AssetsManager

def check_target_path(target):
    if not os.path.exists(os.path.dirname(target)):
        try:
            os.makedirs(os.path.dirname(target))
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise

def write_mono(f, data):
    f.write(data.dump())

do_filter = False
def filter_dict(d):
    if do_filter:
        return dict(filter(lambda elem: elem[1] != 0, d.items()))
    else:
        return d

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

write = write_json
mono_ext = '.json'

def unpack_Texture2D(data, dest):
    print('Texture2D', dest, flush=True)
    dest, _ = os.path.splitext(dest)
    dest = dest + '.png'
    check_target_path(dest)

    img = data.image
    img.save(dest)

def unpack_MonoBehaviour(data, dest):
    print('MonoBehaviour', dest, flush=True)
    dest, _ = os.path.splitext(dest)
    dest = dest + mono_ext
    check_target_path(dest)

    with open(dest, 'w', encoding='utf8', newline='') as f:
        write(f, data)

def unpack_GameObject(data, destination_folder):
    dest = os.path.join(destination_folder, os.path.splitext(data.name)[0])
    print('GameObject', dest, flush=True)
    mono_list = []
    for idx, obj in enumerate(data.components):
        obj_type_str = str(obj.type)
        if obj_type_str in unpack_dict:
            subdata = obj.read()
            if obj_type_str == 'MonoBehaviour':
                if mono_ext == '.json':
                    json_data = subdata.read_type_tree()
                    if json_data:
                        mono_list.append(json_data)
                else:
                    mono_list.append(data.dump())
            elif obj_type_str == 'GameObject':
                unpack_dict[obj_type_str](subdata, os.path.join(dest, '{:02}'.format(idx)))
    if len(mono_list) > 0:
        dest += mono_ext
        check_target_path(dest)
        with open(dest, 'w', encoding='utf8', newline='') as f:
            if mono_ext == '.json':
                json.dump(mono_list, f, indent=2)
            else:
                for m in mono_list:
                    f.write(m)
                    f.write('\n')

unpack_dict = {
    'Texture2D': unpack_Texture2D, 
    'MonoBehaviour': unpack_MonoBehaviour,
    'GameObject': unpack_GameObject,
    'AnimationClip': unpack_MonoBehaviour,
    'AnimatorOverrideController': unpack_MonoBehaviour
}

def unpack_asset(file_path, destination_folder, root=None, source_folder=None):
    # load that file via AssetsManager
    am = AssetsManager(file_path)

    # iterate over all assets and named objects
    for asset in am.assets.values():
        for obj in asset.objects.values():
            # only process specific object types
            # print(obj.type, obj.container)
            obj_type_str = str(obj.type)
            if obj_type_str in unpack_dict:
                # parse the object data
                data = obj.read()

                # create destination path
                if root and source_folder:
                    intermediate = root.replace(source_folder, '')
                    if len(intermediate) > 0 and intermediate[0] == '\\':
                        intermediate = intermediate[1:]
                else:
                    intermediate = ''
                if obj_type_str == 'GameObject':
                    dest = os.path.join(destination_folder, intermediate)
                    unpack_dict[obj_type_str](data, dest)
                elif data.name:
                    dest = os.path.join(destination_folder, intermediate, data.name)
                    unpack_dict[obj_type_str](data, dest)
                

def unpack_all_assets(source_folder, destination_folder):
    # iterate over all files in source folder
    for root, _, files in os.walk(source_folder):
        for file_name in files:
            # generate file_path
            file_path = os.path.join(root, file_name)
            unpack_asset(file_path, destination_folder, root=root, source_folder=source_folder)
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract asset files.')
    parser.add_argument('-i', type=str, help='input dir', default='./download')
    parser.add_argument('-o', type=str, help='output dir', default='./extract')
    parser.add_argument('-mode', type=str, help='export format, default json, can also use mono', default='json')
    args = parser.parse_args()
    if args.mode == 'mono':
        write = write_mono
        mono_ext = '.mono'
    if os.path.isdir(args.i):
        unpack_all_assets(args.i, args.o)
    else:
        unpack_asset(args.i, args.o)