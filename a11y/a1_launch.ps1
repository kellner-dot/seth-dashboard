# A1: full user-session launch test (whoami only - read-only)
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class UL {
    [DllImport("kernel32.dll")] public static extern uint WTSGetActiveConsoleSessionId();
    [DllImport("wtsapi32.dll", SetLastError=true)] public static extern bool WTSQueryUserToken(uint s, out IntPtr t);
    [DllImport("advapi32.dll", SetLastError=true)] public static extern bool DuplicateTokenEx(IntPtr ht, uint da, IntPtr la, int il, int tt, out IntPtr pht);
    [DllImport("advapi32.dll", SetLastError=true, CharSet=CharSet.Unicode)] public static extern bool CreateProcessAsUser(IntPtr ht, string an, StringBuilder cl, IntPtr pa, IntPtr ta, bool ih, uint cf, IntPtr env, string cd, ref SI si, out PI pi);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern uint WaitForSingleObject(IntPtr h, uint ms);
    [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool GetExitCodeProcess(IntPtr hp, out uint ec);
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)] public struct SI { public int cb; public string r1; public string lpDesktop; public string r2; public int x; public int y; public int xs; public int ys; public int xc; public int yc; public int fa; public int fl; public short sw; public short r3; public IntPtr r4; public IntPtr hIn; public IntPtr hOut; public IntPtr hErr; }
    [StructLayout(LayoutKind.Sequential)] public struct PI { public IntPtr hP; public IntPtr hT; public int pid; public int tid; }
}
"@
$sid = [UL]::WTSGetActiveConsoleSessionId()
if ($sid -eq 0xFFFFFFFF) { "RESULT=NO_SESSION"; exit 0 }
$tok = [IntPtr]::Zero
if (-not [UL]::WTSQueryUserToken($sid, [ref]$tok)) { "RESULT=TOKEN_FAIL"; exit 0 }
$pri = [IntPtr]::Zero
if (-not [UL]::DuplicateTokenEx($tok, 0xF01FF, [IntPtr]::Zero, 2, 1, [ref]$pri)) { "RESULT=DUP_FAIL"; exit 0 }
$si = New-Object UL+SI; $si.cb = [Runtime.InteropServices.Marshal]::SizeOf($si); $si.lpDesktop = "winsta0\default"
$pi = New-Object UL+PI
$cmd = New-Object Text.StringBuilder("whoami")
$ok = [UL]::CreateProcessAsUser($pri, $null, $cmd, [IntPtr]::Zero, [IntPtr]::Zero, $false, 0x08000000, [IntPtr]::Zero, $null, [ref]$si, [ref]$pi)
if (-not $ok) { "RESULT=CREATE_FAIL"; exit 0 }
"RESULT=LAUNCHED_PID=$($pi.pid)"
[UL]::WaitForSingleObject($pi.hP, 15000) | Out-Null
$ec = 0; [UL]::GetExitCodeProcess($pi.hP, [ref]$ec) | Out-Null
"RESULT=EXIT_CODE=$ec"
[UL]::CloseHandle($pi.hP) | Out-Null; [UL]::CloseHandle($pi.hT) | Out-Null
[UL]::CloseHandle($pri) | Out-Null; [UL]::CloseHandle($tok) | Out-Null
