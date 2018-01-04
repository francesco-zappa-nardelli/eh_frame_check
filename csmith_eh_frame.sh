#!/bin/bash

NOTEST=0

for (( ; ; ))
do
    NOTEST=`expr $NOTEST + 1`
    echo "TEST NO: $NOTEST"
    echo "  Generating..."
    csmith --ccomp --no-checksum --no-argc --max-funcs 20 --max-expr-complexity 10 -o csmith_file.c
    sed -i '/platform/s/^/ \/\/ /' csmith_file.c

    echo "  Compiling..."
    #ccomp -O -fstruct-passing -fbitfields -I /home/zappa/source/cmmtest/csmith-locks-bin/include/csmith-2.1.0/ -o csmith_file csmith_file.c # > /dev/null 2>&1

    gcc -O1 -I /home/zappa/source/cmmtest/csmith-locks-bin/include/csmith-2.1.0/ -o csmith_file csmith_file.c > /dev/null 2>&1

    echo "  Testing termination..."
    timeout 1 ./csmith_file
    if [ $? -eq 124 ]; then
            echo "... doesn't terminate."
            NOTEST=`expr $NOTEST - 1`
    else
        logfile="csmith_file.log.$NOTEST" 
        echo "  Testing... $logfile"
        /home/zappa/source/gdb-py27/bin/gdb -q -x /home/zappa/repos/zappa/dwarf/src-fzn/eh_frame_check.py csmith_file > $logfile
        grep "Mismatch" $logfile
        greprc=$?
        if [[ $greprc -eq 0 ]] ; 
        then
            echo "Found a mismatch."
            break
        fi
    fi
done
