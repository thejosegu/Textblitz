using System;
using System.Collections.Generic;
using System.Reflection;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Blitztext.Core;

namespace Blitztext.UI;

/// <summary>Feedback-Tab: API status, last result, environment info, log with auto-refresh.</summary>
public class FeedbackTab : UserControl
{
    private readonly AppConfig _config;

    private TextBlock? _providerLabel;
    private TextBlock? _keyStatusLabel;
    private TextBlock? _hotkeysLabel;
    private TextBlock? _transcriptLabel;
    private TextBlock? _outputLabel;
    private TextBlock? _errorLabel;
    private TextBox?   _logBox;

    public FeedbackTab(AppConfig config)
    {
        _config = config;
        Content = BuildUi();
    }

    private UIElement BuildUi()
    {
        var scroll = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        var stack  = new StackPanel { Margin = new Thickness(8, 4, 8, 8) };
        scroll.Content = stack;

        // ── API Status ──
        stack.Children.Add(MakeCardWith("API-Status", inner =>
        {
            _providerLabel  = AddStatusRow(inner, "Anbieter", "—");
            _keyStatusLabel = AddStatusRow(inner, "API-Key",  "—");
            _hotkeysLabel   = AddStatusRow(inner, "Hotkeys",  "—");
            _hotkeysLabel.TextWrapping = TextWrapping.Wrap;
        }));

        // ── Last Result ──
        stack.Children.Add(MakeCardWith("Letztes Ergebnis", inner =>
        {
            _transcriptLabel = AddStatusRow(inner, "Transkript", "—");
            _outputLabel     = AddStatusRow(inner, "Ausgabe",    "—");
            _errorLabel      = AddStatusRow(inner, "Fehler",     "—");
            _transcriptLabel.TextWrapping = TextWrapping.Wrap;
            _outputLabel.TextWrapping     = TextWrapping.Wrap;
            _errorLabel.TextWrapping      = TextWrapping.Wrap;
        }));

        // ── Environment ──
        stack.Children.Add(MakeCardWith("Umgebung", inner =>
        {
            foreach (var (k, v) in CollectEnv())
                AddEnvRow(inner, k, v);
        }));

        // ── Log ──
        stack.Children.Add(MakeCardWith("Ereignis-Log", inner =>
        {
            _logBox = new TextBox
            {
                IsReadOnly  = true,
                AcceptsReturn = true,
                MinHeight   = 120,
                MaxHeight   = 200,
                VerticalScrollBarVisibility   = ScrollBarVisibility.Auto,
                HorizontalScrollBarVisibility = ScrollBarVisibility.Auto,
                FontFamily  = new FontFamily("Cascadia Code, Consolas"),
                FontSize    = 11,
            };
            _logBox.SetResourceReference(StyleProperty, "Input");
            inner.Children.Add(_logBox);

            var btnRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 6, 0, 0) };
            var refreshBtn = new Button { Content = "Aktualisieren", Margin = new Thickness(0, 0, 6, 0) };
            refreshBtn.Click += (_, _) => Refresh();
            var clearBtn = new Button { Content = "Log leeren" };
            clearBtn.Click += (_, _) => { AppLog.Clear(); Refresh(); };
            btnRow.Children.Add(refreshBtn);
            btnRow.Children.Add(clearBtn);
            inner.Children.Add(btnRow);
        }));

        return scroll;
    }

    public void Refresh()
    {
        // Provider / Key
        _providerLabel!.Text = _config.DetectProvider();

        var key = _config.ApiKey;
        if (!string.IsNullOrEmpty(key))
        {
            var masked = key.Length > 10
                ? key[..6] + "…" + key[^4..]
                : "gesetzt";
            _keyStatusLabel!.Text       = $"✓  {masked}";
            _keyStatusLabel.Foreground  = (Brush)FindResource("GreenBrush");
        }
        else
        {
            _keyStatusLabel!.Text       = "✕  Nicht gesetzt";
            _keyStatusLabel.Foreground  = (Brush)FindResource("RedBrush");
        }

        // Hotkeys
        var hkParts = new List<string>();
        foreach (var mode in new[] { "normal", "plus", "rage", "emoji" })
        {
            var label = mode switch { "plus" => "Plus", "rage" => "Rage", "emoji" => "Emoji", _ => "Normal" };
            hkParts.Add($"{label}: {_config.GetHotkey(mode) ?? "—"}");
        }
        _hotkeysLabel!.Text = string.Join("   ", hkParts);

        // Last results
        var t = AppLog.LastTranscript;
        var o = AppLog.LastProcessed;
        var err = AppLog.LastError;

        _transcriptLabel!.Text = Truncate(t, 120);
        _outputLabel!.Text     = Truncate(o, 120);
        _errorLabel!.Text      = Truncate(err, 120);
        _errorLabel.Foreground = !string.IsNullOrEmpty(err)
            ? (Brush)FindResource("RedBrush")
            : (Brush)FindResource("MutedBrush");

        // Log
        var entries = AppLog.GetAll();
        var all = new System.Text.StringBuilder();
        for (int i = entries.Count - 1; i >= 0; i--)
            all.AppendLine(entries[i]);
        _logBox!.Text = all.ToString();
    }

    // ── helpers ───────────────────────────────────────────────────────

    private static string Truncate(string s, int max) =>
        string.IsNullOrEmpty(s) ? "—"
        : s.Length > max ? s[..max] + "…" : s;

    private static Border MakeCardWith(string title, Action<StackPanel> build)
    {
        var inner = new StackPanel();
        var header = new TextBlock { Text = title };
        header.SetResourceReference(TextBlock.StyleProperty, "SectionHeader");
        inner.Children.Add(header);
        build(inner);

        var border = new Border
        {
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(14, 10, 14, 10),
            Margin  = new Thickness(0, 0, 0, 8),
            Child   = inner,
        };
        border.SetResourceReference(Border.BackgroundProperty, "CardBackground");
        return border;
    }

    private static TextBlock AddStatusRow(StackPanel parent, string label, string value)
    {
        var grid = new Grid { Margin = new Thickness(0, 2, 0, 2) };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(110) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

        var lbl = new TextBlock { Text = label, FontSize = 11 };
        lbl.SetResourceReference(TextBlock.ForegroundProperty, "MutedBrush");
        Grid.SetColumn(lbl, 0);

        var val = new TextBlock { Text = value };
        Grid.SetColumn(val, 1);

        grid.Children.Add(lbl);
        grid.Children.Add(val);
        parent.Children.Add(grid);
        return val;
    }

    private static void AddEnvRow(StackPanel parent, string label, string value)
    {
        var val = AddStatusRow(parent, label, value);
        val.FontFamily = new FontFamily("Cascadia Code, Consolas");
        val.FontSize   = 11;
    }

    private static List<(string, string)> CollectEnv()
    {
        var rows = new List<(string, string)>
        {
            ("Runtime", System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription),
            ("OS",      System.Runtime.InteropServices.RuntimeInformation.OSDescription),
        };

        // NAudio version
        try
        {
            var ver = Assembly.GetAssembly(typeof(NAudio.Wave.WaveInEvent))?.GetName().Version?.ToString() ?? "—";
            rows.Add(("NAudio", ver));
        }
        catch { rows.Add(("NAudio", "—")); }

        // Default microphone
        try
        {
            if (NAudio.Wave.WaveIn.DeviceCount > 0)
            {
                var cap = NAudio.Wave.WaveIn.GetCapabilities(0);
                rows.Add(("Mikrofon", cap.ProductName));
            }
        }
        catch { rows.Add(("Mikrofon", "nicht erkannt")); }

        return rows;
    }
}
