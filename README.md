# Requirements

- python 3.8+
- [UnityPy](https://pypi.org/project/UnityPy/)
- [aiohttp](https://docs.aiohttp.org/en/stable/)
- [tqdm](https://github.com/tqdm/tqdm)
- [Unidecode](https://pypi.org/project/Unidecode/)
- [Pillow](https://pypi.org/project/Pillow/)

# Running

1. Manually set up the `manifest` directory to be like the following, these files can be copied from the dated directories. `*.old` files should be the manifests from 1 version earlier.
```
manifest/
  assetbundle.manifest.json
  assetbundle.manifest.json.old
  assetbundle.en_us.manifest.json
  assetbundle.en_us.manifest.json.old
  assetbundle.zh_cn.manifest.json
  assetbundle.zh_cn.manifest.json.old
```

2. Run `python Load_Database.py --do_prep`, this generates a `dl.sqlite` file.
   The `--do_prep` indicates download/extract new assets, it is optional when only db reload is desired.
 
3. Run `python Export_Data.py`
