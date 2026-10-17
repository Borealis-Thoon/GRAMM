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

record TemporalRow(string Engine,int Geometry,int Threads,int InitialAKLA,string Phase,int Step,int Id,string Thermal,double FW,double Radiation,double Wind,double Gradient,short Class,short Expected,float OL,double TST,short AKLA,int BoundaryCells);
static class TemporalCheck
{
    static void Require(bool ok,string message) { if(!ok) throw new Exception(message); }
    static string Hash(string path)=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
    static short Oracle(double rad,double wind,double grad)
    {
        if(wind<=2) return rad<=20?(short)(grad<0?6:7):rad<=175?(short)4:rad<=675?(short)2:(short)1;
        if(wind<=3) return rad<=20?(short)(grad<0?5:6):rad<=175?(short)4:rad<=675?(short)3:rad<=925?(short)2:(short)1;
        if(wind<=5) return rad<=175?(short)4:rad<=675?(short)3:(short)2;
        return rad<=925?(short)4:(short)3;
    }
    public static int Main(string[] args)
    {
        CultureInfo.CurrentCulture=CultureInfo.InvariantCulture;
        string outDir=Path.GetFullPath(args[2]);Directory.CreateDirectory(outDir);
        var rows=new List<TemporalRow>();var checks=new Dictionary<string,int>();var fieldHashes=new List<object>();
        void Assert(bool ok,string key) { Require(ok,key); checks[key]=checks.GetValueOrDefault(key)+1; }
        try
        {
            State[] states=[new("stable_dry",290,289,0,0,1),new("unstable_dry",289,290,0,0,-1),new("humidity_unstable",290,289,0,15,-1),new("zero_flux",290,290,0,0,0)];
            var cases=new List<Scenario>();
            foreach(double fw in new[]{0,0.99,Math.BitIncrement(0.99),1}) foreach(State thermal in states) cases.Add(new(fw,0,1,thermal,200,0.01));
            double[] radiation=[0,100,300,800,300,0];
            string[] names=["baseline","candidate"];
            foreach(int geometry in new[]{0,1,2}) foreach(int threads in new[]{1,2,8}) foreach(short initial in new short[]{1,6})
            {
                var pair=new[]{new Engine(args[0]),new Engine(args[1])};
                var dims=pair[0].Init(cases,geometry,threads);pair[1].Init(cases,geometry,threads);
                foreach(var e in pair)
                {
                    e.Set("AKLA",initial);
                    foreach(var row in (short[][])e.Get("stabilityclass")) Array.Fill(row,initial);
                }
                // Both production engines are invoked in place. Initialization is not repeated between steps.
                var phaseInputs=new List<(string Phase,int Step,double Rad,double Wind,double Gradient)>();
                for(int n=0;n<radiation.Length;n++) phaseInputs.Add(("solar_roundtrip",n,radiation[n],1,0.01));
                double[] winds=[1,2.5,4,6,1];
                for(int n=0;n<winds.Length;n++) phaseInputs.Add(("wind_roundtrip",n,800,winds[n],0.01));
                double[] gradients=[0.01,-0.01,0.01];
                for(int n=0;n<gradients.Length;n++) phaseInputs.Add(("gradient_roundtrip",n,0,1,gradients[n]));
                var signatures=new Dictionary<string,List<short>>();
                foreach(var input in phaseInputs)
                {
                    for(int ei=0;ei<pair.Length;ei++)
                    {
                        Engine e=pair[ei];var z=(ImmutableArray<float>[][])e.Get("ZSPImm");var ah=(ImmutableArray<float>[])e.Get("AHImm");
                        for(int id=0;id<cases.Count;id++)
                        {
                            int i=id%100+2,j=id/100+2;
                            ((double[][])e.Get("GLOBRAD"))[i][j]=input.Rad;
                            var u=((double[][][])e.Get("U"))[i][j];var tabs=((double[][][])e.Get("TABS"))[i][j];
                            for(int k=0;k<u.Length;k++) {u[k]=geometry==2?input.Wind*(z[i][j][k]-ah[i][j])/10:input.Wind; tabs[k]=cases[id].Thermal.Air+input.Gradient*(z[i][j][k]-z[i][j][1]);}
                        }
                        e.Call(dims.NI,dims.NJ,dims.NK,threads);
                        var classes=(short[][])e.Get("stabilityclass");int boundaryCells=0;
                        for(int i=1;i<=dims.NI;i++) for(int j=1;j<=dims.NJ;j++) if(i==1||i==dims.NI||j==1||j==dims.NJ) {Assert(classes[i][j]==initial,"boundary_initial_persists");boundaryCells++;}
                        Assert((short)e.Get("AKLA")==initial,"AKLA_initial_persists");
                        for(int id=0;id<cases.Count;id++)
                        {
                            Scenario s=cases[id];Result r=e.Read(id,geometry,threads,s);
                            short expected=Oracle(input.Rad,input.Wind,input.Gradient);
                            if(ei==1&&s.FW>0.99&&s.Thermal.Sign>=0&&expected<4)expected=4;
                            Assert(r.CandidateClass==expected,"independent_class_oracle");
                            Assert(float.IsFinite(r.OL)&&double.IsFinite(r.TST)&&double.IsFinite(r.UST),"finite_surface_state");
                            Assert(s.Thermal.Sign<0?r.OL<0:r.OL>0,"curated_OL_sign");
                            if(ei==1&&s.FW>0.99&&s.Thermal.Sign>=0)Assert(r.CandidateClass>=4,"positive_OL_water_floor");
                            if(s.FW<=0.99||s.Thermal.Sign<0)Assert(r.CandidateClass==Oracle(input.Rad,input.Wind,input.Gradient),"land_or_unstable_lookup_preserved");
                            rows.Add(new(names[ei],geometry,threads,initial,input.Phase,input.Step,id,s.Thermal.Name,s.FW,input.Rad,input.Wind,input.Gradient,r.CandidateClass,expected,r.OL,r.TST,(short)e.Get("AKLA"),boundaryCells));
                            string key=$"{ei}:{input.Phase}:{id}";if(!signatures.ContainsKey(key))signatures[key]=[];signatures[key].Add(r.CandidateClass);
                        }
                    }
                    // Candidate is a class-only patch. All calculated physical fields must stay bitwise equal at every repeated step.
                    foreach(string field in new[]{"OL","UST","USTV","TST","XWQ","RITSCH","WQU"})
                    {
                        byte[] b=pair[0].Bytes(field),c=pair[1].Bytes(field);Assert(b.AsSpan().SequenceEqual(c),"bitwise_physical_field_pair");
                        fieldHashes.Add(new{geometry,threads,initial_AKLA=initial,phase=input.Phase,step=input.Step,field,sha256=Convert.ToHexString(SHA256.HashData(c)).ToLowerInvariant()});
                    }
                }
                foreach(var item in signatures)
                {
                    string phase=item.Key.Split(':')[1];Assert(item.Value[0]==item.Value[^1],"class_roundtrip_restores_"+phase);
                    // Stable water stays neutral for all daytime inputs, but still switches to its night class.
                    if(phase=="solar_roundtrip") Assert(item.Value.Distinct().Count()>1,"solar_class_changes_in_place");
                }
                Console.WriteLine($"PASS geometry={geometry} threads={threads} initial_AKLA={initial}");
            }
            // In-place changes must be independent of initialization class and configured thread cap.
            foreach(var group in rows.GroupBy(r=>new{r.Engine,r.Geometry,r.Phase,r.Step,r.Id})) Assert(group.Select(r=>r.Class).Distinct().Count()==1,"class_independent_initial_AKLA_and_thread_cap");
            string csv=Path.Combine(outDir,"temporal_cell_results.csv");using(var w=new StreamWriter(csv,false,new UTF8Encoding(false)))
            {
                w.WriteLine("engine,geometry,threads,initial_AKLA,phase,step,id,thermal,FW,radiation,wind10,gradient,class,expected,OL,TST,AKLA,boundary_cells");
                foreach(var r in rows)w.WriteLine(FormattableString.Invariant($"{r.Engine},{r.Geometry},{r.Threads},{r.InitialAKLA},{r.Phase},{r.Step},{r.Id},{r.Thermal},{r.FW:R},{r.Radiation:R},{r.Wind:R},{r.Gradient:R},{r.Class},{r.Expected},{r.OL:R},{r.TST:R},{r.AKLA},{r.BoundaryCells}"));
            }
            var representative=rows.Where(r=>r.Geometry==0&&r.Threads==1&&r.InitialAKLA==6&&r.Phase=="solar_roundtrip"&&r.FW==1&&r.Thermal=="stable_dry").GroupBy(r=>r.Engine).ToDictionary(g=>g.Key,g=>g.Select(r=>r.Class).ToArray());
            string source=Path.Combine(AppContext.BaseDirectory,"..","..","..","Program.cs");
            File.WriteAllText(Path.Combine(outDir,"temporal_checks.json"),JsonSerializer.Serialize(new{status="pass",method="repeated in-place calls to production Prandtl_calculate via isolated AssemblyLoadContext",radiation_sequence=radiation,wind_sequence=new[]{1,2.5,4,6,1},gradient_sequence=new[]{0.01,-0.01,0.01},initial_AKLA=new[]{1,6},geometries=3,maximum_parallelism=new[]{1,2,8},unique_surface_cases=cases.Count,executed_cell_states=rows.Count,production_method_calls=18*14*2,checks,stable_water_solar_classes=representative,baseline_dll_sha256=Hash(args[0]),candidate_dll_sha256=Hash(args[1]),baseline_prandtl_sha256=Hash(args[3]),candidate_prandtl_sha256=Hash(args[4]),initializer_source_sha256=Hash(args[5]),harness_source_sha256=File.Exists(source)?Hash(source):null,harness_dll_sha256=Hash(typeof(TemporalCheck).Assembly.Location),csv_sha256=Hash(csv),physical_field_hashes=fieldHashes,limits=new[]{"synthetic repeated production-method calls; no SIMPLE timestep, radiation solver, INITB execution, or output writer integration", "initial stabilityclass grid manually initialized to the documented INITB assignment; full INITB is not executed", "current radiation, wind and TABS are explicitly changed by the harness; physical time and forcing schedule are not advanced", "1/2/8 are configured maximum thread caps, not measured simultaneous worker counts", "private .NET 10 Parallel.s_defaultParallelOptions control reused from prior harness with assertion and finally restoration", "boundary checks cover i=1/NI and j=1/NJ; ghost cells outside these are not asserted", "curated physical states and existing FW marker are not real geography or field validation"}},new JsonSerializerOptions{WriteIndented=true}));
            Console.WriteLine($"PASS states={rows.Count} calls={18*14*2} checks={checks.Values.Sum()}");return 0;
        }
        catch(Exception ex)
        {
            File.WriteAllText(Path.Combine(outDir,"temporal_checks.json"),JsonSerializer.Serialize(new{status="fail",error=ex.ToString(),completed_cell_states=rows.Count,checks},new JsonSerializerOptions{WriteIndented=true}));Console.Error.WriteLine(ex);return 1;
        }
    }
}
