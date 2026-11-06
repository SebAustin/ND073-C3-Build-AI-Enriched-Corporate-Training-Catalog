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
