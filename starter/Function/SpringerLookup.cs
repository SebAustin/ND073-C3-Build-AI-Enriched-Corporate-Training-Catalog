using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Azure.WebJobs;
using Microsoft.Azure.WebJobs.Extensions.Http;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json;

namespace Udacity.springerlookupdemo
{
    /// <summary>
    /// Azure AI Search custom Web API skill.
    /// Input:  ArticleName (Paper title), FileName (optional, blob name used for DOI lookup).
    /// Output: PublicationName, Publisher, DOI, PublicationDate (ISO 8601).
    /// The Springer API key is read from the SPRINGER_API_KEY app setting; it is never committed.
    /// </summary>
    public static class SpringerLookup
    {
        private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(20) };

        #region Skill request/response contract
        private sealed class InputRecord
        {
            public sealed class InputRecordData
            {
                public string ArticleName { get; set; }
                public string FileName { get; set; }
            }

            public string RecordId { get; set; }
            public InputRecordData Data { get; set; }
        }

        private sealed class WebApiRequest
        {
            public List<InputRecord> Values { get; set; }
        }

        private sealed class OutputRecord
        {
            public sealed class Message
            {
                public string message { get; set; }
            }

            public string RecordId { get; set; }
            public PublicationMetadata Data { get; set; }
            public List<Message> Errors { get; } = new();
            public List<Message> Warnings { get; } = new();
        }

        private sealed class WebApiResponse
        {
            public List<OutputRecord> Values { get; } = new();
        }
        #endregion

        [FunctionName("SpringerLookup")]
        public static async Task<IActionResult> Run(
            [HttpTrigger(AuthorizationLevel.Function, "post", Route = null)] HttpRequest req, ILogger log)
        {
            string requestBody = await new StreamReader(req.Body).ReadToEndAsync();

            WebApiRequest request;
            try
            {
                request = JsonConvert.DeserializeObject<WebApiRequest>(requestBody);
            }
            catch (JsonException)
            {
                return new BadRequestObjectResult("Request body is not valid JSON.");
            }
            if (request?.Values == null)
            {
                return new BadRequestObjectResult("The request schema does not match expected schema. Could not find values array.");
            }

            SpringerClient client;
            try
            {
                client = new SpringerClient(Http, Environment.GetEnvironmentVariable("SPRINGER_API_KEY"));
            }
            catch (InvalidOperationException e)
            {
                log.LogError(e.Message);
                return new ObjectResult(e.Message) { StatusCode = StatusCodes.Status500InternalServerError };
            }

            var response = new WebApiResponse();
            foreach (var record in request.Values)
            {
                if (record?.RecordId == null) continue;
                response.Values.Add(await ProcessRecordAsync(client, record, log));
            }
            return new OkObjectResult(response);
        }

        private static async Task<OutputRecord> ProcessRecordAsync(SpringerClient client, InputRecord record, ILogger log)
        {
            var output = new OutputRecord { RecordId = record.RecordId };
            var articleName = record.Data?.ArticleName ?? "";
            var fileName = record.Data?.FileName ?? "";
            try
            {
                output.Data = await client.LookupAsync(articleName, fileName);
                if (string.IsNullOrEmpty(output.Data.DOI))
                {
                    output.Warnings.Add(new OutputRecord.Message { message = $"No Springer match for '{fileName}' / '{articleName}'." });
                }
            }
            catch (Exception e)
            {
                log.LogWarning("Springer lookup failed for record {RecordId}: {Error}", record.RecordId, e.Message);
                output.Data = PublicationMetadata.Empty;
                output.Errors.Add(new OutputRecord.Message { message = e.Message });
            }
            return output;
        }
    }
}
