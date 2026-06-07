using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using Blitztext.Core;

namespace Blitztext.UI;

/// <summary>Modi-Tab: Prompt TextBoxen für Plus/Rage/Emoji + Emoji-Density-Slider.</summary>
public class ModesTab : UserControl
{
    private readonly AppConfig _config;

    private TextBox? _plusBox, _rageBox, _emojiBox;
    private Slider?  _densitySlider;
    private TextBlock? _densityLabel;

    private static readonly (string Key, string Label, string Hint)[] ModeInfos =
    [
        ("plus",  "Plus-Modus",  "Formuliert gesprochenen Text schriftlicher um."),
        ("rage",  "Rage-Modus",  "Wandelt wütenden Text in eine höfliche Nachricht."),
        ("emoji", "Emoji-Modus", "Fügt passende Emojis in den Text ein."),
    ];

    public ModesTab(AppConfig config)
    {
        _config = config;
        Content = BuildUi();
    }

    private UIElement BuildUi()
    {
        var scroll = new ScrollViewer
        {
            VerticalScrollBarVisibility   = ScrollBarVisibility.Auto,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
        };
        var stack  = new StackPanel { Margin = new Thickness(8, 4, 8, 8) };
        scroll.Content = stack;

        foreach (var (key, label, hint) in ModeInfos)
        {
            var box = new TextBox
            {
                AcceptsReturn = true,
                TextWrapping  = TextWrapping.Wrap,
                MinHeight     = 60,
                MaxHeight     = 100,
                VerticalScrollBarVisibility   = ScrollBarVisibility.Auto,
                HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
            };
            box.SetResourceReference(StyleProperty, "Input");

            switch (key)
            {
                case "plus":  _plusBox  = box; break;
                case "rage":  _rageBox  = box; break;
                case "emoji": _emojiBox = box; break;
            }

            stack.Children.Add(MakeCard(label, hint, box));
        }

        // Emoji Density
        stack.Children.Add(MakeDensityCard());

        return scroll;
    }

    private UIElement MakeDensityCard()
    {
        var inner = new StackPanel();
        inner.Children.Add(MakeHeader("Emoji-Dichte"));
        inner.Children.Add(MakeHint("Wie viele Emojis sollen eingefügt werden?"));

        // Value display
        var valueRow = new DockPanel { Margin = new Thickness(0, 0, 0, 4) };
        var lblLow  = MakeHint("Wenige"); lblLow.Margin = new Thickness(0);
        var lblHigh = MakeHint("Viele");  lblHigh.Margin = new Thickness(0);
        _densityLabel = new TextBlock
        {
            FontWeight = FontWeights.SemiBold,
            MinWidth   = 24,
            TextAlignment = TextAlignment.Right,
        };
        _densityLabel.SetResourceReference(TextBlock.ForegroundProperty, "ForegroundBrush");

        DockPanel.SetDock(lblLow,        System.Windows.Controls.Dock.Left);
        DockPanel.SetDock(_densityLabel, System.Windows.Controls.Dock.Right);
        DockPanel.SetDock(lblHigh,       System.Windows.Controls.Dock.Right);
        valueRow.Children.Add(lblLow);
        valueRow.Children.Add(_densityLabel);
        valueRow.Children.Add(lblHigh);

        _densitySlider = new Slider
        {
            Minimum  = 1,
            Maximum  = 10,
            TickFrequency = 1,
            IsSnapToTickEnabled = true,
        };
        _densitySlider.ValueChanged += (_, e) =>
            _densityLabel.Text = ((int)e.NewValue).ToString();

        inner.Children.Add(valueRow);
        inner.Children.Add(_densitySlider);
        return WrapCard(inner);
    }

    private static UIElement MakeCard(string header, string hint, TextBox box)
    {
        var inner = new StackPanel();
        inner.Children.Add(MakeHeader(header));
        inner.Children.Add(MakeHint(hint));
        inner.Children.Add(box);
        return WrapCard(inner);
    }

    private static Border WrapCard(UIElement content)
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

    private static TextBlock MakeHeader(string text)
    {
        var tb = new TextBlock { Text = text };
        tb.SetResourceReference(TextBlock.StyleProperty, "SectionHeader");
        return tb;
    }

    private static TextBlock MakeHint(string text)
    {
        var tb = new TextBlock { Text = text, TextWrapping = TextWrapping.Wrap };
        tb.SetResourceReference(TextBlock.ForegroundProperty, "MutedBrush");
        tb.FontSize = 11;
        tb.Margin = new Thickness(0, 0, 0, 6);
        return tb;
    }

    public void Load()
    {
        _plusBox!.Text  = _config.GetPrompt("plus");
        _rageBox!.Text  = _config.GetPrompt("rage");
        _emojiBox!.Text = _config.GetPrompt("emoji");
        _densitySlider!.Value = _config.EmojiDensity;
        _densityLabel!.Text   = _config.EmojiDensity.ToString();
    }

    public void Save(AppConfig config)
    {
        config.SetPrompt("plus",  _plusBox!.Text.Trim());
        config.SetPrompt("rage",  _rageBox!.Text.Trim());
        config.SetPrompt("emoji", _emojiBox!.Text.Trim());
        config.EmojiDensity = (int)_densitySlider!.Value;
    }
}
