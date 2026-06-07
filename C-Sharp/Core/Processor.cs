using System;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Collections.Generic;

namespace Blitztext.Core;

/// <summary>
/// Processes transcribed text for Plus / Rage / Emoji modes via Chat API.
/// Normal mode is a no-op. Snippets are applied after processing.
/// Provider detected from API key prefix (sk- = OpenAI, gsk_ = Groq).
/// </summary>
public static class Processor
{
    private static readonly HttpClient _http = new()
    {
        Timeout = TimeSpan.FromSeconds(60),
    };

    public static async Task<string> ProcessAsync(
        string text,
        string mode,
        string apiKey,
        string promptTemplate,
        int emojiDensity = 5,
        string? model = null,
        float temperature = 0.7f,
        int maxTokens = 1024)
    {
        if (mode == "normal") return text;

        var prompt = promptTemplate.Replace("{density}", emojiDensity.ToString());

        return apiKey.StartsWith("gsk_")
            ? await GroqChatAsync(text, prompt, apiKey, model ?? "llama-3.1-8b-instant", temperature, maxTokens)
            : await OpenAiChatAsync(text, prompt, apiKey, model ?? "gpt-4o-mini", temperature, maxTokens);
    }

    public static string ApplySnippets(string text, IEnumerable<SnippetEntry> snippets)
    {
        foreach (var s in snippets)
        {
            if (string.IsNullOrEmpty(s.Keyword)) continue;
            text = Regex.Replace(
                text,
                Regex.Escape(s.Keyword),
                s.Text,
                RegexOptions.IgnoreCase);
        }
        return text;
    }

    // ── OpenAI ────────────────────────────────────────────────────────
    private static async Task<string> OpenAiChatAsync(
        string text, string systemPrompt, string apiKey,
        string model, float temperature, int maxTokens)
    {
        var body = BuildChatBody(text, systemPrompt, model, temperature, maxTokens);
        using var req = new HttpRequestMessage(HttpMethod.Post,
            "https://api.openai.com/v1/chat/completions");
        req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);
        req.Content = new StringContent(body, Encoding.UTF8, "application/json");

        using var resp = await _http.SendAsync(req);
        var json = await resp.Content.ReadAsStringAsync();
        resp.EnsureSuccessStatusCode();

        return JsonNode.Parse(json)?["choices"]?[0]?["message"]?["content"]
            ?.GetValue<string>()?.Trim() ?? text;
    }

    // ── Groq ──────────────────────────────────────────────────────────
    private static async Task<string> GroqChatAsync(
        string text, string systemPrompt, string apiKey,
        string model, float temperature, int maxTokens)
    {
        var body = BuildChatBody(text, systemPrompt, model, temperature, maxTokens);
        using var req = new HttpRequestMessage(HttpMethod.Post,
            "https://api.groq.com/openai/v1/chat/completions");
        req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);
        req.Content = new StringContent(body, Encoding.UTF8, "application/json");

        using var resp = await _http.SendAsync(req);
        var json = await resp.Content.ReadAsStringAsync();
        resp.EnsureSuccessStatusCode();

        return JsonNode.Parse(json)?["choices"]?[0]?["message"]?["content"]
            ?.GetValue<string>()?.Trim() ?? text;
    }

    // ── shared ────────────────────────────────────────────────────────
    private static string BuildChatBody(
        string userText, string systemPrompt,
        string model, float temperature, int maxTokens)
    {
        var obj = new JsonObject
        {
            ["model"]       = model,
            ["temperature"] = temperature,
            ["max_tokens"]  = maxTokens,
            ["messages"] = new JsonArray
            {
                new JsonObject { ["role"] = "system", ["content"] = systemPrompt },
                new JsonObject { ["role"] = "user",   ["content"] = userText },
            },
        };
        return obj.ToJsonString();
    }
}
