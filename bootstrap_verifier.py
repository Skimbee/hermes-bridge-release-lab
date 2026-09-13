"""Independent exact-target bootstrap verifier; no candidate code execution."""
import hashlib,json,pathlib,subprocess,tempfile
from bootstrap_support import ROOT,M,LAB,FORK,PATH,api,identity,completed,artifact,manifest_hash,source,require

def validate(run,ca,r,b,result,policy):
    require(run['repository']['full_name']==LAB and run['head_branch']=='lab-controller' and run['event']=='workflow_dispatch','Bootstrap repository/ref/event')
    require(run['id']==policy['acceptance_run'] and run['head_sha']==policy['acceptance_controller'] and run['workflow_id']==policy['workflow_id'] and run['path']==PATH,'Pinned acceptance identity')
    require(run['status']=='completed' and run['conclusion']=='success','Acceptance not successful')
    require(policy['manifest_sha256']==manifest_hash(),'Pinned manifest hash')
    require(r['schema']=='bootstrap-1' and r['purpose']=='reviewed-control-and-runtime-bootstrap' and r['repository']==FORK,'Original bootstrap schema')
    require(r['candidate']==M['candidate'] and r['base']==M['base'] and r['tree']==M['tree'] and r['upstream']==M['upstream'],'Exact target')
    require(r['source_run']==identity(run) and r['source_job']=='candidate' and r['manifest_sha256']==manifest_hash(),'Original test job identity')
    require(type(r['tests_process_exit']) is int and r['tests_process_exit']==0 and r['sdk_version_asserted']=='0.9.2','Test observations')
    require(ca['expired'] is False,'Expired source artifact')
    expected={'schema':'bootstrap-e2e-1','purpose':r['purpose'],'manifest_sha256':manifest_hash(),'candidate_run':identity(run),'candidate_job':{'name':'candidate','status':'completed','conclusion':'success'},'candidate_artifact':{'id':ca['id'],'run_id':run['id'],'digest':ca['digest'],'expired':False},'candidate':M['candidate'],'bundle_sha256':r['bundle_sha256'],'pre_head':M['client_base'],'publication_enabled':False,'dashboard_identity':identity(run)}
    require(b==expected,'Original Dashboard binding')
    for key,value in expected.items():require(result[key]==value,'Dashboard result binding: '+key)
    require(result['dashboard_run']==identity(run),'Dashboard run')
    for snapshot in (r['snapshot'],result):
        require(snapshot['post_head']==M['candidate'] and snapshot['tracked_tree_matches'] is True and snapshot['candidate_stopped'] is True,'Stopped tracked-tree snapshot')
        require(type(snapshot['tracked_files_verified']) is int and snapshot['tracked_files_verified']>0,'Snapshot file count')
    require(result['passed'] is True and result['reconnected'] is True and result['browser_sandbox_requested'] is True,'Dashboard observations')
    require('PID namespaces Yes' in result['browser_sandbox_status'] and 'Seccomp-BPF sandbox Yes' in result['browser_sandbox_status'],'Browser sandbox')
    require(result['observed_receipt']=={'pre_sha':M['client_base'],'post_sha':M['candidate'],'outcome':'success'},'Native receipt')

def verify():
    policy=json.loads((ROOT/'bootstrap-issuer-policy.json').read_text())
    run=api(LAB,'actions/runs/'+str(policy['acceptance_run']))
    require(run['status']=='completed' and run['conclusion']=='success','Bootstrap acceptance is not complete/success')
    require(api(LAB,'actions/workflows/'+str(run['workflow_id']))['path']==PATH,'Workflow ID/path')
    completed(run,'candidate');completed(run,'dashboard')
    ca,cz=artifact(run,f'bootstrap-candidate-{run["id"]}-{run["run_attempt"]}')
    da,dz=artifact(run,f'bootstrap-dashboard-{run["id"]}-{run["run_attempt"]}')
    require(ca['id']==policy['candidate_artifact_id'] and ca['digest']==policy['candidate_artifact_digest'],'Pinned candidate artifact')
    require(da['id']==policy['dashboard_artifact_id'] and da['digest']==policy['dashboard_artifact_digest'],'Pinned Dashboard artifact')
    raw=cz.read('e2e-input/receipt.json');r=json.loads(raw);b=json.loads(dz.read('e2e-input/binding.json'));result=json.loads(dz.read('evidence/result.json'))
    require(dz.read('e2e-input/original-receipt.json')==raw,'Unchanged original receipt bytes')
    bundle=cz.read('e2e-input/candidate.bundle');require(hashlib.sha256(bundle).hexdigest()==r['bundle_sha256'],'Original bundle bytes')
    validate(run,ca,r,b,result,policy)
    with tempfile.TemporaryDirectory(prefix='bootstrap-verification-') as temp:
        repo,manifest,bpath=source(pathlib.Path(temp)/'objects')
        bpath.write_bytes(bundle)
        subprocess.run(['git','--git-dir='+str(repo),'bundle','verify',str(bpath)],check=True,timeout=90)
        heads=subprocess.check_output(['git','--git-dir='+str(repo),'bundle','list-heads',str(bpath)],text=True).strip()
        require(heads==M['candidate']+' HEAD','Original bundled commit')
        require(result['tracked_files_verified']==len(manifest)==r['snapshot']['tracked_files_verified'],'Independent file count')
    ci=api(FORK,'actions/runs/'+str(policy['fork_ci_run']))
    require(ci['repository']['full_name']==FORK and ci['head_sha']==M['candidate'] and ci['path']=='.github/workflows/bridge-release-ci.yml' and ci['head_branch']==M['branch'] and ci['status']=='completed' and ci['conclusion']=='success','Exact fork branch CI')
    require(api(FORK,'git/ref/heads/main')['object']['sha']==M['base'],'Main moved')
    proof={'schema':'bootstrap-proof-1','repository':FORK,'candidate':M['candidate'],'base':M['base'],'tree':M['tree'],'manifest_sha256':manifest_hash(),'acceptance_run':identity(run),'candidate_artifact':{'id':ca['id'],'digest':ca['digest']},'dashboard_artifact':{'id':da['id'],'digest':da['digest']},'bundle_sha256':r['bundle_sha256'],'original_receipt_sha256':hashlib.sha256(raw).hexdigest(),'fork_ci_run':ci['id'],'tracked_files_verified':result['tracked_files_verified'],'verified':True}
    pathlib.Path('bootstrap-proof.json').write_text(json.dumps(proof,indent=2))
    return proof
if __name__=='__main__':
    p=verify();print(json.dumps(p,indent=2))
