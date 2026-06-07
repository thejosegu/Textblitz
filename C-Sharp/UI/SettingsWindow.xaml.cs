using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using Blitztext.Core;

namespace Blitztext.UI;

public partial class SettingsWindow : Window
{
    private readonly AppConfig _config;
    public event Action<AppConfig>? OnSaved;

    // ── Tab panels (built programmatically into TabItem.Content) ─────
    private GeneralTab   _general  = null!;
    private HotkeysTab   _hotkeys  = null!;
    private ModesTab     _modes    = null!;
    private SnippetsTab  _snippets = null!;
    private NounsTab     _nouns    = null!;
    private FeedbackTab  _feedback = null!;

    private DispatcherTimer? _feedbackTimer;

    public SettingsWindow(AppConfig config)
    {
        _config = config;
        InitializeComponent();
        ApplyTheme();
        BuildTabs();
        LoadValues();
        StartFeedbackRefresh();

        Closed += (_, _) => _feedbackTimer?.Stop();
    }

    // ── theme ─────────────────────────────────────────────────────────
    private void ApplyTheme()
    {
        bool dark = IsDarkMode();
        if (!dark)
        {
            Resources["WindowBackground"] = new SolidColorBrush(Color.FromRgb(0xF3, 0xF3, 0xF3));
            Resources["CardBackground"]   = new SolidColorBrush(Color.FromRgb(0xFF, 0xFF, 0xFF));
            Resources["AccentBrush"]      = new SolidColorBrush(Color.FromRgb(0x00, 0x78, 0xD4));
            Resources["ForegroundBrush"]  = new SolidColorBrush(Color.FromRgb(0x00, 0x00, 0x00));
            Resources["InputBackground"]  = new SolidColorBrush(Color.FromRgb(0xFF, 0xFF, 0xFF));
            Resources["InputBorder"]      = new SolidColorBrush(Color.FromRgb(0xCC, 0xCC, 0xCC));
            Resources["SeparatorBrush"]          = new SolidColorBrush(Color.FromRgb(0xE0, 0xE0, 0xE0));
            Resources["HoverBrush"]              = new SolidColorBrush(Color.FromArgb(0x0A, 0x00, 0x00, 0x00));
            Resources["ButtonBackground"]        = new SolidColorBrush(Color.FromRgb(0xFB, 0xFB, 0xFB));
            Resources["ButtonBorder"]            = new SolidColorBrush(Color.FromRgb(0xC8, 0xC8, 0xC8));
            Resources["ButtonHoverBackground"]   = new SolidColorBrush(Color.FromRgb(0xF5, 0xF5, 0xF5));
            Resources["ButtonPressedBackground"] = new SolidColorBrush(Color.FromRgb(0xEB, 0xEB, 0xEB));
            Background = (SolidColorBrush)Resources["WindowBackground"];
        }

        // Apply Windows accent color
        var accent = GetWindowsAccentColor();
        if (accent.HasValue)
            Resources["AccentBrush"] = new SolidColorBrush(accent.Value);
    }

    private static bool IsDarkMode()
    {
        try
        {
            using var key = Microsoft.Win32.Registry.CurrentUser.OpenSubKey(
                @"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize");
            return (int)(key?.GetValue("AppsUseLightTheme") ?? 1) == 0;
        }
        catch { return true; }
    }

    private static Color? GetWindowsAccentColor()
    {
        try
        {
            using var key = Microsoft.Win32.Registry.CurrentUser.OpenSubKey(
                @"Software\Microsoft\Windows\Dwm");
            var val = (int)(key?.GetValue("AccentColor") ?? 0);
            if (val == 0) return null;
            // ABGR → ARGB
            byte r = (byte)(val & 0xFF);
            byte g = (byte)((val >> 8) & 0xFF);
            byte b = (byte)((val >> 16) & 0xFF);
            return Color.FromRgb(r, g, b);
        }
        catch { return null; }
    }

    // ── tab construction ──────────────────────────────────────────────
    private void BuildTabs()
    {
        _general  = new GeneralTab(_config);   TabGeneral.Content  = _general;
        _hotkeys  = new HotkeysTab(_config);   TabHotkeys.Content  = _hotkeys;
        _modes    = new ModesTab(_config);     TabModes.Content    = _modes;
        _snippets = new SnippetsTab(_config);  TabSnippets.Content = _snippets;
        _nouns    = new NounsTab(_config);     TabNouns.Content    = _nouns;
        _feedback = new FeedbackTab(_config);  TabFeedback.Content = _feedback;
    }

    private void LoadValues()
    {
        _general.Load();
        _hotkeys.Load();
        _modes.Load();
        _snippets.Load();
        _nouns.Load();
        _feedback.Refresh();
    }

    // ── feedback auto-refresh ─────────────────────────────────────────
    private void StartFeedbackRefresh()
    {
        _feedbackTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(2) };
        _feedbackTimer.Tick += (_, _) =>
        {
            if (TabFeedback.IsSelected)
                _feedback.Refresh();
        };
        _feedbackTimer.Start();
    }

    // ── save / cancel ─────────────────────────────────────────────────
    private void SaveButton_Click(object sender, RoutedEventArgs e)
    {
        _general.Save(_config);
        _hotkeys.Save(_config);
        _modes.Save(_config);
        _snippets.Save(_config);
        _nouns.Save(_config);

        ApplyAutostart(_config.Autostart);

        try { _config.Save(); }
        catch (Exception ex) { AppLog.Add($"Config-Fehler: {ex.Message}"); }

        OnSaved?.Invoke(_config);
        Close();
    }

    private void CancelButton_Click(object sender, RoutedEventArgs e) => Close();

    // ── autostart ────────────────────────────────────────────────────
    private static void ApplyAutostart(bool enable)
    {
        const string RegPath = @"Software\Microsoft\Windows\CurrentVersion\Run";
        var exe = $"\"{Process.GetCurrentProcess().MainModule?.FileName}\"";

        using var key = Microsoft.Win32.Registry.CurrentUser.OpenSubKey(RegPath, writable: true);
        if (key == null) return;

        if (enable)
            key.SetValue("Blitztext", exe);
        else
        {
            try { key.DeleteValue("Blitztext"); } catch { /* already gone */ }
        }
    }
}
