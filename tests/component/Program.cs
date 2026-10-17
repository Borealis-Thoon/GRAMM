using System.Collections.Concurrent;
using System.Collections.Immutable;
using System.Globalization;
using System.Reflection;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

record State(string Name, double Air, double Surface, double Qa, double Qg, int Sign);
record Scenario(double FW, double Radiation, double Wind, State Thermal, float InitialOL, double Gradient);
record Result(int Id, int Geometry, int Threads, double FW, double Radiation, double Wind10, string Thermal, float InitialOL, double Gradient, short BaselineClass, short CandidateClass, float OL, double UST, double USTV, double TST, float XWQ, double Ritsch0, double WQU, bool Changed);
sealed class Engine
{
    const BindingFlags Flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static;
    readonly Type core;
    public Engine(string path) => core = new AssemblyLoadContext(Guid.NewGuid().ToString(), true).LoadFromAssemblyPath(Path.GetFullPath(path)).GetType("GRAMM_2001.Program")!;
    public void Set(string name, object value) => core.GetField(name, Flags)!.SetValue(null, value);
    public object Get(string name) => core.GetField(name, Flags)!.GetValue(null)!;
    public void Call(int ni, int nj, int nk, int threads)
    {
        // .NET 10 optionsless Parallel.ForEach uses this private default options object.
        // This isolated test process invokes baseline and candidate serially; production is unchanged.
        var field = typeof(Parallel).GetField("s_defaultParallelOptions", BindingFlags.NonPublic | BindingFlags.Static);
        if (field is null || field.FieldType != typeof(ParallelOptions) || field.GetValue(null) is not ParallelOptions defaults)
            throw new InvalidOperationException("Unsupported runtime: Parallel.s_defaultParallelOptions must be ParallelOptions.");
        int previous = defaults.MaxDegreeOfParallelism;
        try
        {
            defaults.MaxDegreeOfParallelism = threads;
            if (defaults.MaxDegreeOfParallelism != threads || ((ParallelOptions)Get("pOptions")).MaxDegreeOfParallelism != threads)
                throw new InvalidOperationException("Maximum parallelism setting failed.");
            core.GetMethod("Prandtl_calculate", Flags)!.Invoke(null, [ni,nj,nk]);
        }
        finally
        {
            defaults.MaxDegreeOfParallelism = previous;
            if (defaults.MaxDegreeOfParallelism != previous)
                throw new InvalidOperationException("Default ParallelOptions restoration failed.");
        }
    }
    static T[][] Grid<T>(int nx, int ny) => Enumerable.Range(0,nx).Select(_=>new T[ny]).ToArray();
    static T[][][] Volume<T>(int nx, int ny, int nz) => Enumerable.Range(0,nx).Select(_=>Grid<T>(ny,nz)).ToArray();
    public (int NI,int NJ,int NK) Init(List<Scenario> cases, int geometry, int threads)
    {
        int ni=102,nj=(cases.Count+99)/100+2,nk=geometry==0?4:5,nx=ni+2,ny=nj+2,nz=nk+2;
        foreach(string name in new[]{"FW","GLOBRAD","UST","USTV","TST","QUG","WQU","EPSG","RL"}) Set(name,Grid<double>(nx,ny));
        foreach(string name in new[]{"OL","XWQ","Z0"}) Set(name,Grid<float>(nx,ny));
        Set("stabilityclass",Grid<short>(nx,ny));
        foreach(string name in new[]{"U","V","W","T","QU","TABS","TB","TBA"}) Set(name,Volume<double>(nx,ny,nz));
        Set("RITSCH",Volume<double>(nx,ny,nk));
        foreach(string name in new[]{"RHO","FAC"}) Set(name,Volume<float>(nx,ny,nz));
        var heights=Volume<float>(nx,ny,nz); var terrain=Grid<float>(nx,ny);
        double[] z=geometry switch {0=>[0,10,30,90,150,220],1=>[0,5,10,30,60,100,180],_=>[0,20,40,80,120,200,300]};
        for(int i=0;i<nx;i++) for(int j=0;j<ny;j++)
        {
            int index=(j-2)*100+i-2;
            Scenario s=index>=0 && index<cases.Count && i>=2 && i<ni && j>=2 && j<nj ? cases[index] : new(0,0,1,new("padding",290,289,0,0,1),200,0.01);
            float ah=geometry==0?0:geometry==1?123.5f:845.25f; terrain[i][j]=ah;
            ((double[][])Get("FW"))[i][j]=s.FW; ((double[][])Get("GLOBRAD"))[i][j]=s.Radiation;
            ((double[][])Get("QUG"))[i][j]=s.Thermal.Qg; ((float[][])Get("OL"))[i][j]=s.InitialOL;
            ((float[][])Get("Z0"))[i][j]=geometry==2?0.1f:0.001f;
            ((short[][])Get("stabilityclass"))[i][j]=99;
            for(int k=0;k<nz;k++)
            {
                heights[i][j][k]=(float)(ah+z[k]);
                ((double[][][])Get("U"))[i][j][k]=geometry==2?s.Wind*z[k]/10:s.Wind;
                ((double[][][])Get("V"))[i][j][k]=0;
                ((double[][][])Get("W"))[i][j][k]=0.02;
                ((double[][][])Get("T"))[i][j][k]=s.Thermal.Air-273.15 + s.Gradient*(z[k]-z[1]);
                ((double[][][])Get("QU"))[i][j][k]=s.Thermal.Qa;
                ((double[][][])Get("TABS"))[i][j][k]=s.Thermal.Air+s.Gradient*(z[k]-z[1]);
                ((double[][][])Get("TB"))[i][j][k]=s.Thermal.Surface;
                ((double[][][])Get("TBA"))[i][j][k]=s.Thermal.Surface;
                ((float[][][])Get("FAC"))[i][j][k]=1;
                ((float[][][])Get("RHO"))[i][j][k]=1.2f;
            }
        }
        Set("ZSPImm",heights.Select(row=>row.Select(column=>column.ToImmutableArray()).ToArray()).ToArray());
        Set("AHImm",terrain.Select(row=>row.ToImmutableArray()).ToArray());
        Set("DDXImm",Enumerable.Repeat(100f,nx).ToImmutableArray()); Set("DDYImm",Enumerable.Repeat(125f,ny).ToImmutableArray());
        Set("DZB",new float[]{0,0,0.1f,0.2f}); Set("TBZ1",273.15); Set("METEO","N"); Set("ISTAT",(short)2);
        Set("pOptions",new ParallelOptions{MaxDegreeOfParallelism=threads}); Set("StripeCounter",(byte)0);
        Set("PartitionerI",new List<OrderablePartitioner<Tuple<int,int>>>{Partitioner.Create(2,ni,Math.Max(1,100/threads))});
        return(ni,nj,nk);
    }
    public byte[] Bytes(string name)
    {
        using var ms=new MemoryStream(); using var bw=new BinaryWriter(ms);
        object value=Get(name);
        if(value is double[][] d) foreach(var row in d) foreach(double x in row) bw.Write(x);
        else if(value is float[][] f) foreach(var row in f) foreach(float x in row) bw.Write(x);
        else if(value is double[][][] v) foreach(var row in v) foreach(var col in row) foreach(double x in col) bw.Write(x);
        else throw new Exception(name);
        return ms.ToArray();
    }
    public Result Read(int id, int geometry,int threads,Scenario s)
    {
        int i=id%100+2,j=id/100+2;
        short c=((short[][])Get("stabilityclass"))[i][j];
        return new(id,geometry,threads,s.FW,s.Radiation,s.Wind,s.Thermal.Name,s.InitialOL,s.Gradient,c,c,((float[][])Get("OL"))[i][j],((double[][])Get("UST"))[i][j],((double[][])Get("USTV"))[i][j],((double[][])Get("TST"))[i][j],((float[][])Get("XWQ"))[i][j],((double[][][])Get("RITSCH"))[i][j][0],((double[][])Get("WQU"))[i][j],false);
    }
}
static class Check
{
    static void Require(bool ok,string message) { if(!ok) throw new Exception(message); }
    // Independent lookup: rows are the four wind regimes; columns are night, weak, moderate, strong, extreme solar.
    static readonly short[,] Table={{7,4,2,1,1},{6,4,3,2,1},{4,4,3,2,2},{4,4,4,4,3}};
    static short Oracle(Scenario s)
    {
        int wind=s.Wind<=2?0:s.Wind<=3?1:s.Wind<=5?2:3;
        int solar=s.Radiation<=20?0:s.Radiation<=175?1:s.Radiation<=675?2:s.Radiation<=925?3:4;
        short c=Table[wind,solar];
        return solar==0 && wind<2 && s.Gradient<0?(short)(c-1):c;
    }
    static string Hash(string path)=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
    public static int Main(string[] args)
    {
        CultureInfo.CurrentCulture=CultureInfo.InvariantCulture;
        string baselinePath=args[0],candidatePath=args[1],outDir=args[2]; Directory.CreateDirectory(outDir);
        var baseline=new Engine(baselinePath);var candidate=new Engine(candidatePath);
        State[] thermal=[new("stable_dry",290,289,0,0,1),new("unstable_dry",289,290,0,0,-1),new("warm_air_humidity_unstable",290,289,0,15,-1),new("cool_air_humidity_stable",289,290,15,0,1),new("stable_near_zero",290,290-1e-8,0,0,1),new("unstable_near_zero",290,290+1e-8,0,0,-1),new("exact_zero",290,290,0,0,0),new("strong_stable",310,270,0,0,1),new("strong_unstable",270,310,0,0,-1)];
        double[] radiation=[0,19.999,20,20.001,174.999,175,175.001,674.999,675,675.001,924.999,925,925.001,1000];
        double[] wind=[1,1.999,2,2.001,2.999,3,3.001,4.999,5,5.001,6];
        var cases=new List<Scenario>();
        foreach(double fw in new[]{0,0.99,Math.BitIncrement(0.99),1}) foreach(double rad in radiation) foreach(double w in wind) foreach(State st in thermal) foreach(float ol in new[]{-200f,200f}) cases.Add(new(fw,rad,w,st,ol,cases.Count%2==0?0.01:-0.01));
        var rows=new List<Result>();var hashes=new List<object>();var threadSignatures=new Dictionary<int,string>(); var fieldThreadHashes=new Dictionary<string,string>();
        int changed=0,oracleChecks=0,bitwiseFields=0; var clamp=new Dictionary<string,int>{{"positive_5",0},{"negative_5",0},{"positive_1000",0},{"negative_1000",0}};
        foreach(int geometry in new[]{0,1,2}) foreach(int threads in new[]{1,2,8})
        {
            var dims=baseline.Init(cases,geometry,threads);candidate.Init(cases,geometry,threads);
            baseline.Call(dims.NI,dims.NJ,dims.NK,threads);candidate.Call(dims.NI,dims.NJ,dims.NK,threads);
            foreach(string field in new[]{"OL","UST","USTV","TST","XWQ","RITSCH","WQU"})
            {
                byte[] b=baseline.Bytes(field),c=candidate.Bytes(field);Require(b.AsSpan().SequenceEqual(c),$"bitwise {field} geometry={geometry} threads={threads}");bitwiseFields++;
                string fieldHash=Convert.ToHexString(SHA256.HashData(c)).ToLowerInvariant(); string key=$"{geometry}:{field}"; if(threads==1)fieldThreadHashes[key]=fieldHash;else Require(fieldThreadHashes[key]==fieldHash,"field thread invariance "+key); hashes.Add(new{geometry,threads,field,bytes=b.Length,sha256=fieldHash});
            }
            var signature=new StringBuilder();
            for(int id=0;id<cases.Count;id++)
            {
                Scenario s=cases[id]; Result b=baseline.Read(id,geometry,threads,s),c=candidate.Read(id,geometry,threads,s);
                Require(float.IsFinite(c.OL)&&double.IsFinite(c.TST)&&double.IsFinite(c.UST)&&double.IsFinite(c.Ritsch0)&&double.IsFinite(c.WQU),$"finite id={id}");
                Require(b.BaselineClass==Oracle(s),$"lookup oracle id={id} g={geometry}: {b.BaselineClass} !={Oracle(s)}");oracleChecks++;
                // Explicit thermodynamic sign expectation uses curated contrasts including humidity reversal, not computed OL as oracle.
                Require(s.Thermal.Sign==0?c.TST==0:Math.Sign(c.TST)==s.Thermal.Sign,$"thermal sign {s.Thermal.Name} id={id}");
                Require(s.Thermal.Sign<0?c.OL<0:c.OL>0,$"OL sign {s.Thermal.Name} id={id}");
                short expected=s.FW>0.99 && s.Thermal.Sign>=0 && Oracle(s)<4?(short)4:Oracle(s);
                Require(c.CandidateClass==expected,$"candidate oracle id={id}: {c.CandidateClass}!={expected}");oracleChecks++;
                bool isChanged=b.BaselineClass!=c.CandidateClass;
                if(isChanged) {Require(b.BaselineClass is >=1 and <=3 && c.CandidateClass==4,"change outside 1..3 to 4");changed++;}
                if(c.OL==5)clamp["positive_5"]++;if(c.OL==-5)clamp["negative_5"]++;if(c.OL==1000)clamp["positive_1000"]++;if(c.OL==-1000)clamp["negative_1000"]++;
                rows.Add(c with{BaselineClass=b.BaselineClass,Changed=isChanged});signature.Append(c.CandidateClass).Append(':').Append(BitConverter.SingleToInt32Bits(c.OL)).Append(':').Append(BitConverter.DoubleToInt64Bits(c.TST)).Append(';');
            }
            string sign=Convert.ToHexString(SHA256.HashData(Encoding.ASCII.GetBytes(signature.ToString())));
            if(threads==1)threadSignatures[geometry]=sign;else Require(threadSignatures[geometry]==sign,"thread invariance");
            Console.WriteLine($"PASS geometry={geometry} threads={threads} cells={cases.Count}");
        }
        foreach(var kv in clamp)Require(kv.Value>0,"missing clamp "+kv.Key);
        // Radiation independence across all daytime solar bands for positive surface stability over water.
        var waterGroups=rows.Where(r=>r.FW>0.99&&r.OL>0&&r.Radiation>20).GroupBy(r=>new{r.Geometry,r.Threads,r.FW,r.Wind10,r.Thermal,r.InitialOL,r.Gradient}).ToArray();
        foreach(var group in waterGroups)Require(group.All(r=>r.CandidateClass==4),"stable water solar dependence");
        // Fixed representative examples independently assert physical and class expectations at a normal 10 m first level.
        var representatives=new[]{("stable_dry",1.0,675.0,1.0,(short)2,(short)4),("stable_dry",1.0,675.0,2.001,(short)3,(short)4),("stable_dry",1.0,1000.0,1.0,(short)1,(short)4),("unstable_dry",1.0,1000.0,1.0,(short)1,(short)1),("warm_air_humidity_unstable",1.0,1000.0,1.0,(short)1,(short)1),("cool_air_humidity_stable",1.0,1000.0,1.0,(short)1,(short)4),("stable_dry",0.99,1000.0,1.0,(short)1,(short)1),("stable_dry",1.0,175.0,1.0,(short)4,(short)4),("stable_dry",1.0,0.0,1.0,(short)7,(short)7),("stable_dry",1.0,0.0,2.001,(short)6,(short)6)};
        foreach(var r in representatives) {var m=rows.First(x=>x.Geometry==0&&x.Threads==1&&x.Thermal==r.Item1&&x.FW==r.Item2&&x.Radiation==r.Item3&&x.Wind10==r.Item4&&x.InitialOL==-200);Require(m.BaselineClass==r.Item5&&m.CandidateClass==r.Item6,"fixed representative "+r.Item1);}
        string csv=Path.Combine(outDir,"cell_results.csv");using(var writer=new StreamWriter(csv,false,new UTF8Encoding(false)))
        {
            writer.WriteLine("id,geometry,threads,FW,radiation,wind10,thermal,initial_OL,gradient,baseline_class,candidate_class,OL,UST,USTV,TST,XWQ,RITSCH0,WQU,changed");
            foreach(var r in rows)writer.WriteLine(FormattableString.Invariant($"{r.Id},{r.Geometry},{r.Threads},{r.FW:R},{r.Radiation:R},{r.Wind10:R},{r.Thermal},{r.InitialOL:R},{r.Gradient:R},{r.BaselineClass},{r.CandidateClass},{r.OL:R},{r.UST:R},{r.USTV:R},{r.TST:R},{r.XWQ:R},{r.Ritsch0:R},{r.WQU:R},{r.Changed}"));
        }
        var summary=new{status="pass",method="production GRAMM_2001.Program.Prandtl_calculate via isolated AssemblyLoadContext reflection",baseline_dll_sha256=Hash(baselinePath),candidate_dll_sha256=Hash(candidatePath),candidate_prandtl_sha256=args.Length>3?Hash(args[3]):null,harness_dll_sha256=Hash(typeof(Check).Assembly.Location),harness_source_sha256=File.Exists(Path.Combine(AppContext.BaseDirectory,"..","..","..","Program.cs"))?Hash(Path.Combine(AppContext.BaseDirectory,"..","..","..","Program.cs")):null,unique_cell_scenarios=cases.Count,executed_cell_scenarios=rows.Count,changed_classes=changed,unchanged_classes=rows.Count-changed,oracle_checks=oracleChecks,representative_checks=representatives.Length,bitwise_field_comparisons=bitwiseFields,fields=new[]{"OL","UST","USTV","TST","XWQ","RITSCH","WQU"},stable_water_daytime_groups=waterGroups.Length,clamp_counts=clamp,maximum_parallelism_levels=new[]{1,2,8},parallelism_control=new{runtime=Environment.Version.ToString(),first_two_phases="reflection: Parallel.s_defaultParallelOptions.MaxDegreeOfParallelism",last_phase="production Program.pOptions.MaxDegreeOfParallelism",private_field_type_asserted=true,setting_asserted=true,previous_default_restored_in_finally=true,actual_running_threads_measured=false},vertical_geometries=3,baseline_classes=rows.GroupBy(r=>r.BaselineClass).ToDictionary(g=>g.Key.ToString(),g=>g.Count()),candidate_classes=rows.GroupBy(r=>r.CandidateClass).ToDictionary(g=>g.Key.ToString(),g=>g.Count()),class_transitions=rows.GroupBy(r=>$"{r.BaselineClass}->{r.CandidateClass}").ToDictionary(g=>g.Key,g=>g.Count()),csv_sha256=Hash(csv),output_hashes=hashes,limits=new[]{"synthetic initialized production arrays; no full-domain forecast or timestep integration", "FW is an existing water marker, not validated land-sea geography", "maximum parallelism 1/2/8 is configured; actual simultaneously running worker threads are not measured", "the first two optionsless Parallel.ForEach phases are capped by reflection into .NET 10 private Parallel.s_defaultParallelOptions; field type and value are asserted and the previous value is restored in finally; this is a runtime-specific test mechanism", "this corrected run supersedes the earlier unsupported claim that an outer ConcurrentExclusiveSchedulerPair capped the optionsless loops", "zero TST produces infinity in raw OL then existing production clamp yields positive 1000", "NaN inputs excluded as invalid physics"}};
        File.WriteAllText(Path.Combine(outDir,"component_checks.json"),JsonSerializer.Serialize(summary,new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine($"PASS total={rows.Count} changed={changed} oracle={oracleChecks} fields={bitwiseFields}");return 0;
    }
}


