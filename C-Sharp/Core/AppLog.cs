using System;
using System.Collections.Generic;
using System.Threading;

namespace Blitztext.Core;

/// <summary>
/// Thread-safe in-memory ring buffer log (max 100 entries).
/// Mirrors Python log.py behaviour.
/// </summary>
public static class AppLog
{
    private static readonly Lock _lock = new();
    private static readonly Queue<string> _entries = new(100);
    private const int MaxEntries = 100;

    public static string LastTranscript { get; private set; } = "";
    public static string LastProcessed  { get; private set; } = "";
    public static string LastMode       { get; private set; } = "";
    public static string LastError      { get; private set; } = "";

    public static void Add(string message)
    {
        var ts = DateTime.Now.ToString("HH:mm:ss");
        var entry = $"[{ts}] {message}";
        lock (_lock)
        {
            if (_entries.Count >= MaxEntries)
                _entries.Dequeue();
            _entries.Enqueue(entry);
        }
    }

    public static IReadOnlyList<string> GetAll()
    {
        lock (_lock)
            return [.. _entries];
    }

    public static void Clear()
    {
        lock (_lock)
            _entries.Clear();
    }

    public static void SetLast(string transcript, string processed, string mode)
    {
        LastTranscript = transcript;
        LastProcessed  = processed;
        LastMode       = mode;
        LastError      = "";
    }

    public static void SetError(string message)
    {
        LastError = message;
        Add($"FEHLER: {message}");
    }
}
