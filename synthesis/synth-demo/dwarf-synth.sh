#!/bin/bash

~/source/linux-4.14/tools/objtool/objtool orc generate -f $1
../dareog generate-dwarf $1
