#!/bin/bash
python manifest/parse.py $1
python Load_Database.py --do_prep
python exporter/Simulator.py
python Export_Data.py
./run_conf.sh
python Sim_Icons.py