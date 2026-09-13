"""Trusted lab bootstrap helpers; object inspection only, no candidate imports."""
import hashlib,io,json,os,pathlib,subprocess,zipfile
from release_policy import require,sha
ROOT=pathlib.Path.cwd();M=json.loads((ROOT/'bootstrap-manifest.json').read_text())
LAB='Skimbee/hermes-bridge-release-lab';FORK='Skimbee/hermes-agent';PATH='.github/workflows/bootstrap-acceptance.yml'
def api(repo,path,raw=False):
    data=subprocess.check_output(['gh','api','repos/'+repo+'/'+path],timeout=90)
    return data if raw else json.loads(data)
def identity(run):
    return {'repository':run['repository']['full_name'],'id':run['id'],'attempt':run['run_attempt'],'workflow_id':run['workflow_id'],'path':run['path'],'controller':run['head_sha'],'event':run['event']}
def current():
    require(os.environ['GITHUB_REPOSITORY']==LAB and os.environ['GITHUB_REF']=='refs/heads/lab-controller' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted','Hosted lab only')
    run=api(LAB,'actions/runs/'+os.environ['GITHUB_RUN_ID'])
    require(run['head_sha']==os.environ['GITHUB_SHA'] and run['run_attempt']==int(os.environ['GITHUB_RUN_ATTEMPT']) and run['path']==PATH,'Bootstrap runtime')
    return run
def manifest_hash():return hashlib.sha256((ROOT/'bootstrap-manifest.json').read_bytes()).hexdigest()
def completed(run,name):
    data=api(LAB,f'actions/runs/{run["id"]}/attempts/{run["run_attempt"]}/jobs?per_page=100')
    require(data['total_count']==len(data['jobs']) and data['total_count']<100,'Job pagination')
    rows=[j for j in data['jobs'] if j['name']==name]
    require(len(rows)==1 and rows[0]['status']=='completed' and rows[0]['conclusion']=='success','Unfinished bootstrap job: '+name)
def artifact(run,name):
    data=api(LAB,'actions/runs/'+str(run['id'])+'/artifacts?per_page=100')
    require(data['total_count']==len(data['artifacts']) and data['total_count']<100,'Artifact pagination')
    rows=[a for a in data['artifacts'] if a['name']==name and a['expired'] is False];require(len(rows)==1,'Artifact ambiguity')
    a=rows[0];require(a['size_in_bytes']<25*1024*1024,'Artifact size')
    raw=api(LAB,'actions/artifacts/'+str(a['id'])+'/zip',raw=True)
    require('sha256:'+hashlib.sha256(raw).hexdigest()==a['digest'],'Archive digest')
    z=zipfile.ZipFile(io.BytesIO(raw));require(len(z.namelist())==len(set(z.namelist())) and sum(i.file_size for i in z.infolist())<25*1024*1024,'Archive bounds')
    return a,z
def source(directory):
    for key in ('candidate','base','tree','runtime_candidate','upstream','client_base'):sha(M[key])
    require(M['repository']==FORK and M['branch']=='bridge/release-integration','Fixed bootstrap source')
    require(api(FORK,'git/ref/heads/main')['object']['sha']==M['base'],'Main moved')
    require(api(FORK,'git/ref/heads/'+M['branch'])['object']['sha']==M['candidate'],'Candidate branch moved')
    directory.mkdir(parents=True,exist_ok=True);repo=directory/'fixture.git'
    subprocess.run(['git','clone','--bare','https://github.com/'+FORK+'.git',str(repo)],check=True,timeout=300)
    def git(*args):return subprocess.check_output(['git','-c','core.hooksPath=/dev/null','--git-dir='+str(repo),*args],timeout=120)
    require(git('rev-parse',M['candidate']+'^{tree}').decode().strip()==M['tree'],'Expected tree')
    chain=git('rev-list','--first-parent',M['candidate']).decode().splitlines();require(M['base'] in chain,'First-parent chain')
    for ancestor in (M['runtime_candidate'],M['upstream']):git('merge-base','--is-ancestor',ancestor,M['candidate'])
    paths=[p.decode() for p in git('diff','--no-renames','--name-only','-z',M['runtime_candidate'],M['candidate']).split(b'\0') if p]
    delta={p:git('rev-parse',M['candidate']+':'+p).decode().strip() for p in paths}
    require(delta==M['bridge_delta'],'Unexpected changes outside fixed integration delta')
    git('update-ref','refs/heads/main',M['candidate']);git('symbolic-ref','HEAD','refs/heads/main')
    manifest=[]
    for row in git('ls-tree','-rz',M['candidate']).split(b'\0'):
        if not row:continue
        attrs,path=row.split(b'\t',1);mode,kind,oid=attrs.decode().split();require(kind=='blob','Submodule not supported')
        name=path.decode();require(not name.startswith('/') and not any(x in ('','.','..') for x in name.split('/')),'Unsafe tree path')
        manifest.append({'path':name,'mode':mode,'oid':oid})
    attrs=subprocess.check_output(['git','--git-dir='+str(repo),'check-attr','--source='+M['candidate'],'-z','--stdin','eol','filter','working-tree-encoding'],input=b''.join(e['path'].encode()+b'\0' for e in manifest)).split(b'\0')
    require(attrs[-1]==b'' and (len(attrs)-1)%3==0,'Attribute format');values={}
    for i in range(0,len(attrs)-1,3):
        path,key,value=(v.decode() for v in attrs[i:i+3]);values.setdefault(path,{})[key]=value
    for entry in manifest:
        v=values[entry['path']];require(v['filter'] in ('unspecified','unset') and v['working-tree-encoding'] in ('unspecified','unset') and v['eol'] in ('lf','crlf','unspecified','unset'),'Unsupported Git transformation')
        entry['eol']=v['eol']
    (directory/'manifest.json').write_text(json.dumps(manifest))
    bundle=directory/'candidate.bundle';git('bundle','create',str(bundle),M['base']+'..HEAD');git('bundle','verify',str(bundle))
    require(api(FORK,'git/ref/heads/main')['object']['sha']==M['base'],'Main moved while inspecting')
    return repo,manifest,bundle
