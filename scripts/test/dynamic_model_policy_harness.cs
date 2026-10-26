// Offline policy-statement doubles only. PolicyExpressions is generated from the rendered XML,
// without rewriting its C#. This does not emulate APIM networking, JWT validation, or distributed caches.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Xml.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

public class Jwt { public Dictionary<string, string[]> Claims = new Dictionary<string, string[]>(); }
public static class ClaimExtensions {
    public static string GetValueOrDefault(this Dictionary<string, string[]> claims, string name, string fallback) {
        return claims.ContainsKey(name) ? string.Join(",", claims[name]) : fallback;
    }
}
public interface IResponse { int StatusCode { get; } MessageBody Body { get; } }
public class MessageBody {
    public string Text;
    public bool Utf16;
    public T As<T>(bool preserveContent = false) {
        if (typeof(T) == typeof(byte[])) { return (T)(object)(Utf16 ? Encoding.Unicode : Encoding.UTF8).GetBytes(Text); }
        return (T)(object)Text;
    }
}
public class StubResponse : IResponse {
    public int StatusCode { get; set; }
    public MessageBody Body { get; set; }
}
public class RequestData { public string Method; }
public class OperationData { public string Id; }
public class SyntheticContext {
    public Dictionary<string, object> Variables = new Dictionary<string, object>();
    public RequestData Request = new RequestData();
    public OperationData Operation = new OperationData();
    public JObject Input;
    public JObject Headers = new JObject();
    public JObject RequestHeaders = new JObject();
    public JArray Calls = new JArray();
    public JArray Events = new JArray();
    public int Status = 200, PageIndex, Lookups, Stores;
    public string Body = "";
    public bool Returning, Forwarded;
    public double Now;
}
class PlatformError : Exception {
    public int Status;
    public PlatformError(int status) { Status = status; }
}
class HarnessError : Exception { public HarnessError(string message) : base(message) {} }
class CacheEntry { public string Body; public double Expires; }

class PolicyHarness {
    readonly Dictionary<string, CacheEntry> cache = new Dictionary<string, CacheEntry>();
    readonly Dictionary<string, List<double>> counters = new Dictionary<string, List<double>>();
    readonly bool cacheEnabled;
    public PolicyHarness(bool enabled) { cacheEnabled = enabled; }
    object Eval(string value, SyntheticContext context) { return PolicyExpressions.Evaluate(value, context); }
    string Attr(XElement node, string name) { return (string)node.Attribute(name); }

    bool Run(IEnumerable<XElement> nodes, SyntheticContext context) {
        foreach (var node in nodes) {
            var kind = node.Name.LocalName;
            if (kind == "base" || kind == "trace") { continue; }
            if (kind == "choose") {
                var selected = node.Elements().FirstOrDefault(branch => branch.Name == "otherwise" || (bool)Eval(Attr(branch, "condition"), context));
                if (selected != null && Run(selected.Elements(), context)) { return true; }
            } else if (kind == "validate-azure-ad-token") {
                context.Events.Add("authenticate");
                var auth = (string)context.Input["auth"] ?? "role";
                if (auth == "missing" || auth == "invalid") { throw new PlatformError(401); }
                var jwt = new Jwt();
                jwt.Claims["oid"] = new [] { (string)context.Input["user"] ?? "user" };
                jwt.Claims["tid"] = new [] { "tenant" };
                if (auth == "role") { jwt.Claims["roles"] = new [] { "Gateway.User" }; }
                if (auth == "desktop") {
                    jwt.Claims["ver"] = new [] { "2.0" };
                    jwt.Claims["azp"] = new [] { "desktop-client" };
                    jwt.Claims["scp"] = new [] { "Gateway.Access" };
                }
                var claims = context.Input["claims"] as JObject;
                if (claims != null) {
                    foreach (var claim in claims.Properties()) { jwt.Claims[claim.Name] = ((JArray)claim.Value).Select(value => (string)value).ToArray(); }
                }
                context.Variables[Attr(node, "output-token-variable-name")] = jwt;
            } else if (kind == "set-variable") {
                var name = Attr(node, "name");
                context.Variables[name] = Eval(Attr(node, "value"), context);
                // Test seams supply corrupt configuration and elapsed time, not alternative validation/projection logic.
                if (name == "inventoryConfiguration" && context.Input["configuration"] != null) {
                    context.Variables[name] = Convert.ToBase64String(Encoding.UTF8.GetBytes(context.Input["configuration"].ToString(Formatting.None)));
                }
                if (name == "inventoryStarted" && context.Input["elapsedBeforeFetch"] != null) {
                    context.Variables[name] = DateTime.UtcNow.AddSeconds(-(double)context.Input["elapsedBeforeFetch"]);
                }
            } else if (kind == "rate-limit-by-key") {
                var key = (string)Eval(Attr(node, "counter-key"), context);
                context.Events.Add("rate:" + key);
                if ((bool?)context.Input["denyUserRate"] == true && key.StartsWith("claude-foundry:models:rpm:")) { throw new PlatformError(429); }
                if (!counters.ContainsKey(key)) { counters[key] = new List<double>(); }
                var times = counters[key];
                times.RemoveAll(time => time <= context.Now - int.Parse(Attr(node, "renewal-period")));
                if (times.Count >= int.Parse(Attr(node, "calls"))) { throw new PlatformError(429); }
                times.Add(context.Now);
            } else if (kind == "cache-lookup-value") {
                context.Lookups++;
                context.Events.Add("cache-lookup");
                var key = (string)Eval(Attr(node, "key"), context);
                CacheEntry entry;
                if (cacheEnabled && cache.TryGetValue(key, out entry) && entry.Expires > context.Now) {
                    context.Variables[Attr(node, "variable-name")] = entry.Body;
                }
            } else if (kind == "cache-store-value") {
                context.Stores++;
                context.Events.Add("cache-store");
                if (cacheEnabled) {
                    cache[(string)Eval(Attr(node, "key"), context)] = new CacheEntry {
                        Body = (string)Eval(Attr(node, "value"), context), Expires = context.Now + int.Parse(Attr(node, "duration"))
                    };
                }
            } else if (kind == "send-request") {
                var pages = context.Input["pages"] as JArray ?? new JArray();
                if (context.PageIndex >= pages.Count) { throw new HarnessError("Unexpected ARM request: no fixture supplied"); }
                var page = (JObject)pages[context.PageIndex++];
                var headers = new JObject();
                foreach (var header in node.Elements("set-header")) { headers[Attr(header, "name")] = (string)Eval(header.Element("value").Value, context); }
                context.Calls.Add(new JObject(
                    new JProperty("url", (string)Eval(node.Element("set-url").Value, context)),
                    new JProperty("method", node.Element("set-method").Value),
                    new JProperty("mode", Attr(node, "mode")),
                    new JProperty("timeout", Attr(node, "timeout")),
                    new JProperty("headers", headers),
                    new JProperty("identity_resource", Attr(node.Element("authentication-managed-identity"), "resource"))));
                context.Events.Add("ARM");
                if ((bool?)page["identityError"] == true) { throw new PlatformError(500); }
                if (page["elapsedSeconds"] != null) {
                    context.Variables["inventoryStarted"] = ((DateTime)context.Variables["inventoryStarted"]).AddSeconds(-(double)page["elapsedSeconds"]);
                }
                var body = page["body"];
                context.Variables[Attr(node, "response-variable-name")] = (bool?)page["networkError"] == true ? null : new StubResponse {
                    StatusCode = (int?)page["status"] ?? 200,
                    Body = body == null || body.Type == JTokenType.Null ? null : new MessageBody {
                        Text = body.Type == JTokenType.String ? (string)body : body.ToString(Formatting.None), Utf16 = (bool?)page["utf16Body"] == true
                    }
                };
            } else if (kind == "return-response") {
                context.Returning = true;
                Run(node.Elements(), context);
                return true;
            } else if (kind == "set-status") {
                context.Status = int.Parse(Attr(node, "code"));
            } else if (kind == "set-body") {
                context.Body = (string)Eval(node.Value, context);
            } else if (kind == "set-header") {
                var headers = context.Returning ? context.Headers : context.RequestHeaders;
                if (Attr(node, "exists-action") == "delete") { headers.Remove(Attr(node, "name")); }
                else { headers[Attr(node, "name")] = (string)Eval(node.Element("value").Value, context); }
            } else if (kind == "set-query-parameter") {
                context.Events.Add("strip-query:" + Attr(node, "name"));
            } else if (kind == "set-backend-service") {
                context.Events.Add("inference-backend");
            } else if (kind == "authentication-managed-identity") {
                context.Events.Add("inference-identity");
                context.Variables[Attr(node, "output-token-variable-name")] = "synthetic-inference-token";
            } else if (kind == "limit-concurrency") {
                context.Events.Add("inference-concurrency");
                if (Run(node.Elements(), context)) { return true; }
            } else if (kind == "forward-request") {
                context.Forwarded = true;
            } else { throw new HarnessError("Unsupported policy statement: " + kind); }
        }
        return false;
    }

    JObject Request(JObject input) {
        var context = new SyntheticContext { Input = input, Now = (double?)input["time"] ?? 0 };
        context.Request.Method = (string)input["method"] ?? "GET";
        context.Operation.Id = (string)input["operation"] ?? "models";
        context.RequestHeaders = input["headers"] as JObject ?? new JObject();
        var policy = PolicyExpressions.Policies[(string)input["policy"] ?? "primary"];
        try {
            if (!Run(policy.Element("inbound").Elements(), context)) { Run(policy.Element("backend").Elements(), context); }
        } catch (HarnessError) { throw; }
        catch (Exception error) {
            context.Status = error is PlatformError ? ((PlatformError)error).Status : 500;
            Run(policy.Element("on-error").Elements(), context);
        }
        return new JObject(
            new JProperty("status", context.Status), new JProperty("body", context.Body),
            new JProperty("headers", context.Headers), new JProperty("request_headers", context.RequestHeaders),
            new JProperty("calls", context.Calls), new JProperty("events", context.Events),
            new JProperty("lookups", context.Lookups), new JProperty("stores", context.Stores),
            new JProperty("forwarded", context.Forwarded),
            new JProperty("cache_key", context.Variables.ContainsKey("inventoryCacheKey") ? context.Variables["inventoryCacheKey"] : null));
    }

    static int Main(string[] args) {
        try {
            Console.OutputEncoding = new UTF8Encoding(false);
            var input = JObject.Parse(File.ReadAllText(args[0]));
            var harness = new PolicyHarness((bool?)input["cacheEnabled"] ?? true);
            var results = new JArray();
            foreach (var request in (JArray)input["requests"]) { results.Add(harness.Request((JObject)request)); }
            Console.WriteLine(new JObject(new JProperty("results", results),
                new JProperty("runtime", Environment.Version.ToString()),
                new JProperty("newtonsoft", typeof(JObject).Assembly.FullName)).ToString(Formatting.None));
            return 0;
        } catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
}
