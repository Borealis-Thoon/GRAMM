using System.Collections.Concurrent;
using System.Collections.Immutable;
using System.Reflection;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;

sealed class Engine
{
    readonly Type p;
    public Engine(string path, string name)
    {
        var alc = new AssemblyLoadContext(name, false);
        p = alc.LoadFromAssemblyPath(Path.GetFullPath(path)).GetType("GRAMM_2001.Program", true)!;
    }
    public object Get(string name) => p.GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static)!.GetValue(null)!;
    public void Set(string name, object value) { var f=p.GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static)!; f.SetValue(null,value is IConvertible ? Convert.ChangeType(value,f.FieldType) : value); }
    public bool Has(string name) => p.GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static) != null;
    public void Call(string name, params object[] args) => p.GetMethod(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null, args);
    static double[][][] D3(int ni, int nj, int nk, Func<int,int,int,double> f) => Enumerable.Range(0,ni+2).Select(i=>Enumerable.Range(0,nj+2).Select(j=>Enumerable.Range(0,nk+2).Select(k=>f(i,j,k)).ToArray()).ToArray()).ToArray();
    static float[][][] F3(int ni, int nj, int nk, Func<int,int,int,float> f) => Enumerable.Range(0,ni+2).Select(i=>Enumerable.Range(0,nj+2).Select(j=>Enumerable.Range(0,nk+2).Select(k=>f(i,j,k)).ToArray()).ToArray()).ToArray();
    public void Init(int ni,int nj,int nk,int threads,bool enabled)
    {
        Set("pOptions", new ParallelOptions { MaxDegreeOfParallelism=threads });
        Set("NZ1", nk+2); Set("ICSTR", enabled); Set("ICTB", true); Set("RELAXT", .5d); Set("StripeCounter",0); Set("ISTAT",2); Set("BGRAD",47d);
        Set("PartitionerI", new List<OrderablePartitioner<Tuple<int,int>>> { Partitioner.Create(2,ni,Math.Max(1,(ni-2)/threads)) });
        Set("PartitionerJ", new List<OrderablePartitioner<Tuple<int,int>>> { Partitioner.Create(2,nj,Math.Max(1,(nj-2)/threads)) });
        foreach(var name in new[]{"A_PS","B_PS","C_PS","DT_SOL","DT_TERR","NBZKP","PNBZKP","T","TN"})
        {
            Set(name,D3(ni,nj,nk,(i,j,k)=>name switch {
                "A_PS"=>2+.001*k, "B_PS"=>.08, "C_PS"=>.06,
                "DT_SOL"=>.00001*(1+i+2*j+k), "DT_TERR"=>-.000003*(1+i+j+k),
                "NBZKP"=>Math.Clamp(k,1,nk-1), "PNBZKP"=>(i+j+k)%7/7d,
                "T"=>2+.01*k, "TN"=>2+.01*k, _=>0 }));
        }
        Set("RADIATION", Enumerable.Range(0,ni+2).Select(_=>Enumerable.Range(0,nj+2).Select(_=>new double[nk]).ToArray()).ToArray());
        foreach(var name in new[]{"AEAST_PS","ANORTH_PS","ASOUTH_PS","AWEST_PS","AP0_PS","FAC","RHO"})
            Set(name,F3(ni,nj,nk,(i,j,k)=>name switch { "AP0_PS"=>.8f,"FAC"=>1+.0002f*k,"RHO"=>1.2f-.001f*k,_=>0 }));
        Set("VOLImm",F3(ni,nj,nk,(i,j,k)=>10000+10*i+j+k).Select(row=>row.Select(ImmutableArray.CreateRange).ToArray()).ToArray());
        Set("ZSPImm",F3(ni,nj,nk,(i,j,k)=>10*k).Select(row=>row.Select(ImmutableArray.CreateRange).ToArray()).ToArray());
        Set("WQU",Enumerable.Range(0,ni+2).Select(i=>Enumerable.Range(0,nj+2).Select(j=>20d+.1*i+j).ToArray()).ToArray());
        Set("AWQ",Enumerable.Range(0,ni+2).Select(i=>Enumerable.Range(0,nj+2).Select(j=>2f+.01f*j).ToArray()).ToArray());
        Call("INITA",ni,nj,nk);
    }
    public void Modify(string field, Action<double[][][]> mutation) => mutation((double[][][])Get(field));
    public string Hash(string field,int ni,int nj,int nk)
    {
        using var mem=new MemoryStream(); using var bw=new BinaryWriter(mem);
        var arr=(double[][][])Get(field);
        for(int i=2;i<ni;i++)for(int j=2;j<nj;j++)for(int k=1;k<nk;k++)
        { if(!double.IsFinite(arr[i][j][k]))throw new Exception("Nonfinite "+field); bw.Write(arr[i][j][k]); }
        return Convert.ToHexString(SHA256.HashData(mem.ToArray())).ToLowerInvariant();
    }
}

static class Program
{
    static void Main(string[] args)
    {
        var baseline=new Engine(args[0],"reference"); var candidate=new Engine(args[1],"candidate"); var rows=new List<object>();
        foreach(var g in new[]{(8,7,6),(24,18,12),(56,40,20)}) foreach(int t in new[]{1,2,4}) foreach(bool on in new[]{false,true})
        {
            var (ni,nj,nk)=g; baseline.Init(ni,nj,nk,t,on); candidate.Init(ni,nj,nk,t,on);
            foreach(string phase in new[]{"initial","unchanged_source","temperature_only","heating_refresh","situation_refresh","radiation_disabled"})
            {
                foreach(var e in new[]{baseline,candidate})
                {
                    if(phase=="temperature_only")e.Modify("T",a=>a[3][3][2]+=.125);
                    if(phase=="heating_refresh")
                    {
                        e.Modify("DT_SOL",a=>a[3][3][2]+=.002);
                        e.Call("INITA",ni,nj,nk);
                    }
                    if(phase=="situation_refresh")
                    {
                        e.Call("INITA",ni,nj,nk);
                        ((float[][][])e.Get("RHO"))[3][3][2]*=.95f;
                        ((float[][][])e.Get("FAC"))[3][3][2]*=1.03f;
                    }
                    if(phase=="radiation_disabled") { e.Set("ICSTR",false); e.Call("INITA",ni,nj,nk); }
                    if(e.Has("RadiationSourceNeedsUpdate") && phase is "heating_refresh" or "situation_refresh" or "radiation_disabled")
                        if(!(bool)e.Get("RadiationSourceNeedsUpdate"))throw new Exception("INITA did not invalidate");
                    e.Call("Timp_calculate",ni,nj,nk);
                    if(e.Has("RadiationSourceNeedsUpdate") && (bool)e.Get("RadiationSourceNeedsUpdate"))throw new Exception("TIMP did not clear dirty state");
                }
                var br=baseline.Hash("RADIATION",ni,nj,nk); var cr=candidate.Hash("RADIATION",ni,nj,nk); var bt=baseline.Hash("TN",ni,nj,nk);var ct=candidate.Hash("TN",ni,nj,nk);
                if(br!=cr||bt!=ct)throw new Exception($"Mismatch {g} {t} {on} {phase}");
                rows.Add(new {nx=ni,ny=nj,nz=nk,threads=t,radiation=on,phase,radiation_sha256=cr,temperature_sha256=ct,exact=true});
            }
        }
        File.WriteAllText(args[2],JsonSerializer.Serialize(new {status="pass",cases=rows.Count,actual_methods=new[]{"Program.Timp_calculate","Program.INITA (ISTAT=2)"},lateral_transport_coefficients=0,rows},new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine($"[PASS] {rows.Count} actual-method cases");
    }
}
