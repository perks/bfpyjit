import os
import sys
from itertools import accumulate
from collections import defaultdict

DEBUG = False

"""
Translations of native BF instructions -> High Level IR
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


# Define constants at beginning so we can use them elsewhere
OP_ADD = 0
OP_SUB = 1
OP_RIGHT = 2
OP_LEFT = 3
OP_OUT = 4
OP_IN = 5
OP_OPEN_JMP = 6
OP_CLOSE_JMP = 7
OP_MOVE = 8
OP_CLEAR = 9
OP_COPY = 10
OP_SCANR = 11
OP_SCANL = 12

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
    OP_MOVE: "move",
    OP_CLEAR: "clear",
    OP_COPY: "copy",
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

    def __init__(self, op, offset=0, arg=0):
        self.op = op
        self.offset = offset
        self.arg = arg

    def __str__(self):
        name = opcode_to_string(self.op)
        return f"{name} {self.offset} {self.arg}"

    def __repr__(self):
        name = opcode_to_string(self.op)
        return f" * op={name}\n * offset={self.offset}\n * arg={self.arg}"


def cleanup(source):
    return "".join(filter(lambda x: x in instruction_opcode_map.keys(), source))


def _is_clearloop(code, size, index, mptr):
    """
    Detects a clear loop and returns equivalent opcodes
    """

    if index < (size - 3):
        clr = code[index : index + 3]
        if clr == "[+]" or clr == "[-]":
            return [Opcode(OP_CLEAR, mptr)], 3

    return [], 0


def _is_scanloop(code, size, index, mptr):
    """
    Detects a scan loop and returns equivalent opcodes
    """

    if index < (size - 3):
        clr = code[index : index + 3]

        if clr == "[>]":
            return [Opcode(OP_SCANR, mptr)], 3

        elif clr == "[<]":
            return [Opcode(OP_SCANL, mptr)], 3

    return [], 0


def _is_copyloop(code, size, index, mptr):
    # Copy/multiply loop must start with a decrement
    if (index > (size - 6)) or (code[index + 1] != "-"):
        return [], 0

    mult = 0
    depth = 0
    mults = {}
    i = index + 2

    # Consume the loop contents until the cell pointer movement changes
    # direction. Keep track of pointer movement, and the number of increments
    # at each cell, so we can create Opcodes to recreate the copy / multiply
    # operations performed by the loop
    while i < size:
        if code[i] in "><":
            if mult > 0:
                mults[depth] = mult
                mult = 0

            if code[i] == "<":
                break

            depth += 1

        elif code[i] == "+":
            mult += 1

        else:
            return [], 0

        i += 1

    # If no cell or pointer increments by now, this isn't a copy/multiply loop
    if (len(mults) == 0) or (depth == 0) or (i == (size - 1)):
        return [], 0

    ret = [Opcode(OP_COPY, mptr, mults)]

    # Consume all the pointer decrements until the end of the loop.
    # If we encounter any non-"<" characters in the loop at this stage,
    # this isn't a copy/multiply loop (at least, not one I want to mess with!)
    while (i < size) and (code[i] != "]"):
        if code[i] != "<":
            return [], 0

        depth -= 1
        i += 1

    if (depth != 0) or (i == (size - 1)):
        return [], 0

    return ret, (i - index) + 1


def run_loop_optimizers(code, size, index, mptr):
    loop_opts = [_is_clearloop, _is_copyloop, _is_scanloop]

    for opt in loop_opts:
        optcode_list, n_instructions = opt(code, size, index, mptr)
        if n_instructions > 0:
            return optcode_list, n_instructions

    return [], 0


def parse(source):
    code = cleanup(source)
    loop_starts = []
    opcodes = []
    size = len(code)

    pc = 0  # Instruction pointer
    mptr = 0  # Pointer to memory

    while pc < size:
        opcode = instr_to_opcode(code[pc])

        if opcode == OP_OPEN_JMP:

            optcode_list, n_instructions = run_loop_optimizers(code, size, pc, mptr)
            if n_instructions > 0:
                opcodes.extend(optcode_list)
                pc += n_instructions
                mptr = 0
                continue

            # If we are doing a loop to increment/decrement our memory ptr we
            # can replace this with a OP_MOVE
            if mptr != 0:
                opcodes.append(Opcode(OP_MOVE, 0, mptr))
                mptr = 0
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
            mptr = 0

        elif opcode in [OP_IN, OP_OUT]:
            opcodes.append(Opcode(opcode, offset=mptr))
            mptr = 0

        # Handles the OP_RIGHT/OP_LEFT and OP_ADD/OP_SUB
        # Which are just coallescing optimizations
        # Note: We don't need to create OP_RIGHT/OP_LEFT because we can just track them
        # onto our OP_ADD and OP_SUB codes
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

    if len(loop_starts):
        raise RuntimeError("Umatched '[' found")

    return opcodes


def evaluate(opcodes, data_input=None, buffer_output=True):

    stdin = None
    if data_input != None:
        stdin = list(reversed(data_input))

    memory = bytearray(30000)
    # memory = defaultdict(int)
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

        if op.op == OP_MOVE:
            mptr += op.arg

        elif op.op == OP_ADD:
            mptr += op.offset
            memory[mptr] = (memory[mptr] + op.arg) % 256

        elif op.op == OP_SUB:
            mptr += op.offset
            memory[mptr] = (memory[mptr] - op.arg) % 256

        elif op.op == OP_OPEN_JMP:
            mptr += op.offset
            if memory[mptr] == 0:
                pc = op.arg

        elif op.op == OP_CLOSE_JMP:
            mptr += op.offset
            if memory[mptr] != 0:
                pc = op.arg - 1

        elif op.op == OP_OUT:
            mptr += op.offset
            do_write(chr(memory[mptr]))

        elif op.op == OP_IN:
            mptr += op.offset
            ch = do_read()
            if len(ch) > 0 and ord(ch) > 0:
                memory[mptr] = ord(ch)

        elif op.op == OP_CLEAR:
            mptr += op.offset
            memory[mptr] = 0

        elif op.op == OP_COPY:
            mptr += op.offset
            if memory[mptr] > 0:
                for offset in op.arg:
                    idx = mptr + offset
                    memory[idx] = (memory[idx] + (memory[mptr] * op.arg[offset])) % 256
                memory[mptr] = 0

        elif op.op == OP_SCANR:
            mptr += op.offset
            while mptr > 0 and memory[mptr] != 1:
                mptr -= 1

        elif op.op == OP_SCANL:
            mptr += op.offset
            while mptr < (size - 1) and memory[mptr] != 0:
                mptr += 1

        if DEBUG:
            print(f"*op={op}\n* pc={pc}\n* dataptr={mptr}\n* Memory locations:")

            for k, v in memory.items():
                print(f"\t\t*{k}: {v}")

            print("\n")
        pc += 1

    return "".join(out_buffer) if buffer_output == True else None


def main():
    if len(sys.argv) == 2:
        with open(sys.argv[1], "r") as f:
            opcodes = parse(f.read())
            for op in opcodes:
                print(op)
            buffer = evaluate(opcodes, buffer_output=False)
    else:
        print("Usage:", sys.argv[0], "filename")


if __name__ == "__main__":
    main()
