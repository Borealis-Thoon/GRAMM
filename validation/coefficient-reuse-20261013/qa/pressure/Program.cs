using System.Collections.Immutable;
using System.Reflection;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;

internal sealed class Engine
{
    public readonly Type Core;
    const BindingFlags Flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static;
    public Engine(string path) => Core = new AssemblyLoadContext(Path.GetFileName(Path.GetDirectoryName(path)), true).LoadFromAssemblyPath(Path.GetFullPath(path)).GetType("GRAMM_2001.Program")!;
    public void Set(string name, object value) => Core.GetField(name, Flags)!.SetValue(null, value);
    public object Get(string name) => Core.GetField(name, Flags)!.GetValue(null)!;
    public void Call(string name, params object[] args) => Core.GetMethod(name, Flags)!.Invoke(null, args);
    public double? Cache => Core.GetField("PressureCoefficientTimeStep", Flags)?.GetValue(null) as double?;
    public static readonly string[] Coefficients = ["AP", "AB", "AT", "AE", "AN", "AW", "AS"];
    public void Init(int ni, int nj, int nk, int threads, int weather)
    {
        var rand = new Random(8123 + weather);
        foreach (string name in new[] { "ZSPImm", "AREAImm", "AREAXImm", "AREAYImm", "AREAZXImm", "AREAZYImm", "RHO", "AP0" })
        {
            float[][][] a = new float[ni + 2][][];
            for (int i = 0; i < a.Length; i++)
            {
                a[i] = new float[nj + 2][];
                for (int j = 0; j < a[i].Length; j++)
                {
                    a[i][j] = new float[nk + 2];
                    for (int k = 0; k < a[i][j].Length; k++)
                        a[i][j][k] = name == "ZSPImm" ? k * 20 : (float)(0.2 + rand.NextDouble() * 5);
                }
            }
            Set(name, Core.GetField(name, Flags)!.FieldType == typeof(ImmutableArray<float>[][]) ? a.Select(row => row.Select(column => column.ToImmutableArray()).ToArray()).ToArray() : a);
        }
        foreach (string name in Coefficients)
        {
            double[][][] a = new double[ni + 2][][];
            for (int i = 0; i < a.Length; i++)
            {
                a[i] = new double[nj + 2][];
                for (int j = 0; j < a[i].Length; j++) a[i][j] = new double[2 * nk + 2];
            }
            Set(name, a);
        }
        Set("ISTAT", 2); // Execute the real INITA reset without reading meteorological input files.
        Set("pOptions", new ParallelOptions { MaxDegreeOfParallelism = threads });
        Call("INITA", ni, nj, nk);
    }
    public void AdjustInputs(double dt, float scale)
    {
        Set("DT", dt);
        foreach (var column in ((float[][][])Get("AP0")).SelectMany(row => row))
            for (int k = 0; k < column.Length; k++) column[k] *= scale;
    }
    public string Hash()
    {
        using var bytes = new MemoryStream();
        using var writer = new BinaryWriter(bytes);
        foreach (string name in Coefficients)
            foreach (double value in ((double[][][])Get(name)).SelectMany(row => row).SelectMany(column => column))
            {
                if (!double.IsFinite(value)) throw new Exception("Non-finite coefficient: " + name);
                writer.Write(value);
            }
        return Convert.ToHexString(SHA256.HashData(bytes.ToArray())).ToLowerInvariant();
    }
}

internal static class Checks
{
    public static int Main(string[] args)
    {
        var baseline = new Engine(args[0]);
        var candidate = new Engine(args[1]);
        var rows = new List<object>();
        foreach (var dims in new[] { (12, 13, 6), (31, 24, 12), (64, 48, 24) })
        foreach (int threads in new[] { 1, 2, 8 })
        {
            int ni = dims.Item1, nj = dims.Item2, nk = dims.Item3;
            foreach (Engine engine in new[] { baseline, candidate }) engine.Init(ni, nj, nk, threads, 0);
            if (!double.IsNaN(candidate.Cache!.Value)) throw new Exception("INITA failed to invalidate coefficients.");
            foreach (var stage in new[] { ("first", 1.5, 1f), ("unchanged", 1.5, 1f), ("increase_dt", 3.0, 0.5f), ("decrease_dt", 1.5, 2f), ("new_situation_same_dt", 1.5, 1f) })
            {
                if (stage.Item1 == "new_situation_same_dt")
                {
                    foreach (Engine engine in new[] { baseline, candidate })
                    {
                        engine.Call("ClearArrays"); // The same reset used for weather changes and retries.
                        engine.Init(ni, nj, nk, threads, 1);
                    }
                    if (!double.IsNaN(candidate.Cache!.Value)) throw new Exception("Reinitialization did not invalidate cache.");
                }
                foreach (Engine engine in new[] { baseline, candidate })
                {
                    engine.AdjustInputs(stage.Item2, stage.Item3);
                    engine.Call("TERMIPterms", ni, nj, nk);
                }
                string expected = baseline.Hash(), actual = candidate.Hash();
                if (expected != actual) throw new Exception($"Coefficient mismatch {dims} t{threads} {stage.Item1}");
                if (candidate.Cache != stage.Item2) throw new Exception("Cache DT not updated after successful calculation.");
                rows.Add(new { grid = new[] { ni, nj, nk }, threads, stage = stage.Item1, bitwise_equal = true, sha256 = actual });
            }
            // Directly establish that an unchanged DT bypasses the coefficient writer.
            double[][][] ap = (double[][][])candidate.Get("AP");
            double saved = ap[2][2][1];
            ap[2][2][1] = -123456.789;
            candidate.Call("TERMIPterms", ni, nj, nk);
            if (ap[2][2][1] != -123456.789) throw new Exception("Unchanged DT did not reuse coefficients.");
            ap[2][2][1] = saved;
        }
        var result = new { status = "pass", actual_engine_methods = new[] { "TERMIPterms", "INITA", "ClearArrays" }, cases = rows.Count, cache_hit_checks = 9, rows };
        File.WriteAllText(args[2], JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"PASS cases={rows.Count} cache_hits=9");
        return 0;
    }
}
