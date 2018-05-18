#!/usr/bin/env python3
import subprocess
import os
import sys
import gzip
import threading


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

    def upon_failure(result):
        print("FAILED (exit code {}) test {}{}".format(result.returncode,
                                                       test_file,
                                                       output_file_descr),
              file=sys.stderr)

    def run_with_outfile(outfile):
        if not os.path.isdir(os.path.dirname(output_file)):
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
        output_path = output_file + ('.gz' if compress else '')
        result = -1
        with (gzip.open if compress else open)(output_path, 'w') as handle:
            result = do_run(lambda line:
                            handle.write(line.strip().encode('utf-8') + b'\n'))

        if result == 0 and not keep_on_success:
            os.remove(output_path)

        return result

    def run_without_outfile():
        return do_run(lambda line: print(line.strip()))

    output_file_descr = ''
    if output_file:
        output_file_descr = (
            " (results saved in {}{})".format(output_file,
                                              '.gz' if compress else ''))


    args = ['gdb', '-q', '-x', 'gdb_instr', test_file]
    env = get_env()

    had_timeout = False

    def upon_timeout(process):
        nonlocal had_timeout
        if process.poll() is None:
            try:
                process.kill()
                had_timeout = True
            except:
                pass  # Terminated in-between (race condition)

    def gen_replication_command():
        ''' Generates the exact command line to input to replicate this run '''
        def escape_arg(arg):
            if ' ' in arg:
                arg = "'{}'".format(arg.replace("'", r"\'"))
            return arg
        command = ' '.join(list(map(escape_arg, args)))

        env_list = []
        for env_var in env:
            env_list.append('{}={}'.format(env_var, env[env_var]))

        return '{} {}'.format(' '.join(env_list), command)

    def do_run(line_action):
        nonlocal had_timeout
        try:
            line_action("## Running command:")
            line_action("##    {}".format(gen_replication_command()))
            line_action("")

            process = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,  # Force non-interactive mode
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                env=env,
            )

            if timeout != 0:
                timer = threading.Timer(timeout, upon_timeout, [process])
                timer.start()
            else:
                timer = None

            has_failed = False
            for out_line in iter(process.stdout.readline, ''):
                line_action(out_line)
                if out_line.find('Aborting') != -1:
                    has_failed = True

            process.stdout.close()
            rc = process.wait()
            if timer:
                timer.cancel()

            if had_timeout:
                print("TIMEOUT ({}s) test {}{}".format(timeout,
                                                       test_file,
                                                       output_file_descr),
                      file=sys.stderr)
                return 2
            elif has_failed:
                upon_failure(process)
                return 1
            elif rc != 0:
                upon_failure(process)
                return 3
            return 0

        except subprocess.CalledProcessError as exn:
            upon_failure(exn)
            return 3

    if output_file:
        return run_with_outfile(output_file)
    else:
        return run_without_outfile()


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
