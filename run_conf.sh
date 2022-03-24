#!/bin/bash
python Generate_Conf.py
# python Merge_Conf.py -name exability
# python Merge_Conf.py -name wyrmprints
# python Merge_Conf.py -name amp
# python Merge_Conf.py -name fort
cp -r ./out/gen/* ../dl/conf
# python Merge_Conf.py --all