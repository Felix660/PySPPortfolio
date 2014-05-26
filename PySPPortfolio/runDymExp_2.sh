#!/bin/bash
ns=$1
for alpha in  0.5 0.55 0.6 0.65 0.7 0.75 0.8 0.85 0.9 0.95
do 
	for p in 90 100 110 120
	do
	   python dynamicSymbolSPPortfolio.py -n $ns -p $p -a $alpha  -f
   	done
done
