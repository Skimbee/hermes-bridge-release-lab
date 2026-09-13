"""One-shot contents-only ref update of an owner-uploaded workflow commit."""
import base64,json,os,pathlib,urllib.request
from release_policy import require,validate_candidate,validate_check,CHECK,APP_ID
REPO='Skimbee/hermes-bridge-release-lab'
def api(path,method='GET',data=None,token='READ_TOKEN'):
    q=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,method=method,data=json.dumps(data).encode() if data is not None else None,headers={'Authorization':'Bearer '+os.environ[token],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(q,timeout=30) as r:return json.load(r)
def main():
    require(os.environ['GITHUB_REPOSITORY']==REPO and os.environ['GITHUB_REF']=='refs/heads/lab-controller','Lab only')
    case=json.loads(pathlib.Path('workflow-upload-case.json').read_text());base=case['base'];sha=case['candidate'];target=case['target']
    require(target=='lab-workflow-permission','Fixed target')
    def head():return api('git/ref/heads/'+target)['object']['sha']
    commit=api('git/commits/'+sha);validate_candidate(base,head(),sha,[p['sha'] for p in commit['parents']])
    diff=api('compare/'+base+'...'+sha)
    require([(f['filename'],f['status']) for f in diff['files']]==[(case['path'],'added')],'Only inert workflow diff')
    blob=api('contents/'+case['path']+'?ref='+sha)
    require(base64.b64decode(blob['content']).decode()==case['content'],'Fixture content')
    require(api('branches/'+target)['protected'] is True,'Protection missing')
    external='owner-workflow-permission:'+os.environ['GITHUB_RUN_ID'];url='https://github.com/'+REPO+'/actions/runs/'+os.environ['GITHUB_RUN_ID']
    check=api('check-runs','POST',{'name':CHECK,'head_sha':sha,'status':'completed','conclusion':'success','external_id':external,'details_url':url,'output':{'title':'Synthetic permission fixture verified','summary':'LAB ONLY. Owner-uploaded inert workflow. Contents-only App ref update under an App-bound required check; not a codeowner-review acceptance.'}},'CHECK_TOKEN')
    validate_check(api('check-runs/'+str(check['id'])),sha,external,url)
    require(head()==base,'Target changed')
    api('git/refs/heads/'+target,'PATCH',{'sha':sha,'force':False},'PUBLISH_TOKEN')
    require(head()==sha and api('branches/'+target)['protected'] is True,'Exact protected readback')
    result={'repository':REPO,'branch':target,'base':base,'candidate':sha,'run_id':os.environ['GITHUB_RUN_ID'],'contents_only_workflow_ref_update':True,'codeowner_acceptance':False,'check_id':check['id']}
    pathlib.Path('workflow-permission-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
