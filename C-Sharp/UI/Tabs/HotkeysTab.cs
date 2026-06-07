using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using Blitztext.Core;

namespace Blitztext.UI;

/// <summary>Hotkeys-Tab: per mode a TextBox + Aufnehmen + Löschen button.</summary>
public class HotkeysTab : UserControl
{
    private readonly AppConfig _config;
    private readonly Dictionary<string, TextBox> _hotkeyBoxes = [];

    private static readonly string[] Modes = ["normal", "plus", "rage", "emoji"];
    private static readonly Dictionary<string, string> ModeLabels = new()
    {
        ["normal"] = "🎙  Normal",
        ["plus"]   = "✏️  Plus",
        ["rage"]   = "😤  Rage",
        ["emoji"]  = "😊  Emoji",
    };

    public HotkeysTab(AppConfig config)
    {
        _config = config;
        Content = BuildUi();
    }

    private UIElement BuildUi()
    {
        var scroll = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        var stack  = new StackPanel { Margin = new Thickness(8, 4, 8, 8) };
        scroll.Content = stack;

        var hint = new TextBlock
        {
            Text = "Drücke 'Aufnehmen' und halte die gewünschte Tastenkombination.\n" +
                   "Tipp: Rechte Sondertasten (Right Ctrl, Right Alt) kollidieren selten mit anderen Apps.",
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(4, 0, 0, 12),
        };
        hint.SetResourceReference(TextBlock.ForegroundProperty, "MutedBrush");
        stack.Children.Add(hint);

        foreach (var mode in Modes)
        {
            var box = new TextBox
            {
                IsReadOnly = true,
                Width      = 200,
                FontFamily = new FontFamily("Cascadia Code, Consolas"),
            };
            box.SetResourceReference(StyleProperty, "Mono");
            _hotkeyBoxes[mode] = box;

            var clearBtn = new Button { Content = "Löschen", Width = 72 };
            clearBtn.Click += (_, _) => box.Text = "";

            var captureBtn = new Button { Content = "Aufnehmen", Width = 90,
                Margin = new Thickness(0, 0, 8, 0) };
            var m = mode; // capture for lambda
            captureBtn.Click += (_, _) => CaptureHotkey(m, box);

            var row = new DockPanel { Margin = new Thickness(0, 0, 0, 0) };
            DockPanel.SetDock(clearBtn, Dock.Right);
            DockPanel.SetDock(captureBtn, Dock.Right);
            DockPanel.SetDock(box, Dock.Right);
            row.Children.Add(new TextBlock
            {
                Text = ModeLabels[mode],
                VerticalAlignment = VerticalAlignment.Center,
                MinWidth = 100,
            });
            row.Children.Add(clearBtn);
            row.Children.Add(captureBtn);
            row.Children.Add(box);

            var card = MakeCard(row);
            stack.Children.Add(card);
        }

        return scroll;
    }

    private void CaptureHotkey(string mode, TextBox box)
    {
        var dlg = new HotkeyCaptureDialog(ModeLabels[mode]);
        dlg.Owner = Window.GetWindow(this);
        if (dlg.ShowDialog() == true && dlg.CapturedSpec != null)
            box.Text = dlg.CapturedSpec;
    }

    public void Load()
    {
        foreach (var mode in Modes)
            _hotkeyBoxes[mode].Text = _config.GetHotkey(mode);
    }

    public void Save(AppConfig config)
    {
        foreach (var mode in Modes)
            config.SetHotkey(mode, _hotkeyBoxes[mode].Text.Trim());
    }

    private static Border MakeCard(UIElement content)
    {
        var border = new Border
        {
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(14, 10, 14, 10),
            Margin  = new Thickness(0, 0, 0, 8),
            Child   = content,
        };
        border.SetResourceReference(Border.BackgroundProperty, "CardBackground");
        return border;
    }
}

/// <summary>Modal dialog that captures a hotkey combination via low-level hook.</summary>
internal sealed class HotkeyCaptureDialog : Window
{
    public string? CapturedSpec { get; private set; }

    private readonly TextBlock _statusLabel;
    private HotkeyListener?    _listener;
    private System.Collections.Generic.HashSet<uint> _captured = [];

    public HotkeyCaptureDialog(string modeLabel)
    {
        Title  = "Hotkey aufnehmen";
        Width  = 340;
        Height = 150;
        ResizeMode   = ResizeMode.NoResize;
        WindowStartupLocation = WindowStartupLocation.CenterOwner;

        var stack = new StackPanel { Margin = new Thickness(20) };

        stack.Children.Add(new TextBlock
        {
            Text = $"Hotkey für {modeLabel}",
            FontWeight = FontWeights.SemiBold,
            Margin = new Thickness(0, 0, 0, 6),
        });
        stack.Children.Add(new TextBlock
        {
            Text = "Halte jetzt die gewünschte Tastenkombination…",
            Foreground = SystemColors.GrayTextBrush,
            FontSize = 11,
        });

        _statusLabel = new TextBlock
        {
            FontFamily = new FontFamily("Cascadia Code, Consolas"),
            Margin = new Thickness(0, 10, 0, 0),
            FontSize = 13,
        };
        _statusLabel.SetResourceReference(ForegroundProperty, "AccentBrush");
        stack.Children.Add(_statusLabel);

        Content = stack;

        Loaded  += (_, _) => StartCapture();
        Closed  += (_, _) => StopCapture();
    }

    private void StartCapture()
    {
        _listener = new HotkeyListener(
            getHotkeys:    () => [],
            onStart:       _ => {},
            onStop:        _ => {},
            getRecordMode: () => "hold");
        _listener.Capturing = false;

        // We use our own low-level hook by re-using HotkeyListener internals
        // Instead: intercept keyboard via WPF PreviewKeyDown on this dialog window
        PreviewKeyDown += OnKeyDown;
        PreviewKeyUp   += OnKeyUp;
        KeyboardNavigation.SetDirectionalNavigation(this, KeyboardNavigationMode.None);
    }

    private void StopCapture()
    {
        _listener?.Dispose();
    }

    private void OnKeyDown(object sender, System.Windows.Input.KeyEventArgs e)
    {
        e.Handled = true;
        var vk = (uint)System.Windows.Input.KeyInterop.VirtualKeyFromKey(e.Key == Key.System ? e.SystemKey : e.Key);
        _captured.Add(vk);
        _statusLabel.Text = HotkeyListener.HotkeyToString(_captured);
    }

    private void OnKeyUp(object sender, System.Windows.Input.KeyEventArgs e)
    {
        e.Handled = true;
        if (_captured.Count > 0)
        {
            CapturedSpec = HotkeyListener.HotkeyToString(_captured);
            DialogResult = true;
        }
    }
}
