# BFPyJit

This mostly came about just wanting to play around with compiler optimizations and exploring the LLVM JIT.

Was fun figuring out the llvmlite bindings for Python, hopefully this helps serve as an example for others interested in using it.

---

A note on optimizations: 

There is an overhead introduced when you optimize, so play around with that.

For example, on `hanoi.b` optimizing takes some time, but afterwards the execution is so fast you barely see the program on screen for a second

Meanwhile, turning optimizations off will actually execute the unoptimized LLVM IR at a speed that lets you see the disc movement


---

Thanks to the following references which were super helpful serving as a resource to learn!

* http://calmerthanyouare.org/2015/01/07/optimizing-brainfuck.html Free BF optimization tips
* https://github.com/numba/numba Best place to look for llvmlite example operations
* https://github.com/eriknyquist/bfi Pretty much implementing all the bytecode optimizations was adapting directly from this
* https://eli.thegreenplace.net/2017/adventures-in-jit-compilation-part-3-llvm/ An overall amazing series, worth checking out

