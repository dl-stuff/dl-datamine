rm -rf ./download
python Asset_Download.py -m enmanifest_with_asset_labels.txt -l master -out download/en/
python Asset_Download.py -m jpmanifest_with_asset_labels.txt -l master -out download/jp/
python Asset_Download.py -m jpmanifest_with_asset_labels.txt -l actions -out download/
python Asset_Download.py -m jpmanifest_with_asset_labels.txt -f characters/motion -out download/
rm -rf ./extract
python Asset_Extract.py -i ./download/en/master -o ./extract/en/master
python Asset_Extract.py -i ./download/jp/master -o ./extract/jp/master
python Asset_Extract.py -i ./download/actions -o ./extract/actions
python Asset_Extract.py -i ./download/characters_motion -o ./extract/characters_motion
python Asset_Extract.py -i ./download/assets__gluonresources_meshes_characters_motion -o ./extract/characters_motion