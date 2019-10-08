import os
import sys
from itertools import accumulate
from collections import defaultdict

DEBUG = True

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
        return f"{name} {self.offset} {self.arg if self.arg else ''}"


def cleanup(source):
    return "".join(filter(lambda x: x in instruction_opcode_map.keys(), source))


def parse(source):
    code = cleanup(source)
    loop_starts = []
    opcodes = []
    size = len(code)

    pc = 0  # Instruction pointer
    mptr = 0  # Pointer to memory

    while pc < size:
        opcode = instr_to_opcode(code[pc])

        if opcode in [OP_OPEN_JMP, OP_CLOSE_JMP]:
            if opcode == OP_OPEN_JMP:
                # If we get a loop start, record this to be popped
                loop_starts.append(len(opcodes))
                # Our jmp arg will be filled in when encountering the next
                # CLOSE_JMP
                opcodes.append(Opcode(OP_OPEN_JMP))

            elif opcode == OP_CLOSE_JMP:
                if not len(loop_starts):
                    raise RuntimeError("Unmatched ']' found")
                loop_start = loop_starts.pop()
                loop_end = len(opcodes)
                opcodes[loop_start].arg = loop_end

                opcodes.append(Opcode(OP_CLOSE_JMP, offset=mptr, arg=loop_start))

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


def evaluate(opcodes, data_input=None, buffer_output=True):

    stdin = None
    if data_input != None:
        stdin = list(reversed(data_input))

    # memory = bytearray(30000)
    memory = defaultdict(int)
    size = len(opcodes)
    out_buffer = []

    pc, mptr = 0, 0

    syswrite = sys.stdout.write
    sysflush = sys.stdout.flush

    def write_stdout(c):
        syswrite(c)
        sysflush()

    def write_buffer(c):
        out_buffer.append(c)

    def read_stdin():
        return os.read(0, 1)

    def read_buffer():
        try:
            read_in = stdin.pop()
        except:
            return ""

        return read_in

    do_write = write_buffer if buffer_output else write_stdout
    do_read = read_stdin if stdin == None else read_buffer

    while pc < size:

        op = opcodes[pc]

        if op.op == OP_ADD:
            mptr += op.offset
            memory[mptr] = (memory[mptr] + op.arg) % 256

        elif op.op == OP_SUB:
            mptr += op.offset
            memory[mptr] = (memory[mptr] - op.arg) % 256

        elif op.op == OP_OPEN_JMP:
            if op.offset != 0:
                print("Whoops")
            mptr += op.offset  # should be 0 for now
            if memory[mptr] == 0:
                pc = op.arg

        elif op.op == OP_CLOSE_JMP:
            if op.offset != 0:
                print("Whoops")
            mptr += op.offset  # should be 0 for now
            if memory[mptr] != 0:
                pc = op.arg - 1  # - 1?

        elif op.op == OP_OUT:
            mptr += op.offset
            do_write(chr(memory[mptr]))

        elif op.op == OP_IN:
            mptr += op.offset
            ch = do_read()
            if len(ch) > 0 and ord(ch) > 0:
                memory[mptr] = ord(ch)

        if(DEBUG):
            print(f"*op={op}\n* pc={pc}\n* dataptr={mptr}\n* Memory locations:")

            for k, v in memory.items():
                print(f"\t\t*{k}: {v}")

            print("\n")
        pc += 1

    return "".join(out_buffer) if buffer_output == True else None


with open("examples/test.bf", "r") as f:
    x = f.read()
    src = parse(x)
    print([x.__str__() for x in src])
    print(evaluate(src))
