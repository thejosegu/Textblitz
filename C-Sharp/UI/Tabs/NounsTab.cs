using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using Blitztext.Core;

namespace Blitztext.UI;

/// <summary>Eigennamen-Tab: multi-line TextBox, one noun per line.</summary>
public class NounsTab : UserControl
{
    private readonly AppConfig _config;
    private TextBox? _nounsBox;

    public NounsTab(AppConfig config)
    {
        _config = config;
        Content = BuildUi();
    }

    private UIElement BuildUi()
    {
        var grid = new Grid { Margin = new Thickness(8, 4, 8, 8) };
        grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

        var card = new Border { CornerRadius = new CornerRadius(8), Padding = new Thickness(14, 10, 14, 10) };
        card.SetResourceReference(Border.BackgroundProperty, "CardBackground");
        Grid.SetRow(card, 0);

        var inner = new Grid();
        inner.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        inner.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        inner.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

        var header = new TextBlock { Text = "Eigennamen" };
        header.SetResourceReference(TextBlock.StyleProperty, "SectionHeader");
        Grid.SetRow(header, 0);

        var hint = new TextBlock
        {
            Text = "Helfen Whisper, Markennamen, Personen und Fachbegriffe korrekt zu erkennen.\n" +
                   "Ein Begriff pro Zeile.",
            TextWrapping = TextWrapping.Wrap,
            FontSize = 11,
            Margin = new Thickness(0, 0, 0, 8),
        };
        hint.SetResourceReference(TextBlock.ForegroundProperty, "MutedBrush");
        Grid.SetRow(hint, 1);

        _nounsBox = new TextBox
        {
            AcceptsReturn = true,
            TextWrapping  = TextWrapping.NoWrap,
            VerticalScrollBarVisibility   = ScrollBarVisibility.Auto,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Auto,
            MinHeight = 120,
            FontFamily = new System.Windows.Media.FontFamily("Cascadia Code, Consolas"),
        };
        _nounsBox.SetResourceReference(StyleProperty, "Input");
        Grid.SetRow(_nounsBox, 2);

        inner.Children.Add(header);
        inner.Children.Add(hint);
        inner.Children.Add(_nounsBox);
        card.Child = inner;
        grid.Children.Add(card);

        return grid;
    }

    public void Load()
    {
        _nounsBox!.Text = string.Join("\n", _config.ProperNouns);
    }

    public void Save(AppConfig config)
    {
        var nouns = new List<string>();
        foreach (var line in _nounsBox!.Text.Split('\n'))
        {
            var t = line.Trim();
            if (!string.IsNullOrEmpty(t)) nouns.Add(t);
        }
        config.ProperNouns = nouns;
    }
}
