# glibc_setup for eh_frame_check

Running `eh_frame_check.py` over the whole glibc testsuite.

## Dependencies

To run those scripts, you will need

* A recent `gdb`, compiled with **python 3** support
* `virtualenv`
* `git`
* some time ahead of you (it will compile stuff)

## How to run

On the first run, setup everything (this may take some time — we're compiling
glibc and its whole testsuite here):

```bash
  ./setup_env.sh
```

Then, for every subsequent run, you will have to source the virtualenv:

```bash
  source ../venv/bin/activate
```

You may then either run a single test,

```bash
  make glibc/build/math/test-misc.test  # Or any other glibc test path
```

or run the whole testsuite

```bash
  make -j10
```

or even run a single directory of the whole testsuite

```bash
  TESTS_DIR=glibc/build/math make -j10
```

In any case, if any error occurred, the run log will be in the corresponding
directory in `outputs/`. You can parametrize this by passing through the
environment an `OUTPUT_DIR` variable.
