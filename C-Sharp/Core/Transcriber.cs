using System;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading.Tasks;

namespace Blitztext.Core;

/// <summary>
/// Transcribes audio via OpenAI Whisper or Groq Whisper API.
/// Provider is detected automatically from the API key prefix:
///   sk-...  → OpenAI  (whisper-1)
///   gsk_... → Groq    (whisper-large-v3-turbo)
/// </summary>
public static class Transcriber
{
    private static readonly HttpClient _http = new()
    {
        Timeout = TimeSpan.FromSeconds(60),
    };

    public static async Task<string> TranscribeAsync(
        MemoryStream audioWav,
        string apiKey,
        string language = "auto",
        string[]? properNouns = null,
        string? model = null)
    {
        if (string.IsNullOrWhiteSpace(apiKey))
            throw new InvalidOperationException("Kein API-Key gesetzt.");

        return apiKey.StartsWith("gsk_")
            ? await GroqAsync(audioWav, apiKey, language, properNouns, model ?? "whisper-large-v3-turbo")
            : await OpenAiAsync(audioWav, apiKey, language, properNouns, model ?? "whisper-1");
    }

    // ── OpenAI ────────────────────────────────────────────────────────
    private static async Task<string> OpenAiAsync(
        MemoryStream audio, string apiKey,
        string language, string[]? properNouns, string model)
    {
        using var content = BuildMultipart(audio, model, language, properNouns);
        using var req = new HttpRequestMessage(HttpMethod.Post,
            "https://api.openai.com/v1/audio/transcriptions");
        req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);
        req.Content = content;

        using var resp = await _http.SendAsync(req);
        var body = await resp.Content.ReadAsStringAsync();
        resp.EnsureSuccessStatusCode();

        return JsonNode.Parse(body)?["text"]?.GetValue<string>()?.Trim() ?? "";
    }

    // ── Groq ──────────────────────────────────────────────────────────
    private static async Task<string> GroqAsync(
        MemoryStream audio, string apiKey,
        string language, string[]? properNouns, string model)
    {
        using var content = BuildMultipart(audio, model, language, properNouns);
        using var req = new HttpRequestMessage(HttpMethod.Post,
            "https://api.groq.com/openai/v1/audio/transcriptions");
        req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);
        req.Content = content;

        using var resp = await _http.SendAsync(req);
        var body = await resp.Content.ReadAsStringAsync();
        resp.EnsureSuccessStatusCode();

        return JsonNode.Parse(body)?["text"]?.GetValue<string>()?.Trim() ?? "";
    }

    // ── shared helpers ────────────────────────────────────────────────
    private static MultipartFormDataContent BuildMultipart(
        MemoryStream audio, string model,
        string language, string[]? properNouns)
    {
        audio.Position = 0;
        var content = new MultipartFormDataContent();

        var audioContent = new StreamContent(audio);
        audioContent.Headers.ContentType = new MediaTypeHeaderValue("audio/wav");
        content.Add(audioContent, "file", "audio.wav");
        content.Add(new StringContent(model), "model");
        content.Add(new StringContent("json"), "response_format");

        if (!string.IsNullOrEmpty(language) && language != "auto")
            content.Add(new StringContent(language), "language");

        if (properNouns is { Length: > 0 })
            content.Add(new StringContent(string.Join(", ", properNouns)), "prompt");

        return content;
    }
}
