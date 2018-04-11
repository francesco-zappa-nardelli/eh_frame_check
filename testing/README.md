eh_frame_check.py
=================

Author: Francesco Zappa Nardelli

Last revision of this README: June 2nd, 2016.

`eh_frame_check.py` is a simple tool that attempts to _validate_ the
eh_frame tables.  It is limited to return addresses for now.  It step
through the program with gdb, checks the call and ret instructions to
build a concrete view of the stack frames, evaluate the `.eh_frame` infos
with the current register values, and compares them.  Mismatches are
reported.

Setup
-----

`eh_frame_check.py` relies on gdb with the python 2.7 or 3 interpreter
compiled in.  To check:

```
$ gdb
(gdb) python print (sys.version)
````

In case, the magic incantation to recompile gdb is:

- download gdb from http://ftp.gnu.org/gnu/gdb (tested with GNU gdb (GDB) 7.11)
- ./configure --prefix /usr/local/gdb-python2 --with-python
- make; make install

To run `eh_frame_check.py` you will require the packages from
`requirements.txt`. A working example can be found in the `glibc_setup`
directory.

Invocation
----------

```
$ gdb -q -se <path_to_binary>  -P eh_frame_check.py <options>
```

`verbose`, `dbg_eval` and `cs_eval` can be set to true using the options.
By default these options are false and can be set to true to obtain respectively
a trace of the analysed instructions, of the dwarf expression evaluator and check also the calle-saved register

A sample trace with `verbose` enabled:

> old example
```
$ gdb -q -x eh_frame_check.py ~/tmp/foo3
Reading symbols from /home/zappa/tmp/foo3...done.
INIT: ['0x-1', '0x7fffffffe1f8']
=> 0x400530 (sub)
=> 0x400534 (lea)
=> 0x40053c (movl)
=> 0x400544 (movl)
=> 0x40054c (movl)
=> 0x400554 (mov)
=> 0x400558 (mov)
=> 0x40055c (mov)
=> 0x40055e (callq)
CALL: ['0x-1', '0x7fffffffe1f8', '0x7fffffffe1d8']
=> 0x400410 (jmpq)
=> 0x400416 (pushq)
=> 0x40041b (jmpq)
=> 0x400400 (pushq)
=> 0x400406 (jmpq)
=> 0x7ffff7df04e0 (sub)
 ----------------------------------
 | eh_frame for ra = 0x7fffffffe1c8
 | status   for ra = 0x7fffffffe1d8
 | Table Mismatch at IP: 0x7ffff7df04e0
 | eh_frame entry from : 0x4005f0 : ({16: RegisterRule(OFFSET, -8), 'pc': 4195824, 'cfa': CFARule(reg=7, offset=8, expr=None)}, ([16], 16))
Aborting...
````

The INIT/CALL/RET tags show the expected locations of the return
addresses on the stack after each call/ret instruction.  The =>
preceedes the address of each instruction being executed/analysed.
The error message lists the return address computed from the eh_frame
tabels and the expected one, together with the IP at which the
mismatch is detected.

Notes
-----

The concrete view of the stack frame is built by:

- intercept CALL: a return address is pushed on the stack
- intercept RET: a return address is popped by the stack

The status of the calle-saved registers are built in their own way:
- RBP
  - intercept PUSH: a saved address is pushed on the stack
  - intercept POP: a saved address is "restored" on the stack
  - intercept RET: removes all restored addresses from the stack
  - intercept LEAVE: acts as a POP + RET for rbp

Attic
-----

- intercept PUSH imm(%rip), as in (from objdump -d /bin/true):

Disassembly of section .plt:

````
0000000000401030 <__uflow@plt-0x10>:
  401030:       ff 35 d2 4f 20 00       pushq  0x204fd2(%rip)        # 606008 <__ctype_b_loc@plt+0x204cd8>
  401036:       ff 25 d4 4f 20 00       jmpq   *0x204fd4(%rip)        # 606010 <__ctype_b_loc@plt+0x204ce0>
````

Csmith
------

```shell
mkdir tmp
cd tmp
export CFLAGS="-I/usr/include/csmith-*/ -w"
export PYTHONPATH=/path/to/pyelftools
../../util/csmith-batch.py ../csmith-test.sh
```
