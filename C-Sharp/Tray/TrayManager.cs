using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows;
using Blitztext.Core;

namespace Blitztext.Tray;

public enum TrayStatus { Ready, Recording, Processing, Error }

/// <summary>
/// Win32 Shell_NotifyIcon tray icon manager.
/// Generates icons at runtime via GDI+ (no external icon file required).
/// </summary>
public sealed class TrayManager : IDisposable
{
    // ── Win32 ──────────────────────────────────────────────────────────
    [DllImport("shell32.dll")] private static extern bool Shell_NotifyIcon(uint dwMessage, ref NOTIFYICONDATA lpdata);
    [DllImport("user32.dll")]  private static extern nint CreatePopupMenu();
    [DllImport("user32.dll")]  private static extern bool AppendMenu(nint hMenu, uint uFlags, nint uIDNewItem, string lpNewItem);
    [DllImport("user32.dll")]  private static extern uint TrackPopupMenu(nint hMenu, uint uFlags, int x, int y, int nReserved, nint hWnd, nint prcRect);
    [DllImport("user32.dll")]  private static extern bool DestroyMenu(nint hMenu);
    [DllImport("user32.dll")]  private static extern bool GetCursorPos(out POINT lpPoint);
    [DllImport("user32.dll")]  private static extern bool SetForegroundWindow(nint hWnd);

    private const uint NIM_ADD    = 0x00;
    private const uint NIM_MODIFY = 0x01;
    private const uint NIM_DELETE = 0x02;
    private const uint NIF_ICON   = 0x02;
    private const uint NIF_TIP    = 0x04;
    private const uint NIF_MESSAGE = 0x01;
    private const uint WM_APP_TRAY = 0x8000 + 1;
    private const uint MF_STRING   = 0x00;
    private const uint TPM_BOTTOMALIGN = 0x0020;
    private const uint TPM_RIGHTALIGN  = 0x0008;
    private const uint TPM_RETURNCMD   = 0x0100;
    private const int  ID_SETTINGS = 1001;
    private const int  ID_QUIT     = 1002;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct NOTIFYICONDATA
    {
        public uint cbSize;
        public nint hWnd;
        public uint uID;
        public uint uFlags;
        public uint uCallbackMessage;
        public nint hIcon;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
        public string szTip;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct POINT { public int x, y; }

    // ── state ──────────────────────────────────────────────────────────
    private readonly Action _onOpenSettings;
    private readonly Action _onQuit;
    private NOTIFYICONDATA _nid;
    private Icon?  _currentIcon;
    private Icon?  _previousIcon;  // kept alive until next update so Windows can read the handle
    private bool   _added;

    // We need an HWND for Shell_NotifyIcon — use a hidden WPF window as message sink
    private readonly System.Windows.Window _msgWindow;
    private nint _hwnd;

    public TrayManager(Action onOpenSettings, Action onQuit)
    {
        _onOpenSettings = onOpenSettings;
        _onQuit         = onQuit;

        _msgWindow = new System.Windows.Window
        {
            Width = 0, Height = 0,
            WindowStyle = WindowStyle.None,
            ShowInTaskbar = false,
            Visibility = Visibility.Hidden,
        };
        _msgWindow.Show();
        _hwnd = new System.Windows.Interop.WindowInteropHelper(_msgWindow).Handle;

        // Hook WndProc for tray callback message
        System.Windows.Interop.HwndSource.FromHwnd(_hwnd)
            ?.AddHook(WndProc);

        Add();
    }

    private void Add()
    {
        _currentIcon = MakeIcon(TrayStatus.Ready);
        _nid = new NOTIFYICONDATA
        {
            cbSize          = (uint)Marshal.SizeOf<NOTIFYICONDATA>(),
            hWnd            = _hwnd,
            uID             = 1,
            uFlags          = NIF_ICON | NIF_TIP | NIF_MESSAGE,
            uCallbackMessage = WM_APP_TRAY,
            hIcon           = _currentIcon.Handle,
            szTip           = "Blitztext",
        };
        Shell_NotifyIcon(NIM_ADD, ref _nid);
        _added = true;
    }

    public void SetStatus(TrayStatus status, string? mode = null)
    {
        // Shell_NotifyIcon must run on the UI thread
        if (!System.Windows.Application.Current.Dispatcher.CheckAccess())
        {
            System.Windows.Application.Current.Dispatcher.Invoke(() => SetStatus(status, mode));
            return;
        }

        _previousIcon?.Dispose();
        _previousIcon = _currentIcon;
        _currentIcon  = MakeIcon(status, mode);
        _nid.hIcon   = _currentIcon.Handle;
        _nid.szTip   = status switch
        {
            TrayStatus.Recording  => $"Blitztext — Aufnahme ({mode ?? ""})",
            TrayStatus.Processing => "Blitztext — Verarbeite…",
            TrayStatus.Error      => "Blitztext — Fehler",
            _                     => "Blitztext",
        };
        if (_added) Shell_NotifyIcon(NIM_MODIFY, ref _nid);
    }

    private nint WndProc(nint hwnd, int msg, nint wParam, nint lParam, ref bool handled)
    {
        if ((uint)msg == WM_APP_TRAY)
        {
            uint notif = (uint)(lParam & 0xFFFF);
            if (notif == 0x0205 /* WM_RBUTTONUP */ || notif == 0x007F /* NIN_KEYSELECT */)
            {
                ShowContextMenu();
                handled = true;
            }
            else if (notif == 0x0203 /* WM_LBUTTONDBLCLK */)
            {
                _onOpenSettings();
                handled = true;
            }
        }
        return nint.Zero;
    }

    private void ShowContextMenu()
    {
        GetCursorPos(out var pt);
        nint menu = CreatePopupMenu();
        AppendMenu(menu, MF_STRING, ID_SETTINGS, "Einstellungen");
        AppendMenu(menu, MF_STRING, ID_QUIT,     "Beenden");

        // Bring window to foreground so menu dismisses correctly
        SetForegroundWindow(_hwnd);

        uint cmd = TrackPopupMenu(menu,
            TPM_BOTTOMALIGN | TPM_RIGHTALIGN | TPM_RETURNCMD,
            pt.x, pt.y, 0, _hwnd, nint.Zero);
        DestroyMenu(menu);

        if (cmd == ID_SETTINGS) _onOpenSettings();
        else if (cmd == ID_QUIT) _onQuit();
    }

    // ── icon generation ───────────────────────────────────────────────
    private static Icon MakeIcon(TrayStatus status, string? mode = null)
    {
        using var bmp = new Bitmap(64, 64);
        using var g   = Graphics.FromImage(bmp);
        g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;

        Color fill = status switch
        {
            TrayStatus.Recording  => Color.FromArgb(220, 60, 60),
            TrayStatus.Processing => Color.FromArgb(230, 180, 0),
            TrayStatus.Error      => Color.FromArgb(200, 50, 50),
            _                     => Color.FromArgb(0, 160, 220),
        };

        g.FillEllipse(new SolidBrush(fill), 4, 4, 56, 56);

        // Mic symbol
        using var white = new SolidBrush(Color.White);
        g.FillRoundedRectangle(white, new Rectangle(24, 10, 16, 24), 8);
        using var pen = new System.Drawing.Pen(Color.White, 3);
        g.DrawArc(pen, 12, 22, 40, 24, 0, 180);
        g.DrawLine(pen, 32, 46, 32, 54);

        nint hIcon = bmp.GetHicon();
        return Icon.FromHandle(hIcon);
    }

    public void Dispose()
    {
        if (_added)
        {
            Shell_NotifyIcon(NIM_DELETE, ref _nid);
            _added = false;
        }
        _previousIcon?.Dispose();
        _currentIcon?.Dispose();
        _msgWindow.Close();
    }
}

// Extension so we can draw rounded rectangles (GDI+ helper)
internal static class GraphicsExtensions
{
    public static void FillRoundedRectangle(this Graphics g, Brush brush, Rectangle rect, int radius)
    {
        using var path = new System.Drawing.Drawing2D.GraphicsPath();
        path.AddArc(rect.X, rect.Y, radius * 2, radius * 2, 180, 90);
        path.AddArc(rect.Right - radius * 2, rect.Y, radius * 2, radius * 2, 270, 90);
        path.AddArc(rect.Right - radius * 2, rect.Bottom - radius * 2, radius * 2, radius * 2, 0, 90);
        path.AddArc(rect.X, rect.Bottom - radius * 2, radius * 2, radius * 2, 90, 90);
        path.CloseFigure();
        g.FillPath(brush, path);
    }
}
