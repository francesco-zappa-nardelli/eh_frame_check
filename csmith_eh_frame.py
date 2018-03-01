#!/usr/bin/env python3
from subprocess import call

class InvalidTestException(Exception):
    pass

class MismatchException(Exception):
    pass

no_test = 0


def generate():
    print('  Generating...')
    with open('/dev/null') as outfile:
        if call(["csmith", "--ccomp", "--no-checksum", "--no-argc",
                       "--max-funcs", "20", "--max-expr-complexity", "10",
                       "-o", "csmith_file.c"], stdout=outfile) != 0:
            raise InvalidTestException()
#    call(["sed", "-i '/platform/s/^/ \/\/ /'",  "csmith_file.c"])


def gcccompile():
    opts = "-O1"
    print('  Compiling... ', opts )
    with open('/dev/null') as outfile:
        if call(["gcc", opts,
                    "-I", "/home/zappanar/repos/zappa/compiler_testing/csmith_with_locks/runtime",
                    "-o", "csmith_file", "csmith_file.c"], stdout=outfile, stderr=outfile) != 0:
            raise InvalidTestException()

        
def terminates():
    print('  Terminates...')
    with open('/dev/null') as outfile:
        if call(["timeout", "1", "./csmith_file"], stdout=outfile) == 124:
            print('  ...does not terminate')
            raise InvalidTestException()



def test():
    print('  Validating...')
    logname = 'csmith_file.log.'+str(no_test)
    with open(logname, "w") as logfile:
        if call(["gdb", "-q", "-x", "/home/zappanar/repos/eh_frame_check/eh_frame_check.py",
                        "csmith_file"], stdout=logfile) != 0:
            print('VALIDATION RETURNED NOT ZERO')

    if call(["grep", "Mismatch", logname]) == 0:
        print('FOUND A MISMATCH')
        raise MismatchException()


def clean():
    pass


if __name__=="__main__":
    while True:
        no_test = no_test+1;
        try:
            print('TEST NO: ', no_test)
            generate()
            gcccompile()
            terminates()
            test()
        except InvalidTestException as e:
            print('EXCEPTION')
            clean()
        except MismatchException as e:
            print('MISMATCH')
            break
        
            
            
# for (( ; ; ))
# do
#     NOTEST=`expr $NOTEST + 1`
#     echo "TEST NO: $NOTEST"
#     echo "  Generating..."
#     csmith --ccomp --no-checksum --no-argc --max-funcs 20 --max-expr-complexity 10 -o csmith_file.c
#     sed -i '/platform/s/^/ \/\/ /' csmith_file.c

#     echo "  Compiling..."
#     #ccomp -O -fstruct-passing -fbitfields -I /home/zappa/source/cmmtest/csmith-locks-bin/include/csmith-2.1.0/ -o csmith_file csmith_file.c # > /dev/null 2>&1

#     gcc -O1 -I /home/zappa/source/cmmtest/csmith-locks-bin/include/csmith-2.1.0/ -o csmith_file csmith_file.c > /dev/null 

#     echo "  Testing termination..."
#     timeout 1 ./csmith_file
#     if [ $? -eq 124 ]; then
#             echo "... doesn't terminate."
#             NOTEST=`expr $NOTEST - 1`
#     else
#         logfile="csmith_file.log.$NOTEST" 
#         echo "  Testing... $logfile"
#         /home/zappa/source/gdb-py27/bin/gdb -q -x /home/zappa/repos/zappa/dwarf/src-fzn/eh_frame_check.py csmith_file > $logfile
#         grep "Mismatch" $logfile
#         greprc=$?
#         if [[ $greprc -eq 0 ]] ; 
#         then
#             echo "Found a mismatch."
#             break
#         fi
#     fi
# done
