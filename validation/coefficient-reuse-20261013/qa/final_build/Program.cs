using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using System.Security.Cryptography;
using System.Text.Json;

static SortedDictionary<string, string> ReadMethods(string path)
{
    using var stream = File.OpenRead(path);
    using var pe = new PEReader(stream);
    var metadata = pe.GetMetadataReader();
    var rows = new SortedDictionary<string, string>();
    foreach (var handle in metadata.MethodDefinitions)
    {
        var method = metadata.GetMethodDefinition(handle);
        var type = metadata.GetTypeDefinition(method.GetDeclaringType());
        var name = MetadataTokens.GetToken(handle).ToString("X8") + ":" +
            metadata.GetString(type.Namespace) + "." + metadata.GetString(type.Name) + ":" + metadata.GetString(method.Name);
        var record = new List<string> {
            Convert.ToHexString(metadata.GetBlobBytes(method.Signature)),
            method.Attributes.ToString(), method.ImplAttributes.ToString()
        };
        if (method.RelativeVirtualAddress != 0)
        {
            var body = pe.GetMethodBody(method.RelativeVirtualAddress);
            record.Add(Convert.ToHexString(body.GetILBytes() ?? Array.Empty<byte>()));
            record.Add(body.MaxStack.ToString());
            record.Add(body.LocalVariablesInitialized.ToString());
            record.Add(body.LocalSignature.IsNil ? "" : Convert.ToHexString(metadata.GetBlobBytes(metadata.GetStandaloneSignature(body.LocalSignature).Signature)));
            foreach (var region in body.ExceptionRegions)
                record.Add($"{region.Kind}:{region.TryOffset}:{region.TryLength}:{region.HandlerOffset}:{region.HandlerLength}:{region.FilterOffset}:{MetadataTokens.GetToken(region.CatchType)}");
        }
        rows.Add(name, Convert.ToHexString(SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(string.Join("\n", record)))).ToLowerInvariant());
    }
    foreach (var handle in metadata.MemberReferences)
    {
        var member = metadata.GetMemberReference(handle);
        rows.Add("member:" + MetadataTokens.GetToken(handle).ToString("X8"), MetadataTokens.GetToken(member.Parent) + ":" + metadata.GetString(member.Name) + ":" + Convert.ToHexString(metadata.GetBlobBytes(member.Signature)));
    }
    foreach (var handle in metadata.TypeReferences)
    {
        var type = metadata.GetTypeReference(handle);
        rows.Add("type:" + MetadataTokens.GetToken(handle).ToString("X8"), MetadataTokens.GetToken(type.ResolutionScope) + ":" + metadata.GetString(type.Namespace) + "." + metadata.GetString(type.Name));
    }
    return rows;
}

if (args.Length < 4 || (args.Length - 1) % 3 != 0)
    throw new ArgumentException("Usage: output.json variant old.dll new.dll [variant old.dll new.dll ...]");
var results = new List<object>();
var pass = true;
for (var i = 1; i < args.Length; i += 3)
{
    var before = ReadMethods(args[i + 1]);
    var after = ReadMethods(args[i + 2]);
    var mismatches = before.Keys.Union(after.Keys).Where(k => !before.TryGetValue(k, out var a) || !after.TryGetValue(k, out var b) || a != b).ToArray();
    pass &= mismatches.Length == 0;
    results.Add(new {
        variant = args[i], old_sha256 = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(args[i + 1]))).ToLowerInvariant(),
        new_sha256 = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(args[i + 2]))).ToLowerInvariant(),
        method_count = before.Keys.Count(k => !k.StartsWith("member:") && !k.StartsWith("type:")),
        compared_metadata_records = before.Count, identical = mismatches.Length == 0, mismatches
    });
}
File.WriteAllText(args[0], JsonSerializer.Serialize(new {
    status = pass ? "pass" : "fail",
    scope = "Method IL bytes, signatures, implementation flags, local signatures, exception regions, and member/type reference records; build paths and assembly informational version are excluded.",
    variants = results
}, new JsonSerializerOptions { WriteIndented = true }));
return pass ? 0 : 1;
