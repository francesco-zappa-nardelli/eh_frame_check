#!/usr/bin/env python

import operator
import argparse
from elftools.elf.elffile import ELFFile
from elftools.dwarf.descriptions import (
    set_global_machine_arch,
    describe_CFI_register_rule,
    describe_CFI_CFA_rule,
)
from elftools.dwarf.callframe import FDE, CFARule, RegisterRule

parser = argparse.ArgumentParser()
parser.add_argument('--strict', help='enable strict mode', action='store_true')
parser.add_argument('--verbose', help='enable verbose mode', action='store_true')
parser.add_argument('--cfa', help='compare CFA when not used by register rules', action='store_true')
parser.add_argument('files', nargs='+')

args = parser.parse_args()
strict = args.strict
verbose = args.verbose
check_cfa = args.cfa
filenames = args.files

def compare_CFI_CFA_rule(a, b):
    return a.reg == b.reg and a.offset == b.offset and a.expr == b.expr

def compare_CFI_register_rule(a, b):
    if not strict and (a.type == 'UNDEFINED' or b.type == 'UNDEFINED'):
        return True
    return a.type == b.type and a.arg == b.arg

elf_files = [ELFFile(open(filename, 'rb')) for filename in filenames]

machine_arch = None
for elf_file in elf_files:
    arch = elf_file.get_machine_arch()
    if machine_arch is None:
        machine_arch = arch
    elif machine_arch != arch:
        raise "Cannot compare ELF files with different machine architectures"
set_global_machine_arch(machine_arch)

# TODO: optimize dwarf_tables data type
dwarf_tables = []
pcs = set()
for elf_file in elf_files:
    if not elf_file.has_dwarf_info():
        raise "ELF file is missing DWARF info"

    dwarf_info = elf_file.get_dwarf_info()
    dwarf_table = {}
    cfi_entries = None
    if dwarf_info.has_EH_CFI():
        cfi_entries = dwarf_info.EH_CFI_entries()
    # TODO: .debug_frame
    if cfi_entries is None:
        raise "ELF file is missing CFI entries"

    # TODO: sorted insertion
    dwarf_table = []
    for entry in cfi_entries:
        if isinstance(entry, FDE):
            decoded_table = entry.get_decoded()
            for line in decoded_table.table:
                line['reg_order'] = decoded_table.reg_order
                dwarf_table.append(line)
                pcs.add(line['pc'])
    dwarf_table = sorted(dwarf_table, key=lambda line: line['pc'])

    dwarf_tables.append(dwarf_table)

pcs = sorted(pcs)

mismatched = False
for pc in pcs:
    if verbose:
        print("pc=%x" % pc)

    ref_line = {}
    ref_filenames = {}
    for i, dwarf_table in enumerate(dwarf_tables):
        filename = filenames[i]

        line = None
        while len(dwarf_table) > 0:
            line = dwarf_table[0]
            if line['pc'] > pc:
                line = None
                break
            if len(dwarf_table) < 2:
                break
            next_line = dwarf_table[1]
            if next_line['pc'] > pc:
                break
            dwarf_table.pop(0)
        if line is None:
            continue

        cfa_ok = True
        if verbose:
            print("%s cfa=%s" % (filename, describe_CFI_CFA_rule(line['cfa'])))
        if 'cfa' not in ref_line:
            ref_line['cfa'] = line['cfa']
            ref_filenames['cfa'] = filename
        else:
            cfa_ok = compare_CFI_CFA_rule(ref_line['cfa'], line['cfa'])

        needs_cfa = False
        for reg_num in line['reg_order']:
            reg_rule = line.get(reg_num, RegisterRule(RegisterRule.UNDEFINED))
            if reg_num not in ref_line:
                ref_line[reg_num] = reg_rule
                ref_filenames[reg_num] = filename
            else:
                # TODO: more precise criteria
                needs_cfa = reg_rule.type != RegisterRule.UNDEFINED
                if not compare_CFI_register_rule(ref_line[reg_num], reg_rule):
                    print("Register rule mismatch at pc=0x%x: %s (in %s) vs %s (in %s)" % (
                        pc,
                        describe_CFI_register_rule(ref_line[reg_num]),
                        ref_filenames[reg_num],
                        describe_CFI_register_rule(reg_rule),
                        filename,
                    ))
                    mismatched = True

        if not cfa_ok and (check_cfa or needs_cfa):
            print("CFA rule mismatch at pc=0x%x: %s (in %s) vs %s (in %s)" % (
                pc,
                describe_CFI_CFA_rule(ref_line['cfa']),
                ref_filenames['cfa'],
                describe_CFI_CFA_rule(line['cfa']),
                filename,
            ))
            mismatched = True

if mismatched:
    exit(1)
else:
    print("All green.")
