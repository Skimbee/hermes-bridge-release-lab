"""Prepare original bootstrap test evidence for a separate Dashboard runner."""
import hashlib,json,pathlib,subprocess
from bootstrap_support import ROOT,M,current,completed,artifact,identity,source,manifest_hash,require

def main():
    run=current();completed(run,'candidate')
    a,z=artifact(run,f'bootstrap-candidate-{run["id"]}-{run["run_attempt"]}')
    raw=z.read('e2e-input/receipt.json');receipt=json.loads(raw);bundle=z.read('e2e-input/candidate.bundle')
    require(receipt['schema']=='bootstrap-1' and receipt['source_run']==identity(run) and receipt['source_job']=='candidate','Original bootstrap identity')
    require(receipt['manifest_sha256']==manifest_hash() and receipt['candidate']==M['candidate'] and receipt['base']==M['base'] and receipt['tree']==M['tree'],'Original bootstrap manifest/candidate')
    require(receipt['tests_process_exit']==0 and receipt['sdk_version_asserted']=='0.9.2' and receipt['snapshot']['tracked_tree_matches'] is True and receipt['snapshot']['candidate_stopped'] is True,'Bootstrap test observations')
    require(hashlib.sha256(bundle).hexdigest()==receipt['bundle_sha256'],'Original bundle digest')
    inputs=ROOT/'e2e-input';repo,manifest,bpath=source(inputs);bpath.write_bytes(bundle)
    subprocess.run(['git','--git-dir='+str(repo),'bundle','verify',str(bpath)],check=True,timeout=90)
    got=subprocess.check_output(['git','--git-dir='+str(repo),'bundle','list-heads',str(bpath)],text=True)
    require(got.strip()==M['candidate']+' HEAD','Original bundle head')
    require(receipt['snapshot']['tracked_files_verified']==len(manifest),'Bootstrap file count')
    (inputs/'original-receipt.json').write_bytes(raw)
    meta={'schema':'bootstrap-e2e-1','purpose':'reviewed-control-and-runtime-bootstrap','manifest_sha256':manifest_hash(),'candidate_run':identity(run),'candidate_job':{'name':'candidate','status':'completed','conclusion':'success'},'candidate_artifact':{'id':a['id'],'run_id':run['id'],'digest':a['digest'],'expired':False},'candidate':M['candidate'],'bundle_sha256':receipt['bundle_sha256'],'pre_head':M['client_base'],'publication_enabled':False,'dashboard_identity':identity(run)}
    (inputs/'binding.json').write_text(json.dumps(meta,indent=2))
    print('ORIGINAL_BOOTSTRAP_BINDING_PREPARED',run['id'],a['id'],M['candidate'])
if __name__=='__main__':main()
