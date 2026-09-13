"""Only synthetic check-source tests; never executes candidate code."""
import json,os,urllib.request,urllib.error
REPO='Skimbee/hermes-bridge-release-lab'
BRANCH='lab-issuer-matrix'
NAME='Bridge release / exact-candidate'
BASE='67afb2cbe6c16fdee627833a602fda1af9b202f9'
def api(path,method='GET',data=None,token='PUBLISH_TOKEN'):
    req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,method=method,
        data=json.dumps(data).encode() if data is not None else None,
        headers={'Authorization':'Bearer '+os.environ[token],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def main():
    assert os.environ['GITHUB_REPOSITORY']==REPO and os.environ['GITHUB_REF']=='refs/heads/lab-controller'
    def head():return api('git/ref/heads/'+BRANCH)['object']['sha']
    assert head()==BASE, 'One-shot matrix base changed'
    assert api('branches/'+BRANCH)['protected']
    parent=api('git/commits/'+BASE)
    tree=api('git/trees','POST',{'base_tree':parent['tree']['sha'],'tree':[{'path':'synthetic-issuer-matrix.txt','mode':'100644','type':'blob','content':'Fixed synthetic check-issuer matrix.\n'}]})
    c=api('git/commits','POST',{'message':'test: exact candidate issuer matrix','parents':[BASE],'tree':tree['sha']})['sha']
    branch='lab/matrix-'+c
    api('git/refs','POST',{'ref':'refs/heads/'+branch,'sha':c})
    assert api('git/ref/heads/'+branch)['object']['sha']==c
    results=[]
    def reject(label):
        assert head()==BASE
        try:api('git/refs/heads/'+BRANCH,'PATCH',{'sha':c,'force':False})
        except urllib.error.HTTPError as e:
            message=json.loads(e.read()).get('message','')
            assert e.code in (403,422) and ('check' in message.lower()), message
            assert head()==BASE
            results.append({'case':label,'result':'rejected','http':e.code,'message':message})
            print(json.dumps(results[-1]),flush=True)
        else:raise RuntimeError('SECURITY FAILURE: accepted '+label)
    def check(sha,conclusion,token,expected_app):
        result=api('check-runs','POST',{'name':NAME,'head_sha':sha,'status':'completed','conclusion':conclusion,
            'external_id':'issuer-matrix:'+os.environ['GITHUB_RUN_ID']+':'+os.environ['GITHUB_RUN_ATTEMPT'],
            'output':{'title':'Synthetic issuer acceptance probe','summary':'LAB ONLY; no production or release evidence.'}},token=token)
        rb=api('check-runs/'+str(result['id']),token=token)
        assert rb['app']['id']==expected_app and rb['head_sha']==sha and rb['conclusion']==conclusion
        return result['id']
    reject('missing-check')
    check(c,'success','ACTIONS_TOKEN',15368)
    reject('wrong-issuer-success')
    check(BASE,'success','VERIFIER_TOKEN',4931424)
    reject('correct-issuer-wrong-sha')
    check(c,'failure','VERIFIER_TOKEN',4931424)
    reject('correct-issuer-failed-check')
    check_id=check(c,'success','VERIFIER_TOKEN',4931424)
    assert head()==BASE
    api('git/refs/heads/'+BRANCH,'PATCH',{'sha':c,'force':False})
    assert head()==c
    results.append({'case':'correct-issuer-exact-sha-success','result':'published','sha':c,'check_id':check_id})
    report={'repository':REPO,'branch':BRANCH,'base':BASE,'candidate':c,'run_id':os.environ['GITHUB_RUN_ID'],'attempt':os.environ['GITHUB_RUN_ATTEMPT'],'cases':results}
    with open('issuer-matrix-result.json','w') as f:json.dump(report,f,indent=2)
    assert len(results)==5
    print(json.dumps(report),flush=True)
if __name__=='__main__':main()
