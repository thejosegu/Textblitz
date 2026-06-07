using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace Blitztext.Core;

public static class Injector
{
    [DllImport("user32.dll")] private static extern uint SendInput(uint n, INPUT[] p, int cb);
    [DllImport("user32.dll")] private static extern nint GetMessageExtraInfo();
    [DllImport("user32.dll")] private static extern nint GetForegroundWindow();
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetWindowText(nint h, StringBuilder s, int n);
    [DllImport("user32.dll")] private static extern bool OpenClipboard(nint h);
    [DllImport("user32.dll")] private static extern bool CloseClipboard();
    [DllImport("user32.dll")] private static extern bool EmptyClipboard();
    [DllImport("user32.dll")] private static extern nint SetClipboardData(uint f, nint h);
    [DllImport("user32.dll")] private static extern nint GetClipboardData(uint f);
    [DllImport("kernel32.dll")] private static extern nint GlobalAlloc(uint f, nuint n);
    [DllImport("kernel32.dll")] private static extern nint GlobalLock(nint h);
    [DllImport("kernel32.dll")] private static extern bool GlobalUnlock(nint h);

    private const uint CF_UNICODETEXT    = 13;
    private const uint GMEM_MOVEABLE     = 0x0002;
    private const uint INPUT_KEYBOARD    = 1;
    private const ushort VK_CONTROL      = 0x11;
    private const ushort VK_V            = 0x56;
    private const uint KEYEVENTF_KEYUP   = 0x0002;
    private const uint KEYEVENTF_UNICODE = 0x0004;

    // INPUT must be exactly 40 bytes on x64 (MOUSEINPUT is the largest union member)
    [StructLayout(LayoutKind.Explicit, Size = 40)]
    private struct INPUT
    {
        [FieldOffset(0)] public uint      type;
        [FieldOffset(8)] public KEYBDINPUT ki;
    }
    [StructLayout(LayoutKind.Sequential)]
    private struct KEYBDINPUT { public ushort wVk, wScan; public uint dwFlags, time; public nint dwExtraInfo; }

    public static nint CaptureTarget() => GetForegroundWindow();

    public static string GetWindowTitle(nint hwnd)
    {
        var sb = new StringBuilder(256);
        GetWindowText(hwnd, sb, sb.Capacity);
        return sb.ToString();
    }

    // Raw Win32 clipboard — no STA/WPF needed
    public static string? RawGetClipboard()
    {
        for (int i = 0; i < 5; i++)
        {
            if (!OpenClipboard(0)) { Thread.Sleep(10); continue; }
            try
            {
                nint hData = GetClipboardData(CF_UNICODETEXT);
                if (hData == 0) return null;
                nint ptr = GlobalLock(hData);
                if (ptr == 0) return null;
                try   { return Marshal.PtrToStringUni(ptr); }
                finally { GlobalUnlock(hData); }
            }
            finally { CloseClipboard(); }
        }
        return null;
    }

    public static bool RawSetClipboard(string? text)
    {
        for (int i = 0; i < 5; i++)
        {
            if (!OpenClipboard(0)) { Thread.Sleep(10); continue; }
            try
            {
                EmptyClipboard();
                if (text == null) return true;
                int byteCount = (text.Length + 1) * 2;
                nint hGlobal  = GlobalAlloc(GMEM_MOVEABLE, (nuint)byteCount);
                if (hGlobal == 0) return false;
                nint ptr = GlobalLock(hGlobal);
                if (ptr == 0) return false;
                Marshal.Copy(text.ToCharArray(), 0, ptr, text.Length);
                Marshal.WriteInt16(ptr + text.Length * 2, 0);
                GlobalUnlock(hGlobal);
                SetClipboardData(CF_UNICODETEXT, hGlobal);
                return true;
            }
            finally { CloseClipboard(); }
        }
        return false;
    }

    // Type each character via KEYEVENTF_UNICODE — no focus change needed
    public static void TypeUnicode(string text)
    {
        var inputs = new List<INPUT>(text.Length * 2);
        foreach (char c in text)
        {
            inputs.Add(new INPUT { type = INPUT_KEYBOARD, ki = new KEYBDINPUT
                { wScan = c, dwFlags = KEYEVENTF_UNICODE, dwExtraInfo = GetMessageExtraInfo() }});
            inputs.Add(new INPUT { type = INPUT_KEYBOARD, ki = new KEYBDINPUT
                { wScan = c, dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, dwExtraInfo = GetMessageExtraInfo() }});
        }
        SendInput((uint)inputs.Count, inputs.ToArray(), Marshal.SizeOf<INPUT>());
    }

    public static void SendCtrlV()
    {
        var inputs = new INPUT[]
        {
            new() { type = INPUT_KEYBOARD, ki = new KEYBDINPUT { wVk = VK_CONTROL, dwExtraInfo = GetMessageExtraInfo() }},
            new() { type = INPUT_KEYBOARD, ki = new KEYBDINPUT { wVk = VK_V,       dwExtraInfo = GetMessageExtraInfo() }},
            new() { type = INPUT_KEYBOARD, ki = new KEYBDINPUT { wVk = VK_V,       dwFlags = KEYEVENTF_KEYUP, dwExtraInfo = GetMessageExtraInfo() }},
            new() { type = INPUT_KEYBOARD, ki = new KEYBDINPUT { wVk = VK_CONTROL, dwFlags = KEYEVENTF_KEYUP, dwExtraInfo = GetMessageExtraInfo() }},
        };
        SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<INPUT>());
    }
}