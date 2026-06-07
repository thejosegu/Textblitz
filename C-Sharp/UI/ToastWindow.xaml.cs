using System;
using System.Windows;
using System.Windows.Media.Animation;

namespace Blitztext.UI;

public partial class ToastWindow : Window
{
    private const int DisplayMs = 2800;

    public ToastWindow(string message)
    {
        InitializeComponent();
        MessageText.Text = message.Length > 200 ? message[..200] + "…" : message;
        PositionBottomRight();
    }

    public static void Show(string message)
    {
        var w = new ToastWindow(message);
        w.Show();

        var timer = new System.Windows.Threading.DispatcherTimer
        {
            Interval = TimeSpan.FromMilliseconds(DisplayMs),
        };
        timer.Tick += (_, _) =>
        {
            timer.Stop();
            var fade = new DoubleAnimation(1, 0, TimeSpan.FromMilliseconds(300));
            fade.Completed += (_, _) => w.Close();
            w.BeginAnimation(OpacityProperty, fade);
        };
        timer.Start();
    }

    private void PositionBottomRight()
    {
        var screen = SystemParameters.WorkArea;
        Left = screen.Right  - Width  - 16;
        Top  = screen.Bottom - Height - 16;
    }
}
