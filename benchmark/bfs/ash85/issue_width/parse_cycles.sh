#! /bin/bash


for i in 1 2 4 8 16 32 64
do
	cat pim_${i}.out.zsim.out | grep -A 1 "core-" | grep "cycles" | awk 'BEGIN{a=   0}{if ($2>0+a) a=$2} END{print a}'
done
