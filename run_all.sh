#!/bin/bash
python manifest/parse.py $1
python Load_Database.py --do_prep
python exporter/Simulator.py
python Export_Data.py
python exporter/AdvConf.py -a all
python exporter/AdvConf.py -d all
python exporter/AdvConf.py -wp all
python exporter/AdvConf.py -w all
python exporter/AdvConf.py -w base
python Merge_Conf.py -name skillshare
python Merge_Conf.py -name exability
python Merge_Conf.py -name wyrmprints