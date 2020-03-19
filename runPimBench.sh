#!/bin/bash
zsimDir='../ramulator-pim/zsim-ramulator/'
ramulatorDir='../ramulator-pim/ramulator/'

# Parameters
cfgFile='./pim.cfg' # Remember to check the cfg file before run
saveDir='./benchmarkTest/BFS/ash85/'

# Run benchmark
rm *.out*
${zsimDir}build/opt/zsim ${cfgFile}
mv pim.out* $saveDir

${ramulatorDir}ramulator \
--config ${ramulatorDir}Configs/pim.cfg \
--disable-perf-scheduling true \
--mode=cpu --stats pim.stats \
--trace ${saveDir}pim.out \
--core-org=outOrder \
--number-cores=4 \
--trace-format=zsim \
--split-trace=true
mv pim.stats $saveDir



# Cleanup
rm heartbeat
rm out.cfg
