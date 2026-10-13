using System.Security.Cryptography;
using System.Text.Json;

static class Check {
    static string Digest(double[][][][] fields, out long n) {
        using var hash=IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        n=0;
        foreach(var field in fields) foreach(var row in field) foreach(var column in row) foreach(double value in column) {
            if(!double.IsFinite(value)) throw new Exception("Non-finite output");
            hash.AppendData(BitConverter.GetBytes(value)); n++;
        }
        return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
    }
    static void Main(string[] args) {
        var rows=new List<object>(); long total=0;
        foreach(var grid in new[]{(1,1,2),(8,7,10),(24,18,25),(64,48,40),(0,5,10),(5,0,10),(5,5,0),(5,5,1)}) {
            var (ni,nj,nk)=grid;
            foreach(int profile in Enumerable.Range(0,5)) foreach(int phase in Enumerable.Range(0,3)) {
                var baseline=new Baseline.RadiationCalculation(); var candidate=new Candidate.RadiationCalculation();
                baseline.Init(ni,nj,nk,profile,phase); candidate.Init(ni,nj,nk,profile,phase);
                foreach(int loopNk in nk==25 ? new[]{3,nk} : new[]{nk}) {
                baseline.Calls=0; candidate.Calls=0;
                baseline.RunProfile(ni,nj,loopNk); candidate.RunProfile(ni,nj,loopNk);
                string b=Digest(baseline.Fields(),out long count),c=Digest(candidate.Fields(),out long count2);
                if(b!=c||count!=count2) throw new Exception($"Output mismatch {grid} {profile} {phase}");
                long expectedBase=(long)ni*nj*Math.Max(0,loopNk-1),expectedCandidate=Math.Max(0,loopNk-1);
                if(baseline.Calls!=expectedBase||candidate.Calls!=expectedCandidate) throw new Exception("Call count mismatch");
                if(nk>=2) {
                    double[] clean=candidate.IgnoredRefInputs(2,0), dirty=candidate.IgnoredRefInputs(2,double.NaN);
                    if(!clean.Select(BitConverter.DoubleToInt64Bits).SequenceEqual(dirty.Select(BitConverter.DoubleToInt64Bits))) throw new Exception("Previous ref values affected result");
                }
                total+=count;
                rows.Add(new{ni,nj,nk,loop_nk=loopNk,profile,phase,values=count,sha256=c,baseline_calls=expectedBase,candidate_calls=expectedCandidate,bitwise_equal=true});
                }
            }
        }
        var report=new{status="pass",cases=rows.Count,finite_bitwise_equal_values=total,actual_source_loop=true,actual_methods=new[]{"RadiationCalculation.Cl_EpsA","RadiationCalculation.Cl_Eps"},thread_note="The changed block is serial. Worker-setting coverage belongs to whole-engine validation.",rows};
        File.WriteAllText(args[0],JsonSerializer.Serialize(report,new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine($"[PASS] {rows.Count} source-derived cases; {total} finite exact values");
    }
}
