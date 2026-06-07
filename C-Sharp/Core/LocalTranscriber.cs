using System;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using Whisper.net;
using Whisper.net.Ggml;

namespace Blitztext.Core;

/// <summary>
/// Transcribes audio locally via Whisper.net (whisper.cpp).
/// Requires a GGML model file (e.g. ggml-small.bin).
/// Model is loaded lazily and cached for reuse.
/// </summary>
public static class LocalTranscriber
{
    private static WhisperFactory?    _factory;
    private static WhisperProcessor?  _processor;
    private static string?            _loadedPath;
    private static readonly object    _lock = new();

    public static bool IsModelLoaded => _factory != null;

    /// <summary>
    /// Returns true if the given path points to an existing GGML model file.
    /// </summary>
    public static bool ModelExists(string? path)
        => !string.IsNullOrWhiteSpace(path) && File.Exists(path);

    /// <summary>
    /// Transcribes the given WAV stream using a local GGML Whisper model.
    /// Loads and caches the model on first call (or if path changed).
    /// </summary>
    public static async Task<string> TranscribeAsync(
        MemoryStream audioWav,
        string modelPath,
        string language = "auto")
    {
        if (!File.Exists(modelPath))
            throw new FileNotFoundException($"Whisper-Modell nicht gefunden: {modelPath}");

        EnsureProcessor(modelPath, language);

        audioWav.Position = 0;
        var sb = new StringBuilder();

        await foreach (var seg in _processor!.ProcessAsync(audioWav))
            sb.Append(seg.Text);

        return sb.ToString().Trim();
    }

    private static void EnsureProcessor(string modelPath, string language)
    {
        lock (_lock)
        {
            if (_processor != null && _loadedPath == modelPath)
                return;

            _processor?.Dispose();
            _factory?.Dispose();

            _factory   = WhisperFactory.FromPath(modelPath);
            _processor = _factory.CreateBuilder()
                .WithLanguage(language == "auto" ? "auto" : language)
                .Build();

            _loadedPath = modelPath;
            AppLog.Add($"Lokales Whisper-Modell geladen: {Path.GetFileName(modelPath)}");
        }
    }

    public static void Unload()
    {
        lock (_lock)
        {
            _processor?.Dispose(); _processor = null;
            _factory?.Dispose();   _factory   = null;
            _loadedPath = null;
        }
    }
}
