# SPDX-License-Identifier: AGPL-3.0-only
# Test driver only. Geometry operations run through native slicer commands.
param(
    [Parameter(Mandatory)][ValidateSet('orca','bambu')][string]$Target,
    [Parameter(Mandatory)][ValidateSet('launch','experiment','check-reopened','add-linked','update-linked','revert-linked','capture','show','close')][string]$Action,
    [string]$Project,
    [switch]$Portable
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$testRoot = Join-Path $root "artifacts\$Target"
$binaryName = if ($Target -eq 'orca') {'orca-slicer.exe'} else {'bambu-studio.exe'}
$buildBinary = Join-Path $root "build\$Target\src\Release\$binaryName"
$portableBinary = Join-Path $testRoot "portable\$binaryName"
$binary = if ($Portable) { $portableBinary } else { $buildBinary }
$processRecord = Join-Path $testRoot 'process.json'
if ($Action -eq 'launch') {
    if (!(Test-Path -LiteralPath $binary)) { throw "Build not found: $binary" }
    $env:OSL_EXPERIMENT_DIR = if ($Portable) { Join-Path $testRoot 'portable\experiment' } else { $testRoot }
    $env:OSL_COMPANION_FILE = Join-Path $root 'artifacts\onshape\bridge.json'
    $profile = if ($Portable) { Join-Path $testRoot 'portable\profile' } else { Join-Path $testRoot 'profile' }
    $arguments = '--datadir "' + $profile + '"'
    if ($Project) {
        $resolvedProject = (Resolve-Path -LiteralPath $Project).Path
        if (!$resolvedProject.StartsWith($testRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Only an isolated experiment project may be opened by this driver.'
        }
        $arguments += ' "' + $resolvedProject + '"'
    }
    $slicer = Start-Process -FilePath $binary -ArgumentList $arguments -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $testRoot 'stdout.log') -RedirectStandardError (Join-Path $testRoot 'stderr.log')
    @{process_id=$slicer.Id; binary=$binary; profile=$profile} | ConvertTo-Json | Set-Content -LiteralPath $processRecord
    Write-Output "Started isolated $Target process $($slicer.Id)."
    exit
}
$record = Get-Content -Raw -LiteralPath $processRecord | ConvertFrom-Json
$binary = $record.binary
if ($binary -ne $buildBinary -and $binary -ne $portableBinary) { throw 'Unrecognized test binary location.' }
$slicer = Get-Process -Id $record.process_id
if ($slicer.Path -ne $binary -or $record.binary -ne $binary) { throw 'Process identity mismatch.' }
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class OslTestWindows {
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int command);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [StructLayout(LayoutKind.Sequential)] public struct Rect {public int Left, Top, Right, Bottom;}
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out Rect rect);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint processId);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("kernel32.dll")] private static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] private static extern bool AttachThreadInput(uint first, uint second, bool attach);
    [DllImport("user32.dll")] private static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int width, int height, uint flags);
    public static bool Focus(IntPtr window) {
        uint unused; uint foreground = GetWindowThreadProcessId(GetForegroundWindow(), out unused);
        uint current = GetCurrentThreadId();
        bool attached = foreground != current && AttachThreadInput(current, foreground, true);
        try {
            ShowWindow(window, 9);
            if (SetForegroundWindow(window)) return true;
            SetWindowPos(window, new IntPtr(-1), 0, 0, 0, 0, 0x43);
            SetWindowPos(window, new IntPtr(-2), 0, 0, 0, 0, 0x43);
            return SetForegroundWindow(window) || GetForegroundWindow() == window;
        }
        finally { if (attached) AttachThreadInput(current, foreground, false); }
    }
    private delegate bool EnumWindow(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] private static extern bool EnumWindows(EnumWindow callback, IntPtr l);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetWindowText(IntPtr h, StringBuilder text, int max);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetClassName(IntPtr h, StringBuilder text, int max);
    public static IntPtr FindMainWindow(uint processId) {
        IntPtr result = IntPtr.Zero;
        EnumWindows((h,l) => {
            uint owner; GetWindowThreadProcessId(h, out owner);
            if (owner != processId) return true;
            var title = new StringBuilder(512); var cls = new StringBuilder(128);
            GetWindowText(h, title, 512); GetClassName(h, cls, 128);
            if (cls.ToString() == "wxWindowNR" && (title.ToString().Contains("OrcaSlicer") || title.ToString().Contains("BambuStudio"))) result = h;
            return true;
        }, IntPtr.Zero);
        return result;
    }
}
'@
[OslTestWindows]::SetProcessDPIAware() | Out-Null
$slicer.Refresh()
$window = if ($record.window_handle) { [IntPtr]$record.window_handle } else { $slicer.MainWindowHandle }
if ($window -eq [IntPtr]::Zero) { $window = [OslTestWindows]::FindMainWindow($slicer.Id) }
if ($window -eq [IntPtr]::Zero) { throw 'The isolated slicer has no main window yet.' }
$ownerId = [uint32]0
[OslTestWindows]::GetWindowThreadProcessId($window, [ref]$ownerId) | Out-Null
if ($ownerId -ne $slicer.Id) { throw 'Window identity mismatch.' }
$record | Add-Member -NotePropertyName window_handle -NotePropertyValue $window.ToInt64() -Force
$record | ConvertTo-Json | Set-Content -LiteralPath $processRecord
if ($Action -eq 'show') {
    if (![OslTestWindows]::Focus($window)) { throw 'Could not focus the isolated test window.' }
} elseif ($Action -eq 'close') {
    [OslTestWindows]::PostMessage($window,0x0010,[IntPtr]::Zero,[IntPtr]::Zero) | Out-Null
    Write-Output "Requested close of isolated process $($slicer.Id)."
} elseif ($Action -eq 'capture') {
    $foregroundOwner = [uint32]0
    [OslTestWindows]::GetWindowThreadProcessId([OslTestWindows]::GetForegroundWindow(), [ref]$foregroundOwner) | Out-Null
    if ($foregroundOwner -ne $slicer.Id) { throw 'Bring the isolated test window to the foreground before capturing.' }
    Start-Sleep -Milliseconds 600
    [OslTestWindows]::GetWindowThreadProcessId([OslTestWindows]::GetForegroundWindow(), [ref]$foregroundOwner) | Out-Null
    if ($foregroundOwner -ne $slicer.Id) { throw 'Focus changed before capture. No screenshot saved.' }
    Add-Type -AssemblyName System.Drawing
    $rect = New-Object OslTestWindows+Rect
    [OslTestWindows]::GetWindowRect($window, [ref]$rect) | Out-Null
    $bitmap = New-Object System.Drawing.Bitmap ($rect.Right-$rect.Left),($rect.Bottom-$rect.Top)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen($rect.Left,$rect.Top,0,0,$bitmap.Size)
        [OslTestWindows]::GetWindowThreadProcessId([OslTestWindows]::GetForegroundWindow(), [ref]$foregroundOwner) | Out-Null
        if ($foregroundOwner -ne $slicer.Id) { throw 'Focus changed during capture. No screenshot saved.' }
        $imagePath = Join-Path $testRoot 'slicer.png'
        $bitmap.Save($imagePath,[System.Drawing.Imaging.ImageFormat]::Png)
        Write-Output $imagePath
    } finally { $graphics.Dispose(); $bitmap.Dispose() }
} else {
    $command = switch ($Action) { 'experiment' {6874} 'check-reopened' {6875} 'add-linked' {6871} 'update-linked' {6872} 'revert-linked' {6873} }
    if (![OslTestWindows]::PostMessage($window,0x0111,[IntPtr]$command,[IntPtr]::Zero)) {
        throw 'Could not post the native test command.'
    }
    Write-Output "Invoked $Action in isolated process $($slicer.Id)."
}
