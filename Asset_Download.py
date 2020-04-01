import os
import re
import errno
import aiohttp
import asyncio
import argparse

def merge_path_dir(path):
    new_dir = os.path.dirname(path).replace('/', '_')
    return new_dir + '/' + os.path.basename(path)

def check_target_path(target):
    if not os.path.exists(os.path.dirname(target)):
        try:
            os.makedirs(os.path.dirname(target))
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise

async def download(session, source, target):
    if os.path.exists(target):
        return
    print('Download', source, target)
    async with session.get(source) as resp:
        assert resp.status == 200
        check_target_path(target)
        with open(target, 'wb') as f:
            f.write(await resp.read())

def read_manifest_by_filter_str(manifest, filter_str, output):
    manifest_set = set()
    with open(manifest, 'r') as m:
        for l in m:
            sp = l.split('|')
            if not filter_str or filter_str in sp[1]:
                # yield sp[0].strip(), 'output/'+merge_path_dir(sp[1].strip())
                # yield sp[0].strip(), './'+sp[1].strip()
                mtuple = sp[0].strip(), output+merge_path_dir(sp[1].strip())
                manifest_set.add(mtuple)
    return manifest_set

def read_manifest_by_file_list(manifest, file_list, output):
    manifest_set = set()
    with open(manifest, 'r') as m:
        for l in m:
            sp = l.split('|')
            label = sp[1].strip()
            if label in file_list:
                mtuple = sp[0].strip(), output+merge_path_dir(label)
                manifest_set.add(mtuple)
                file_list.remove(label)
            if len(file_list) == 0:
                break
    return manifest_set

async def main(manifest, filter_str, output, old_manifest=None, file_list=[]):
    if file_list:
        manifest_set = read_manifest_by_file_list(manifest, file_list, output)
    else:
        manifest_set = read_manifest_by_filter_str(manifest, filter_str, output)
        if old_manifest is not None:
            manifest_old = read_manifest_by_filter_str(old_manifest, filter_str, output)
            manifest_set = manifest_set - manifest_old
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*[
            download(session, source, target)
            for source, target in manifest_set
        ])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download asset files from manifest.')
    parser.add_argument('-m', type=str, help='manifest file', required=True)
    parser.add_argument('-l', type=str, help='list of files, exact names', default=[], action='extend', nargs='+')
    parser.add_argument('-f', type=str, help='filter string', default=None)
    parser.add_argument('-o', type=str, help='older manifest', default=None)
    parser.add_argument('-out', type=str, help='output', default='download/')
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(args.m, args.f, args.out, args.o, [l.strip() for l in args.l]))