using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using Blitztext.Core;

namespace Blitztext.UI;

/// <summary>Snippets-Tab: dynamic keyword → replacement rows.</summary>
public class SnippetsTab : UserControl
{
    private readonly AppConfig _config;
    private StackPanel? _rowsPanel;

    private readonly List<(TextBox Keyword, TextBox Text)> _rows = [];

    public SnippetsTab(AppConfig config)
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
        var outer  = new StackPanel { Margin = new Thickness(8, 4, 8, 8) };
        scroll.Content = outer;

        var card = new Border
        {
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(14, 10, 14, 10),
        };
        card.SetResourceReference(Border.BackgroundProperty, "CardBackground");

        var inner = new StackPanel();
        card.Child = inner;

        var header = new TextBlock { Text = "Snippets" };
        header.SetResourceReference(TextBlock.StyleProperty, "SectionHeader");
        inner.Children.Add(header);

        var hint = new TextBlock
        {
            Text = "Sprich ein Keyword — es wird automatisch durch den definierten Text ersetzt.\n" +
                   "Groß-/Kleinschreibung wird ignoriert.",
            TextWrapping = TextWrapping.Wrap,
            FontSize = 11,
            Margin = new Thickness(0, 0, 0, 10),
        };
        hint.SetResourceReference(TextBlock.ForegroundProperty, "MutedBrush");
        inner.Children.Add(hint);

        // Column headers
        var hdrRow = new Grid { Margin = new Thickness(0, 0, 0, 4) };
        hdrRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(150) });
        hdrRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        hdrRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(30) });

        var kwHdr  = new TextBlock { Text = "Keyword", FontWeight = FontWeights.SemiBold };
        var txtHdr = new TextBlock { Text = "Ersatztext", FontWeight = FontWeights.SemiBold };
        Grid.SetColumn(kwHdr,  0);
        Grid.SetColumn(txtHdr, 1);
        hdrRow.Children.Add(kwHdr);
        hdrRow.Children.Add(txtHdr);
        inner.Children.Add(hdrRow);

        _rowsPanel = new StackPanel();
        inner.Children.Add(_rowsPanel);

        var addBtn = new Button
        {
            Content = "+ Snippet hinzufügen",
            HorizontalAlignment = HorizontalAlignment.Left,
            Margin = new Thickness(0, 10, 0, 0),
        };
        addBtn.Click += (_, _) => AddRow("", "");
        inner.Children.Add(addBtn);

        outer.Children.Add(card);
        return scroll;
    }

    private void AddRow(string keyword, string text)
    {
        var kwBox = new TextBox { Margin = new Thickness(0, 0, 6, 0) };
        kwBox.SetResourceReference(StyleProperty, "Input");
        kwBox.Text = keyword;

        var txtBox = new TextBox { Margin = new Thickness(0, 0, 6, 0) };
        txtBox.SetResourceReference(StyleProperty, "Input");
        txtBox.Text = text;

        var pair = (kwBox, txtBox);
        _rows.Add(pair);

        var grid = new Grid { Margin = new Thickness(0, 3, 0, 3) };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(150) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(30) });

        Grid.SetColumn(kwBox,  0);
        Grid.SetColumn(txtBox, 1);

        var delBtn = new Button { Content = "×", Width = 26 };
        delBtn.SetResourceReference(Button.ForegroundProperty, "RedBrush");
        Grid.SetColumn(delBtn, 2);
        delBtn.Click += (_, _) =>
        {
            _rows.Remove(pair);
            _rowsPanel!.Children.Remove(grid);
        };

        grid.Children.Add(kwBox);
        grid.Children.Add(txtBox);
        grid.Children.Add(delBtn);

        _rowsPanel!.Children.Add(grid);
    }

    public void Load()
    {
        _rows.Clear();
        _rowsPanel!.Children.Clear();
        foreach (var s in _config.Snippets)
            AddRow(s.Keyword, s.Text);
    }

    public void Save(AppConfig config)
    {
        var list = new List<SnippetEntry>();
        foreach (var (kw, txt) in _rows)
        {
            var k = kw.Text.Trim();
            if (!string.IsNullOrEmpty(k))
                list.Add(new SnippetEntry(k, txt.Text.Trim()));
        }
        config.Snippets = list;
    }
}
