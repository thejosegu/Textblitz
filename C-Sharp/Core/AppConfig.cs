using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Blitztext.Core;

/// <summary>
/// JSON-backed application configuration.
/// API key is stored in a separate .env file (not in config.json).
/// </summary>
public class AppConfig
{
    // ── defaults ──────────────────────────────────────────────────────
    private static readonly Dictionary<string, string> DefaultHotkeys = new()
    {
        ["normal"] = "F8",
        ["plus"]   = "alt_r",
        ["rage"]   = "ctrl_r+alt_r",
        ["emoji"]  = "ctrl_r+shift_r",
    };

    private static readonly Dictionary<string, string> DefaultPrompts = new()
    {
        ["plus"] =
            "Formuliere diesen gesprochenen Text natürlicher und schriftlicher um. " +
            "Behalte den Sinn und die ungefähre Länge bei. " +
            "Antworte NUR mit dem umformulierten Text, ohne Erklärungen oder Kommentare.",
        ["rage"] =
            "Diese Person klingt aufgebracht oder frustriert. " +
            "Schreibe eine höfliche, professionelle Version dieser Nachricht, " +
            "die den Kerninhalt beibehält. " +
            "Antworte NUR mit der höflichen Version, ohne Erklärungen.",
        ["emoji"] =
            "Füge passende Emojis in diesen Text ein. " +
            "Emoji-Dichte: {density}/10 (1=sehr wenige, 10=sehr viele). " +
            "Behalte den Text ansonsten unverändert. " +
            "Antworte NUR mit dem Text mit Emojis, ohne Erklärungen.",
    };

    private static readonly List<SnippetEntry> DefaultSnippets =
    [
        new("freundliche grüße",  "Mit freundlichen Grüßen"),
        new("vielen dank",        "Vielen Dank und mit freundlichen Grüßen"),
        new("auf wiedersehen",    "Auf Wiedersehen und einen schönen Tag noch!"),
    ];

    // ── storage ───────────────────────────────────────────────────────
    private static string AppDir =>
        AppContext.BaseDirectory;

    private static string ConfigPath =>
        Path.Combine(AppDir, "config.json");

    private static string EnvPath =>
        Path.Combine(AppDir, ".env");

    // ── backing store ─────────────────────────────────────────────────
    private JsonObject _data = new();

    // ── ctor ──────────────────────────────────────────────────────────
    public AppConfig() => Load();

    // ── persistence ───────────────────────────────────────────────────
    public void Load()
    {
        _data = new JsonObject();

        if (File.Exists(ConfigPath))
        {
            try
            {
                var json = File.ReadAllText(ConfigPath);
                _data = JsonNode.Parse(json)?.AsObject() ?? new JsonObject();
            }
            catch { /* use empty */ }
        }

        // Load API key from .env (GROQ_API_KEY=...)
        if (File.Exists(EnvPath))
        {
            foreach (var line in File.ReadAllLines(EnvPath))
            {
                var idx = line.IndexOf('=');
                if (idx > 0)
                {
                    var key = line[..idx].Trim();
                    var val = line[(idx + 1)..].Trim();
                    Environment.SetEnvironmentVariable(key, val);
                }
            }
        }
    }

    public void Save()
    {
        var opts = new JsonSerializerOptions { WriteIndented = true };

        // Persist hotkeys
        var hkObj = new JsonObject();
        foreach (var (mode, val) in Hotkeys)
            hkObj[mode] = val;
        _data["hotkeys"] = hkObj;

        // Persist prompts
        var prObj = new JsonObject();
        foreach (var (mode, val) in Prompts)
            prObj[mode] = val;
        _data["prompts"] = prObj;

        // Persist snippets
        var snArr = new JsonArray();
        foreach (var s in Snippets)
            snArr.Add(JsonNode.Parse(JsonSerializer.Serialize(s)));
        _data["snippets"] = snArr;

        // Other properties are written via their setters already

        File.WriteAllText(ConfigPath,
            _data.ToJsonString(opts),
            System.Text.Encoding.UTF8);

        // Persist API key to .env
        File.WriteAllText(EnvPath,
            $"GROQ_API_KEY={ApiKey}\n",
            System.Text.Encoding.UTF8);
    }

    // ── typed properties ──────────────────────────────────────────────

    /// <summary>API key — read from environment (GROQ_API_KEY), written to .env.</summary>
    public string ApiKey
    {
        get => Environment.GetEnvironmentVariable("GROQ_API_KEY") ?? _data["api_key"]?.GetValue<string>() ?? "";
        set
        {
            Environment.SetEnvironmentVariable("GROQ_API_KEY", value);
            _data["api_key"] = value;
        }
    }

    public string WhisperLanguage
    {
        get => _data["whisper_language"]?.GetValue<string>() ?? "auto";
        set => _data["whisper_language"] = value;
    }

    /// <summary>"hold" or "toggle"</summary>
    public string RecordMode
    {
        get => _data["record_mode"]?.GetValue<string>() ?? "hold";
        set => _data["record_mode"] = value;
    }

    public bool Autostart
    {
        get => _data["autostart"]?.GetValue<bool>() ?? false;
        set => _data["autostart"] = value;
    }

    public int EmojiDensity
    {
        get => _data["emoji_density"]?.GetValue<int>() ?? 5;
        set => _data["emoji_density"] = value;
    }

    public string WhisperModelOpenAi
    {
        get => _data["whisper_model_openai"]?.GetValue<string>() ?? "whisper-1";
        set => _data["whisper_model_openai"] = value;
    }

    public string WhisperModelGroq
    {
        get => _data["whisper_model_groq"]?.GetValue<string>() ?? "whisper-large-v3-turbo";
        set => _data["whisper_model_groq"] = value;
    }

    public string ChatModelOpenAi
    {
        get => _data["chat_model_openai"]?.GetValue<string>() ?? "gpt-4o-mini";
        set => _data["chat_model_openai"] = value;
    }

    public string ChatModelGroq
    {
        get => _data["chat_model_groq"]?.GetValue<string>() ?? "llama-3.1-8b-instant";
        set => _data["chat_model_groq"] = value;
    }

    public float Temperature
    {
        get => _data["temperature"]?.GetValue<float>() ?? 0.7f;
        set => _data["temperature"] = value;
    }

    public int MaxTokens
    {
        get => _data["max_tokens"]?.GetValue<int>() ?? 1024;
        set => _data["max_tokens"] = value;
    }

    /// <summary>"api" or "local"</summary>
    public string TranscribeMode
    {
        get => _data["transcribe_mode"]?.GetValue<string>() ?? "api";
        set => _data["transcribe_mode"] = value;
    }

    /// <summary>Path to GGML model file for local Whisper transcription.</summary>
    public string LocalModelPath
    {
        get => _data["local_model_path"]?.GetValue<string>() ?? "";
        set => _data["local_model_path"] = value;
    }

    // ── hotkeys ───────────────────────────────────────────────────────

    private Dictionary<string, string>? _hotkeys;

    public Dictionary<string, string> Hotkeys
    {
        get
        {
            if (_hotkeys != null) return _hotkeys;
            _hotkeys = new Dictionary<string, string>(DefaultHotkeys);
            if (_data["hotkeys"] is JsonObject obj)
            {
                foreach (var (k, v) in obj)
                    _hotkeys[k] = v?.GetValue<string>() ?? "";
            }
            return _hotkeys;
        }
    }

    public string GetHotkey(string mode) =>
        Hotkeys.TryGetValue(mode, out var v) ? v : "";

    public void SetHotkey(string mode, string spec)
    {
        Hotkeys[mode] = spec;
        if (_data["hotkeys"] is not JsonObject obj)
        {
            obj = new JsonObject();
            _data["hotkeys"] = obj;
        }
        obj[mode] = spec;
    }

    // ── prompts ───────────────────────────────────────────────────────

    private Dictionary<string, string>? _prompts;

    public Dictionary<string, string> Prompts
    {
        get
        {
            if (_prompts != null) return _prompts;
            _prompts = new Dictionary<string, string>(DefaultPrompts);
            if (_data["prompts"] is JsonObject obj)
            {
                foreach (var (k, v) in obj)
                    _prompts[k] = v?.GetValue<string>() ?? "";
            }
            return _prompts;
        }
    }

    public string GetPrompt(string mode) =>
        Prompts.TryGetValue(mode, out var v) ? v : "";

    public void SetPrompt(string mode, string text)
    {
        Prompts[mode] = text;
        if (_data["prompts"] is not JsonObject obj)
        {
            obj = new JsonObject();
            _data["prompts"] = obj;
        }
        obj[mode] = text;
    }

    // ── proper nouns ──────────────────────────────────────────────────

    public List<string> ProperNouns
    {
        get
        {
            var list = new List<string>();
            if (_data["proper_nouns"] is JsonArray arr)
                foreach (var n in arr)
                    if (n?.GetValue<string>() is { } s)
                        list.Add(s);
            return list;
        }
        set
        {
            var arr = new JsonArray();
            foreach (var n in value) arr.Add(n);
            _data["proper_nouns"] = arr;
        }
    }

    // ── snippets ──────────────────────────────────────────────────────

    public List<SnippetEntry> Snippets
    {
        get
        {
            var list = new List<SnippetEntry>();
            if (_data["snippets"] is JsonArray arr)
            {
                foreach (var item in arr)
                {
                    var kw  = item?["keyword"]?.GetValue<string>() ?? "";
                    var txt = item?["text"]?.GetValue<string>()    ?? "";
                    if (kw.Length > 0)
                        list.Add(new SnippetEntry(kw, txt));
                }
                return list;
            }
            return new List<SnippetEntry>(DefaultSnippets);
        }
        set
        {
            var arr = new JsonArray();
            foreach (var s in value)
            {
                var obj = new JsonObject
                {
                    ["keyword"] = s.Keyword,
                    ["text"]    = s.Text,
                };
                arr.Add(obj);
            }
            _data["snippets"] = arr;
        }
    }

    // ── helpers ───────────────────────────────────────────────────────

    public string DetectProvider()
    {
        if (string.IsNullOrEmpty(ApiKey)) return "Nicht gesetzt";
        if (ApiKey.StartsWith("gsk_")) return "Groq";
        if (ApiKey.StartsWith("sk-"))  return "OpenAI";
        return "Unbekannt";
    }

    public bool IsGroq => ApiKey.StartsWith("gsk_");

    public string ActiveWhisperModel => IsGroq ? WhisperModelGroq : WhisperModelOpenAi;
    public string ActiveChatModel    => IsGroq ? ChatModelGroq    : ChatModelOpenAi;
}

public record SnippetEntry(string Keyword, string Text);
