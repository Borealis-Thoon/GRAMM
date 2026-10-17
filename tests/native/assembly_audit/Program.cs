using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
static SortedDictionary<string,string> Read(string path) {
 var a=Assembly.LoadFile(Path.GetFullPath(path));var r=new SortedDictionary<string,string>();
 foreach(var t in a.GetTypes()) foreach(var m in t.GetMethods(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static|BindingFlags.DeclaredOnly).Cast<MethodBase>().Concat(t.GetConstructors(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static|BindingFlags.DeclaredOnly))) {
 var b=m.GetMethodBody(); if(b is null)continue;var il=b.GetILAsByteArray()??Array.Empty<byte>();
 var locals=string.Join(";",b.LocalVariables.Select(v=>v.LocalType.FullName+":"+v.IsPinned));
 var clauses=string.Join(";",b.ExceptionHandlingClauses.Select(v=>v.Flags+":"+v.TryOffset+":"+v.TryLength+":"+v.HandlerOffset+":"+v.HandlerLength));
 r.Add(t.FullName+"::"+m.MetadataToken,Convert.ToHexString(SHA256.HashData(il))+"|"+locals+"|"+clauses+"|"+b.InitLocals+"|"+b.MaxStackSize);
 }
 return r;
}
var x=Read(args[0]);var y=Read(args[1]);var diffs=x.Keys.Union(y.Keys).Where(k=>!x.TryGetValue(k,out var a)||!y.TryGetValue(k,out var b)||a!=b).ToArray();
Console.WriteLine(JsonSerializer.Serialize(new { assembly_a=args[0],assembly_b=args[1],methods_a=x.Count,methods_b=y.Count,method_bodies_identical=diffs.Length==0,differences=diffs },new JsonSerializerOptions{WriteIndented=true}));
return diffs.Length==0?0:1;
