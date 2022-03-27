from collections import defaultdict
import re
import argparse
from loader.AssetExtractor import Extractor, MANIFESTS, get_manifests


def pattern(arg):
    split = arg.split(":")
    exp = split[0]
    try:
        target = split[1]
    except IndexError:
        target = None
    try:
        region = split[2]
        if region not in MANIFESTS:
            region = None
    except IndexError:
        region = None
    return region, exp, target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download and unpack assets.")
    parser.add_argument("-op", "--operation", type=str, default="extract", help="Operation to perform")
    parser.add_argument("-dl", "--download_dir", type=str, help="Download directory, 0 to skip")
    parser.add_argument("-ex", "--extract_dir", type=str, help="Extract directory, 0 to skip")
    parser.add_argument("-ex_img", "--extract_img_dir", type=str, help="Extract image directory, 0 to skip")
    parser.add_argument("-ex_media", "--extract_media_dir", type=str, help="Extract media directory, 0 to skip")
    parser.add_argument("-m", "--manifest", type=str, help="Manifest directory")
    parser.add_argument("-r", "--region", type=str, help="Region {!r}".format(MANIFESTS.keys()))
    parser.add_argument("patterns", type=pattern, nargs="*", help="Extract patterns. Syntax: {regex}, {regex}:{target}, {regex}:{target}:{region}")
    args = parser.parse_args()

    ex_kwargs = {}
    for key, arg in (("dl_dir", args.download_dir), ("ex_dir", args.extract_dir), ("ex_img_dir", args.extract_img_dir), ("ex_media_dir", args.extract_media_dir)):
        if arg == "0":
            ex_kwargs["dl_dir"] = None
        elif arg:
            ex_kwargs["dl_dir"] = arg

    if args.manifest and args.operation in ("extract", "mirror"):
        if args.manifest == "ALLTIME":
            ex_kwargs["manifest_override"] = args.manifest
        else:
            ex_kwargs["manifest_override"] = get_manifests(args.manifest, args.manifest)

    ex = Extractor(**ex_kwargs)
    # dl_dir="./_download", ex_dir="./_extract", ex_img_dir="./_images", ex_media_dir="./_media"
    if args.operation == "apk":
        ex.apk_assets_extract(args.patterns[0][1])
    elif args.operation == "diff":
        if args.region:
            print(f"{args.region}: ", flush=True, end="")
            ex.download_and_extract_by_diff(region=args.region)
        else:
            for region in MANIFESTS.keys():
                ex.download_and_extract_by_diff(region=region)
    elif args.operation == "mirror":
        ex.mirror_files()
    elif args.operation == "report":
        ex.report_diff()
    else:
        ex_patterns = defaultdict(dict)
        for region, exp, target in args.patterns:
            if not (region := (region or args.region)):
                for reg in MANIFESTS.keys():
                    ex_patterns[reg][exp] = target
            else:
                ex_patterns[region][exp] = target
        print(f"Patterns {dict(ex_patterns)}")
        ex.download_and_extract_by_pattern(ex_patterns)
