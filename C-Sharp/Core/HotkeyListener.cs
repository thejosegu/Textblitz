using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;

namespace Blitztext.Core;

/// <summary>
/// Global hotkey listener using Win32 low-level keyboard hook (WH_KEYBOARD_LL).
/// Supports multi-key combos with 50ms debounce, hold and toggle mode.
/// </summary>
public sealed class HotkeyListener : IDisposable
{
    // ── Win32 ──────────────────────────────────────────────────────────
    private delegate nint LowLevelKeyboardProc(int nCode, nint wParam, nint lParam);

    [DllImport("user32.dll")] private static extern nint SetWindowsHookEx(int idHook, LowLevelKeyboardProc lpfn, nint hMod, uint dwThreadId);
    [DllImport("user32.dll")] private static extern bool UnhookWindowsHookEx(nint hhk);
    [DllImport("user32.dll")] private static extern nint CallNextHookEx(nint hhk, int nCode, nint wParam, nint lParam);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] private static extern nint GetModuleHandle(string lpModuleName);

    private const int WH_KEYBOARD_LL = 13;
    private const int WM_KEYDOWN = 0x0100;
    private const int WM_SYSKEYDOWN = 0x0104;
    private const int WM_KEYUP = 0x0101;
    private const int WM_SYSKEYUP = 0x0105;

    [StructLayout(LayoutKind.Sequential)]
    private struct KBDLLHOOKSTRUCT
    {
        public uint vkCode;
        public uint scanCode;
        public uint flags;
        public uint time;
        public nint dwExtraInfo;
    }

    // ── state ──────────────────────────────────────────────────────────
    private readonly Func<Dictionary<string, string>> _getHotkeys;
    private readonly Action<string> _onStart;
    private readonly Action<string> _onStop;
    private readonly Func<string> _getRecordMode;

    private readonly HashSet<uint> _pressed = [];
    private readonly Lock _lock = new();
    private string? _activeMode;
    private Timer? _debounceTimer;
    private nint _hookHandle;
    private LowLevelKeyboardProc? _hookProc;   // keep alive – GC guard

    public bool Capturing { get; set; }        // True while settings window records a hotkey

    public HotkeyListener(
        Func<Dictionary<string, string>> getHotkeys,
        Action<string> onStart,
        Action<string> onStop,
        Func<string>? getRecordMode = null)
    {
        _getHotkeys    = getHotkeys;
        _onStart       = onStart;
        _onStop        = onStop;
        _getRecordMode = getRecordMode ?? (() => "hold");
    }

    public void Start()
    {
        _hookProc = HookCallback;
        using var process = System.Diagnostics.Process.GetCurrentProcess();
        using var module  = process.MainModule!;
        _hookHandle = SetWindowsHookEx(WH_KEYBOARD_LL, _hookProc, GetModuleHandle(module.ModuleName!), 0);
    }

    public void Stop()
    {
        if (_hookHandle != 0)
        {
            UnhookWindowsHookEx(_hookHandle);
            _hookHandle = 0;
        }
    }

    public void Dispose() => Stop();

    // ── hook callback ─────────────────────────────────────────────────
    private nint HookCallback(int nCode, nint wParam, nint lParam)
    {
        if (nCode >= 0 && !Capturing)
        {
            var kb  = Marshal.PtrToStructure<KBDLLHOOKSTRUCT>(lParam);
            bool dn = wParam == WM_KEYDOWN || wParam == WM_SYSKEYDOWN;
            bool up = wParam == WM_KEYUP   || wParam == WM_SYSKEYUP;

            if (dn) OnKeyDown(kb.vkCode);
            if (up) OnKeyUp(kb.vkCode);
        }
        return CallNextHookEx(_hookHandle, nCode, wParam, lParam);
    }

    private void OnKeyDown(uint vk)
    {
        string? modeToStop = null;

        lock (_lock)
        {
            _pressed.Add(vk);

            if (_activeMode != null)
            {
                if (_getRecordMode() == "toggle")
                {
                    var combo = ParseHotkey(_getHotkeys().GetValueOrDefault(_activeMode, ""));
                    if (combo.Count > 0 && combo.IsSubsetOf(_pressed))
                    {
                        modeToStop   = _activeMode;
                        _activeMode  = null;
                    }
                }
                if (modeToStop == null) return;
            }

            if (modeToStop == null)
            {
                _debounceTimer?.Change(Timeout.Infinite, Timeout.Infinite);
                _debounceTimer = new Timer(_ => TryTrigger(), null, 50, Timeout.Infinite);
            }
        }

        if (modeToStop != null)
            _onStop(modeToStop);
    }

    private void OnKeyUp(uint vk)
    {
        string? modeToStop = null;

        lock (_lock)
        {
            _debounceTimer?.Change(Timeout.Infinite, Timeout.Infinite);
            _debounceTimer = null;

            if (_activeMode != null && _getRecordMode() == "hold")
            {
                var combo = ParseHotkey(_getHotkeys().GetValueOrDefault(_activeMode, ""));
                if (combo.Contains(vk))
                {
                    modeToStop  = _activeMode;
                    _activeMode = null;
                }
            }
            _pressed.Remove(vk);
        }

        if (modeToStop != null)
            _onStop(modeToStop);
    }

    private void TryTrigger()
    {
        string? bestMode = null;

        lock (_lock)
        {
            _debounceTimer = null;
            if (_activeMode != null) return;

            int bestLen = 0;
            foreach (var (mode, spec) in _getHotkeys())
            {
                var combo = ParseHotkey(spec);
                if (combo.Count > 0 && combo.IsSubsetOf(_pressed) && combo.Count > bestLen)
                {
                    bestLen  = combo.Count;
                    bestMode = mode;
                }
            }

            if (bestMode != null)
                _activeMode = bestMode;
        }

        if (bestMode != null)
            _onStart(bestMode);
    }

    // ── hotkey parsing ────────────────────────────────────────────────

    /// <summary>Map config token strings → virtual-key codes.</summary>
    private static readonly Dictionary<string, uint> KeyMap = new(StringComparer.OrdinalIgnoreCase)
    {
        ["ctrl_r"]       = 0xA3,  // VK_RCONTROL
        ["ctrl_l"]       = 0xA2,  // VK_LCONTROL
        ["ctrl"]         = 0x11,  // VK_CONTROL
        ["alt_r"]        = 0xA5,  // VK_RMENU
        ["alt_l"]        = 0xA4,  // VK_LMENU
        ["alt"]          = 0x12,  // VK_MENU
        ["shift_r"]      = 0xA1,  // VK_RSHIFT
        ["shift_l"]      = 0xA0,  // VK_LSHIFT
        ["shift"]        = 0x10,  // VK_SHIFT
        ["win_r"]        = 0x5C,  // VK_RWIN
        ["win_l"]        = 0x5B,  // VK_LWIN
        ["space"]        = 0x20,  // VK_SPACE
        ["f8"]           = 0x77,
        ["f13"]          = 0x7C,
        ["f14"]          = 0x7D,
        ["f15"]          = 0x7E,
        ["scroll_lock"]  = 0x91,
        ["pause"]        = 0x13,
    };

    public static HashSet<uint> ParseHotkey(string spec)
    {
        var result = new HashSet<uint>();
        if (string.IsNullOrWhiteSpace(spec)) return result;

        foreach (var token in spec.Split('+'))
        {
            var t = token.Trim().ToLowerInvariant();
            if (KeyMap.TryGetValue(t, out var vk))
                result.Add(vk);
            else if (t.Length == 1)
                result.Add((uint)char.ToUpperInvariant(t[0]));
        }
        return result;
    }

    public static string HotkeyToString(HashSet<uint> keys)
    {
        var reverse = new Dictionary<uint, string>();
        foreach (var (name, vk) in KeyMap) reverse.TryAdd(vk, name);

        var parts = new List<string>();
        foreach (var vk in keys)
            parts.Add(reverse.TryGetValue(vk, out var name) ? name : $"0x{vk:X2}");

        parts.Sort();
        return string.Join("+", parts);
    }
}
