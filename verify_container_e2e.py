"""Read-only final verifier for lab container E2E. Never issues release checks."""
import argparse,hashlib,io,json,pathlib,re,subprocess,zipfile
LAB='Skimbee/hermes-bridge-release-lab';FORK='Skimbee/hermes-agent'
def api(repo,path):return json.loads(subprocess.check_output(['gh','api','repos/'+repo+'/'+path]))
def require(value,message):
    if not value:raise ValueError(message)
def run(repo,rid,path,controller):
    r=api(repo,'actions/runs/'+str(rid))
    require(r['repository']['full_name']==repo and r['status']=='completed' and r['conclusion']=='success','run status')
    require(r['path']==path and r['head_sha']==controller and r['event'] in ('workflow_dispatch','schedule'),'run identity')
    workflow=api(repo,'actions/workflows/'+str(r['workflow_id']))
    require(workflow['path']==path,'workflow ID/path')
    return r
def artifact(repo,r,name):
    listing=api(repo,'actions/runs/'+str(r['id'])+'/artifacts?per_page=100')
    require(listing['total_count']<100,'artifact pagination')
    rows=[a for a in listing['artifacts'] if a['name']==name and a['expired'] is False]
    require(len(rows)==1,'artifact ambiguity');a=rows[0]
    require(a['size_in_bytes']<25*1024*1024,'artifact size')
    data=subprocess.check_output(['gh','api',f'repos/{repo}/actions/artifacts/{a["id"]}/zip'])
    require('sha256:'+hashlib.sha256(data).hexdigest()==a['digest'],'artifact digest')
    z=zipfile.ZipFile(io.BytesIO(data));names=z.namelist()
    require(len(names)==len(set(names)) and sum(i.file_size for i in z.infolist())<25*1024*1024,'archive bounds')
    return a,z
def identity(repo,r):
    return {'repository':repo,'id':r['id'],'attempt':r['run_attempt'],'workflow_id':r['workflow_id'],'path':r['path'],'controller':r['head_sha'],'event':r['event']}
def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True);p.add_argument('--controller',required=True);p.add_argument('--candidate-run',type=int,required=True);p.add_argument('--output',required=True);args=p.parse_args()
    require(re.fullmatch('[0-9a-f]{40}',args.controller) is not None,'controller SHA')
    main_sha=api(FORK,'git/ref/heads/main')['object']['sha']
    c=run(FORK,args.candidate_run,'.github/workflows/bridge-hourly-pilot.yml',main_sha)
    d=run(LAB,args.run,'.github/workflows/container-dashboard.yml',args.controller)
    ca,cz=artifact(FORK,c,f'bridge-candidate-{c["id"]}-{c["run_attempt"]}')
    da,dz=artifact(LAB,d,f'container-dashboard-{d["id"]}-{d["run_attempt"]}')
    require(set(cz.namelist())=={'receipt.json','candidate.bundle'},'candidate archive')
    r=json.loads(cz.read('receipt.json'))
    require(r['run_id']==str(c['id']) and str(r['run_attempt'])==str(c['run_attempt']),'receipt run')
    require(r['workflow_sha']==main_sha==r['base'],'receipt base')
    require(hashlib.sha256(cz.read('candidate.bundle')).hexdigest()==r['bundle_sha256'],'bundle digest')
    result=json.loads(dz.read('evidence/result.json'))
    binding=json.loads(dz.read('e2e-input/binding.json'))
    require(dz.read('e2e-input/original-receipt.json')==cz.read('receipt.json'),'original receipt bytes')
    expected_c={**identity(FORK,c),'status':c['status'],'conclusion':c['conclusion']}
    expected_a={'id':ca['id'],'run_id':c['id'],'digest':ca['digest'],'expired':False}
    for evidence in (result,binding):
        require(evidence['schema']==2 and evidence['candidate_run']==expected_c,'original candidate binding')
        require(evidence['candidate_artifact']==expected_a,'original artifact binding')
        require(evidence['candidate']==r['candidate'] and evidence['bundle_sha256']==r['bundle_sha256'],'candidate/bundle binding')
        require(evidence['dashboard_identity']==identity(LAB,d),'original dashboard identity')
    require(result['dashboard_run']==identity(LAB,d),'dashboard identity')
    require(result['passed'] is True and result['reconnected'] is True and result['tracked_tree_matches'] is True and result['candidate_stopped'] is True,'E2E/snapshot failed')
    require(result['post_head']==r['candidate'] and result['pre_head']=='d131988d53c3b8389801f6cee03b990bd51ac49a','snapshot heads')
    require(type(result['tracked_files_verified']) is int and result['tracked_files_verified']>0,'snapshot count')
    require(result['observed_receipt']=={'pre_sha':result['pre_head'],'post_sha':r['candidate'],'outcome':'success'},'observed receipt')
    require(api(FORK,'git/ref/heads/main')['object']['sha']==main_sha,'base moved during verification')
    report={'lab_e2e_verified':True,'publication_enabled':False,'candidate':r['candidate'],'base':main_sha,'candidate_run':c['id'],'candidate_attempt':c['run_attempt'],'candidate_artifact':expected_a,'dashboard_run':d['id'],'dashboard_attempt':d['run_attempt'],'dashboard_artifact_id':da['id'],'dashboard_artifact_digest':da['digest'],'controller':args.controller,'tracked_files_verified':result['tracked_files_verified'],'scope':'lab external controller observations and offline tracked tree, not benign-code proof'}
    pathlib.Path(args.output).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
