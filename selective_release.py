"""Synthetic end-to-end policy test. Only lab-selective-review is writable."""
import json,os,pathlib,urllib.request,urllib.error
from release_policy import require,sha,validate_candidate,validate_check,protected_paths,CHECK,APP_ID
REPO='Skimbee/hermes-bridge-release-lab';BRANCH='lab-selective-review'

def api(path,method='GET',data=None,token='READ_TOKEN'):
    request=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,method=method,
        data=json.dumps(data).encode() if data is not None else None,
        headers={'Authorization':'Bearer '+os.environ[token],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(request,timeout=30) as r:return json.load(r)

def main():
    require(os.environ['GITHUB_REPOSITORY']==REPO and os.environ['GITHUB_REF']=='refs/heads/lab-controller','Lab only')
    rid=os.environ['GITHUB_RUN_ID'];attempt=os.environ['GITHUB_RUN_ATTEMPT'];mode=os.environ['MODE']
    def head():return api('git/ref/heads/'+BRANCH)['object']['sha']
    def output(k,v):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write(k+'='+v+'\n')
    if mode=='prepare':
        base=head();parent=api('git/commits/'+base)
        commits=[]
        for kind,path in [('routine','routine-'+rid+'.txt'),('control','scripts/control-'+rid+'.txt')]:
            tree=api('git/trees','POST',{'base_tree':parent['tree']['sha'],'tree':[{'path':path,'mode':'100644','type':'blob','content':'Synthetic '+kind+' '+rid+'\n'}]},'APP_TOKEN')
            c=api('git/commits','POST',{'message':'test: selective '+kind+' '+rid,'tree':tree['sha'],'parents':[parent['sha']]},'APP_TOKEN')
            branch='lab/selective-'+kind+'-'+rid
            api('git/refs','POST',{'ref':'refs/heads/'+branch,'sha':c['sha']},'APP_TOKEN')
            require(api('git/ref/heads/'+branch)['object']['sha']==c['sha'],'Ref readback')
            pr=api('pulls','POST',{'title':'Lab selective '+kind+' '+rid,'head':branch,'base':BRANCH,'body':'Synthetic only; policy test. No Hermes release.','draft':False,'maintainer_can_modify':False},'APP_TOKEN')
            require(api('pulls/'+str(pr['number']))['head']['sha']==c['sha'],'PR readback')
            output(kind,c['sha']);output(kind+'_pr',str(pr['number']));commits.append(c['sha']);parent=c
        output('base',base)
        return
    base=sha(os.environ['BASE']);routine=sha(os.environ['ROUTINE']);control=sha(os.environ['CONTROL'])
    targets=[('routine',routine,base,'routine-'+rid+'.txt'),('control',control,routine,'scripts/control-'+rid+'.txt')]
    for kind,c,parent,path in targets:
        commit=api('git/commits/'+c)
        validate_candidate(parent,parent,c,[p['sha'] for p in commit['parents']])
        diff=api('compare/'+parent+'...'+c)
        require([(f['filename'],f['status']) for f in diff['files']]==[(path,'added')],'Diff')
        blob=api('contents/'+path+'?ref='+c)
        import base64
        require(base64.b64decode(blob['content']).decode()=='Synthetic '+kind+' '+rid+'\n','Content')
        require(bool(protected_paths([path]))==(kind=='control'),'Classifier')
    external='selective-lab:'+rid+':'+attempt
    url='https://github.com/'+REPO+'/actions/runs/'+rid
    if mode=='verify':
        require(head()==base,'Base moved')
        if os.environ.get('FAIL_VERIFIER')=='true':raise ValueError('Intentional verifier failure: no checks or publication permitted')
        print('SYNTHETIC_EVIDENCE_VERIFIED')
    elif mode=='attest':
        require(head()==base,'Base moved')
        for _,candidate,_,_ in targets:
            check=api('check-runs','POST',{'name':CHECK,'head_sha':candidate,'status':'completed','conclusion':'success','external_id':external,'details_url':url,'output':{'title':'Synthetic lab verification','summary':'LAB ONLY. Independent verifier job passed. Codeowner protection must still hold.'}},'APP_TOKEN')
            validate_check(api('check-runs/'+str(check['id'])),candidate,external,url)
    elif mode=='publish':
        require(head()==base,'Base moved')
        reports=[]
        for kind,c,parent,path in targets:
            checks=api('commits/'+c+'/check-runs?filter=latest&per_page=100')['check_runs']
            matches=[r for r in checks if r['name']==CHECK and r['app']['id']==APP_ID]
            require(len(matches)==1,'Check count');validate_check(matches[0],c,external,url)
            require(head()==parent,'Unexpected publication base')
            try:api('git/refs/heads/'+BRANCH,'PATCH',{'sha':c,'force':False},'APP_TOKEN')
            except urllib.error.HTTPError as exc:
                message=json.loads(exc.read()).get('message','')
                require(kind=='control' and exc.code in (403,422) and 'review' in message.lower(),'Unexpected rejection: '+message)
                require(head()==parent,'Ref moved on rejection');reports.append({'case':kind,'result':'rejected_owner_review','message':message})
            else:
                require(kind=='routine','SECURITY FAILURE: protected content published without owner')
                require(head()==c,'Exact SHA readback');reports.append({'case':kind,'result':'exact_sha_published','sha':c})
        pathlib.Path('selective-result.json').write_text(json.dumps({'run':rid,'attempt':attempt,'base':base,'routine':routine,'control':control,'reports':reports},indent=2))
        print(json.dumps(reports))
    else:raise ValueError('Invalid mode')
if __name__=='__main__':main()
