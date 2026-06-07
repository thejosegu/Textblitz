using System;
using System.Threading;
using System.Threading.Tasks;
using Blitztext.Core;
using Blitztext.Tray;

namespace Blitztext;

/// <summary>
/// Main orchestrator — connects HotkeyListener → AudioRecorder → Pipeline.
/// Runs on the WPF UI thread; pipeline executes on a dedicated Task (max 1 at a time).
/// </summary>
public sealed class BlitztextApp : IDisposable
{
    private readonly AppConfig       _config;
    private readonly AudioRecorder   _recorder;
    private readonly HotkeyListener  _hotkeys;
    public  readonly TrayManager     Tray;

    private readonly SemaphoreSlim   _pipelineLock = new(1, 1);
    private bool                     _recordingActive;
    private nint                     _targetHwnd;

    // Callbacks so UI layer can show Toast and recording overlay
    public Action<string>? OnShowToast;
    public Action?         OnOpenSettings;
    public Action<string>? OnOverlayRecording;   // (mode)  — show blinking dot
    public Action?         OnOverlayProcessing;  //         — switch to amber dot
    public Action?         OnOverlayHide;        //         — fade out
    public Action?         OnOverlayHideImmediate; //       — instant hide before inject

    public BlitztextApp(AppConfig config)
    {
        _config   = config;
        _recorder = new AudioRecorder();

        Tray = new TrayManager(
            onOpenSettings: () => OnOpenSettings?.Invoke(),
            onQuit: Quit);

        _hotkeys = new HotkeyListener(
            getHotkeys:    () => _config.Hotkeys,
            onStart:       OnRecordingStart,
            onStop:        OnRecordingStop,
            getRecordMode: () => _config.RecordMode);

        _hotkeys.Start();
        AppLog.Add("Blitztext gestartet — bereit");
    }

    // ── hotkey callbacks (called from hook thread) ────────────────────

    private void OnRecordingStart(string mode)
    {
        if (_config.TranscribeMode != "local" && string.IsNullOrEmpty(_config.ApiKey))
        {
            AppLog.Add("Kein API-Key gesetzt — Einstellungen öffnen");
            Tray.SetStatus(TrayStatus.Error);
            OnOpenSettings?.Invoke();
            return;
        }

        if (_config.TranscribeMode == "local" && !LocalTranscriber.ModelExists(_config.LocalModelPath))
        {
            AppLog.Add("Lokales Modell nicht gefunden — Einstellungen öffnen");
            Tray.SetStatus(TrayStatus.Error);
            OnOpenSettings?.Invoke();
            return;
        }

        if (!_pipelineLock.Wait(0))
        {
            AppLog.Add("Aufnahme ignoriert — vorherige Verarbeitung läuft noch");
            return;
        }

        // Capture BEFORE any Dispatcher call — at this moment the user's window has focus
        _targetHwnd = Injector.CaptureTarget();

        _recordingActive = true;
        AppLog.Add($"Aufnahme gestartet ({mode})");
        Tray.SetStatus(TrayStatus.Recording, mode);
        OnOverlayRecording?.Invoke(mode);
        _recorder.Start();
    }

    private void OnRecordingStop(string mode)
    {
        if (!_recordingActive) return;
        _recordingActive = false;

        AppLog.Add($"Aufnahme gestoppt ({mode})");
        var audio = _recorder.Stop();

        if (audio == null)
        {
            AppLog.Add("Keine Audiodaten — zu kurze Aufnahme?");
            Tray.SetStatus(TrayStatus.Ready);
            OnOverlayHide?.Invoke();
            _pipelineLock.Release();
            return;
        }

        Tray.SetStatus(TrayStatus.Processing, mode);
        OnOverlayProcessing?.Invoke();
        _ = Task.Run(() => RunPipelineAsync(audio, mode));
    }

    // ── pipeline (background Task) ────────────────────────────────────

    private async Task RunPipelineAsync(System.IO.MemoryStream audio, string mode)
    {
        try
        {
            // 1. Transcribe
            string transcript;
            if (_config.TranscribeMode == "local")
            {
                transcript = await LocalTranscriber.TranscribeAsync(
                    audio,
                    modelPath: _config.LocalModelPath,
                    language:  _config.WhisperLanguage);
            }
            else
            {
                transcript = await Transcriber.TranscribeAsync(
                    audio,
                    apiKey:      _config.ApiKey,
                    language:    _config.WhisperLanguage,
                    properNouns: _config.ProperNouns.Count > 0
                                     ? [.. _config.ProperNouns]
                                     : null,
                    model: _config.ActiveWhisperModel);
            }

            AppLog.Add($"Transkript ({mode}): {transcript}");

            // 2. Process (Plus / Rage / Emoji)
            var result = await Processor.ProcessAsync(
                transcript,
                mode:            mode,
                apiKey:          _config.ApiKey,
                promptTemplate:  _config.GetPrompt(mode),
                emojiDensity:    _config.EmojiDensity,
                model:           _config.ActiveChatModel,
                temperature:     _config.Temperature,
                maxTokens:       _config.MaxTokens);

            if (mode != "normal")
                AppLog.Add($"Verarbeitet ({mode}): {result}");

            AppLog.SetLast(transcript, result, mode);

            // 3. Apply snippets
            result = Processor.ApplySnippets(result, _config.Snippets);

            // 4. Inject via clipboard paste — atomic, no per-char flickering.
            //    RawSetClipboard uses Win32 directly (no WPF, no focus change).
            var hwnd = _targetHwnd;
            AppLog.Add($"Inject: target={hwnd:X} title='{Injector.GetWindowTitle(hwnd)}'");

            string? oldClip = Injector.RawGetClipboard();
            Injector.RawSetClipboard(result);

            await App.Current.Dispatcher.InvokeAsync(() => OnOverlayHideImmediate?.Invoke());
            await Task.Delay(50);

            Injector.SendCtrlV();
            await Task.Delay(150);

            Injector.RawSetClipboard(oldClip);
            Tray.SetStatus(TrayStatus.Ready);
        }
        catch (Exception ex)
        {
            AppLog.SetError(ex.Message);
            Tray.SetStatus(TrayStatus.Error);
            OnOverlayHide?.Invoke();
            _ = Task.Delay(3000).ContinueWith(_ => Tray.SetStatus(TrayStatus.Ready));
        }
        finally
        {
            audio.Dispose();
            _pipelineLock.Release();
        }
    }

    // ── lifecycle ─────────────────────────────────────────────────────

    public void Quit()
    {
        _hotkeys.Stop();
        _recorder.Dispose();
        Tray.Dispose();
        App.Current.Dispatcher.Invoke(() => App.Current.Shutdown());
    }

    public void Dispose()
    {
        _hotkeys.Stop();
        _recorder.Dispose();
        Tray.Dispose();
    }
}
