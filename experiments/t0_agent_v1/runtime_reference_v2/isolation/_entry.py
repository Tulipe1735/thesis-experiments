"""Trusted bootstrap, executed with -I; never runs skill text before seccomp."""

import builtins
import ctypes
import errno
import json
import math
import os
import resource
import sys


WIRE_LIMIT = 64 * 1024 * 1024
ALLOWED_IMPORTS = (
    "math", "numpy", "numpy.linalg", "numpy.random", "numpy.fft",
    "numpy._core._methods",  # ndarray reductions import this helper from C.
)


def _read_message(limit):
    raw = sys.stdin.buffer.readline(limit + 1)
    if not raw:
        return None
    if len(raw) > limit or not raw.endswith(b"\n"):
        raise ValueError("input exceeds the message limit")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("request must be a JSON object")
    return result


def _send(message):
    encoded = json.dumps(message, allow_nan=False, separators=(",", ":"))
    sys.stdout.write(encoded + "\n")
    sys.stdout.flush()


def _install_boundary(limits):
    if sys.platform != "linux":
        raise RuntimeError("a Linux kernel and libseccomp are mandatory")
    import numpy as np
    import numpy.fft
    import numpy.linalg
    import numpy.ma
    import numpy.random

    # Prewarm lazy native paths before denying all filesystem access and cloning.
    np.linalg.solve(np.eye(3), np.ones(3))
    np.linalg.svd(np.eye(3))
    np.linalg.inv(np.eye(3))
    np.linalg.eigh(np.eye(3))
    np.linalg.cond(np.eye(3))
    np.linalg.lstsq(np.eye(3), np.ones(3), rcond=None)
    values = np.arange(4, dtype=float)
    np.histogram(values, bins=2)
    np.percentile(values, 50)
    np.convolve(values, np.ones(2))
    np.ptp(values)
    np.cross([1., 0., 0.], [0., 1., 0.])
    values.mean(), values.std(), values.min(), values.max(), values.sum()
    np.fft.fft(np.ones(8))
    np.random.default_rng(0).normal(size=4)
    if len(os.listdir("/proc/self/task")) != 1:
        raise RuntimeError("numeric runtime unexpectedly created background threads")

    library = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS failed")
    if libc.prctl(4, 0, 0, 0, 0) != 0:  # PR_SET_DUMPABLE
        raise OSError(ctypes.get_errno(), "PR_SET_DUMPABLE failed")

    class ArgumentComparison(ctypes.Structure):
        _fields_ = [
            ("arg", ctypes.c_uint),
            ("op", ctypes.c_int),
            ("datum_a", ctypes.c_uint64),
            ("datum_b", ctypes.c_uint64),
        ]

    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_syscall_resolve_name.restype = ctypes.c_int
    library.seccomp_rule_add_array.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint,
        ctypes.POINTER(ArgumentComparison),
    ]
    library.seccomp_rule_add_array.restype = ctypes.c_int
    library.seccomp_attr_set.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
    library.seccomp_attr_set.restype = ctypes.c_int
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    library.seccomp_load.restype = ctypes.c_int
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    library.seccomp_release.restype = None
    context = library.seccomp_init(0x00050000 | errno.EPERM)
    if not context:
        raise RuntimeError("seccomp_init failed")

    def allow(name, comparisons=()):
        number = library.seccomp_syscall_resolve_name(name.encode("ascii"))
        if number < 0:
            raise RuntimeError("unknown required syscall: " + name)
        array = (ArgumentComparison * len(comparisons))(*comparisons)
        result = library.seccomp_rule_add_array(context, 0x7FFF0000, number, len(array), array)
        if result != 0:
            raise RuntimeError(f"could not allow syscall {name}: {result}")

    try:
        if library.seccomp_attr_set(context, 4, 1) != 0:  # SCMP_FLTATR_CTL_TSYNC
            raise RuntimeError("seccomp thread synchronization unavailable")
        allow("read", (ArgumentComparison(0, 4, 0, 0),))  # SCMP_CMP_EQ
        for descriptor in (1, 2):
            allow("write", (ArgumentComparison(0, 4, descriptor, 0),))
        # Only anonymous memory: no mapping inherited descriptors or disk files.
        allow("mmap", (ArgumentComparison(3, 7, 0x20, 0x20),))  # SCMP_CMP_MASKED_EQ
        for name in (
            "brk", "munmap", "mremap", "madvise", "mprotect", "futex",
            "clock_gettime", "clock_nanosleep", "nanosleep", "getrandom",
            "getpid", "gettid", "sched_yield", "rt_sigaction", "rt_sigprocmask",
            "rt_sigreturn", "sigaltstack", "exit", "exit_group",
        ):
            allow(name)

        memory = int(limits["memory_bytes"])
        cpu = int(limits["cpu_seconds"])
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
        os.environ.clear()
        os.chdir("/")
        # Enumerate before filtering, then discard every inherited descriptor.
        for entry in os.listdir("/proc/self/fd"):
            descriptor = int(entry)
            if descriptor >= 3:
                try:
                    os.close(descriptor)
                except OSError as exc:
                    if exc.errno != errno.EBADF:
                        raise
        resource.setrlimit(resource.RLIMIT_NOFILE, (3, 3))
        result = library.seccomp_load(context)
        if result != 0:
            raise RuntimeError(f"mandatory seccomp_load failed: {result}")
    finally:
        library.seccomp_release(context)
    return np


def _skill_globals(np):
    real_import = builtins.__import__

    def numeric_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level != 0 or name not in ALLOWED_IMPORTS:
            raise ImportError(f"import {name!r} denied; skill imports are restricted to: " + ", ".join(ALLOWED_IMPORTS))
        return real_import(name, globals, locals, fromlist, level)

    def diagnostic_print(*args, **kwargs):
        kwargs["file"] = sys.stderr
        return builtins.print(*args, **kwargs)

    names = (
        "__build_class__", "abs", "all", "any", "ascii", "bin", "bool", "bytearray",
        "bytes", "callable", "chr", "classmethod", "complex", "dict", "dir", "divmod",
        "enumerate", "filter", "float", "format", "frozenset", "getattr", "hasattr",
        "hash", "hex", "id", "int", "isinstance", "issubclass", "iter", "len", "list",
        "map", "max", "memoryview", "min", "next", "object", "oct", "ord", "pow",
        "property", "range", "repr", "reversed", "round", "set", "setattr", "slice",
        "sorted", "staticmethod", "str", "sum", "super", "tuple", "type", "vars", "zip",
        "BaseException", "Exception", "ArithmeticError", "AssertionError", "AttributeError",
        "EOFError", "ImportError", "IndexError", "KeyError", "LookupError", "MemoryError",
        "NameError", "NotImplementedError", "OSError", "OverflowError", "PermissionError",
        "RuntimeError", "StopIteration", "TypeError", "ValueError", "ZeroDivisionError",
        "NotImplemented", "Ellipsis",
    )
    namespace = {name: getattr(builtins, name) for name in names}
    namespace["__import__"] = numeric_import
    namespace["print"] = diagnostic_print
    return {"__builtins__": namespace, "__name__": "numeric_skill", "np": np, "math": math}


def _error_text(exc):
    return type(exc).__name__ + ": " + str(exc)[:2000]


def main():
    request_id = 0
    secured = False
    try:
        request = _read_message(WIRE_LIMIT)
        if request is None or request.get("kind") != "start":
            raise ValueError("first request must initialize a skill")
        limits = request["limits"]
        np = _install_boundary(limits)
        secured = True
        namespace = _skill_globals(np)
        exec(compile(request["source"], "<numeric-skill>", "exec"), namespace, namespace)
        action_function = namespace.get("act")
        if not callable(action_function):
            raise TypeError("source must define act(observation, task, state)")
        initialize = namespace.get("init")
        state = initialize(request["profile"]) if callable(initialize) else None
        _send(
            {
                "id": 0,
                "kind": "ready",
                "state": state,
                "security": {
                    "seccomp": True,
                    "default_action": "EPERM",
                    "imports": list(ALLOWED_IMPORTS),
                    "memory_bytes": limits["memory_bytes"],
                    "cpu_seconds": limits["cpu_seconds"],
                },
            }
        )
        while True:
            request = _read_message(limits["max_input_bytes"])
            if request is None:
                return
            request_id = request.get("id")
            if request.get("kind") != "act":
                raise ValueError("unexpected message kind")
            result = action_function(request["observation"], request["task"], request["state"])
            if not isinstance(result, dict) or not isinstance(result.get("action"), dict):
                raise TypeError("act must return a dictionary containing an action object")
            if "state" not in result:
                result["state"] = request["state"]
            _send({"id": request_id, "kind": "result", "result": result})
    except BaseException as exc:
        _send(
            {
                "id": request_id,
                "kind": "error" if secured else "isolation_error",
                "error": _error_text(exc),
            }
        )


if __name__ == "__main__":
    main()
