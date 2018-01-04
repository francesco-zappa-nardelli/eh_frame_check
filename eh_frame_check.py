#                       eh_frame_check.py
#
#     Francesco Zappa Nardelli, Parkas project, INRIA Paris
#
# Copyright 2016
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
# 3. The names of the authors may not be used to endorse or promote
# products derived from this software without specific prior written
# permission.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHORS ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE
# GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
# IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import sys
import re
import traceback

import cProfile

# Options
verbose = True
dbg_eval = False

# Setup pyelftools
#sys.path[0:0] = ['/home/zappa/repos/zappa/dwarf/src-fzn/pyelftools/']
sys.path.insert(1, '/home/zappa/repos/zappa/dwarf/src-fzn/pyelftools/')

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection
from elftools.elf.descriptions import describe_symbol_type

from elftools.dwarf.callframe import CIE, FDE, RegisterRule
from elftools.common.py3compat import (
    ifilter, bytes2str )
from elftools.dwarf.descriptions import (
    describe_reg_name, describe_attr_value, set_global_machine_arch,
    describe_CFI_instructions, describe_CFI_register_rule,
    describe_CFI_CFA_rule, describe_DWARF_expr
    )
from elftools.dwarf.dwarf_expr import GenericExprVisitor

sys.path.insert(1, '/home/zappa/repos/zappa/dwarf/src-fzn/pyelftools/scripts')
from intervaltree import Interval, IntervalTree

ARCH = '<unknown>'

def pyelftools_init():
    global ARCH
    # This should be fixed in get_machine_arch
    if ARCH == '<unknown>':
        ARCH = 'power'
    set_global_machine_arch(ARCH) 

# Aux functions
def abort():
    print ('Aborting...')
    gdb_execute ('quit')

def error(e):
    print ("\n*** Error")
    for l in e.split('\n'):
        print (" * " + l)
    abort()

# Output
def debug_eval(s):
    if dbg_eval:
        print (s)

def emit(s):
    if verbose:
        sys.stdout.write(str(s))

def emitline(s=''):
    if verbose:
        sys.stdout.write(str(s).rstrip() + '\n')

def format_hex(addr, fieldsize=None, fullhex=False, lead0x=True, alternate=False):
    """ Format an address into a hexadecimal string.

    fieldsize:
      Size of the hexadecimal field (with leading zeros to fit the
      address into. For example with fieldsize=8, the format will
      be %08x
      If None, the minimal required field size will be used.

    fullhex:
      If True, override fieldsize to set it to the maximal size
      needed for the elfclass

    lead0x:
      If True, leading 0x is added

    alternate:
      If True, override lead0x to emulate the alternate
      hexadecimal form specified in format string with the #
      character: only non-zero values are prefixed with 0x.
      This form is used by readelf.
    """
    if alternate:
        if addr == 0:
            lead0x = False
        else:
            lead0x = True
            fieldsize -= 2

    s = '0x' if lead0x else ''
    if fullhex:
        fieldsize = 16  # FIXME 8 if self.elffile.elfclass == 32 else 16
    if fieldsize is None:
        field = '%x'
    else:
        field = '%' + '0%sx' % fieldsize
    return s + field % addr

def dump_eh_frame_table_entry(entry):
    """ dumps an interpreted EH_CFI entry
    """ 
    if isinstance(entry, CIE):
        emitline('\n%08x %s %s CIE "%s" cf=%d df=%d ra=%d' % (
            entry.offset,
            format_hex(entry['length'], fullhex=True, lead0x=False),
            format_hex(entry['CIE_id'], fullhex=True, lead0x=False),
            bytes2str(entry['augmentation']),
            entry['code_alignment_factor'],
            entry['data_alignment_factor'],
            entry['return_address_register']))
        ra_regnum = entry['return_address_register']
    else: # FDE
        emitline('\n%08x %s %s FDE cie=%08x pc=%s..%s' % (
            entry.offset,
            format_hex(entry['length'], fullhex=True, lead0x=False),
            format_hex(entry['CIE_pointer'], fullhex=True, lead0x=False),
            entry.cie.offset,
            format_hex(entry['initial_location'], fullhex=True, lead0x=False),
            format_hex(entry['initial_location'] + entry['address_range'],
                             fullhex=True, lead0x=False)))
        ra_regnum = entry.cie['return_address_register']
        
    # Print the heading row for the decoded table
    emit('   LOC')
    emit('  ' if entry.structs.address_size == 4 else '          ')
    emit(' CFA      ')
        
    # Decode the table nad look at the registers it describes.
    # We build reg_order here to match readelf's order. In particular,
    # registers are sorted by their number, and the register matching
    # ra_regnum is always listed last with a special heading.
    decoded_table = entry.get_decoded()
        
    # print ("\n\nDecoded table:\n"+(str(decoded_table))+"\n\n")

    reg_order = sorted(ifilter(
        lambda r: r != ra_regnum,
        decoded_table.reg_order))
    if len(decoded_table.reg_order):
            
        # Headings for the registers
        for regnum in reg_order:
            emit('%-6s' % describe_reg_name(regnum))
        emitline('ra      ')

        # Now include ra_regnum in reg_order to print its values similarly
        # to the other registers.
        reg_order.append(ra_regnum)
    else:
        emitline()
                
    for line in decoded_table.table:
        emit(format_hex(line['pc'], fullhex=True, lead0x=False))
        emit(' %-9s' % describe_CFI_CFA_rule(line['cfa']))
                    
        for regnum in reg_order:
            if regnum in line:
                s = describe_CFI_register_rule(line[regnum])
            else:
                s = 'u'
            emit('%-6s' % s)
        emitline()
    emitline()

# def dump_eh_frame_line(line, reg_order):
#     emit(format_hex(line['pc'], fullhex=True, lead0x=False))
#     emit(' %-9s' % describe_CFI_CFA_rule(line['cfa']))
                    
#     for regnum in reg_order:
#         if regnum in line:
#             s = describe_CFI_register_rule(line[regnum])
#         else:
#             s = 'u'
#             emit('%-6s' % s)


def dump_eh_frame_table(dwarfinfo):
    for entry in dwarfinfo.EH_CFI_entries():
        dump_eh_frame_table_entry(entry)

def memorize_eh_frame_table_entry(eh_frame_table, entry):
    decoded_entry = entry.get_decoded()

    for line, next_line in zip(decoded_entry.table, decoded_entry.table[1:]+[None]):
        base = line['pc']
        if next_line != None:
            top = next_line['pc']
        else:
            top = entry['initial_location'] + entry['address_range']
        eh_frame_table[base:top] = (line, 
                                    (decoded_entry.reg_order, 
                                     entry.cie['return_address_register']))

def memorize_eh_frame_table(dwarfinfo):
    eh_frame_table = IntervalTree()

    for entry in dwarfinfo.EH_CFI_entries():
        if isinstance(entry, FDE):
            memorize_eh_frame_table_entry(eh_frame_table, entry)

    return eh_frame_table

def search_eh_frame_table(eh_frame_table, address):
    try:
        return eh_frame_table[address].pop().data
    except:
        return None

def read_eh_frame_table(elffile):
    """ return the decoded eh_frame_table
    """
    if not elffile.has_eh_frame_info():
        error ('No eh_frame table in the binary: '+ filename) 
    dwarfinfo = elffile.get_dwarf_info()
    return dwarfinfo

def memorize_symbol_table(elffile, symbol_table, file_name, base=0):
    if file_name in symbol_table['files']:
        return
        
    for section in elffile.iter_sections():
        if not isinstance(section, SymbolTableSection):
            continue
            
        if section['sh_entsize'] == 0:
            emit("Symbol table '%s' has a sh_entsize of zero." % (section.name))
            continue

        for symbol in section.iter_symbols():
             if describe_symbol_type(symbol['st_info']['type']) == 'FUNC':
                start = symbol['st_value']+base
                end = symbol['st_value']+symbol['st_size']+base
                if end != start:
                    symbol_table['table'][start:end] = symbol.name 

    symbol_table['files'].append(file_name)
        
def dump_symbol_table(symbol_table):
    print "*** dump symbol table"
    for f in symbol_table['files']:
        print (" :: "+f)
    for s in sorted(symbol_table['table']):
        print (" {0}-{1}: {2}".format(hex(s.begin), hex(s.end), s.data))
    

def get_function_name(symbol_table, linked_files, ip):
    # print ("* looking for "+hex(ip))
    try:
        return symbol_table['table'][ip].pop().data
    except:
        try:
            lib_name = linked_files[ip].pop().data
            if lib_name in symbol_table['files']:
                return '_unknown @ [{0}]'.format(lib_name)
            
            lib_base = linked_files[ip].pop().begin
            print ("* loading symbol table for {0} at {1} ".format(lib_name, hex(lib_base)))
            with open(lib_name, 'rb') as f:
#                print "* opened"
                elffile = ELFFile(f)
#                print "* got the elfile"
                memorize_symbol_table(elffile, symbol_table, lib_name, lib_base)
#                print "* memorization done"
#            print "* file closed"
#             dump_symbol_table(symbol_table)
            try:
                return symbol_table[ip].pop().data
            except:
                return '_unknown @ [{0}]'.format(lib_name)
        
        except:
            return '_unknown @ [???]'

        
def get_function_name_OLD(symbol_table, linked_files, ip):
    try:
        return symbol_table[ip].pop().data
    except:
        try:
            lib_name = linked_files[ip].pop().data
            return '_unknown @ '+lib_name
        except:
            return '_unknown @ [???]'
            
    


# arch specific

def reg_sp():
    if ARCH == 'x64':
        return '$rsp'
    elif ARCH == 'x86':
        return '$esp'
    elif ARCH == 'power':
        return '$r1'
    else:
        error("unsupported arch in reg_sp")

def reg_ip():
    if ARCH == 'x64':
        return '$rip'
    elif ARCH == 'x86':
        return '$eip'
    elif ARCH == 'power':
        return '$pc'
    else:
        error("unsupported arch in reg_ip")
    
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
        
def gdb_current_file():
    str = (gdb_execute('info file')).split('\n',1)[0]
    return str[str.find('"')+1:str.rfind('"')]

def gdb_dyn_linked_files():
    """ Return the list of dynamically linked files, and relative PC addresses.
        Must be invoked after gdb_goto_main
    """
    linked_files = IntervalTree()
    
    lines = gdb_execute('info file').split('\n')
    for l in lines:
        try:
            words = l.split()
            linked_files[int(words[0],16):int(words[2],16)] = words[6]
        except:
            pass

    return linked_files
            
def gdb_get_ip():
    return long(gdb.parse_and_eval(reg_ip()))

def gdb_get_instruction():
    i = gdb_execute("x/i "+reg_ip())
    c = (i[i.index(':')+1:]).split()

    if c[0] == 'repz':
        c.remove('repz')

    try:
        return c[0],c[1]
    except IndexError:
        return c[0], ''

def gdb_get_sp():
    # r = reg_sp()
    # v = gdb.parse_and_eval(r)
    # print ("r: {0} , v: {1}".format(r,v))
    # return v
    return gdb.parse_and_eval(reg_sp())

def gdb_get_reg_num(regnum):
    regname = describe_reg_name(regnum)
    value = gdb.parse_and_eval("$"+regname)
    return long(value)

def gdb_get_reg(reg):
    value = gdb.parse_and_eval("$"+reg)
    return long(value)


# interpreter of Dwarf expressions
def eval_reg(reg):
    r = gdb.parse_and_eval('$'+describe_reg_name(reg))
    debug_eval (describe_reg_name(reg) + " : " + str(r))
    return r

_DWARF_EXPR_EVAL_CACHE = {}

def eval_expr(structs, expr):
    debug_eval(describe_DWARF_expr(expr, structs))

    cache_key = id(structs)
    if cache_key not in _DWARF_EXPR_EVAL_CACHE:
        _DWARF_EXPR_EVAL_CACHE[cache_key] = ExprEval(structs)
    dwarf_expr_eval = _DWARF_EXPR_EVAL_CACHE[cache_key]
    dwarf_expr_eval.clear()
    dwarf_expr_eval.process_expr(expr)
    return dwarf_expr_eval.get_value()

class ExprEval(GenericExprVisitor):
    """ A concrete visitor for DWARF expressions that computes a Dwarf
        expression given the current register / memory

        Usage: after creation, call process_expr, and then get_value
    """
    def __init__(self, structs):
        super(ExprEval, self).__init__(structs)
        self._init_lookups()
        self._value_parts = []
        self._stack = [] 

    def clear(self):
        self._value_parts = []

    def get_value(self):
        debug_eval ("Expr debug: " + repr(self._value_parts))
        self._dump_stack()
        return self._stack.pop()

    def _init_lookups(self):
        self._ops_with_decimal_arg = set([
            'DW_OP_const1u', 'DW_OP_const1s', 'DW_OP_const2u', 'DW_OP_const2s',
            'DW_OP_const4u', 'DW_OP_const4s', 'DW_OP_constu', 'DW_OP_consts',
            'DW_OP_pick', 'DW_OP_plus_uconst', 'DW_OP_bra', 'DW_OP_skip',
            'DW_OP_fbreg', 'DW_OP_piece', 'DW_OP_deref_size',
            'DW_OP_xderef_size', 'DW_OP_regx',])

        for n in range(0, 32):
            self._ops_with_decimal_arg.add('DW_OP_breg%s' % n)

        self._ops_with_two_decimal_args = set([
            'DW_OP_const8u', 'DW_OP_const8s', 'DW_OP_bregx', 'DW_OP_bit_piece'])

        self._ops_with_hex_arg = set(
            ['DW_OP_addr', 'DW_OP_call2', 'DW_OP_call4', 'DW_OP_call_ref'])

    def _after_visit(self, opcode, opcode_name, args):
        self._value_parts.append(self._eval(opcode, opcode_name, args))

    def _dump_stack(self):
        debug_eval ("STACK")
        for e in self._stack:
            debug_eval (" | "+format_hex(e))
        debug_eval ("----")

    def _eval(self, opcode, opcode_name, args):
        self._dump_stack()
        if len(args) == 0:
            if opcode_name.startswith('DW_OP_reg'):
                regnum = int(opcode_name[9:])
                return '%s (%s)' % (
                    opcode_name,
                    describe_reg_name(regnum))
            elif opcode_name.startswith('DW_OP_lit'):
                v = int(opcode_name[9:])
                self._stack.append(v)
                debug_eval (' * debug lit: {0}'.format(v))
                return "(I)"+opcode_name             
            # binary ops   
            elif opcode_name.startswith('DW_OP_plus'):
                v1 = self._stack.pop()
                v2 = self._stack.pop()
                debug_eval (' * debug plus v1: {0}; v2 {1}; {2}'.format(v1,v2,v1+v2))
                self._stack.append(v1 + v2)
                return "(I)"+opcode_name                                
            elif opcode_name.startswith('DW_OP_and'):
                v1 = self._stack.pop()
                v2 = self._stack.pop()
                v= v2 & v1
                self._stack.append(v)
                debug_eval (' * debug and v1: {0}; v2 {1}; {2}'.format(v1,v2,v))
                return "(I)"+opcode_name                                
            elif opcode_name.startswith('DW_OP_shl'):
                v1 = self._stack.pop()
                v2 = self._stack.pop()
                v= v2 << v1
                self._stack.append(v)
                debug_eval (' * debug shl v1: {0}; v2 {1}; {2}'.format(v1,v2,v))
                return "(I)"+opcode_name                                
            # comparison
            elif opcode_name.startswith('DW_OP_ge'):
                v1 = self._stack.pop()
                v2 = self._stack.pop()
                v = 1 if v2 >= v1 else 0
                self._stack.append(v)
                debug_eval (' * debug ge v1: {0}; v2 {1}; {2}'.format(v1,v2,v))
                return "(I)"+opcode_name                                
            else:
                return opcode_name
        elif opcode_name in self._ops_with_decimal_arg:
            if opcode_name.startswith('DW_OP_breg'):
                regnum = int(opcode_name[10:])
#                s = gdb_execute ("x/g $"+describe_reg_name(regnum)
#                                 +"+"+str(args[0]))
#                v = int(s[s.find(':')+1:],16)
                v = gdb_get_reg_num(regnum) + args[0]
                debug_eval (' * debug breg '+(describe_reg_name(regnum))+" : "+format_hex(v))
                self._stack.append(v)
                return '(I)%s (%s): %s' % (
                    opcode_name,
                    describe_reg_name(regnum),
                    args[0])
            elif opcode_name.endswith('regx'):
                # applies to both regx and bregx
                return '%s: %s (%s)' % (
                    opcode_name,
                    args[0],
                    describe_reg_name(args[0]))
            else:
                error ("unimplemented opcode in expr")
                return '%s: %s' % (opcode_name, args[0])
        elif opcode_name in self._ops_with_hex_arg:
            error ("unimplemented opcode in expr")
            return '%s: %x' % (opcode_name, args[0])
        elif opcode_name in self._ops_with_two_decimal_args:
            error ("unimplemented opcode in expr")
            return '%s: %s %s' % (opcode_name, args[0], args[1])
        else:
            error ("unknown opcode in expr")
            return '<unknown %s>' % opcode_name

def eval_CFARule(structs, cfa_rule):
    debug_eval ("eval CFA: " + repr(cfa_rule))

    if cfa_rule.expr == None:
        return eval_reg(cfa_rule.reg) + cfa_rule.offset
    else:
        return eval_expr(structs, cfa_rule.expr)

def eval_RegisterRule(structs, rule, cfa_rule):
    assert (isinstance(rule, RegisterRule))

    debug_eval ("\neval RR: "+repr(rule)+" -- CFA: "+ repr(cfa_rule))

    if rule.type == RegisterRule.OFFSET:
        return eval_CFARule(structs, cfa_rule) + rule.arg
    elif rule.type == RegisterRule.UNDEFINED:
        return None
    else:
        error ("eval_RegisterRule, unimplemented")

# instruction parsing
def x86_extract_registers(s):
    try:
      return s[s.index('(')+1:s.index(')')]
    except:
      return ''

def power_extract_registers(s):
    try:
        rs = s.split(',')
        r1 = rs[0]
        try:
            rs1 = rs[1]
            off = long(rs1[:rs1.index('(')])
            r2 = rs1[rs1.index('(')+1:rs1.index(')')]
        except:
            off = None
            r2 = rs[1]
    except:
        r1 = s
        off = None
        r2 = None
    return {'r1':r1, 'off':off, 'r2':r2}

# validation (limited to ra for now)
class X86_Status:
    def __init__(self, sp):
        self._ra_at = int(str(sp),16)
        self._ra_stack = [-1]
        self._after_push_rip_count = 0
        self._after_push_rip = False

    def __str__(self):
        s1 = (str(map(lambda x: format_hex(x), self._ra_stack))).strip('[]')
        return '['+s1+', \''+format_hex(self._ra_at)+'\']'

    def get_ra(self):
        if self._after_push_rip:
            return self._ra_stack[len(self._ra_stack)-1]
        return self._ra_at

    def push_ra(self,new_sp):
        self._ra_stack.append(self._ra_at)
        self._ra_at = int(str(new_sp),16)

    def pop_ra(self):
        self._ra_at = self._ra_stack.pop()

    def set_after_push_rip(self):
        self._after_push_rip_count = 1
        self._after_push_rip = True

    def reset_after_push_rip(self):
        if self._after_push_rip_count == 0:
            self._after_push_rip = False
        self._after_push_rip_count = self._after_push_rip_count - 1

class Power_Status:
    def __init__(self):
        self._ra_at = 'lr'

    def __str__(self):
        return '[ ra_at: ' + str(self._ra_at) + ' ]'

    def get_ra(self):
        return self._ra_at

    # FIXME : merge the updates?
    def update_ra_reg(self,reg):
        self._ra_at = reg

    def update_ra_addr(self,addr):
        self._ra_at = addr

def validate(structs, entry, regs_info, status):
    reg_order, ra_regnum = regs_info

    try:
        ra_eh_frame = eval_RegisterRule(structs, entry[ra_regnum], entry['cfa'])
    except:
        ra_eh_frame = None

    if ra_eh_frame == None:
        # CFA is undefined in the eh_frame_table
        return True

    ra_status = status.get_ra()

    # print ("\n  => RA: eh_frame = "+format_hex(ra_eh_frame))
    # print ("  => RA: status   = "+format_hex(ra_status))

    if ra_eh_frame != ra_status:
        print ("\n ---------------------------------- ")
        print (" | RA: eh_frame = "+format_hex(ra_eh_frame))
        print (" | RA: status   = "+format_hex(ra_status))

    return ra_eh_frame == ra_status

    
# main
def main():
    global ARCH
    
    try:
        gdb_check_and_init()
        symbol_table = IntervalTree()

        current_file = gdb_current_file()

        symbol_table = { 'table': IntervalTree(), 'files': [] }

        with open(current_file, 'rb') as f:
            elffile = ELFFile(f)
            ARCH = elffile.get_machine_arch()
            memorize_symbol_table(elffile, symbol_table, current_file)
            dump_symbol_table(symbol_table)
            dwarfinfo = read_eh_frame_table(elffile) 
            eh_frame_table = memorize_eh_frame_table(dwarfinfo)

        pyelftools_init()

        # dump_eh_frame_table(dwarfinfo)

        # go to main
        gdb_goto_main()

        linked_files = gdb_dyn_linked_files()
        print "linked files"
        for f in linked_files:
            print("{0}-{1}: {2}".format(hex(f.begin), hex(f.end), f.data))
        print "end linked files"
        
        if ARCH=='x64' or ARCH=='x86':
            status = X86_Status(gdb_get_sp())
        elif ARCH=='power':
            status = Power_Status()
        else:
            error ("ARCH not specified: supported arch are x64, x86, and power")

        emitline ("INIT: "+ str(status))
 
        # work
        while True:

            current_ip = gdb_get_ip() 
            current_function = get_function_name(symbol_table,
                                                 linked_files, current_ip)
            current_instruction = gdb_get_instruction()
            emit ("=> %s [%s] (%s %s)" % (format_hex(current_ip), 
                                          current_function,
                                          current_instruction[0],
                                          current_instruction[1]))

            current_eh = search_eh_frame_table(eh_frame_table, current_ip)

            if current_eh != None:
                current_eh_frame_entry, regs_info = current_eh

                # emit ("\n  => from %s\n" % format_hex(current_eh_frame_entry['pc']))
                # print (repr(current_eh))

                if not(validate(dwarfinfo.structs, current_eh_frame_entry, 
                                regs_info, status)):
                    print (" | Table Mismatch at IP: "+format_hex(current_ip))
                    print (" | eh_frame entry from : "+format_hex(current_eh_frame_entry['pc']) + ' : ' + repr(current_eh))
                    abort()

                emitline ()
            else:
                emitline ("  [SKIPPED]")

            current_opcode = current_instruction[0]

            if ARCH == 'x64' or ARCH == 'x86':
                if current_opcode[:4] == "call":
                    status.push_ra(gdb_get_sp()-8)
                    emitline ("CALL: "+ str(status))

                elif current_opcode[:3] == "ret":
                    status.pop_ra()
                    emitline ("RET: "+ str(status))
                    if status.get_ra() == -1:
                        break

                elif current_opcode[:4] == "push":
                    regs = x86_extract_registers(current_instruction[1])
                    if regs == "%rip":
                        status.push_ra(gdb_get_sp()-8)
                        status.set_after_push_rip()
                        emitline ("PUSH (%rip): "+ str(status))

                status.reset_after_push_rip()

            elif ARCH == 'power':
                if current_opcode == "mflr":
                    regs = power_extract_registers(current_instruction[1])
                    status.update_ra_reg(regs['r1'])
                    emitline ("MFLR: "+ str(status))

                elif current_opcode == "stw":
                    regs = power_extract_registers(current_instruction[1])
                    if (regs['r2'] == 'r1') and (regs['r1'] == status.get_ra()):
                        status.update_ra_addr(gdb_get_reg(regs['r2'])+regs['off'])
                        emitline ("STW: "+ str(status))


            gdb_execute("stepi")

        print ("Completed: "+current_file)    
        gdb_execute('quit')
    except: 
        error ("Unexpected error\n\n" + traceback.format_exc())

if __name__ == '__main__':
    main() 
   # cProfile.run('main()','profile.log')
