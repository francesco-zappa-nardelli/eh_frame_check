#!/bin/sh

bin_dir=$(dirname "$0")

if [ "$CREDUCE_FILE" = "" ] ; then
	echo "Missing \$CREDUCE_FILE"
	exit 1
fi

"$bin_dir/check.sh" "$CREDUCE_FILE"
if [ "$?" = 42 ]; then
	exit 0 # Check failed, mark file as interesting
else
	exit 1 # Compilation failed or check succeeded, reject file
fi
