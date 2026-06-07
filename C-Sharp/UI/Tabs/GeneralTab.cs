using System.Windows;
using System.Windows.Controls;
using Microsoft.Win32;
using Blitztext.Core;

namespace Blitztext.UI;

/// <summary>Allgemein-Tab: Transkriptions-Modus, API Key, Sprache, Aufnahme-Modus, Autostart.</summary>
public class GeneralTab : UserControl
{
    private readonly AppConfig _config;

    private RadioButton? _modeApi, _modeLocal;
    private StackPanel?  _apiKeyCard;
    private StackPanel?  _localModelCard;

    private TextBox?     _apiKeyBox;
    private PasswordBox? _apiKeyPwd;
    private bool         _showingKey;
    private Button?      _toggleBtn;

    private TextBox?     _modelPathBox;

    private ComboBox?    _langCombo;
    private RadioButton? _holdMode, _toggleMode;
    private CheckBox?    _autostartCheck;

    private static readonly string[] Languages =
        ["auto", "de", "en", "fr", "es", "it", "pt", "nl", "pl", "ru", "zh", "ja"];

    public GeneralTab(AppConfig config)
    {
        _config = config;
        Content = BuildUi();
    }

    private UIElement BuildUi()
    {
        var scroll = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        var stack  = new StackPanel { Margin = new Thickness(8, 4, 8, 8) };
        scroll.Content = stack;

        // ── Transkriptions-Modus ──
        stack.Children.Add(MakeCard(card =>
        {
            card.Children.Add(MakeHeader("Transkriptions-Modus"));
            _modeApi   = new RadioButton { Content = "API  —  OpenAI oder Groq (Internet erforderlich)" };
            _modeLocal = new RadioButton { Content = "Lokal  —  Whisper auf diesem PC (kein Internet)",
                Margin = new Thickness(0, 4, 0, 0) };
            _modeApi.Checked   += (_, _) => UpdateModeVisibility();
            _modeLocal.Checked += (_, _) => UpdateModeVisibility();
            card.Children.Add(_modeApi);
            card.Children.Add(_modeLocal);
        }));

        // ── API Key (nur bei API-Modus) ──
        _apiKeyCard = MakeCard(card =>
        {
            card.Children.Add(MakeHeader("API Key"));
            card.Children.Add(MakeHint("OpenAI (sk-…) oder Groq (gsk_…)"));

            var row = new DockPanel { LastChildFill = true };
            _toggleBtn = new Button { Content = "Anzeigen", Width = 80,
                Margin = new Thickness(8, 0, 0, 0) };
            _toggleBtn.Click += ToggleKeyVisibility;
            DockPanel.SetDock(_toggleBtn, Dock.Right);
            row.Children.Add(_toggleBtn);

            _apiKeyPwd = new PasswordBox { PasswordChar = '●' };
            _apiKeyPwd.SetResourceReference(StyleProperty, "PasswordInput");
            row.Children.Add(_apiKeyPwd);

            _apiKeyBox = new TextBox { Visibility = Visibility.Collapsed };
            _apiKeyBox.SetResourceReference(StyleProperty, "Input");

            card.Children.Add(row);
            card.Children.Add(_apiKeyBox);
        });
        stack.Children.Add(_apiKeyCard);

        // ── Lokales Modell (nur bei lokalem Modus) ──
        _localModelCard = MakeCard(card =>
        {
            card.Children.Add(MakeHeader("Whisper-Modelldatei"));
            card.Children.Add(MakeHint("GGML-Modelldatei auswählen (ggml-small.bin). Download: huggingface.co/ggerganov/whisper.cpp"));

            var row = new DockPanel { LastChildFill = true };
            var browseBtn = new Button { Content = "Durchsuchen…", Width = 110,
                Margin = new Thickness(8, 0, 0, 0) };
            browseBtn.Click += BrowseModel;
            DockPanel.SetDock(browseBtn, Dock.Right);
            row.Children.Add(browseBtn);

            _modelPathBox = new TextBox { IsReadOnly = true };
            _modelPathBox.SetResourceReference(StyleProperty, "Input");
            row.Children.Add(_modelPathBox);

            card.Children.Add(row);
        });
        stack.Children.Add(_localModelCard);

        // ── Sprache ──
        stack.Children.Add(MakeCard(card =>
        {
            card.Children.Add(MakeHeader("Whisper-Sprache"));
            card.Children.Add(MakeHint("'auto' erkennt die Sprache automatisch."));
            _langCombo = new ComboBox { Width = 130, HorizontalAlignment = HorizontalAlignment.Left };
            foreach (var l in Languages) _langCombo.Items.Add(l);
            card.Children.Add(_langCombo);
        }));

        // ── Aufnahme-Modus ──
        stack.Children.Add(MakeCard(card =>
        {
            card.Children.Add(MakeHeader("Aufnahme-Modus"));
            _holdMode   = new RadioButton { Content = "Halten  —  Taste gedrückt halten" };
            _toggleMode = new RadioButton { Content = "Umschalten  —  1× drücken = Start, 1× = Stop",
                Margin = new Thickness(0, 4, 0, 0) };
            card.Children.Add(_holdMode);
            card.Children.Add(_toggleMode);
        }));

        // ── Autostart ──
        stack.Children.Add(MakeCard(card =>
        {
            card.Children.Add(MakeHeader("Autostart"));
            _autostartCheck = new CheckBox
            {
                Content = "Blitztext beim Windows-Start automatisch öffnen"
            };
            card.Children.Add(_autostartCheck);
        }));

        return scroll;
    }

    private void UpdateModeVisibility()
    {
        bool isLocal = _modeLocal?.IsChecked == true;
        if (_apiKeyCard    != null) _apiKeyCard.Visibility     = isLocal ? Visibility.Collapsed : Visibility.Visible;
        if (_localModelCard != null) _localModelCard.Visibility = isLocal ? Visibility.Visible  : Visibility.Collapsed;
    }

    private void BrowseModel(object sender, RoutedEventArgs e)
    {
        var dlg = new OpenFileDialog
        {
            Title  = "Whisper GGML-Modelldatei auswählen",
            Filter = "GGML-Modell (*.bin)|*.bin|Alle Dateien (*.*)|*.*",
        };
        if (dlg.ShowDialog() == true)
            _modelPathBox!.Text = dlg.FileName;
    }

    private void ToggleKeyVisibility(object sender, RoutedEventArgs e)
    {
        _showingKey = !_showingKey;
        if (_showingKey)
        {
            _apiKeyBox!.Text = _apiKeyPwd!.Password;
            _apiKeyPwd.Visibility = Visibility.Collapsed;
            _apiKeyBox.Visibility = Visibility.Visible;
            _toggleBtn!.Content = "Verbergen";
        }
        else
        {
            _apiKeyPwd!.Password = _apiKeyBox!.Text;
            _apiKeyBox.Visibility = Visibility.Collapsed;
            _apiKeyPwd.Visibility = Visibility.Visible;
            _toggleBtn!.Content = "Anzeigen";
        }
    }

    public void Load()
    {
        bool isLocal = _config.TranscribeMode == "local";
        _modeLocal!.IsChecked = isLocal;
        _modeApi!.IsChecked   = !isLocal;

        _apiKeyPwd!.Password = _config.ApiKey;
        _apiKeyBox!.Text     = _config.ApiKey;
        _modelPathBox!.Text  = _config.LocalModelPath;

        _langCombo!.SelectedItem = _config.WhisperLanguage;
        if (_langCombo.SelectedItem == null) _langCombo.SelectedIndex = 0;

        (_config.RecordMode == "toggle" ? _toggleMode : _holdMode)!.IsChecked = true;
        _autostartCheck!.IsChecked = _config.Autostart;

        UpdateModeVisibility();
    }

    public void Save(AppConfig config)
    {
        config.TranscribeMode  = _modeLocal!.IsChecked == true ? "local" : "api";
        config.LocalModelPath  = _modelPathBox!.Text.Trim();
        config.ApiKey          = _showingKey ? _apiKeyBox!.Text.Trim() : _apiKeyPwd!.Password.Trim();
        config.WhisperLanguage = _langCombo!.SelectedItem?.ToString() ?? "auto";
        config.RecordMode      = _toggleMode!.IsChecked == true ? "toggle" : "hold";
        config.Autostart       = _autostartCheck!.IsChecked == true;
    }

    // ── layout helpers ────────────────────────────────────────────────
    private static StackPanel MakeCard(System.Action<StackPanel> build)
    {
        var panel = new StackPanel { Margin = new Thickness(0, 0, 0, 8) };
        var border = new Border();
        border.SetResourceReference(Border.BackgroundProperty, "CardBackground");
        border.CornerRadius = new CornerRadius(8);
        border.Padding = new Thickness(14, 10, 14, 10);
        border.Child = panel;
        build(panel);

        // Wrap in outer panel so margin applies outside the card
        var outer = new StackPanel();
        outer.Children.Add(border);
        return outer;
    }

    private static TextBlock MakeHeader(string text)
    {
        var tb = new TextBlock { Text = text };
        tb.SetResourceReference(TextBlock.StyleProperty, "SectionHeader");
        return tb;
    }

    private static TextBlock MakeHint(string text)
    {
        var tb = new TextBlock { Text = text };
        tb.SetResourceReference(TextBlock.StyleProperty, "Hint");
        return tb;
    }
}
