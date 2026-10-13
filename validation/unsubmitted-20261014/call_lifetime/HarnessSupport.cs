using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text.Json;
using System.Threading.Tasks;

namespace GRAMM_2001
{
    // Test-only adapters. This file is not part of any proposed GRAMM source patch.
    internal static class HarnessParallel
    {
        internal static readonly bool Serial = Environment.GetEnvironmentVariable("GRAMM_TEST_SERIAL") == "1";
        public static void For(int fromInclusive, int toExclusive, ParallelOptions options, Action<int> body)
        {
            if (Serial)
            {
                for (int i = fromInclusive; i < toExclusive; i++) body(i);
                return;
            }
            Parallel.For(fromInclusive, toExclusive, options, body);
        }
        public static void ForEach<T>(Partitioner<T> source, Action<T> body)
        {
            if (Serial)
            {
                using (IEnumerator<T> iterator = source.GetPartitions(1)[0])
                {
                    while (iterator.MoveNext()) body(iterator.Current);
                }
                return;
            }
            Parallel.ForEach(source, body);
        }
    }
    internal static class HarnessConsole
    {
        public static int CursorTop
        {
            get
            {
                if (Console.IsOutputRedirected) return 0;
                try { return Console.CursorTop; }
                catch (IOException) { return 0; }
                catch (PlatformNotSupportedException) { return 0; }
            }
        }
        public static void SetCursorPosition(int left, int top)
        {
            if (Console.IsOutputRedirected) return;
            try { Console.SetCursorPosition(left, top); }
            catch (IOException) { }
            catch (PlatformNotSupportedException) { }
        }
    }
    internal static class HarnessSnapshot
    {
        internal static void Write(int startWeather, int endWeather, int iterations, double realtime)
        {
            if (Environment.GetEnvironmentVariable("GRAMM_TEST_SNAPSHOT") != "1") return;
            if (!BitConverter.IsLittleEndian) throw new PlatformNotSupportedException("Snapshot uses little-endian doubles");
            bool binary = Environment.GetEnvironmentVariable("GRAMM_TEST_BINARY") == "1";
            string prefix = "harness_snapshot_" + startWeather.ToString("D5", CultureInfo.InvariantCulture);
            var fields = new List<object>();
            foreach (var entry in new (string Name, double[][][] Data)[] {
                ("U", Program.U), ("V", Program.V), ("W", Program.W), ("T", Program.T), ("QU", Program.QU),
                ("PN", Program.PN), ("TE", Program.TE), ("DISS", Program.DISS), ("RADIATION", Program.RADIATION) })
            {
                string binaryPath = binary ? prefix + "_" + entry.Name + ".bin" : null;
                using var output = binary ? File.Create(binaryPath) : null;
                using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
                long count = 0, finiteCount = 0;
                double min = double.PositiveInfinity, max = double.NegativeInfinity;
                foreach (var plane in entry.Data)
                foreach (var column in plane)
                {
                    ReadOnlySpan<byte> bytes = System.Runtime.InteropServices.MemoryMarshal.AsBytes(column.AsSpan());
                    hash.AppendData(bytes);
                    output?.Write(bytes);
                    foreach (double value in column)
                    {
                        count++;
                        if (double.IsFinite(value))
                        {
                            finiteCount++; min = Math.Min(min, value); max = Math.Max(max, value);
                        }
                    }
                }
                fields.Add(new { name = entry.Name, count, finite_count = finiteCount, finite = count == finiteCount,
                    min = finiteCount > 0 ? (double?)min : null, max = finiteCount > 0 ? (double?)max : null,
                    sha256 = Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant(), binary_file = binaryPath });
            }
            File.WriteAllText(prefix + ".json", JsonSerializer.Serialize(new {
                weather_start = startWeather, weather_end = endWeather, itime = iterations, realtime,
                nx = Program.NX, ny = Program.NY, nz = Program.NZ,
                encoding = "float64-le", order = "i,j,k including allocated halo cells", fields
            }, new JsonSerializerOptions { WriteIndented = true }));
        }
    }
    internal static class HarnessTiming
    {
        internal static void Write(Stopwatch timer, int startWeather, int endWeather, int iterations, double dt,
            double realtime, double timeLimit, int retries, int configuredThreads)
        {
            const string path = "harness_integration.csv";
            bool header = !File.Exists(path);
            using (var writer = new StreamWriter(path, true))
            {
                if (header) writer.WriteLine("weather_start,weather_end,elapsed_seconds,itime,dt,realtime,tlimit,retries,configured_threads,serial");
                writer.WriteLine(string.Join(",", startWeather.ToString(CultureInfo.InvariantCulture),
                    endWeather.ToString(CultureInfo.InvariantCulture), timer.Elapsed.TotalSeconds.ToString("R", CultureInfo.InvariantCulture),
                    iterations.ToString(CultureInfo.InvariantCulture), dt.ToString("R", CultureInfo.InvariantCulture),
                    realtime.ToString("R", CultureInfo.InvariantCulture), timeLimit.ToString("R", CultureInfo.InvariantCulture),
                    retries.ToString(CultureInfo.InvariantCulture), configuredThreads.ToString(CultureInfo.InvariantCulture), HarnessParallel.Serial ? "1" : "0"));
            }
        }
    }
}
