#!/bin/sh

set -e -o pipefail

bin_dir=$(dirname "$0")

if echo $CFLAGS | grep -q -e '-fomit-frame-pointer' -; then
	export OBJTOOLFLAGS="$OBJTOOLFLAGS --no-fp"
fi

"$bin_dir/check.sh" $1
