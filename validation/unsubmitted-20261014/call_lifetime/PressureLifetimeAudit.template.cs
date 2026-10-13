using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;

namespace GRAMM_2001
{
    // Audit only: observe completed calls without writing any model field.
    internal static class PressureLifetimeAudit
    {
        private static int calls;
        private static object Field<T>(string name, T[][][] data) where T : unmanaged
        {
            using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
            long count = 0, finite = 0;
            foreach (var plane in data)
            foreach (var column in plane)
            {
                hash.AppendData(MemoryMarshal.AsBytes(column.AsSpan()));
                foreach (T value in column)
                {
                    count++;
                    if (typeof(T) == typeof(float) ? float.IsFinite((float)(object)value) : double.IsFinite((double)(object)value)) finite++;
                }
            }
            if (count != finite) throw new InvalidDataException("Nonfinite audit field: " + name);
            return new { name, count, finite, sha256 = Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant() };
        }
        private static string Hash(double[] data)
        {
            if (data.Any(v => !double.IsFinite(v))) throw new InvalidDataException("Nonfinite audit scalar");
            return Convert.ToHexString(SHA256.HashData(MemoryMarshal.AsBytes(data.AsSpan()))).ToLowerInvariant();
        }
        internal static void Write(bool returned)
        {
            if (returned) calls++;
            long restored = 0;
            if (returned)
            {
                for (int i = 2; i < Program.NX; i++)
                for (int j = 2; j < Program.NY; j++)
                {
                    ReadOnlySpan<float> AREA_L = Program.AREAImm[i][j].AsSpan();
                    ReadOnlySpan<float> AREAZ_L = Program.AREAZImm[i][j].AsSpan();
                    ReadOnlySpan<float> AREAX_L = Program.AREAXImm[i][j].AsSpan();
                    ReadOnlySpan<float> AREAY_L = Program.AREAYImm[i][j].AsSpan();
                    ReadOnlySpan<float> AREAZY_L = Program.AREAZYImm[i][j].AsSpan();
                    ReadOnlySpan<float> AREAZX_L = Program.AREAZXImm[i][j].AsSpan();
                    ReadOnlySpan<float> AREAXYZ_L = Program.AREAXYZImm[i][j].AsSpan();
                    ReadOnlySpan<float> U1NRHO_L = Program.U1NRHO[i][j];
                    ReadOnlySpan<float> U2NRHO_L = Program.U2NRHO[i][j];
                    ReadOnlySpan<float> V1NRHO_L = Program.V1NRHO[i][j];
                    ReadOnlySpan<float> V2NRHO_L = Program.V2NRHO[i][j];
                    ReadOnlySpan<float> W1NRHO_L = Program.W1NRHO[i][j];
                    ReadOnlySpan<float> W2NRHO_L = Program.W2NRHO[i][j];
                    for (int k = 1; k < Program.NZ; k++)
                    {
                        float expectedZ = __EXPRESSION_Z__;
                        float expectedXYZ = __EXPRESSION_XYZ__;
                        if (BitConverter.SingleToInt32Bits(expectedZ) != BitConverter.SingleToInt32Bits(Program.SUZ[i][j][k]) ||
                            BitConverter.SingleToInt32Bits(expectedXYZ) != BitConverter.SingleToInt32Bits(Program.SUXYZ[i][j][k]))
                            throw new InvalidDataException("Unrestored pressure divergence");
                        restored += 2;
                    }
                }
            }
            var fields = new List<object> {
                Field("SUZ", Program.SUZ), Field("SUXYZ", Program.SUXYZ),
                Field("DP", Program.DP), Field("DPX", Program.DPX), Field("DPY", Program.DPY), Field("DPZ", Program.DPZ),
                Field("U1N", Program.U1N), Field("U2N", Program.U2N), Field("V1N", Program.V1N), Field("V2N", Program.V2N),
                Field("W1N", Program.W1N), Field("W2N", Program.W2N)
            };
            var scalarValues = new double[] { Program.SUMG, Program.MASSOURCE_FIRST, Program.MASSOURCE_Act,
                Program.MASSOURCE_Old, Program.STEIGUNG, Program.DT, Program.REALTIME };
            var row = new {
                kind = returned ? "calcpr_return" : "weather_end", calls, weather = Program.IWETTER, itime = Program.ITIME,
                icpn = Program.ICPN, nx = Program.NX, ny = Program.NY, nz = Program.NZ, inums = Program.INUMS,
                idiv = Program.IDIV, idiv_up = Program.IDIV_Up, retries = Program.computation_retry,
                restored_values = restored, scalar_values = scalarValues, scalar_sha256 = Hash(scalarValues),
                massource_values = Program.MASSOURCE, massource_sha256 = Hash(Program.MASSOURCE),
                queue_sha256 = Hash(Program.MASSOURCE_Queue.ToArray()), fields
            };
            File.AppendAllText("pressure_lifetime.jsonl", JsonSerializer.Serialize(row) + Environment.NewLine);
        }
    }
}
