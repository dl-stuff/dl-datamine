import os
import shutil
import json

from loader.AssetExtractor import Extractor

DEPENDENCIES = {
    'jp': {
        r'^images/ingame/ui': None,
        r'^prefabs/ingame/ingamebuffui': None
    }
}
PATH_ID_FILE = './_icons/jp/images_ingame/_path_id.json'
INGAME_UI_FILE = './_icons/jp/prefabs_ingame/InGameBuffUI.json'
COMBINED_MAP_FILE = './_icons/icons.json'

def make_buff_icon_mapping():
    try:
        shutil.rmtree('./_icons')
    except FileNotFoundError:
        pass
    ex = Extractor(ex_img_dir='./_icons', ex_dir='./_icons', mf_mode=1)
    ex.download_and_extract_by_pattern(DEPENDENCIES)

    with open(PATH_ID_FILE, 'r') as fp:
        path_id_map = json.load(fp)
    
    with open(INGAME_UI_FILE, 'r') as fp:
        ingame_ui = {}
        for icon_type, data in json.load(fp)[0].items():
            if not icon_type.endswith('Icon'):
                continue
            ingame_ui[icon_type] = {idx: path_id_map.get(str(entry['m_PathID'])) for idx, entry in enumerate(data) if entry['m_FileID']}

    missing_icons = set()
    for icon_type, icon_map in ingame_ui.items():
        new_folder = f'./_icons/{icon_type}'
        os.makedirs(new_folder)
        for icon in icon_map.values():
            src = f'./_icons/jp/images_ingame/{icon}.png'
            if os.path.exists(src):
                shutil.move(src, f'{new_folder}/{icon}.png')
            else:
                missing_icons.add(icon)
    shutil.rmtree('./_icons/jp')

    ingame_ui['missingIcons'] = list(missing_icons)

    try:
        from loader.InGameBuffUI import BuffIconType, UniqueBuffIconType
        unique_icons = {}
        for idx, icon in ingame_ui['buffIcon'].items():
            try:
                unique_icons[UniqueBuffIconType[BuffIconType(idx).name].value] = icon
            except (KeyError, ValueError):
                pass
        ingame_ui['uniqueBuffIcon'] = unique_icons
    except ImportError:
        pass

    with open(COMBINED_MAP_FILE, 'w') as fp:
        json.dump(ingame_ui, fp, indent=4)


if __name__ == '__main__':
    make_buff_icon_mapping()