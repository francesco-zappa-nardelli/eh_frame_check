#!/bin/bash

set -x

obj_name=$(basename "$1" .c).o
bin_name=$(basename "$1" .c)

clang -c -fomit-frame-pointer -fno-asynchronous-unwind-tables -o $obj_name $1
~/source/linux-4.14/tools/objtool/objtool orc generate -f $obj_name
../dareog generate-dwarf $obj_name
gcc $obj_name -o $bin_name


