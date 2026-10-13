using System;
using System.Collections.Immutable;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
namespace GRAMM_2001
{
    static class ScalarMethodCheck
    {
        static readonly Type Model=typeof(Program);
        static FieldInfo Field(string name)=>Model.GetField(name,BindingFlags.Public|BindingFlags.Static);
        static void Fill3(string name,Func<int,int,int,double> value)
        {
            object data=Field(name).GetValue(null);
            if(data is double[][][] d){for(int i=0;i<d.Length;i++)for(int j=0;j<d[i].Length;j++)for(int k=0;k<d[i][j].Length;k++)d[i][j][k]=value(i,j,k);}
            else if(data is float[][][] f){for(int i=0;i<f.Length;i++)for(int j=0;j<f[i].Length;j++)for(int k=0;k<f[i][j].Length;k++)f[i][j][k]=(float)value(i,j,k);}
            else throw new Exception(name);
        }
        static void Fill2(string name,double value)
        {
            object data=Field(name).GetValue(null);
            if(data is double[][] d){foreach(var row in d)Array.Fill(row,value);}
            else if(data is float[][] f){foreach(var row in f)Array.Fill(row,(float)value);}
            else throw new Exception(name);
        }
        static void Freeze(string name)
        {
            var a=(float[][][])Field(name).GetValue(null);var b=new ImmutableArray<float>[a.Length][];
            for(int i=0;i<a.Length;i++){b[i]=new ImmutableArray<float>[a[i].Length];for(int j=0;j<a[i].Length;j++)b[i][j]=ImmutableArray.Create(a[i][j]);}
            Field(name+"Imm").SetValue(null,b);
        }
        static void Init(int nx,int ny,int nz,int threads,int mode)
        {
            Program.NX=nx;Program.NY=ny;Program.NZ=nz;
            Model.GetMethod("Define_Arrays",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,null);
            foreach(string name in new[]{"AREA","AREAX","AREAY"})Fill3(name,(i,j,k)=>100);
            foreach(string name in new[]{"AREAZX","AREAZY"})Fill3(name,(i,j,k)=>0.03*((i+j)%3));
            Fill3("VOL",(i,j,k)=>1000);Fill3("ZSP",(i,j,k)=>5+k*10);
            foreach(string name in new[]{"AREA","AREAX","AREAY","AREAZX","AREAZY","VOL","ZSP"})Freeze(name);
            var dx=new float[nx+1];var dy=new float[ny+1];Array.Fill(dx,10);Array.Fill(dy,10);Program.DDXImm=ImmutableArray.Create(dx);Program.DDYImm=ImmutableArray.Create(dy);
            Fill3("RHO",(i,j,k)=>1.2-k*.001);Fill3("VISH",(i,j,k)=>.2+(i+j+k)%3*.03);
            Fill3("UN",(i,j,k)=>1+(i+j)%3*.01);Fill3("VN",(i,j,k)=>.3+(i+k)%3*.01);Fill3("WN",(i,j,k)=>.001*(k%2));
            foreach(string name in new[]{"T","TN"})Fill3(name,(i,j,k)=>10+(i+j+k)%7*.07);
            foreach(string name in new[]{"QU","QUN"})Fill3(name,(i,j,k)=>4+(i+j+k)%5*.03);
            Fill3("FAC",(i,j,k)=>.001);Fill3("NBZKP",(i,j,k)=>1+k%5);Fill3("PNBZKP",(i,j,k)=>.4);
            Fill3("DT_SOL",(i,j,k)=>.0001*(1+k));Fill3("DT_TERR",(i,j,k)=>-.00002*(1+k));
            Fill2("WQU",2);Fill2("AWQ",.2);Fill2("UST",.12);Fill2("XWQ",.2);Fill2("QUG",3.5);
            Program.ICT=(mode&1)!=0;Program.ICQU=(mode&2)!=0;Program.ICTB=true;Program.ICSTR=true;Program.RELAXT=.4;Program.StripeCounter=0;
            File.WriteAllText("Max_Proc.txt",threads.ToString());Program.Max_Proc_File_Read(true);
        }
        static void Save(string path)
        {
            using var writer=new BinaryWriter(File.Create(path));
            foreach(string name in new[]{"TN","QUN","A_PS","B_PS","C_PS","RADIATION"})
            foreach(var plane in (double[][][])Field(name).GetValue(null))foreach(var row in plane)foreach(double value in row)
            {if(!double.IsFinite(value))throw new Exception("Nonfinite "+name);writer.Write(value);}
        }
        public static int Main(string[] args)
        {
            string output=Path.GetFullPath(args[0]);Directory.CreateDirectory(output);Directory.SetCurrentDirectory(output);
            var records=new List<object>();var cache=Field("H_PS");
            foreach(var shape in new[]{(12,13,3),(18,16,12),(34,30,28)})
            foreach(int threads in new[]{1,4,8})for(int mode=0;mode<4;mode++)
            {
                Init(shape.Item1,shape.Item2,shape.Item3,threads,mode);
                int stage=0;
                foreach(double dt in new[]{1.5,5.0,2.0})
                {
                    Program.DT=dt;
                    if(stage==1)Fill3("RHO",(i,j,k)=>1.23-k*.001);
                    if(cache!=null)Fill3("H_PS",(i,j,k)=>-12345);
                    Program.TERMIPSterms(Program.NX,Program.NY,Program.NZ);
                    if(cache!=null && mode==0)
                    foreach(var plane in (double[][][])cache.GetValue(null))foreach(var row in plane)foreach(double v in row)
                    if(v!=-12345)throw new Exception("Disabled cache was written");
                    if(Program.ICT)Program.Timp_calculate(Program.NX,Program.NY,Program.NZ);
                    if(Program.ICQU)Program.Fimp_calculate(Program.NX,Program.NY,Program.NZ);
                    string id=$"{shape.Item1}x{shape.Item2}x{shape.Item3}_t{threads}_m{mode}_s{stage}";
                    string file=id+".bin";Save(file);byte[] bytes=File.ReadAllBytes(file);
                    records.Add(new{id,threads,mode,stage,dt,values=bytes.Length/8,sha256=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),finite=true,serial=HarnessParallel.Serial});stage++;
                }
            }
            File.WriteAllText("cases.json",JsonSerializer.Serialize(records,new JsonSerializerOptions{WriteIndented=true}));Console.WriteLine($"cases={records.Count} finite=true");return 0;
        }
    }
}
