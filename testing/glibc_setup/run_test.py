#!/usr/bin/env python3
import subprocess
import os
import sys
import gzip


def get_env():
    glibc_base = "glibc/build"
    python_base = None
    for pdir in os.scandir('../venv/lib/'):
        if pdir.name.startswith('python'):
            python_base = '{}/site-packages'.format(pdir.path)
    if not python_base:
        raise Exception("No virtualenv found in venv")

    out = {
        'LIB_PATH': (
            "{glibc}"
            + "{glibc}/math"
            + "{glibc}/elf"
            + "{glibc}/dlfcn"
            + "{glibc}/nss"
            + "{glibc}/nis"
            + "{glibc}/rt"
            + "{glibc}/resolv"
            + "{glibc}/crypt"
            + "{glibc}/mathvec"
            + "{glibc}/support"
            + "{glibc}/nptl").format(glibc=glibc_base),
        'GCONV_PATH': '{}/iconvdata'.format(glibc_base),
        'LOCPATH': '{}/localedata'.format(glibc_base),
        'LC_ALL': 'C',
        'PYTHONPATH': '{}:{}'.format(os.getenv('PYTHON_PATH', ''),
                                     python_base),
    }
    return out


def run_single(test_file,
               output_file=None,
               timeout=600,  # seconds = 10min
               compress=False,
               keep_on_success=False):
    """ Run a single test file.

    If `output_file` is None, the output of the program are printed directly;
    else, it is redirected to the given file.

    If `timeout` is not 0, the program is killed after `timeout` seconds and
    the run is considered failed.

    If `compress` is True, the output file is gzipped after the run.

    If `keep_on_success` is False, the output file is deleted if the run ends
    up successfully.
    """

    def last_line(s):
        ''' Returns the last line of `s` '''
        s = s.strip()
        last_split = s.rfind('\n')
        return s[last_split+1:]

    def save_output(content):
        if not output_file or not content:
            return
        if not os.path.isdir(os.path.dirname(output_file)):
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
        output_path = output_file + ('.gz' if compress else '')
        with (gzip.open if compress else open)(output_path, 'w') as handle:
            handle.write(content)

    def upon_failure(result):
        print("FAILED (exit code {}) test {}{}".format(result.returncode,
                                                       test_file,
                                                       output_file_descr),
              file=sys.stderr)
        save_output(result.stdout)


    output_file_descr = ''
    if output_file:
        output_file_descr = (
            " (results saved in {}{})".format(output_file,
                                              '.gz' if compress else ''))


    args = ['gdb', '-q', '-x', 'gdb_instr', test_file]
    env = get_env()

    try:
        output = subprocess.run(
            args,
            timeout=timeout if timeout != 0 else None,
            stdout=subprocess.PIPE if output_file else None,
            stderr=subprocess.STDOUT if output_file else None,
            check=True,
            env=env,
        )

        if output_file is not None:
            if last_line(output.stdout.decode('utf-8')).find('Aborting') != -1:
                upon_failure(output)
                return 1
            elif keep_on_success:
                save_output(output.stdout)
        return 0

    except subprocess.TimeoutExpired as exn:
        print("TIMEOUT ({}s) test {}{}".format(timeout,
                                               test_file,
                                               output_file_descr),
              file=sys.stderr)
        save_output(exn.stdout)
        return 2
    except subprocess.CalledProcessError as exn:
        upon_failure(exn)
        return 3


if __name__ == '__main__':
    argv = sys.argv
    test_file = argv[1]
    output_dir = argv[2] if len(argv) > 2 else None
    if not test_file.startswith('glibc'):
        test_file = 'glibc/build/{}'.format(test_file)

    if output_dir:
        output_path = os.path.join(
            output_dir,
            test_file[len('glibc/build/'):],  # FIXME Not robust at all…
        )
    else:
        output_path = None

    sys.exit(
        run_single(test_file,
                   output_file=output_path,
                   compress=True))
