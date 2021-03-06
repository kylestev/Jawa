# -*- coding: utf8 -*-
__all__ = ('Label', 'assemble')
from collections import namedtuple

from jawa.constants import Constant
from jawa.util.bytecode import *


Label = namedtuple('Label', ['name'])


def assemble(code):
    """
    A convienience method for 'assembling' bytecode over the regular
    :meth:`~jawa.attributes.code.CodeAttribute.assemble()` method with
    support for labels and direct constants.
    """
    final = []

    # We need to make three passes, because we cannot know the offset for
    # jump labels until after we've figured out the PC for each instructions,
    # which is complicated by the variable-width instructions set and
    # alignment padding.
    for line in code:
        if isinstance(line, Label):
            final.append(line)
            continue

        mnemonic, operands = line[0], line[1:]
        operand_fmts = definition_from_mnemonic(mnemonic)[1]

        # We need to coerce each opcodes operands into their
        # final `Operand` form.
        final_operands = []
        for i, operand in enumerate(operands):
            if isinstance(operand, Operand):
                # Already in Operand form.
                final_operands.append(operand)
            elif isinstance(operand, Constant):
                # Convert constants into CONSTANT_INDEX'es
                final_operands.append(Operand(
                    OperandTypes.CONSTANT_INDEX,
                    operand.index
                ))
            elif isinstance(operand, dict):
                    # lookupswitch's operand is a dict as
                # a special usability case.
                final_operands.append(operand)
            elif isinstance(operand, Label):
                final_operands.append(operand)
            else:
                # For anything else, lookup that opcode's operand
                # type from its definition.
                final_operands.append(Operand(
                    operand_fmts[i][1],
                    operand
                ))

        # Build the final, immutable `Instruction`.
        final.append(Instruction.from_mnemonic(
            mnemonic,
            operands=final_operands
        ))

    label_pcs = {}

    # The second pass, find the absolute PC for each label.
    current_pc = 0
    for ins in final:
        if isinstance(ins, Label):
            label_pcs[ins.name] = current_pc
            continue

        # size_on_disk must know the current pc because of alignment on
        # tableswitch and lookupswitch.
        current_pc += ins.size_on_disk(current_pc)

    # The third pass, now that we know where each label is we can figure
    # out the offset for each jump.
    current_pc = 0
    offset = lambda l: Operand(40, label_pcs[l.name] - current_pc)

    for ins in final:
        if isinstance(ins, Label):
            continue

        for i, operand in enumerate(ins.operands):
            if isinstance(operand, dict):
                # lookupswitch is a special case
                for k, v in operand.items():
                    if isinstance(v, Label):
                        operand[k] = offset(v)
            elif isinstance(operand, Label):
                ins.operands[i] = offset(operand)

        current_pc += ins.size_on_disk(current_pc)

        yield ins
