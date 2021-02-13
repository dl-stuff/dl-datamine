import os
import pathlib
import subprocess
import shutil
import json

from loader.AssetExtractor import Extractor

STICKER_PATTERN = {
    "jp": {
        r"images/icon/stamp/l/framed": "stickers",
        r"localize/ja_jp/sound/v/other/vo_chr_stamp": "voices",
        r"localize/en_us/sound/v/other/vo_chr_stamp": "../en/voices",
    },
    "en": {
        r"images/icon/stamp/l/framed": "stickers",
    },
    "cn": {
        r"images/icon/stamp/l/framed": "stickers",
    },
}
OUT_DIR = "_stickers"
LIBCGSS = os.path.join(
    pathlib.Path(__file__).parent.absolute(), "..", "..", "libcgss", "acb2wavs.exe"
)
LIBCGSS_ARGS = ("-b", "000002b2", "-a", "e7889cad", "-n")
ARROW_STICKERS = (
    "11102.png",
    "11103.png",
    "11104.png",
    "11105.png",
    "11106.png",
    "11107.png",
    "11108.png",
)


def download_sticker_assets():
    ex = Extractor(ex_dir=OUT_DIR, ex_img_dir=OUT_DIR, stdout_log=False)
    ex.download_and_extract_by_pattern(STICKER_PATTERN)
    for region in ("jp", "en"):
        voice_dir = os.path.join(OUT_DIR, region, "voices")
        cmd = [LIBCGSS, os.path.join(voice_dir, "vo_chr_stamp.acb"), *LIBCGSS_ARGS]
        subprocess.check_output(cmd)
        os.remove(os.path.join(voice_dir, "vo_chr_stamp.acb"))
        os.remove(os.path.join(voice_dir, "vo_chr_stamp.awb"))
        external_dir = os.path.join(voice_dir, "_acb_vo_chr_stamp.acb", "external")
        for wav in os.listdir(
            os.path.join(voice_dir, "_acb_vo_chr_stamp.acb", "external")
        ):
            shutil.copy(os.path.join(external_dir, wav), voice_dir)
        shutil.rmtree(os.path.join(voice_dir, "_acb_vo_chr_stamp.acb"))


def make_sticker_index():
    sticker_index = {}
    for region in ("jp", "en"):
        sticker_dir = os.path.join(OUT_DIR, region, "stickers")
        voice_dir = os.path.join(OUT_DIR, region, "voices")
        sticker_index[region] = {}
        for png in os.listdir(sticker_dir):
            if png in ARROW_STICKERS:
                sticker_index[region][png] = "VO_CHR_STAMP_1101.wav"
            else:
                idx, _ = os.path.splitext(png)
                idx = int(idx) - 10000
                wav = f"VO_CHR_STAMP_{idx:04d}.wav"
                full_wav = os.path.join(voice_dir, wav)
                if not os.path.exists(full_wav):
                    print(f"No voice file ({full_wav}) found for {png}")
                    wav = None
                sticker_index[region][png] = wav
    with open(os.path.join(OUT_DIR, "index.json"), "w") as fp:
        json.dump(sticker_index, fp)


if __name__ == "__main__":
    # download_sticker_assets()
    make_sticker_index()
