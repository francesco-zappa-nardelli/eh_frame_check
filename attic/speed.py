import sys

# gdb interaction
def gdb_check_and_init():
    "eh_frame_check requires a gdb linked to Python 2"
    if sys.version_info[0] == 3:
        error ("GDB with Python 2 is required.\n" +
               "Recipe: dowload gdb from http://ftp.gnu.org/gnu/gdb/.\n" +
               "./configure --prefix /usr/local/gdb-python2 --with-python\n" +
               "make; make install")
    gdb_execute('set confirm off')
    gdb_execute('set height unlimited')
    gdb_execute('set pagination off')

def gdb_execute(s, sl=[]):
    """ Execute one or more GDB commands.  
        Returns the output of the last one.
    """ 
    str = gdb.execute(s, True, True)
    if sl == []:
        return str
    else:
        for s in sl:
            str = gdb.execute(s, True, True)
        return str

def gdb_goto_main():
    try:
        gdb_execute('break *main+0', ['run'])
    except:
        info_file = gdb_execute('info file').split('\n')
        entry_point_s = next(l for l in info_file if "Entry point" in l)
        entry_point = long(entry_point_s[entry_point_s.find(':')+1:],16)
        gdb_execute('break *'+format_hex(entry_point), ['run'])
        dis_libc_init = gdb_execute('x/14i $pc')
        main_addr = None
        for l in dis_libc_init.split('\n'):
            if 'libc_start_main' in l:
                main_addr = (((pl.split())[2]).split(',')[0]).lstrip('$')
            pl = l
        if main_addr == None:
            error ("gdb_goto_main, cannot determine the address of main")
        gdb_execute('break *'+main_addr, ['cont'])

def current_file():
    str = (gdb_execute('info file')).split('\n',1)[0]
    return str[str.find('"')+1:str.rfind('"')]

# main
if __name__ == '__main__':
    gdb_check_and_init()
    current_file = current_file()
    gdb_goto_main()
    
    i = 0
    while True:
        if i==1000:
            print ("=> "+ str(i))
            gdb_execute("quit")
        i = i+1
        gdb_execute("stepi")
