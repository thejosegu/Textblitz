using System.Windows;
using Blitztext.Core;
using Blitztext.UI;

namespace Blitztext;

public partial class App : Application
{
    private BlitztextApp? _app;
    private SettingsWindow? _settingsWindow;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        // DPI awareness
        try { NativeMethods.SetProcessDpiAwarenessContext(-4); } catch { }

        var config = new AppConfig();
        _app = new BlitztextApp(config);

        var overlay = new RecordingOverlay();

        _app.OnOverlayRecording = mode =>
            Dispatcher.Invoke(() => overlay.ShowRecording(mode));

        _app.OnOverlayProcessing = () =>
            Dispatcher.Invoke(() => overlay.ShowProcessing());

        _app.OnOverlayHide = () =>
            Dispatcher.Invoke(() => overlay.HideOverlay());

        _app.OnOverlayHideImmediate = () =>
            Dispatcher.Invoke(() => overlay.HideImmediate());

        _app.OnOpenSettings = () =>
            Dispatcher.Invoke(() => EnsureSettingsOpen(config));
    }

    private void EnsureSettingsOpen(AppConfig config)
    {
        if (_settingsWindow is { IsVisible: true })
        {
            _settingsWindow.Activate();
            return;
        }

        _settingsWindow = new SettingsWindow(config);
        _settingsWindow.OnSaved += updatedConfig =>
        {
            // hotkeys and config already updated inside SettingsWindow
        };
        _settingsWindow.Show();
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _app?.Dispose();
        base.OnExit(e);
    }
}

internal static class NativeMethods
{
    [System.Runtime.InteropServices.DllImport("user32.dll")]
    internal static extern bool SetProcessDpiAwarenessContext(int value);
}
