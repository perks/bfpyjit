import os
import sys
from itertools import accumulate
from collections import defaultdict

import llvmlite.binding as llvm
import llvmlite.ir as ir

from ctypes import CFUNCTYPE, c_int32

bit = ir.IntType(1)
int8 = ir.IntType(8)
int32 = ir.IntType(32)
int64 = ir.IntType(64)
int8ptr = int8.as_pointer()

def cleanup(source):
    return "".join(
        filter(lambda x: x in ["+", "-", "[", "]", ",", ".", "<", ">"], source)
    )


def ir_putchar(builder, char):
    mod = builder.module
    f_arg = ir.Constant(ir.IntType(8), char)

    fn_type = ir.FunctionType(int32, [ir.IntType(8)])
    try:
        fn = mod.get_global('putchar')
    except KeyError:
        fn = ir.Function(mod, fn_type, name='putchar')

    return builder.call(fn, [char])

def ir_getchar(builder,):
    mod = builder.module
    fn_type = ir.FunctionType(int8, [])
    try:
        fn = mod.get_global('getchar')
    except KeyError:
        fn = ir.Function(mod, fn_type, name='getchar')

    return builder.call(fn, [])

def execute(instructions):


    MEMORY_SIZE = 30000

    # Intialize LLVM
    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    # Create our module
    module = ir.Module()
    function_type = ir.FunctionType(int32, [])
    function = ir.Function(module, function_type, name="bf_jit_exec")

    bb_entry = function.append_basic_block("entry")
    irb = ir.IRBuilder(bb_entry)

    # Initialize and declare our memory pointers
    memory = irb.alloca(int8, MEMORY_SIZE)
    dataptr_addr = irb.alloca(int32)

    memset = module.declare_intrinsic("llvm.memset", [int8ptr, int32])
    memcpy = module.declare_intrinsic("llvm.memcpy", [int8ptr, int8ptr, int32])

    # memset(ptr, val, size, align, isVolitile)
    # Might not need to zero-out stack but just in case
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
    left_stack = []
    pc, size = 0, len(instructions)
    while pc < size:
        inst = instructions[pc]

        # These 'inefficient' incremental IR emissions are actually good because
        # they let the optimizer go HAM instead of us trying to preempt it
        if inst == '>':
            dataptr = irb.load(dataptr_addr, "dataptr")
            inc_dataptr = irb.add(dataptr, int32(1), "inc_dataptr")
            irb.store(inc_dataptr, dataptr_addr)

        elif inst == '<':
            dataptr = irb.load(dataptr_addr, "dataptr")
            dec_dataptr = irb.sub(dataptr, int32(1), "dec_dataptr")
            irb.store(dec_dataptr, dataptr_addr)

        elif inst == '+':
            dataptr = irb.load(dataptr_addr, "dataptr")
            element_addr = irb.gep(memory, [dataptr], inbounds=True, name="element_addr")
            element = irb.load(element_addr, "element")
            inc_element = irb.add(element, int8(1), "inc_element")
            irb.store(inc_element, element_addr)

        elif inst == '-':
            dataptr = irb.load(dataptr_addr, "dataptr")
            element_addr = irb.gep(memory, [dataptr], inbounds=True, name="element_addr")
            element = irb.load(element_addr, "element")
            dec_element = irb.sub(element, int8(1), "dec_element")
            irb.store(dec_element, element_addr)

        elif inst == '.':
            dataptr = irb.load(dataptr_addr, "dataptr")
            element_addr = irb.gep(memory, [dataptr], inbounds=True, name="element_addr")
            element = irb.load(element_addr, "element")
            # CreateIntCast(element, int32, isSigned=False, name="element_i32_)
            # zext is unsigned
            element_i8 = irb.zext(element, int8, "element_i8_")

            ir_putchar(irb, element_i8)

        elif inst == ',':
            ir_getchar(irb)

        elif inst == '[':
            dataptr = irb.load(dataptr_addr, "dataptr")
            element_addr = irb.gep(memory, [dataptr], inbounds=True, name="element_addr")
            element = irb.load(element_addr, "element")
            cmp = irb.icmp_unsigned("==", element, int8(0), "compare_zero")

            loop_body_block = irb.append_basic_block("loop_body")
            post_loop_block = irb.append_basic_block("post_loop")

            irb.cbranch(cmp, post_loop_block, loop_body_block)

            left_stack.append((loop_body_block, post_loop_block))
            irb.position_at_end(loop_body_block)

        elif inst == ']':
            loop_body_block, post_loop_block = left_stack.pop()

            dataptr = irb.load(dataptr_addr, "dataptr")
            element_addr = irb.gep(memory, [dataptr], inbounds=True, name="element_addr")
            element = irb.load(element_addr, "element")
            cmp = irb.icmp_unsigned("!=", element, int8(0), "compare_zero")

            irb.cbranch(cmp, loop_body_block, post_loop_block)
            irb.position_at_end(post_loop_block)

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

        cfptr = ee.get_function_address('bf_jit_exec')
        cfunc = CFUNCTYPE(c_int32)(cfptr)

        res = cfunc()

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
