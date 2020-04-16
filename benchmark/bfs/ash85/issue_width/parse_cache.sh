#! /bin/bash


for i in 1 2 4 8 16 32 64
do
	cat pim_${i}.stats | grep "L1_cache_write_miss" | awk 'BEGIN{a=   0}{if ($2>0+a) a=$2} END{print a}'
done

echo "read miss"

for i in 1 2 4 8 16 32 64
do
        cat pim_${i}.stats | grep "L1_cache_read_miss" | awk 'BEGIN{a=   0}{if ($2>0+a) a=$2} END{print a}'
done
