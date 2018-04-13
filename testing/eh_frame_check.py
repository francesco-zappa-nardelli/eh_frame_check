#                       eh_frame_check.py
#
#     Francesco Zappa Nardelli, Parkas project, INRIA Paris
#
# Copyright 2016-2018
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
from copy import copy
import traceback
import functools
import signal

import cProfile

# Options
verbose = False
dbg_eval = False
cs_eval = False

# Setup pyelftools
# myPath = '/home/raph/Documents/TRAVAIL/X/Project/pyelftools/'
myPath = '/home/zappanar/repos/pyelftools.git/trunk'
#sys.path[0:0] = ['/home/zappa/repos/zappa/dwarf/src-fzn/pyelftools/']
sys.path.insert(1, myPath)

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

# using std intervaltree and storagecontainers

ITPath = '/home/zappanar/source/intervaltree-2.1.0'
SCPath = '/home/zappanar/source/sortedcontainers-1.5.9'
sys.path.insert(1, ITPath)
sys.path.insert(1, SCPath)
from intervaltree import Interval, IntervalTree

ARCH = '<unknown>'

def cs_eval_func(default_return=None):
    """ A function returning None that should be executed iff `cs_eval`

    If `cs_eval` is False, the function will return `default_return` instead of
    executing the wrapped function.
    """

    def wrapper(fct):
        @functools.wraps(fct)
        def wrapping(*args, **kwargs):
            global cs_eval
            if not cs_eval:
                return default_return
            return fct(*args, **kwargs)
        return wrapping
    return wrapper

def cs_eval_effect(func):
    ''' Same as `cs_eval_func`, but returns None '''
    return cs_eval_func()(func)

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
    return s + field % int(addr)

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
    if not elffile.get_section_by_name('.eh_frame'):
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
    print ("*** dump symbol table")
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
#                print ("* opened")
                elffile = ELFFile(f)
#                print ("* got the elfile")
                memorize_symbol_table(elffile, symbol_table, lib_name, lib_base)
#                print ("* memorization done")
#            print ("* file closed")
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
    if sys.version_info[0] > 3:
        error ("GDB with Python 2 or 3 is required.\n" +
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
    gdb_out = gdb.execute(s, True, True)
    if sl == []:
        return gdb_out
    else:
        for s in sl:
            gdb_out = gdb.execute(s, True, True)
        return gdb_out

def gdb_goto_main():
    try:
        gdb_execute('break *main+0', ['run'])
    except:
        info_file = gdb_execute('info file').split('\n')
        entry_point_s = next(l for l in info_file if "Entry point" in l)
        entry_point = int(entry_point_s[entry_point_s.find(':')+1:],16)
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
    return int(gdb.parse_and_eval(reg_ip()))

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
    return int(value)

def gdb_get_reg(reg):
    value = gdb.parse_and_eval("$"+reg)
    return int(value)


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
            off = int(rs1[:rs1.index('(')])
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

        # The registers RBX, RBP, RDI, RSI, RSP, R12, R13, R14, and R15 are considered nonvolatile (callee-saved).
        self._cs_list = ["rbx", "rbp", "rdi", "rsi", "rsp", "r12", "r13", "r14", "r15"]
        # a list of stack each one following one calle-saved register
        self._cs_stack = [[-1] for x in range(len(self._cs_list))]
        # Determines if a push or a pop is to be considered as a Callee-saved register
        #   save or restore operation
        # regname : (saved, saved_address, restored)
        # we consider the epilogue pop to be the one restoring the prologue pushed value
        self._cs_tracking_template = {
                'rbx': (False, 0x0, False),
                'rbp': (False, 0x0, False),
                'rdi': (False, 0x0, False),
                'rsi': (False, 0x0, False),
                'rsp': (False, 0x0, False),
                'r12': (False, 0x0, False),
                'r13': (False, 0x0, False),
                'r14': (False, 0x0, False),
                'r15': (False, 0x0, False),
        }

        self._cs_tracking = [
            copy(self._cs_tracking_template),
            copy(self._cs_tracking_template),
        ]
        # ^^^ Twice: we don't call main but return from it

    def __str__(self):
        s_ra = ""
        for i in self._ra_stack:
            s_ra = s_ra + '\'' + format_hex(i) + '\', '
        s_ra = '\n\tRA: ['+s_ra.strip('[]')+'\''+format_hex(self._ra_at)+'\']'

        res = "{}\n{}".format(s_ra, self._cs_tracking_strs())
        return res

    @cs_eval_func('')
    def _cs_tracking_strs(self):
        s_cs = "Calle-saved registers\n"
        i = 0
        # print(self._cs_stack)
        for stack in self._cs_stack:
            regname = self._index_to_name(i)
            s_reg_info = self._cs_tracking_str(regname)
            s_stack_cs = ""
            for e in stack:
                if e == 'u':
                    s_stack_cs = s_stack_cs + '\'u\', '
                else:
                    s_stack_cs = s_stack_cs + '\'' + format_hex(e) + '\', '
            s_reg_info += '\t{}: [{}]\n'.format(
                self._index_to_name(i),
                (s_stack_cs.strip('[]'))[:(len(s_stack_cs)-2)])
            s_cs = s_cs + s_reg_info
            i = i + 1
        return s_cs

    @cs_eval_func('')
    def _cs_tracking_str(self, regname):
        msg = '\t'
        msg += '    saved' if self._cs_tracking[-1][regname][0] else 'not saved'
        msg += ' @ :'
        msg += (
            'xxxxxxxxxxxxxx' if self._cs_tracking[-1][regname][1] == 0x0
            else str(self._cs_tracking[-1][regname][1]))
        msg += ('     restored' if self._cs_tracking[-1][regname][2]
                else ' not restored')
        return msg


    def _name_to_index(self, regname):
        switcher = {
            'rbx': 0,
            'rbp': 1,
            'rdi': 2,
            'rsi': 3,
            'rsp': 4,
            'r12': 5,
            'r13': 6,
            'r14': 7,
            'r15': 8,
        }
        return switcher.get(regname, "Invalid regname")

    def _index_to_name(self, index):
        return self._cs_list[index]

    def is_cs_reg(self, regname):
        return regname in self._cs_list

    # checks if it is the first save of the callee-saved register of the function
    #   (in the "prologue")
    @cs_eval_func(False)
    def _is_save_relevant(self, regname, address):
        if self._cs_tracking[-1][regname][0] == False:
            assert(self._cs_tracking[-1][regname][2] is False)
            tupl = (True, address, False)
            self._cs_tracking[-1][regname] = tupl
            return True
        return False

    # checks if it is a restore of a callee-saved register in the epilogue
    #   it does so by checking it restores the value saved in the prologue
    @cs_eval_func(False)
    def _is_restore_relevant(self, regname, address):
        if (self._cs_tracking[-1][regname][0]
                and self._cs_tracking[-1][regname][1] == address):
            assert(not self._cs_tracking[-1][regname[2]])

            tupl = (self._cs_tracking[-1][regname][0],  self._cs_tracking[-1][regname][1], True)
            self._cs_tracking[-1][regname] = tupl
            return True
        return False

    @cs_eval_func(False)
    def is_reg_restored(self, regname):
        return self._cs_tracking[-1][regname][2]

    @cs_eval_effect
    def reset_cs_tracking(self):
        ''' Upon entering a new function we must push a new cs_tracking frame
        to the cs_tracking stack, so that the first pushes will count as
        prologue. '''
        self._cs_tracking.append(self._cs_tracking_template)

    @cs_eval_effect
    def restore_cs_tracking(self):
        ''' restore a call frame after a return '''
        self._cs_tracking.pop()

    def get_ra(self):
        if self._after_push_rip:
            return self._ra_stack[len(self._ra_stack)-1]
        return self._ra_at

    def push_ra(self, new_sp):
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

    @cs_eval_func(-1)
    def get_cs(self, regname):
        index = self._name_to_index(regname)
        if len(self._cs_stack[index]) > 1:
            return self._cs_stack[index][-1]
        else:
            return -1

    @cs_eval_effect
    def push_cs(self, regname, new_addr):
        if self._is_save_relevant(regname, new_addr):
            index = self._name_to_index(regname)
            self._cs_stack[index].append(int(str(new_addr), 16))
            emitline('PUSH %'+regname+': ')
        else:
            emitline('[IGNORED] PUSH %'+regname+': ')

    @cs_eval_effect
    def pop_cs(self, regname):
        if self._is_restore_relevant(regname, int(str(gdb_get_sp()), 16)):
            index = self._name_to_index(regname)
            self._cs_stack[index][-1] = 'u'
            emitline('POP %'+regname+': ')
        else:
            emitline('[IGNORED] POP %'+regname+': ')

    @cs_eval_effect
    def restore_cs(self, regname):
        index = self._name_to_index(regname)
        self._cs_stack[index][-1] = 'u'

    @cs_eval_effect
    def purge_restored_cs(self):
        for i in range(len(self._cs_list)):
            self._cs_stack[i] = [x for x in self._cs_stack[i] if x != 'u']

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

@cs_eval_func(True)
def validate_cs_register(structs, entry, status, regnum, regname):
    cs_eh_frame = eval_RegisterRule(structs, entry[regnum], entry['cfa'])
    cs_status = status.get_cs(regname)

    if status.is_reg_restored(regname) and cs_status == 'u':
        return True

    # print ("\n  => CS: cs_eh_frame = "+format_hex(cs_eh_frame))
    # print (  "  => CS: cs_status   = "+ ('u' if cs_status == 'u' else format_hex(cs_status)))

    if cs_eh_frame != cs_status:
        print ("\n +----------------CS-CHECK----------------------")
        print (  " | register | cs_eh_frame       | cs_status     ")
        print (  " +----------+-------------------+---------------")
        print (  " | "+regname+"      | "+format_hex(cs_eh_frame)+"    | " + format_hex(cs_status))

    return cs_eh_frame == cs_status


@cs_eval_func(True)
def validate_cs_registers(structs, entry, regs_info, status):
    reg_order, ra_regnum = regs_info
    ### Called Saved registers check ###
    cs_check = {
        'rbx': True,
        'rbp': True,
        'rdi': True,
        'rsi': True,
        'rsp': True,
        'r12': True,
        'r13': True,
        'r14': True,
        'r15': True,
    }
    # for k, v in cs_check:
    #     validate_cs_register(structs, entry, ..., key)
    for regnum in reg_order:
        regname = describe_reg_name(regnum)
        try:
            cs_check[regname] = validate_cs_register(structs, entry, status, regnum, regname)
        except Exception as e:
            # print("exception: "+str(e))
            pass

    for k, v in cs_check.items():
        if not v:
            return False
    return True

def validate_ra(structs, entry, regs_info, status):
    reg_order, ra_regnum = regs_info

    try:
        ra_eh_frame = eval_RegisterRule(structs, entry[ra_regnum], entry['cfa'])
    except:
        # CFA is undefined in the eh_frame_table
        ra_eh_frame = None
        return True

    ra_status = status.get_ra()

    # print ("\n  => RA: eh_frame = "+format_hex(ra_eh_frame))
    # print (  "  => RA: status   = "+format_hex(ra_status))

    if ra_eh_frame != ra_status:
        print ("\n -------------------------------------- ")
        print (" | RA: eh_frame = "+format_hex(ra_eh_frame))
        print (" | RA: status   = "+format_hex(ra_status))

    return ra_eh_frame == ra_status


def validate(structs, entry, regs_info, status):
    cs_validation = validate_cs_registers(structs, entry, regs_info, status)
    ra_validation = validate_ra(structs, entry, regs_info, status)

    return ra_validation and cs_validation

def process_push(status, regname):
    if regname == 'rip':
        status.push_ra(gdb_get_sp()-8)
        status.set_after_push_rip()
        emitline("PUSH %rip: "+ str(status))
    elif status.is_cs_reg(regname):
        status.push_cs(regname, gdb_get_sp()-8)
        emitline(str(status))

def process_pop(status, regname):
    if status.is_cs_reg(regname):
        status.pop_cs(regname)
        emitline(str(status))

class MmapEntry:
    """ A line in the memory map of the process (where does the data at each
    position of the ELF comes from? Which shared library? etc.) """

    def __init__(self, beg, end, section, path, offset):
        self.beg = beg
        self.end = end
        self.section = section
        self.path = path
        self.offset = offset

    def translate(self, ip):
        return ip - self.beg + self.offset

    def __contains__(self, ip):
        return self.beg <= ip < self.end

class Mmap(list):
    """ The full memory map, holding individual memory map rows `MmapEntry` """

    def entry_for(self, ip):
        """ Find the memory map entry for this ip """

        def bisect(low, high):
            if low >= high:
                raise KeyError

            mid = (low + high) // 2
            mid_val = self[mid]

            if ip < mid_val.beg:
                return bisect(low, mid)
            elif ip in mid_val:
                return mid_val
            else:
                return bisect(mid+1, high)
        return bisect(0, len(self))


def get_mmap():
    """ Processes GDB's `info files` (the process' memory map) """

    def int_of_hex(x):
        assert(x[:2] == '0x')
        return int(x[2:], 16)

    infos = gdb.execute('info files', to_string=True)

    entries = Mmap()
    lines =  infos.split('\n')
    for line in lines:
        line = line.strip()
        words = line.split(' ')
        if len(words) < 5:
            continue
        if words[1] != '-' or words[3] != 'is':
            continue
        beg = int_of_hex(words[0])
        end = int_of_hex(words[2])
        sec = words[4]
        path = words[6] if len(words) >= 7 else 'here'
        offset = 0
        for pos in range(len(words)):
            if words[pos] == 'at':
                offset = int_of_hex(words[pos+1])

        entry = MmapEntry(
            beg,
            end,
            sec,
            path,
            offset)
        entries.append(entry)

    entries.sort(key=lambda x: x.beg)

    return entries

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
        print ("linked files")
        for f in linked_files:
            print("{0}-{1}: {2}".format(hex(f.begin), hex(f.end), f.data))
        print ("end linked files")

        if ARCH=='x64' or ARCH=='x86':
            status = X86_Status(gdb_get_sp())
        elif ARCH=='power':
            status = Power_Status()
        else:
            error ("ARCH not specified: supported arch are x64, x86, and power")

        emitline ("INIT: "+ str(status))

        mmap = get_mmap()

        # work
        while True:

            current_ip = gdb_get_ip()
            current_function = get_function_name(symbol_table,
                                                 linked_files, current_ip)
            current_instruction = gdb_get_instruction()
            try:
                mmap_entry = mmap.entry_for(current_ip)
            except KeyError:
                emitline("@@ Cannot get mapped region for {}"
                         .format(format_hex(current_ip)))

            emit ("=> %s (%s) [%s] (%s %s)"
                  % (format_hex(current_ip),
                     format_hex(mmap_entry.translate(current_ip)) or '',
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
                    print (" +----------------------------------------------")
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
                    status.reset_cs_tracking()
                    emitline ("CALL: "+ str(status))

                elif current_opcode[:3] == "ret":
                    status.pop_ra()
                    status.purge_restored_cs()
                    status.restore_cs_tracking()
                    emitline ("RET: "+ str(status))
                    if status.get_ra() == -1:
                        break

                elif current_opcode[:4] == "push":
                    process_push(status, current_instruction[1].strip('%'))

                elif current_opcode[:3] == "pop":
                    process_pop(status, current_instruction[1].strip('%'))

                elif current_opcode[:6] == "leaveq":
                    status.restore_cs('rbp')
                    emitline("LEAVEQ")

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


def print_usage():
    print("\n#### Usage ####")
    print("gdb -q -batch -ex 'py arg_verbose = True' -x eh_frame_check.py <testfile>")
    print("\n# Options:")
    print("#arg_verbose (False), arg_debug (False), arg_check_cs (True)")


def parse_options():
    global verbose
    global dbg_eval
    global cs_eval

    # FZN: if anybody knows of an alternative way to do this...
    try:
        if arg_verbose:
            verbose = True
        else:
            verbose = False
    except NameError:
        verbose = False

    try:
        if arg_debug:
            dbg_eval = True
        else:
            dbg_eval = False
    except NameError:
        dbg_eval = False

    try:
        if arg_check_cs:
            cs_eval = True
        else:
            cs_eval = False
    except NameError:
        cs_eval = True

    # for arg in sys.argv:
    #     if arg == "--check-cs":
    #         cs_eval = True
    #     elif arg == '--debug' or arg == '-d':
    #         dbg_eval = True
    #     elif arg =='--verbose' or arg == '-v':
    #         verbose = True
    #     elif arg == '--help' or arg == '-h':
    #         print_usage()
    #         quit()
    #     else:
    #         print ("Unknown option %s" % arg)


class Killer:
    def __init__(self):
        signal.signal(signal.SIGINT, self.do_quit)
        signal.signal(signal.SIGTERM, self.do_quit)

    def do_quit(self, sig, frame):
        print("Got kill signal {}".format(sig))
        abort()


if __name__ == '__main__':
    killer = Killer()
    try:
        gdb
    except NameError:
        print_usage()
        sys.exit("")

    parse_options()
    main()
   # cProfile.run('main()','profile.log')
