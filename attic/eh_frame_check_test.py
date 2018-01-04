import sys
import re

# Setup pyelftools
sys.path[0:0] = ['pyelftools/']
from elftools.elf.elffile import ELFFile
from elftools.dwarf.callframe import CIE, FDE
from elftools.common.py3compat import (
    ifilter, bytes2str )
from elftools.dwarf.descriptions import (
    describe_reg_name, describe_attr_value, set_global_machine_arch,
    describe_CFI_instructions, describe_CFI_register_rule,
    describe_CFI_CFA_rule,
    )


# Output
def emit(s):
    sys.stdout.write(str(s))

def emitline(s=''):
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

def dump_eh_frame_table(entry):
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


def read_eh_frame_table(filename):
    """ return the decoded eh_frame_table
    """
    print('Processing file:', filename)
    with open(filename, 'rb') as f:
        elffile = ELFFile(f)

        if not elffile.has_eh_frame_info():
            print ('no eh_frame table') 
        
        dwarfinfo = elffile.get_dwarf_info()
        
        for entry in dwarfinfo.EH_CFI_entries():
#            decoded_table = entry.get_decoded()
            dump_eh_frame_table(entry)
            
#            print ("\n\nDecoded table:\n\n"+(str(decoded_table))+"\n\n")


# gdb interaction
def current_file():
    str = (gdb.execute('info file', True, True)).split('\n',1)[0]
    return str[str.find('"')+1:str.rfind('"')]

# main
if __name__ == '__main__':
    current_file = sys.argv[1]
    print (current_file)
    read_eh_frame_table(current_file)

