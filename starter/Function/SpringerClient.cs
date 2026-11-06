using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Net.Http;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;

namespace Udacity.springerlookupdemo
{
    /// <summary>
    /// Publication metadata for one Paper, as returned to the search skillset.
    /// PublicationDate is ISO 8601 (or null) so it can be indexed as Edm.DateTimeOffset.
    /// </summary>
    public sealed record PublicationMetadata(
        string PublicationName,
        string Publisher,
        string DOI,
        string PublicationDate)
    {
        public static readonly PublicationMetadata Empty = new("", "", "", null);
    }

    /// <summary>
    /// Looks up Papers in the Springer Nature Open Access API.
    ///
    /// The free API tier rejects field queries such as title:"..." ("premium feature")
    /// and caps page size at 20, so the lookup works in two steps:
    ///   1. DOI derived from the file name (SpringerOpen files are named after their article id,
    ///      e.g. s40537-019-0210-7.pdf -> 10.1186/s40537-019-0210-7 or 10.1007/...).
    ///   2. Phrase search on the article name, accepting only a record whose title matches exactly.
    /// </summary>
    public sealed class SpringerClient
    {
        private const string Endpoint = "https://api.springernature.com/openaccess/json";
        private const int MaxFreeTierPageSize = 20;
        private static readonly string[] DoiPrefixes = { "10.1186", "10.1007" };
        private static readonly Regex ArticleIdPattern =
            new(@"^s\d{5}-\d{3}-\d{4,5}-[0-9a-z]$", RegexOptions.Compiled | RegexOptions.IgnoreCase);
        private static readonly Regex NonAlphanumeric = new(@"[^a-z0-9]", RegexOptions.Compiled);

        private readonly HttpClient http;
        private readonly string apiKey;

        public SpringerClient(HttpClient http, string apiKey)
        {
            if (string.IsNullOrWhiteSpace(apiKey))
            {
                throw new InvalidOperationException("SPRINGER_API_KEY app setting is not configured.");
            }
            this.http = http;
            this.apiKey = apiKey;
        }

        public async Task<PublicationMetadata> LookupAsync(string articleName, string fileName)
        {
            foreach (var doi in CandidateDois(fileName))
            {
                var record = (await QueryAsync($"doi:{doi}", 1)).FirstOrDefault();
                if (record != null) return ToMetadata(record);
            }

            if (string.IsNullOrWhiteSpace(articleName)) return PublicationMetadata.Empty;

            var wanted = Normalize(articleName);
            var records = await QueryAsync($"\"{articleName.Replace("\"", "")}\"", MaxFreeTierPageSize);
            var match = records.FirstOrDefault(r => Normalize(r.Value<string>("title")) == wanted);
            return match == null ? PublicationMetadata.Empty : ToMetadata(match);
        }

        public static IEnumerable<string> CandidateDois(string fileName)
        {
            if (string.IsNullOrWhiteSpace(fileName)) return Enumerable.Empty<string>();
            var stem = System.IO.Path.GetFileNameWithoutExtension(fileName.Trim());
            return ArticleIdPattern.IsMatch(stem)
                ? DoiPrefixes.Select(prefix => $"{prefix}/{stem.ToLowerInvariant()}")
                : Enumerable.Empty<string>();
        }

        public static string ToIsoDate(string springerDate)
        {
            return DateTime.TryParseExact(springerDate, "yyyy-MM-dd", CultureInfo.InvariantCulture,
                    DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out var parsed)
                ? parsed.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'", CultureInfo.InvariantCulture)
                : null;
        }

        private async Task<IReadOnlyList<JToken>> QueryAsync(string query, int pageSize)
        {
            var uri = $"{Endpoint}?q={Uri.EscapeDataString(query)}&p={pageSize}&api_key={Uri.EscapeDataString(apiKey)}";
            using var response = await http.GetAsync(uri);
            var body = await response.Content.ReadAsStringAsync();
            if (!response.IsSuccessStatusCode)
            {
                // Never surface the request URI: it carries the API key.
                throw new HttpRequestException($"Springer API returned {(int)response.StatusCode}: {Truncate(body, 200)}");
            }
            return JObject.Parse(body)["records"]?.Children().ToList() ?? new List<JToken>();
        }

        private static PublicationMetadata ToMetadata(JToken record) => new(
            record.Value<string>("publicationName") ?? "",
            record.Value<string>("publisher") ?? "",
            record.Value<string>("doi") ?? "",
            ToIsoDate(record.Value<string>("publicationDate")));

        private static string Normalize(string text) =>
            NonAlphanumeric.Replace((text ?? "").ToLowerInvariant(), "");

        private static string Truncate(string text, int max) =>
            text.Length <= max ? text : text.Substring(0, max);
    }
}
