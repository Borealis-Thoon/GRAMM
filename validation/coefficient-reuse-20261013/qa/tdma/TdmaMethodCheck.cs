using System;
using System.Collections.Immutable;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text.Json;
namespace GRAMM_2001
{
    static class TdmaMethodCheck
    {
        static readonly Type Model = typeof(Program);
        static readonly string[] Outputs = {"U1N", "U2N", "V1N", "V2N", "W1N", "W2N"};
        static void Set(string name, object value) => Model.GetField(name, BindingFlags.Public | BindingFlags.Static).SetValue(null,value);
        static float[][][] Floats(int nx,int ny,int nz, Func<int,int,int,float> value)
        {
            var a=new float[nx][][];
            for(int i=0;i<nx;i++) {a[i]=new float[ny][]; for(int j=0;j<ny;j++) {a[i][j]=new float[nz]; for(int k=0;k<nz;k++) a[i][j][k]=value(i,j,k);}}
            return a;
        }
        static double[][][] Doubles(int nx,int ny,int nz, Func<int,int,int,double> value)
        {
            var a=new double[nx][][];
            for(int i=0;i<nx;i++) {a[i]=new double[ny][]; for(int j=0;j<ny;j++) {a[i][j]=new double[nz]; for(int k=0;k<nz;k++) a[i][j][k]=value(i,j,k);}}
            return a;
        }
        static ImmutableArray<float>[][] Immutable(float[][][] a)
        {
            var b=new ImmutableArray<float>[a.Length][];
            for(int i=0;i<a.Length;i++){b[i]=new ImmutableArray<float>[a[i].Length];for(int j=0;j<a[i].Length;j++)b[i][j]=ImmutableArray.Create(a[i][j]);}
            return b;
        }
        static void Init(int nx,int ny,int nz,int variant)
        {
            int x=nx+2,y=ny+2,z=nz+2,half=2*nz+2;
            foreach(string n in new[]{"AIM","BIM","CIM","AW1","AS1","AE2","AN2","F1U","F2U","F1V","F2V","F1W","F2W","RHO"})
            {
                float start=n=="AIM"?8.0f:n=="BIM"?0.31f:n=="CIM"?0.22f:n=="RHO"?1.15f:n.StartsWith("F")?0.13f:0.05f;
                Set(n,Floats(x,y,half,(i,j,k)=>start+(i*7+j*3+k*11)%19*0.001f));
            }
            for(int c=0;c<Outputs.Length;c++) {int component=c;Set(Outputs[c],Doubles(x,y,z,(i,j,k)=>(component-2)*0.43+(i*7+j*3+k*11)%29*0.017+variant*0.14));}
            Set("AREAImm",Immutable(Floats(x,y,z,(i,j,k)=>1.0f+(i+j+k)%7*0.1f)));
            Set("AREAZXImm",Immutable(Floats(x,y,z,(i,j,k)=>variant==0?0f:(i+j+k)%7*0.13f)));
            Set("AREAZYImm",Immutable(Floats(x,y,z,(i,j,k)=>variant==0?0f:(i-j+k)%9*0.11f)));
            var ust=new double[x][];var ustv=new double[x][];var relax=new float[x][];
            for(int i=0;i<x;i++){ust[i]=new double[y];ustv[i]=new double[y];relax[i]=new float[y];for(int j=0;j<y;j++){ust[i][j]=variant==0?0:0.13+(i+j)%3*0.04;ustv[i][j]=0.21;relax[i][j]=0.73f+(i+j)%5*0.05f;}}
            Set("UST",ust);Set("USTV",ustv);Set("Relax_Border_factor",relax);Set("RELAXV",0.4);
        }
        public static int Main(string[] args)
        {
            string outPath=args[0];Directory.CreateDirectory(outPath);
            var method=Model.GetMethod("UIMPKernel",BindingFlags.NonPublic | BindingFlags.Static);
            var rows=new List<object>();
            foreach(var shape in new[]{(3,4,2),(4,5,3),(7,9,8),(11,13,28),(17,11,65)})
            for(int variant=0;variant<2;variant++)
            for(int sweep=0;sweep<8;sweep++)
            {
                int nx=shape.Item1,ny=shape.Item2,nz=shape.Item3;
                Init(nx,ny,nz,variant);
                bool outerI=(sweep&4)==0,outerReverse=(sweep&2)!=0,innerReverse=(sweep&1)!=0;
                method.Invoke(null,new object[]{Tuple.Create(2,outerI?nx:ny),outerI?ny:nx,nz,outerReverse,innerReverse,outerI});
                string id=$"{nx}x{ny}x{nz}_v{variant}_s{sweep}";
                using var stream=File.Create(Path.Combine(outPath,id+".bin"));using var writer=new BinaryWriter(stream);
                long values=0;double sum=0;
                foreach(string name in Outputs)
                foreach(var plane in (double[][][])Model.GetField(name,BindingFlags.Public | BindingFlags.Static).GetValue(null))
                foreach(var col in plane)foreach(double value in col){if(!double.IsFinite(value))throw new Exception("Non-finite state");writer.Write(value);values++;sum+=value;}
                rows.Add(new{id,nx,ny,nz,variant,sweep,values,sum});
            }
            File.WriteAllText(Path.Combine(outPath,"cases.json"),JsonSerializer.Serialize(rows,new JsonSerializerOptions{WriteIndented=true}));
            Console.WriteLine($"cases={rows.Count} finite=true");return 0;
        }
    }
}
