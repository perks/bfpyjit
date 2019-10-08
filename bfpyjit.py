import os
import sys

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


class Opcode(object):
    """
    IR that the interpreter will execute/optimize bytecode for
    """

    def __init__(self, op, value=0, jmp=None):
        self.op = op
        self.value = value
        self.jmp = jmp

    def __str__(self):
        return f"{opcode_name_map[self.op]} {self.value} {self.jmp if self.jmp else ''}"

x = Opcode(OP_OUT)
print(x)


