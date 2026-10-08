# A1 technique validation: can Session-0 SYSTEM launch a user-session process?
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WTS {
    [DllImport("kernel32.dll")] public static extern uint WTSGetActiveConsoleSessionId();
    [DllImport("wtsapi32.dll", SetLastError=true)] public static extern bool WTSQueryUserToken(uint sessionId, out IntPtr token);
    [DllImport("advapi32.dll", SetLastError=true)] public static extern bool DuplicateTokenEx(IntPtr hToken, uint dwDesiredAccess, IntPtr lpAttrs, int impersonationLevel, int tokenType, out IntPtr phNewToken);
    [DllImport("advapi32.dll", SetLastError=true, CharSet=CharSet.Unicode)] public static extern bool CreateProcessAsUser(IntPtr hToken, string appName, string cmdLine, IntPtr procAttrs, IntPtr threadAttrs, bool inheritHandles, uint creationFlags, IntPtr env, string curDir, ref STARTUPINFO si, out PROCESS_INFORMATION pi);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern uint WaitForSingleObject(IntPtr hHandle, uint ms);
    [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool GetExitCodeProcess(IntPtr hProcess, out uint exitCode);
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)] public struct STARTUPINFO { public int cb; public string lpReserved; public string lpDesktop; public string lpTitle; public int dwX; public int dwY; public int dwXSize; public int dwYSize; public int dwXCountChars; public int dwYCountChars; public int dwFillAttribute; public int dwFlags; public short wShowWindow; public short cbReserved2; public IntPtr lpReserved2; public IntPtr hStdInput; public IntPtr hStdOutput; public IntPtr hStdError; }
    [StructLayout(LayoutKind.Sequential)] public struct PROCESS_INFORMATION { public IntPtr hProcess; public IntPtr hThread; public int dwProcessId; public int dwThreadId; }
}
"@
$sid = [WTS]::WTSGetActiveConsoleSessionId()
Write-Output "CONSOLE_SESSION_ID=$sid"
if ($sid -eq 0xFFFFFFFF) { Write-Output "RESULT=NO_CONSOLE_SESSION_FAIL_CLOSED"; exit 0 }
$tok = [IntPtr]::Zero
if (-not [WTS]::WTSQueryUserToken($sid, [ref]$tok)) { Write-Output "RESULT=WTSQueryUserToken_FAILED"; exit 0 }
Write-Output "RESULT=TOKEN_ACQUIRED"
[WTS]::CloseHandle($tok) | Out-Null
