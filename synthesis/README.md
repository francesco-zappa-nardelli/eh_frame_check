# synthesis

Generate debug frame information from ORC.

Dependencies:
* GCC
* `objtool` from the Linux kernel tree
* [`dareog`](https://github.com/emersion/dareog)
* [`pyelftools`](https://github.com/eliben/pyelftools)
* [Csmith](https://embed.cs.utah.edu/csmith/) (optional)
* [C-Reduce](https://embed.cs.utah.edu/creduce/) (optional)

Usage:

```shell
./check.sh test.c
```

(You can set `CC`, `OBJTOOL` and `DAREOG` environment variables to paths to
these tools)

Example Csmith usage:

```shell
mkdir tmp
cd tmp
export CFLAGS="-I/usr/include/csmith-*/ -w"
export PYTHONPATH=/path/to/pyelftools
../../util/csmith-batch.py ../csmith-test.sh
```

## License

MIT
