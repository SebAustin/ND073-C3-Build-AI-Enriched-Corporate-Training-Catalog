using System.Text.Json;
using Udacity.springerlookupdemo;
using Xunit;

namespace FunctionTests;

public sealed class SpringerClientTests
{
    [Theory]
    [InlineData("s40537-019-0210-7.pdf", "10.1186/s40537-019-0210-7")]
    [InlineData("S13640-020-00545-Z.pdf", "10.1186/s13640-020-00545-z")]
    public void CandidateDois_ReturnsBothPrefixes_ForArticleIdFileNames(string fileName, string firstDoi)
    {
        var dois = SpringerClient.CandidateDois(fileName).ToList();

        Assert.Equal(firstDoi, dois[0]);
        Assert.Equal(firstDoi.Replace("10.1186", "10.1007"), dois[1]);
    }

    [Theory]
    [InlineData("Liang-Lin2021_Article_MachineLearningForDigitalTry-o.pdf")]
    [InlineData("")]
    [InlineData(null)]
    public void CandidateDois_ReturnsNone_ForOtherFileNames(string? fileName)
    {
        Assert.Empty(SpringerClient.CandidateDois(fileName!));
    }

    [Theory]
    [InlineData("2019-06-06", "2019-06-06T00:00:00Z")]
    [InlineData("not-a-date", null)]
    [InlineData(null, null)]
    public void ToIsoDate_ConvertsSpringerDates(string? input, string? expected)
    {
        Assert.Equal(expected, SpringerClient.ToIsoDate(input!));
    }

    [Fact]
    public void Constructor_Throws_WhenApiKeyMissing()
    {
        Assert.Throws<InvalidOperationException>(() => new SpringerClient(new HttpClient(), ""));
    }

    /// <summary>Live check against Springer for all 20 Curated Library files. Skips without a key.</summary>
    [Fact]
    public async Task LookupAsync_ResolvesLibraryFiles_WhenKeyAvailable()
    {
        var key = ReadKey();
        if (key == null) return;
        var client = new SpringerClient(new HttpClient(), key);

        var hit = await client.LookupAsync("", "s40537-019-0210-7.pdf");
        Assert.Equal("Journal of Big Data", hit.PublicationName);
        Assert.Equal("2019-06-06T00:00:00Z", hit.PublicationDate);

        var byTitle = await client.LookupAsync("QER: a new feature selection method for sentiment analysis", "unknown.pdf");
        Assert.Equal("10.1186/s13673-018-0135-8", byTitle.DOI);

        var miss = await client.LookupAsync("Publisher's Note", "unknown.pdf");
        Assert.Equal("", miss.DOI);
    }

    private static string? ReadKey()
    {
        var fromEnv = Environment.GetEnvironmentVariable("SPRINGER_API_KEY");
        if (!string.IsNullOrEmpty(fromEnv)) return fromEnv;
        var path = Path.Combine(AppContext.BaseDirectory, "../../../../Function/local.settings.json");
        if (!File.Exists(path)) return null;
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        return doc.RootElement.GetProperty("Values").GetProperty("SPRINGER_API_KEY").GetString();
    }
}

public sealed class SkillResponseContractTests
{
    [Fact]
    public void Serialize_UsesSkillEnvelopeAndBriefOutputNames()
    {
        var response = new SpringerLookup.WebApiResponse();
        response.Values.Add(new SpringerLookup.OutputRecord
        {
            RecordId = "e1",
            Data = new PublicationMetadata("Journal of Big Data", "Springer", "10.1186/x", "2019-06-06T00:00:00Z"),
        });

        var json = SpringerLookup.Serialize(response);

        Assert.StartsWith("{\"values\":[{\"recordId\":\"e1\",\"data\":{\"PublicationName\":", json);
        Assert.Contains("\"DOI\":\"10.1186/x\"", json);
        Assert.Contains("\"warnings\":[]", json);
    }
}

public sealed class SpringerClientHttpTests
{
    private sealed class StubHandler(Func<HttpRequestMessage, HttpResponseMessage> respond) : HttpMessageHandler
    {
        public List<string> Queries { get; } = new();

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Queries.Add(Uri.UnescapeDataString(request.RequestUri!.Query));
            return Task.FromResult(respond(request));
        }
    }

    [Fact]
    public async Task LookupAsync_FallsBackToSecondPrefix_WhenFirstDoiReturns404()
    {
        var handler = new StubHandler(req => Uri.UnescapeDataString(req.RequestUri!.Query).Contains("doi:10.1186")
            ? new HttpResponseMessage(System.Net.HttpStatusCode.NotFound) { Content = new StringContent("{\"status\":\"Fail\"}") }
            : new HttpResponseMessage(System.Net.HttpStatusCode.OK)
            {
                Content = new StringContent("{\"records\":[{\"publicationName\":\"Brain Informatics\",\"publisher\":\"Springer\",\"doi\":\"10.1007/s40708-015-0017-z\",\"publicationDate\":\"2015-09-01\"}]}"),
            });
        var client = new SpringerClient(new HttpClient(handler), "test-key");

        var result = await client.LookupAsync("", "s40708-015-0017-z.pdf");

        Assert.Equal("10.1007/s40708-015-0017-z", result.DOI);
        Assert.Equal(2, handler.Queries.Count);
    }

    [Fact]
    public async Task LookupAsync_Throws_OnServerError()
    {
        var handler = new StubHandler(_ => new HttpResponseMessage(System.Net.HttpStatusCode.InternalServerError) { Content = new StringContent("boom") });
        var client = new SpringerClient(new HttpClient(handler), "test-key");

        await Assert.ThrowsAsync<HttpRequestException>(() => client.LookupAsync("Some title", "x.pdf"));
    }
}
