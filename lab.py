"""Synthetic exact-SHA publication laboratory. Never targets the real fork."""
import base64, json, os, re, urllib.request, urllib.error
REPO='Skimbee/hermes-bridge-release-lab'
CHECK='Bridge release / exact-candidate'
TEXT='Synthetic fixture for exact-commit publication acceptance.\n'

def validate(expected, current, candidate, parents):
    if not all(re.fullmatch('[0-9a-f]{40}',s) for s in (expected,current,candidate)):
        raise ValueError('Invalid SHA')
    if (current!=expected or candidate==expected or len(parents) not in (1,2)
            or parents[0]!=expected or len(set(parents))!=len(parents)
            or not all(re.fullmatch('[0-9a-f]{40}',p) for p in parents)):
        raise ValueError('Stale base or unexpected candidate topology')

def api(path, method='GET', data=None, checks=False):
    token=os.environ['CHECK_TOKEN' if checks else 'APP_TOKEN']
    request=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,
        data=json.dumps(data).encode() if data is not None else None,method=method,
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(request,timeout=30) as response:
        text=response.read()
        return json.loads(text) if text else None

def main():
    if os.environ['GITHUB_REPOSITORY']!=REPO or os.environ['GITHUB_REF']!='refs/heads/lab-controller':
        raise ValueError('Wrong repository or controller')
    mode=os.environ['MODE']
    base=api('git/ref/heads/main')['object']['sha']
    if mode in ('prepare','prepare-merge'):
        parent=api('git/commits/'+base)
        path='scripts/lab-merge-fixture.txt' if mode=='prepare-merge' else 'scripts/lab-fixture.txt'
        tree=api('git/trees','POST',{'base_tree':parent['tree']['sha'],'tree':[{'path':path,'mode':'100644','type':'blob','content':TEXT}]})
        if tree['sha']==parent['tree']['sha']: raise ValueError('Fixture already present; no new candidate')
        parents=[base]
        if mode=='prepare-merge':
            if len(parent['parents'])!=1: raise ValueError('Expected linear base for divergence probe')
            common=parent['parents'][0]['sha']
            common_commit=api('git/commits/'+common)
            upstream_tree=api('git/trees','POST',{'base_tree':common_commit['tree']['sha'],'tree':[{'path':path,'mode':'100644','type':'blob','content':TEXT}]})
            upstream=api('git/commits','POST',{'message':'test: independent synthetic upstream','tree':upstream_tree['sha'],'parents':[common]})
            parents.append(upstream['sha'])
        commit=api('git/commits','POST',{'message':'test: synthetic exact-SHA publication candidate','tree':tree['sha'],'parents':parents})
        sha=commit['sha']; branch='lab/candidate-'+sha
        api('git/refs','POST',{'ref':'refs/heads/'+branch,'sha':sha})
        if api('git/ref/heads/'+branch)['object']['sha']!=sha: raise ValueError('Branch mismatch')
        pr=api('pulls','POST',{'title':'Lab: approve synthetic exact-SHA candidate','head':branch,'base':'main','draft':False,'maintainer_can_modify':False,'body':'Synthetic test only. No Hermes code or production change. Approve this exact commit after the controller confirms both negative probes. Do NOT use the Merge button. Candidate: '+sha+'; base: '+base})
        print('PR_CREATED',pr['html_url'],flush=True)
    elif mode=='publish':
        number=os.environ['PR_NUMBER']
        if not re.fullmatch('[1-9][0-9]*',number): raise ValueError('Invalid PR number')
        pr=api('pulls/'+number); sha=pr['head']['sha']
        commit=api('git/commits/'+sha)
        base=commit['parents'][0]['sha']
    else: raise ValueError('Invalid mode')
    if pr['state']!='open' or pr['base']['ref']!='main' or pr['head']['repo']['full_name']!=REPO or pr['head']['ref']!='lab/candidate-'+sha:
        raise ValueError('Wrong PR binding')
    if pr['user']['type']!='Bot': raise ValueError('PR is not bot-authored')
    commit=api('git/commits/'+sha)
    validate(base,api('git/ref/heads/main')['object']['sha'],sha,[p['sha'] for p in commit['parents']])
    path='scripts/lab-merge-fixture.txt' if len(commit['parents'])==2 else 'scripts/lab-fixture.txt'
    if len(commit['parents'])==2:
        divergence=api('compare/'+base+'...'+commit['parents'][1]['sha'])
        if divergence['status']!='diverged': raise ValueError('Parents do not have diverged history')
        print('DIVERGED_TWO_PARENT_CANDIDATE',sha,flush=True)
    diff=api('compare/'+base+'...'+sha)
    if [(f['filename'],f['status']) for f in diff['files']]!=[(path,'added')]: raise ValueError('Unexpected diff')
    content=api('contents/'+path+'?ref='+sha)
    if content['type']!='file' or base64.b64decode(content['content']).decode()!=TEXT: raise ValueError('Wrong fixture')
    if not api('branches/main')['protected']: raise ValueError('Protection absent')
    def attempt(expect_rejection):
        validate(base,api('git/ref/heads/main')['object']['sha'],sha,[p['sha'] for p in commit['parents']])
        try:
            api('git/refs/heads/main','PATCH',{'sha':sha,'force':False})
        except urllib.error.HTTPError as exc:
            if not expect_rejection or exc.code not in (403,422): raise
            message=json.loads(exc.read()).get('message','')
            if api('git/ref/heads/main')['object']['sha']!=base: raise ValueError('Main changed despite rejection')
            print('PROTECTED_REJECTION',exc.code,message,flush=True)
            return
        if expect_rejection: raise RuntimeError('SECURITY FAILURE: main accepted unapproved candidate')
        if api('git/ref/heads/main')['object']['sha']!=sha: raise ValueError('Published SHA mismatch')
        print('EXACT_SHA_PUBLISHED',sha,flush=True)
    if mode in ('prepare','prepare-merge'):
        attempt(True)
        check=api('check-runs','POST',{'name':CHECK,'head_sha':sha,'status':'completed','conclusion':'success','external_id':'synthetic-lab:'+sha,'output':{'title':'Synthetic candidate binding verified','summary':'Verified exact parent, unchanged base and only the fixed synthetic fixture. LAB ONLY; not a Hermes release test.'}},checks=True)
        observed=api('check-runs/'+str(check['id']),checks=True)
        if observed['head_sha']!=sha or observed['conclusion']!='success': raise ValueError('Check readback failed')
        attempt(True)
        print('READY_FOR_HUMAN_APPROVAL',pr['html_url'],sha,flush=True)
    else:
        reviews=api('pulls/'+str(pr['number'])+'/reviews?per_page=100')
        if len(reviews)>=100: raise ValueError('Review pagination requires manual inspection')
        latest={}
        for r in reviews:
            if r['state']!='COMMENTED': latest[r['user']['login']]=r
        approval=latest.get('Skimbee',{})
        if approval.get('state')!='APPROVED' or approval.get('commit_id')!=sha: raise ValueError('Missing exact-head owner approval')
        checks=api('commits/'+sha+'/check-runs?filter=latest&per_page=100',checks=True)
        matches=[c for c in checks['check_runs'] if c['name']==CHECK]
        if len(matches)!=1 or matches[0]['conclusion']!='success' or matches[0]['app']['id']!=15368 or matches[0]['external_id']!='synthetic-lab:'+sha: raise ValueError('Missing or wrong synthetic check')
        attempt(False)

if __name__=='__main__': main()
