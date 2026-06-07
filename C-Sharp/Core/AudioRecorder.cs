using System;
using System.IO;
using System.Threading;
using NAudio.Wave;

namespace Blitztext.Core;

/// <summary>
/// Records audio from the default microphone into an in-memory WAV buffer.
/// Uses NAudio WaveInEvent (async, callback-based).
/// </summary>
public sealed class AudioRecorder : IDisposable
{
    private const int SampleRate = 16_000;
    private const int Channels   = 1;
    private const int BitDepth   = 16;

    private WaveInEvent?    _waveIn;
    private MemoryStream?   _ms;
    private WaveFileWriter? _writer;
    private readonly Lock   _lock = new();
    private bool            _recording;

    public bool IsRecording => _recording;

    public void Start()
    {
        lock (_lock)
        {
            if (_recording) return;

            _ms     = new MemoryStream();
            var fmt = new WaveFormat(SampleRate, BitDepth, Channels);
            _writer = new WaveFileWriter(_ms, fmt);

            _waveIn = new WaveInEvent
            {
                WaveFormat  = fmt,
                BufferMilliseconds = 50,
            };
            _waveIn.DataAvailable    += OnData;
            _waveIn.RecordingStopped += OnStopped;
            _waveIn.StartRecording();
            _recording = true;
        }
    }

    /// <summary>
    /// Stop recording and return a seeked MemoryStream containing a valid WAV file.
    /// Returns null if no audio was captured.
    /// </summary>
    public MemoryStream? Stop()
    {
        WaveInEvent?    wi;
        WaveFileWriter? wf;
        MemoryStream?   ms;

        lock (_lock)
        {
            if (!_recording) return null;
            _recording = false;
            wi = _waveIn;
            wf = _writer;
            ms = _ms;
            _waveIn  = null;
            _writer  = null;
            _ms      = null;
        }

        wi?.StopRecording();
        wi?.Dispose();

        wf?.Flush();
        wf?.Dispose();   // finalises WAV header — also disposes ms internally

        // MemoryStream.ToArray() is documented to work even after Close/Dispose
        byte[]? bytes = ms?.ToArray();
        ms?.Dispose();

        if (bytes == null || bytes.Length == 0)
            return null;

        return new MemoryStream(bytes);
    }

    private void OnData(object? sender, WaveInEventArgs e)
    {
        lock (_lock)
        {
            if (_recording)
                _writer?.Write(e.Buffer, 0, e.BytesRecorded);
        }
    }

    private static void OnStopped(object? sender, StoppedEventArgs e)
    {
        if (e.Exception != null)
            AppLog.Add($"Aufnahme-Fehler: {e.Exception.Message}");
    }

    public void Dispose()
    {
        Stop()?.Dispose();
    }
}
