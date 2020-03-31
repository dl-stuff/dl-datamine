import argparse
import json
import os
from typing import Dict


def get_text_label(in_dir: str) -> Dict[str, str]:
    with open(os.path.join(in_dir, 'TextLabel.json')) as f:
        return {entry['_Id']: entry['_Text'] for entry in json.load(f)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Text Label.')
    parser.add_argument('-i', type=str, help='input dir', default='./extract')
    parser.add_argument('-o', type=str, help='output file', default='./out/TextLabel.json')
    args = parser.parse_args()
    with open(args.o, 'w+', encoding='utf8') as f:
        json.dump(get_text_label(args.i), f, indent=2)
