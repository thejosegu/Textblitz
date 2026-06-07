using System;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Animation;

namespace Blitztext.UI;

/// <summary>
/// Top-center status overlay — shown while recording or transcribing.
/// Singleton: created once, Show()/Hide() without Close() so WPF state stays intact.
/// </summary>
public partial class RecordingOverlay : Window
{
    private static readonly Color DotRecording  = Color.FromRgb(0xFF, 0x44, 0x44); // red
    private static readonly Color DotProcessing = Color.FromRgb(0xE6, 0xB4, 0x00); // amber

    private Storyboard? _blink;
    private bool        _blinking;

    public RecordingOverlay()
    {
        InitializeComponent();
        _blink = (Storyboard)Resources["BlinkStoryboard"];
    }

    // ── public API (must be called on UI thread) ──────────────────────

    /// <summary>Show with blinking red dot: recording in progress.</summary>
    public void ShowRecording(string mode)
    {
        Dot.Fill        = new SolidColorBrush(DotRecording);
        Dot.Opacity     = 1;
        ModeLabel.Text  = ModeDisplayName(mode);
        StatusLabel.Text = "Aufzeichnung läuft";

        StartBlink();
        EnsureVisible();
    }

    /// <summary>Switch to static amber dot: transcription / processing.</summary>
    public void ShowProcessing()
    {
        StopBlink();
        Dot.Fill    = new SolidColorBrush(DotProcessing);
        Dot.Opacity = 1;
        StatusLabel.Text = "Transkribiere…";
    }

    /// <summary>Fade out and hide (animated).</summary>
    public void HideOverlay()
    {
        StopBlink();

        if (Opacity <= 0 || !IsVisible) return;

        var fadeOut = (Storyboard)Resources["FadeOutStoryboard"];

        // Clone so we can attach Completed without accumulating handlers
        var clone = fadeOut.Clone();
        clone.Completed += (_, _) =>
        {
            Hide();
            Opacity = 0;
        };
        clone.Begin(this);
    }

    /// <summary>Hide instantly without animation — use before injecting text.</summary>
    public void HideImmediate()
    {
        StopBlink();
        Hide();
        Opacity = 0;
    }

    // ── internals ─────────────────────────────────────────────────────

    private void EnsureVisible()
    {
        if (!IsVisible)
        {
            Show();
        }

        Opacity = 0;
        ((Storyboard)Resources["FadeInStoryboard"]).Begin(this);

        // Position after layout is complete
        Dispatcher.InvokeAsync(PositionTopCenter,
            System.Windows.Threading.DispatcherPriority.Render);
    }

    private void StartBlink()
    {
        if (_blinking) return;
        _blink?.Begin(this, isControllable: true);
        _blinking = true;
    }

    private void StopBlink()
    {
        if (!_blinking) return;
        _blink?.Stop(this);
        _blinking = false;
    }

    private void PositionTopCenter()
    {
        var area = SystemParameters.WorkArea;
        Left = area.Left + (area.Width  - ActualWidth)  / 2;
        Top  = area.Top  + 16;
    }

    private static string ModeDisplayName(string mode) => mode switch
    {
        "plus"  => "Plus",
        "rage"  => "Rage",
        "emoji" => "Emoji",
        _       => "Normal",
    };
}
