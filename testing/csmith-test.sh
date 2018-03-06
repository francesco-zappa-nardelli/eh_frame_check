#!/bin/sh

bin_dir=$(dirname "$0")

$CC $CFLAGS $LDFLAGS -o csmith.out "$1"
gdb -q -x "$bin_dir/eh_frame_check.py" csmith.out | tee csmith.log
grep Mismatch csmith.log && exit 1 || exit 0
