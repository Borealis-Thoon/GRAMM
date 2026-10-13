using System;
using System.Collections.Concurrent;
using System.Collections.Immutable;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using System.Threading.Tasks;
namespace GRAMM_2001
{
    static class HalfCellMethodCheck
    {
        static readonly Type Model = typeof(Program);
        static readonly string[] Outputs = {"U1N", "U2N", "V1N", "V2N", "W1N", "W2N"};
        static readonly string[] Sources = {"F1U", "F2U", "F1V", "F2V", "F1W", "F2W"};
        static void Set(string name, object value) => Model.GetField(name, BindingFlags.Public | BindingFlags.Static).SetValue(null,value);
        static float[][][] Floats(int nx,int ny,int nz, Func<int,int,int,float> value)
        {
            var a=new float[nx][][];
            for(int i=0;i<nx;i++){a[i]=new float[ny][];for(int j=0;j<ny;j++){a[i][j]=new float[nz];for(int k=0;k<nz;k++)a[i][j][k]=value(i,j,k);}}
            return a;
        }
        static double[][][] Doubles(int nx,int ny,int nz, Func<int,int,int,double> value)
        {
            var a=new double[nx][][];
            for(int i=0;i<nx;i++){a[i]=new double[ny][];for(int j=0;j<ny;j++){a[i][j]=new double[nz];for(int k=0;k<nz;k++)a[i][j][k]=value(i,j,k);}}
            return a;
        }
        static ImmutableArray<float>[][] Immutable(float[][][] a)
        {
            var b=new ImmutableArray<float>[a.Length][];
            for(int i=0;i<a.Length;i++){b[i]=new ImmutableArray<float>[a[i].Length];for(int j=0;j<a[i].Length;j++)b[i][j]=ImmutableArray.Create(a[i][j]);}
            return b;
        }
        static void Init(int nx,int ny,int nz,int variant,bool icpsi,bool icu,int workers)
        {
            int x=nx+2,y=ny+2,z=nz+2,half=2*nz+2;
            foreach(string n in new[]{"AIM","BIM","CIM","AW1","AS1","AE2","AN2","RHO","RHOBZ"})
            {
                float start=n=="AIM"?8.0f:n=="BIM"?0.31f:n=="CIM"?0.22f:n.StartsWith("RHO")?1.15f:0.05f;
                Set(n,Floats(x,y,half,(i,j,k)=>start+(i*7+j*3+k*11)%19*0.001f));
            }
            foreach(string n in Sources)Set(n,Floats(x,y,half,(i,j,k)=>float.NaN));
            for(int c=0;c<Outputs.Length;c++)
            {
                int component=c;
                Set(Outputs[c],Doubles(x,y,z,(i,j,k)=>(component-2)*0.43+(i*7+j*3+k*11)%29*0.017+variant*0.14));
                Set(Outputs[c].Substring(0,2),Doubles(x,y,z,(i,j,k)=>(component-1)*0.38+(i*5+j*9+k*3)%31*0.013));
            }
            foreach(string n in new[]{"QUN","QBZ","UG","VG","TPDX","TPDY","TBZ","TN"})
            {
                double b=n=="TBZ"?290:n=="TN"?2:n.StartsWith("Q")?6:n=="UG"?2:n=="VG"?-1:0.08;
                Set(n,Doubles(x,y,z,(i,j,k)=>b+(i*7+j*3+k*11)%19*0.012));
            }
            Set("AREAImm",Immutable(Floats(x,y,z,(i,j,k)=>1.0f+(i+j+k)%7*0.1f)));
            Set("VOLImm",Immutable(Floats(x,y,z,(i,j,k)=>2.0f+(i+j+k)%7*0.13f)));
            Set("AREAZXImm",Immutable(Floats(x,y,z,(i,j,k)=>variant==0?0f:(i+j+k)%7*0.13f)));
            Set("AREAZYImm",Immutable(Floats(x,y,z,(i,j,k)=>variant==0?0f:(i-j+k)%9*0.11f)));
            var ust=new double[x][];var ustv=new double[x][];var relax=new float[x][];
            for(int i=0;i<x;i++){ust[i]=new double[y];ustv[i]=new double[y];relax[i]=new float[y];for(int j=0;j<y;j++){ust[i][j]=variant==0?0:0.13+(i+j)%3*0.04;ustv[i][j]=0.21;relax[i][j]=0.73f+(i+j)%5*0.05f;}}
            Set("UST",ust);Set("USTV",ustv);Set("Relax_Border_factor",relax);Set("RELAXV",0.4);
            Program.FN=0.000087;Program.FH=0.000113;Program.TBZ1=290;Program.ICPSI=icpsi;Program.ICU=icu;
            Program.pOptions=new ParallelOptions{MaxDegreeOfParallelism=workers};Program.StripeCounter=0;
            // Each sweep has one range; only the independent source prepass is parallel.
            Program.PartitionerI=new List<OrderablePartitioner<Tuple<int,int>>>{Partitioner.Create(2,nx,nx-2)};
            Program.PartitionerJ=new List<OrderablePartitioner<Tuple<int,int>>>{Partitioner.Create(2,ny,ny-2)};
        }
        static void UpdateStep(int nx,int ny,int nz,int stage,double dt,float poison)
        {
            int x=nx+2,y=ny+2,z=nz+2,half=2*nz+2;
            Set("AP0",Floats(x,y,z,(i,j,k)=>(float)((1.1+(i+j+k)%5*0.011)/dt)));
            int c=0;
            foreach(string n in new[]{"DIMU","DIMV","DIMW"})
            {
                int component=c++;
                Set(n,Doubles(x,y,half,(i,j,k)=>(component-1)*0.027+(i*11+j*7+k*5)%23*0.003+stage*0.009));
            }
            foreach(string n in Sources)
            foreach(var plane in (float[][][])Model.GetField(n,BindingFlags.Public|BindingFlags.Static).GetValue(null))
            foreach(var col in plane)Array.Fill(col,poison);
        }
        static (string hash,long count) State()
        {
            using var h=IncrementalHash.CreateHash(HashAlgorithmName.SHA256);long count=0;Span<byte> b=stackalloc byte[8];
            foreach(string n in Outputs)
            foreach(var plane in (double[][][])Model.GetField(n,BindingFlags.Public|BindingFlags.Static).GetValue(null))
            foreach(var col in plane)foreach(double v in col)
            {
                if(!double.IsFinite(v))throw new Exception("Non-finite model state: "+n);
                BitConverter.TryWriteBytes(b,v);h.AppendData(b);count++;
            }
            return (Convert.ToHexString(h.GetHashAndReset()).ToLowerInvariant(),count);
        }
        static (string hash,long used,long untouched) CheckSources(int nx,int ny,int nz,bool icu,bool sparse,float poison)
        {
            using var h=IncrementalHash.CreateHash(HashAlgorithmName.SHA256);long used=0,untouched=0;Span<byte>b=stackalloc byte[4];
            foreach(string n in Sources)
            {
                var a=(float[][][])Model.GetField(n,BindingFlags.Public|BindingFlags.Static).GetValue(null);
                for(int i=2;i<nx;i++)for(int j=2;j<ny;j++)for(int kn=1;kn<=2*(nz-1);kn++)
                {
                    bool consumed=icu&&((n[1]=='1')==((kn&1)==1));float value=a[i][j][kn];
                    if(consumed)
                    {
                        if(!float.IsFinite(value))throw new Exception("Non-finite consumed source");
                        BitConverter.TryWriteBytes(b,value);h.AppendData(b);used++;
                    }
                    else if(sparse||!icu)
                    {
                        if(BitConverter.SingleToInt32Bits(value)!=BitConverter.SingleToInt32Bits(poison))throw new Exception("Unused source was written");
                        untouched++;
                    }
                }
            }
            return (Convert.ToHexString(h.GetHashAndReset()).ToLowerInvariant(),used,untouched);
        }
        public static int Main(string[] args)
        {
            string outPath=args[0];bool sparse=args[1]=="patched";Directory.CreateDirectory(outPath);
            var rows=new List<object>();var poisonIdentity=new Dictionary<string,string>();
            foreach(var shape in new[]{(3,4,2),(4,5,3),(7,9,8),(11,13,28),(17,11,65)})
            for(int variant=0;variant<2;variant++)foreach(bool icpsi in new[]{false,true})foreach(bool icu in new[]{false,true})foreach(int workers in new[]{1,4,8})
            for(int sentinel=0;sentinel<2;sentinel++)
            {
                int nx=shape.Item1,ny=shape.Item2,nz=shape.Item3;
                Init(nx,ny,nz,variant,icpsi,icu,workers);string initial=State().hash;
                double[] dts={1.5,5.0,2.0};float poison=sentinel==0?float.NaN:-1234567.5f;
                for(int stage=0;stage<dts.Length;stage++)
                {
                    UpdateStep(nx,ny,nz,stage,dts[stage],poison);
                    Program.UVWIMPcalculate(nx,ny,nz);
                    var state=State();var sources=CheckSources(nx,ny,nz,icu,sparse,poison);
                    if(!icu&&state.hash!=initial)throw new Exception("ICU=false changed state");
                    string key=$"{nx}x{ny}x{nz}_v{variant}_p{icpsi}_u{icu}_w{workers}_s{stage}";
                    if(sentinel==0)poisonIdentity.Add(key,state.hash);else if(poisonIdentity[key]!=state.hash)throw new Exception("Unused sentinel affects result");
                    rows.Add(new{id=key+"_sentinel"+sentinel,nx,ny,nz,variant,icpsi,icu,workers,stage,dt=dts[stage],sentinel,state_sha256=state.hash,state_values=state.count,consumed_source_sha256=sources.hash,consumed_source_values=sources.used,untouched_source_values=sources.untouched});
                }
            }
            File.WriteAllText(Path.Combine(outPath,"cases.json"),JsonSerializer.Serialize(rows,new JsonSerializerOptions{WriteIndented=true}));
            Console.WriteLine($"cases={rows.Count} finite=true sentinel_independent=true");return 0;
        }
    }
}