#!/bin/sh

ulimit -t 20

cp input.c input-framac.c
perl -pi.bak -e 's/int main \(int argc, char\* argv\[\]\)/int argc; char **argv; int main (void)/' input-framac.c

if
  # clang -pedantic -Wall -O0 -c -I/home/zappa/source/cmmtest/csmith-locks-bin/include/csmith-2.1.0/ input.c > out.txt 2>&1 &&\
  # ! grep 'conversions than data arguments' out.txt &&\
  # ! grep 'incompatible redeclaration' out.txt &&\
  # ! grep 'ordered comparison between pointer' out.txt &&\
  # ! grep 'eliding middle term' out.txt &&\
  # ! grep 'end of non-void function' out.txt &&\
  # ! grep 'invalid in C99' out.txt &&\
  # ! grep 'specifies type' out.txt &&\
  # ! grep 'should return a value' out.txt &&\
  # ! grep 'uninitialized' out.txt &&\
  # ! grep 'incompatible pointer to' out.txt &&\
  # ! grep 'incompatible integer to' out.txt &&\
  # ! grep 'type specifier missing' out.txt &&\
  gcc -Wall -Wextra -O2 -I/home/zappa/source/cmmtest/csmith-locks-bin/include/csmith-2.1.0/ input.c -o smallz > outa.txt 2>&1 &&\
  ! grep uninitialized outa.txt &&\
  ! grep 'without a cast' outa.txt &&\
  ! grep 'control reaches end' outa.txt &&\
  ! grep 'return type defaults' outa.txt &&\
  ! grep 'cast from pointer to integer' outa.txt &&\
  ! grep 'useless type name in empty declaration' outa.txt &&\
  ! grep 'no semicolon at end' outa.txt &&\
  ! grep 'type defaults to' outa.txt &&\
  ! grep 'too few arguments for format' outa.txt &&\
  ! grep 'ordered comparison of pointer with integer' outa.txt &&\
  ! grep 'declaration does not declare anything' outa.txt &&\
  ! grep 'expects type' outa.txt &&\
  ! grep 'pointer from integer' outa.txt &&\
  ! grep 'incompatible implicit' outa.txt &&\
  ! grep 'initialization discards' outa.txt &&\
  ! grep 'initialization from incompatible pointer type' outa.txt &&\
  ! grep 'excess elements in struct initializer' outa.txt &&\
  ! grep 'comparison between pointer and integer' outa.txt &&\
  frama-c -cpp-command "gcc -C -Dvolatile= -E -I. -I/home/zappa/source/cmmtest/csmith-locks-bin/include/csmith-2.1.0/" -val -no-val-show-progress -machdep x86_64 -obviously-terminates input-framac.c > framac_result 2>&1 &&\
  ! egrep -i '(user error|assert)' framac_result > /dev/null 2>&1 &&\
  echo "Curr dir:" &&\
  echo `pwd` &&\
  echo "COMPILING" &&\
  clang -O3 -I /home/zappa/source/cmmtest/csmith-locks-bin/include/csmith-2.1.0/ -o input input.c > /dev/null 2>&1 &&\
#  gcc -O2 -static -I /home/zappa/source/cmmtest/csmith-locks-bin/include/csmith-2.1.0/ -o input input.c > /dev/null 2>&1 &&\
  # echo "PRE TESTING" &&\
  # echo `pwd` &&\
  # /home/zappa/source/gdb-py27/bin/gdb -x /home/zappa/repos/zappa/dwarf/src-fzn/eh_frame_check.py input &&\
  echo "TESTING" &&\
  /home/zappa/source/gdb-py27/bin/gdb -x /home/zappa/repos/zappa/dwarf/src-fzn/eh_frame_check.py input > eh_frame_check_result.txt 2>&1 < /dev/null &&\
  echo "SEARCHING" &&\
  grep "Mismatch" eh_frame_check_result.txt
then
  exit 0
else
  exit 1
fi
