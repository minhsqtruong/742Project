#! /bin/bash

for k in tc
do
	for g in ash85 blckhole bcspwr01 
	do
	 	./runPimBench.sh ${k} ${g} issue_width $1
	done
done
