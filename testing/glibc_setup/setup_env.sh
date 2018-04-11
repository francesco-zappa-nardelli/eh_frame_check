#!/bin/bash

function status_update {
    echo "### $1 ###"
}

function fail {
    echo "An error has occured. Exiting."
    exit 1
}

function gitclone {
    if [ -d "$2" ] ; then
        if [ -d "$2/.git" ] ; then
            git -C "$2" pull || fail
        else
            >&2 echo "Directory "$2" is present and not git. Aborting."
            fail
        fi
    else
        git clone "$1" "$2" || fail
    fi
}

function do_make {
    make $(MAKE_FLAGS) $1
}


base_dir="$(dirname "$(readlink -f "$0")")"
cd "$base_dir"

# First, clone glibc
status_update "Cloning glibc"
gitclone git://sourceware.org/git/glibc.git glibc

# Install a virtualenv with required pip packages
status_update "Installing python virtualenv"
virtualenv -p python3 ../venv || fail
source ../venv/bin/activate
pip install -r ../requirements.txt || fail

# Compiling glibc
install_dir="$base_dir/glibc/build/install"
status_update "Compiling base glibc"
(
    mkdir -p glibc/build/install
    cd glibc/build
    ../configure --prefix="$install_dir" || exit 1
    do_make || exit 1
    do_make install || exit 1
) || fail

# Compiling testsuite
status_update "Compiling glibc testsuite"
status_update "Feel free to go and drink some coffee now. This will take some time."
(
    cd glibc/build
    CPATH="$install_dir/include:$CPATH" do_make check || exit 1
) || fail

# Done!
status_update "All set!"
