# Requirements

- python 3.8+
- [UnityPy](https://pypi.org/project/UnityPy/)
- [tqdm](https://github.com/tqdm/tqdm)
- [Unidecode](https://pypi.org/project/Unidecode/)

Can use the `venv.sh` script to setup.

# Loading and Parsing Data

Run `python Load_Database.py --do_prep`, this generates a `dl.sqlite` file.

The `--do_prep` means download/extract new assets, it is optional when only db reload is desired.
 
`python Export_Data.py` creates linked json describing various elements of the game using the database. 

`./run_conf` exports sim compatible json, not all mechanics are implemented.

# Asset Extraction

The Asset_Extract tool downloads data from the manifest and unpack/convert supported formats.

By default, the latest manifest is used.

Examples:

- `python Asset_Extract.py images/icon/chara/l` to download & extract all assets whose names contains "images/icon/chara/l".

- `python Asset_Extract.py "\.usm$"` to download & extract all assets whose names end in ".usm$".

See `python Asset_Extract.py -h` for more arguments.
