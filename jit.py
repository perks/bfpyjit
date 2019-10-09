import os
import sys
from itertools import accumulate
from collections import defaultdict

import llvmlite.binding as llvm
import llvmlite.ir as ll


def cleanup(source):
    return "".join(
        filter(lambda x: x in ["+", "-", "[", "]", ",", ".", "<", ">"], source)
    )


def execute(instructions):

    bit = ll.IntType(1)
    int8 = ll.IntType(8)
    int32 = ll.IntType(32)
    int64 = ll.IntType(64)
    int8ptr = int8.as_pointer()

    MEMORY_SIZE = 30000

    # Intialize LLVM
    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    # Create our function/entry_point
    module = ll.Module()
    function_type = ll.FunctionType(int32, [])
    function = ll.Function(module, function_type, name="bf_jit_exec")

    bb_entry = function.append_basic_block("entry")
    irb = ll.IRBuilder(bb_entry)

    # Initialize and declare our memory pointers
    memory = irb.alloca(int8, MEMORY_SIZE)
    dataptr_addr = irb.alloca(int32)

    memset = module.declare_intrinsic("llvm.memset", [int8ptr, int32])
    memcpy = module.declare_intrinsic("llvm.memcpy", [int8ptr, int8ptr, int32])

    # memset(ptr, val, size, align, isVolitile)
    # Might not need to 0 out stack but just in case
    irb.call(memset, [memory, int8(0), int32(MEMORY_SIZE), int32(1), bit(0)])
    # As per spec, this starts at 0
    irb.store(int32(0), dataptr_addr)


    syswrite = sys.stdout.write
    sysflush = sys.stdout.flush

    def write_stdout(c):
        syswrite(c)
        sysflush()

    def read_stdin():
        return os.read(0, 1)

    # We don't translate from opcode -> llvmir because we want to take advantage
    # of internal optimizations from LLVM
    #
    pc, size = 0, len(instructions)
    while pc < size:
        inst = instructions[pc]

        if inst == ">":
            dataptr = irb.load(dataptr_addr, "dataptr")
            inc_dataptr = irb.add(dataptr, int32(1), "inc_dataptr")
            irb.store(inc_dataptr, dataptr_addr)

        elif inst == "<":
            dataptr = irb.load(dataptr_addr, "dataptr")
            dec_dataptr = irb.sub(dataptr, int32(1), "dec_dataptr")
            irb.store(dec_dataptr, dataptr_addr)


        pc += 1


    irb.ret(int32(0))
    print('====== LLVM IR ')
    print(module)


    llvm_module = llvm.parse_assembly(str(module))

    tm = llvm.Target.from_default_triple().create_target_machine()
    with llvm.create_mcjit_compiler(llvm_module, tm) as ee:
        ee.finalize_object()

        print("============Assembly")
        print(tm.emit_assembly(llvm_module))

    # Set the return type on the entry point function

def main():
    if len(sys.argv) == 2:
        with open(sys.argv[1], "r") as f:
            source = cleanup(f.read())
            execute(source)
    else:
        print("Usage:", sys.argv[0], "filename")


if __name__ == "__main__":
    main()
