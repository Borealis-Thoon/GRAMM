import os
from pathlib import Path
import argparse, hashlib, json

ap=argparse.ArgumentParser()
ap.add_argument('--baseline',type=Path,required=True)
ap.add_argument('--candidate',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args()
a.output.mkdir(parents=True,exist_ok=True)

def method(s, signature):
    start=s.index(signature)
    opening=s.index('{',start)
    depth=1
    end=opening+1
    while depth:
        if s[end]=='{': depth+=1
        if s[end]=='}': depth-=1
        end+=1
    return s[start:end]

metadata={}
for label,srcdir in [('Baseline',a.baseline),('Candidate',a.candidate)]:
    p=srcdir/'src'/'RADIAT.cs'
    raw=p.read_bytes()
    s=raw.decode('utf-8-sig')
    methods=[method(s,'private double Cl_Eps('),method(s,'private double Cl_EpsA(')]
    loop=s[s.index('            //Epsilon Above'):s.index('            //Terrestrial radiation')]
    methods[1]=methods[1].replace('{','{\n            Calls++;',1)
    # Loop and numerical methods come directly from each tested source revision.
    unit='using System;\nnamespace '+label+' {\npublic partial class RadiationCalculation {\n'+ '\n'.join(methods)+'\npublic void RunProfile(int NI,int NJ,int NK) {\n'+loop+'\n}\n}\n}\n'
    (a.output/(label+'.generated.cs')).write_text(unit,encoding='utf-8')
    support=Path(__file__).with_name('Support.template.cs').read_text(encoding='utf-8').replace('__NAMESPACE__',label)
    (a.output/(label+'.support.cs')).write_text(support,encoding='utf-8')
    metadata[label.lower()]={'source_sha256':hashlib.sha256(raw).hexdigest(),'loop_sha256':hashlib.sha256(loop.encode()).hexdigest(),'methods':['RadiationCalculation.Cl_Eps','RadiationCalculation.Cl_EpsA'],'instrumentation':'Calls++ at Cl_EpsA entry only; no arithmetic edits'}
(a.output/'Program.cs').write_text(Path(__file__).with_name('Program.cs').read_text(encoding='utf-8'),encoding='utf-8')
(a.output/'RadiationColumnCheck.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable><TreatWarningsAsErrors>true</TreatWarningsAsErrors></PropertyGroup></Project>',encoding='utf-8')
(a.output/'provenance.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
print('[SAVE] source-derived radiation loop and methods')
