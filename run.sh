rm -rf dl.sqlite
python Load_Database.py
rm -rf ./out
python exporter/Adventurers.py
python exporter/Dragons.py
python exporter/Wyrmprints.py
python exporter/Weapons.py