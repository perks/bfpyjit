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
    OP_CLEAR: "clear"
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
        return f"{name} {self.offset} {self.arg if self.arg else ''}"

    def __repr__(self):
        name = opcode_to_string(self.op)
        return f" * op={name}\n * offset={self.offset}\n * arg={self.arg}"

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

        if opcode == OP_OPEN_JMP:

            # Let's look for OP_CLEAR loops
            if pc < (size - 3): # [+] or [-] need to be able to do +3
                clear_instruction = code[pc:pc+3]
                if clear_instruction in ["[+]", "[-]"]:
                    opcodes.append(Opcode(OP_CLEAR, offset=mptr))
                    pc += 3
                    mptr = 0
                    continue # continue since 


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

    # We can optimize OP_CLEAR followed by OP_ADD or OP_SUB, let's coallesce these nodes
    # into a single OP_CLEAR that uses the arg as the default store value
    #

    _i = 0
    _opcodes = []
    while _i < len(opcodes) - 1:
        current = opcodes[_i]
        nxt = opcodes[_i + 1]
        if current == OP_CLEAR and (nxt == OP_ADD or nxt == OP_SUB):
            current.arg += nxt.arg
            _i += 2 # skip our nxt since it was coallesced
        else:
            _i += 1 # go pairwise next

        _opcodes.append(current)

    # opcodes = _opcodes

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
            if op.arg == 0:
                memory[mptr] = 0
            # Coallesced clears
            elif op.arg < 0:
                memory[mptr] = (memory[mptr] - op.arg) % 256
            elif op.arg > 0:
                memory[mptr] = (memory[mptr] + op.arg) % 256

        if(DEBUG):
            print(f"*op={op}\n* pc={pc}\n* dataptr={mptr}\n* Memory locations:")

            for k, v in memory.items():
                print(f"\t\t*{k}: {v}")

            print("\n")
        pc += 1

    return "".join(out_buffer) if buffer_output == True else None

def main():
    if len(sys.argv) == 2:
        with open(sys.argv[1], 'r') as f:
            opcodes = parse(f.read())
            buffer = evaluate(opcodes, buffer_output=False)
            print(buffer)
    else:
        print("Usage:", sys.argv[0], "filename")


if __name__ == "__main__":
    main()

