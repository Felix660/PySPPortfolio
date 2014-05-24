#!/bin/bash
ns=$1
for alpha in 0.75 0.8 0.85 0.9 0.95
do 
	for p in 70 80 90
	do
	   python dynamicSymbolSPPortfolio.py -n $ns -p $p -a $alpha  -f
   	done
done