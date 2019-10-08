import os
import sys
from itertools import accumulate

"""
+----+-------+---------------------+
| BF |  IR   |          C          |
+----+-------+---------------------+
| +  | Add   | mem[p]++;           |
| -  | Sub   | mem[p]--;           |
| >  | Right | p++;                |
| <  | Left  | p--;                |
| .  | Out   | putchar(mem[p]);    |
| ,  | In    | mem[p] = getchar(); |
| [  | Open  | while(mem[p]) {     |
| ]  | Close | }                   |
+----+-------+---------------------+
"""


OP_ADD = 0
OP_SUB = 1
OP_RIGHT = 2
OP_LEFT = 3
OP_OUT = 4
OP_IN = 5
OP_OPEN_JMP = 6
OP_CLOSE_JMP = 7

# Used to naively go from BF -> IR type
instruction_opcode_map = {
    "+": OP_ADD,
    "-": OP_SUB,
    ">": OP_RIGHT,
    "<": OP_LEFT,
    ".": OP_OUT,
    ",": OP_IN,
    "[": OP_OPEN_JMP,
    "]": OP_CLOSE_JMP,
}

# Used to lookup IR code for the opcode
opcode_name_map = {
    OP_ADD: "add",
    OP_SUB: "sub",
    OP_RIGHT: "right",
    OP_LEFT: "left",
    OP_OUT: "out",
    OP_IN: "in",
    OP_OPEN_JMP: "openjmp",
    OP_CLOSE_JMP: "closejmp",
}


def instr_to_opcode(instr_char):
    return instruction_opcode_map[instr_char]


def opcode_to_string(opcode_num):
    return opcode_name_map[opcode_num]


def _get_repeated_count(source, start):
    repeats = 0
    match = source[start]
    for char in source[start + 1 :]:
        if match == char:
            repeats += 1
            match = char
        else:
            break

    return repeats


class Opcode(object):
    """
    IR that the interpreter will execute/optimize bytecode for
    """

    def __init__(self, op, offset=0, arg=None):
        self.op = op
        self.offset = offset
        self.arg = arg

    def __str__(self):
        name = opcode_to_string(self.op)
        return (
            f"{name} {self.offset} {self.arg if self.arg else ''}"
        )


def cleanup(source):
    return "".join(filter(lambda x: x in instruction_opcode_map.keys(), source))


def buildbracemap(code):
    temp_bracestack, bracemap = [], {}

    for position, command in enumerate(code):
        if command == "[":
            temp_bracestack.append(position)
        if command == "]":
            start = temp_bracestack.pop()
            bracemap[start] = position
            bracemap[position] = start
    return bracemap


def parse(source):
    code = cleanup(source)
    jmp_table = buildbracemap(code)
    opcodes = []
    size = len(code)

    pc = 0  # Instruction pointer
    mptr = 0  # Pointer to memory

    while pc < size:
        opcode = instr_to_opcode(code[pc])

        if opcode in [OP_OPEN_JMP, OP_CLOSE_JMP]:
            _arg = jmp_table[pc] if pc in jmp_table else None
            opcodes.append(Opcode(opcode, offset=0, arg=_arg))
        elif opcode in [OP_IN, OP_OUT]:
            opcodes.append(Opcode(opcode, offset=mptr))
        # Handles the OP_RIGHT/OP_LEFT and OP_ADD/OP_SUB
        # Which are just coallescing optimizations
        else:
            repeats = _get_repeated_count(code, pc)
            # If we are just moving, we can encode this into the offset directly
            # for other opcodes, no need to gen opcodes
            if opcode == OP_LEFT:
                mptr -= repeats + 1
            elif opcode == OP_RIGHT:
                mptr += repeats + 1
            # Generate the
            else:
                opcodes.append(Opcode(opcode, offset=mptr, arg=repeats + 1))
                mptr = 0
            pc += repeats

        pc += 1

    return opcodes


with open('examples/test.bf', 'r') as f:
    x = f.read()
    src = parse(x)
    print([x.__str__() for x in src])



