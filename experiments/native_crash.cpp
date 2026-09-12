// SPDX-License-Identifier: AGPL-3.0-only
// Diagnostics for native tests, including failures before main().
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#include <dbghelp.h>
#include <cstdio>
#pragma comment(lib, "dbghelp.lib")

static LONG WINAPI report_native_failure(EXCEPTION_POINTERS* exception)
{
    auto process = GetCurrentProcess();
    SymSetOptions(SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS | SYMOPT_LOAD_LINES);
    SymInitialize(process, nullptr, TRUE);
    CONTEXT context = *exception->ContextRecord;
    STACKFRAME64 frame{};
    frame.AddrPC = {context.Rip, AddrModeFlat};
    frame.AddrFrame = {context.Rbp, AddrModeFlat};
    frame.AddrStack = {context.Rsp, AddrModeFlat};
    std::fprintf(stderr, "Native exception %08lx at %p\n", exception->ExceptionRecord->ExceptionCode,
                 exception->ExceptionRecord->ExceptionAddress);
    for (int i=0; i<32; ++i) {
        alignas(SYMBOL_INFO) char storage[sizeof(SYMBOL_INFO) + 512]{};
        auto* symbol = reinterpret_cast<SYMBOL_INFO*>(storage);
        symbol->SizeOfStruct = sizeof(SYMBOL_INFO); symbol->MaxNameLen = 511;
        DWORD64 displacement = 0;
        if (SymFromAddr(process, frame.AddrPC.Offset, &displacement, symbol))
            std::fprintf(stderr, "  %s + 0x%llx\n", symbol->Name, displacement);
        else std::fprintf(stderr, "  0x%llx\n", frame.AddrPC.Offset);
        if (!StackWalk64(IMAGE_FILE_MACHINE_AMD64, process, GetCurrentThread(), &frame, &context,
                         nullptr, SymFunctionTableAccess64, SymGetModuleBase64, nullptr)) break;
    }
    return EXCEPTION_EXECUTE_HANDLER;
}
#pragma init_seg(lib)
struct InstallNativeDiagnostics {
    InstallNativeDiagnostics() { SetUnhandledExceptionFilter(report_native_failure); }
} install_native_diagnostics;
#endif
