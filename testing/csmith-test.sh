#!/bin/sh

set -e -o pipefail

bin_dir=$(dirname "$0")

if [ -z "$CC" ] ; then
	CC="cc"
fi

$CC $CFLAGS $LDFLAGS -o csmith.out "$1"
gdb -q -x "$bin_dir/eh_frame_check.py" csmith.out | tee csmith.log
grep Mismatch csmith.log && exit 1 || exit 0
