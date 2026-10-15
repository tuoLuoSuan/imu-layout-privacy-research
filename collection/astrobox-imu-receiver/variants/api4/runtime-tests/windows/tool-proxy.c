#include <windows.h>
#include <process.h>
#include <stdlib.h>
#include <wchar.h>

int wmain(int argc, wchar_t **argv) {
    wchar_t zig[32768];
    if (!GetModuleFileNameW(NULL, zig, 32768)) return 101;
    wchar_t *slash = wcsrchr(zig, L'\\');
    if (!slash) return 102;
    const wchar_t *mode = wcsncmp(slash + 1, L"cc-", 3) == 0 ? L"cc" : wcsncmp(slash + 1, L"ar-", 3) == 0 ? L"ar" : L"dlltool";
    wcscpy(slash + 1, L"compiler\\zig-x86_64-windows-0.14.1\\zig.exe");
    const wchar_t **args = calloc(argc + 2, sizeof(wchar_t*));
    if (!args) return 103;
    args[0] = zig;
    args[1] = mode;
    for (int i=1; i<argc; i++) {
        args[i+1] = wcscmp(argv[i], L"--temp-prefix") == 0 ? L"-t" :
            wcscmp(argv[i], L"--target=x86_64-pc-windows-gnu") == 0 ? L"--target=x86_64-windows-gnu" : argv[i];
    }
    intptr_t rc = _wspawnv(_P_WAIT, zig, args);
    free(args);
    return rc == -1 ? 104 : (int)rc;
}
