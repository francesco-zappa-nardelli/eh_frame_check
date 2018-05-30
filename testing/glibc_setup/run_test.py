#!/usr/bin/env python3
import argparse
import subprocess
import os
import sys
import gzip
import threading


class KeepPolicy:
    """ Carries what log files are kept after a run """
    def __init__(self, on_success=False, on_timeout=False):
        self.on_success = on_success
        self.on_timeout = on_timeout


def get_env():
    glibc_base = "glibc/build"
    python_base = None
    for pdir in os.scandir('../venv/lib/'):
        if pdir.name.startswith('python'):
            python_base = '{}/site-packages'.format(pdir.path)
    if not python_base:
        raise Exception("No virtualenv found in venv")

    lib_path_list = [
        "{glibc}",
        "{glibc}/math",
        "{glibc}/elf",
        "{glibc}/dlfcn",
        "{glibc}/nss",
        "{glibc}/nis",
        "{glibc}/rt",
        "{glibc}/resolv",
        "{glibc}/crypt",
        "{glibc}/mathvec",
        "{glibc}/support",
        "{glibc}/nptl",
    ]

    out = {
        'LIB_PATH': ':'.join(lib_path_list).format(glibc=glibc_base),
        # ^^^ No idea what this does, but it was present in the original
        # `make test` glibc Makefile. Kept in doubt.
        'GCONV_PATH': '{}/iconvdata'.format(glibc_base),
        'LOCPATH': '{}/localedata'.format(glibc_base),
        'LC_ALL': 'C',
        'PYTHONPATH': '{}:{}'.format(os.getenv('PYTHON_PATH', ''),
                                     python_base),
    }
    return out


def run_single(test_file,
               output_dir=None,
               output_file=None,
               timeout=600,  # seconds = 10min
               compress=False,
               keep_policy=None):
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
        def suffix_gz_path(path):
            return path + ('.gz' if compress else '')

        def open_file(path, compress):
            if compress:
                return gzip.open(path, 'w')
            return open(path, 'bw')

        if not os.path.isdir(os.path.dirname(outfile)):
            os.makedirs(os.path.dirname(outfile), exist_ok=True)
        output_path = suffix_gz_path(outfile)
        result = -1
        with open_file(output_path, compress) as handle:
            result = do_run(lambda line:
                            handle.write(line.strip().encode('utf-8') + b'\n'))

        do_remove = False
        if result == 0 and not keep_policy.on_success:
            do_remove = True
        elif result == 2:  # Timeout
            if keep_policy.on_timeout:
                os.rename(output_path, suffix_gz_path(outfile + '.timeout'))
            else:
                do_remove = True

        if do_remove:
            os.remove(output_path)

        return result

    def run_without_outfile():
        return do_run(lambda line: print(line.strip()))

    if keep_policy is None:
        keep_policy = KeepPolicy()

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


def parse_args():
    ''' parse command-line arguments '''
    parser = argparse.ArgumentParser(
        description="Painlessly run a test case from the glibc test suite",
    )

    parser.add_argument('--timeout', default='600',
                        help=("Timeout duration, in seconds, before the "
                              "process gets killed. 0 for no timeout."))
    parser.add_argument('--keep-on-success', action='store_true',
                        help=("Keep the log file of runs that exited "
                              "successfully."))
    parser.add_argument('--keep-on-timeout', action='store_true',
                        help=("Keep the log file of runs that exited with a "
                              "timeout."))
    parser.add_argument('--keep-all', action='store_true',
                        help=("Keep the log file of all runs (timeout, "
                              "error, success). By default, only errors are "
                              "kept."))

    parser.add_argument('--no-compress', '-Z', action='store_false',
                        dest='compress',
                        help=("Do not gzip the log files (default: gzip)"))

    parser.add_argument('--output', '-o', default=None,
                        help=("Output directory for the log file. If omitted, "
                              "the output is directly printed on the standard "
                              "output."))
    parser.add_argument('test_file', metavar='test path',
                        help=("The file to be run. The prefix `glibc/build` "
                              "can be safely omitted."))

    return parser.parse_args()


def main():
    ''' Main function, called upon script invocation '''
    args = parse_args()

    test_file = args.test_file
    output_dir = args.output
    if not test_file.startswith('glibc'):
        test_file = 'glibc/build/{}'.format(test_file)

    if output_dir:
        output_path = os.path.join(
            output_dir,
            test_file[len('glibc/build/'):],  # FIXME Not robust at all…
        )
    else:
        output_path = None

    keep = KeepPolicy(
        on_success=args.keep_on_success or args.keep_all,
        on_timeout=args.keep_on_timeout or args.keep_all,
    )

    sys.exit(
        run_single(test_file,
                   output_dir=output_dir,
                   output_file=output_path,
                   timeout=int(args.timeout),
                   keep_policy=keep,
                   compress=args.compress)
    )


if __name__ == '__main__':
    main()
