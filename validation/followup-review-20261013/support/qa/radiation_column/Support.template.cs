using System;
using System.Linq;
namespace __NAMESPACE__ {
static class Program {
    public static int NZ;
    public static double[] ZZ=Array.Empty<double>();
    public static double[][][] TABS=Array.Empty<double[][]>();
}
public partial class RadiationCalculation {
    private const double Wcrit=0.03;
    private const double EpsTop=0.2;
    private const double TTop=216.65;
    private double[][] Wrad=Array.Empty<double[]>(), CGp=Array.Empty<double[]>(), Rp=Array.Empty<double[]>();
    private double[] Dz1=Array.Empty<double>(), Dz2=Array.Empty<double>();
    private double[][][] EpsAp=Array.Empty<double[][]>(), EpsAm=Array.Empty<double[][]>(), Eab=Array.Empty<double[][]>(), Tab=Array.Empty<double[][]>();
    public long Calls;
    private static double[][][] Volume(int ni,int nj,int nk,Func<int,int,int,double> f) =>
        Enumerable.Range(0,Math.Max(ni+2,2)).Select(i=>Enumerable.Range(0,Math.Max(nj+2,2)).Select(j=>Enumerable.Range(0,nk+2).Select(k=>f(i,j,k)).ToArray()).ToArray()).ToArray();
    public void Init(int ni,int nj,int nk,int profile,int phase) {
        Program.NZ=nk;
        Program.ZZ=Enumerable.Range(0,nk+2).Select(k=>5d+15*k+0.5*k*k).ToArray();
        Program.TABS=Volume(ni,nj,nk,(i,j,k)=>280+phase*3-i*.13+j*.27-k*.42);
        Dz1=Program.ZZ.Select(z=>z-7).ToArray(); Dz2=Program.ZZ.Select(z=>z+7).ToArray();
        Wrad=Enumerable.Range(0,nk+2).Select(_=>new double[4]).ToArray();
        CGp=Enumerable.Range(0,nk+2).Select(_=>new double[4]).ToArray();
        Rp=Enumerable.Range(0,nk+2).Select(_=>new double[4]).ToArray();
        for(int k=0;k<nk+2;k++) {
            Wrad[k][2]=profile switch {0=>0,1=>0.004+phase*.0003,2=>0.06,3=>k==Math.Max(2,nk/2)?0.03:0,_=>k%4==1?0.035:0.0001};
            CGp[k][2]=(.001+.0007*k)*(phase+1);
            Rp[k][2]=(.0008+.0005*k)*(profile+1);
        }
        for(int k=nk;k>=0;k--) {
            Wrad[k][3]=Wrad[k+1][3]+Wrad[k][2];
            CGp[k][3]=CGp[k+1][3]+CGp[k][2];
            Rp[k][3]=Rp[k+1][3]+Rp[k][2];
        }
        EpsAp=Volume(ni,nj,nk,(i,j,k)=>-.1*(1+i+2*j+k));
        EpsAm=Volume(ni,nj,nk,(i,j,k)=>.2*(1+i+2*j+k));
        Eab=Volume(ni,nj,nk,(i,j,k)=>-2*(1+i+2*j+k));
        Tab=Volume(ni,nj,nk,(i,j,k)=>-100-3*i-4*j-k);
        Calls=0;
    }
    public double[][][][] Fields()=>new[]{EpsAp,EpsAm,Eab,Tab};
    public double[] IgnoredRefInputs(int k,double initial) {
        double ap=initial,am=initial,ab=initial,tb=initial;
        Cl_EpsA(1,1,k,ref ap,ref am,ref ab,ref tb);
        return new[]{ap,am,ab,tb};
    }
}
}
