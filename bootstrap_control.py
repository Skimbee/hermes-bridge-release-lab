"""Reviewed control-change PR/check only: existing protections and exact owner approval."""
import hashlib,json,os,pathlib,urllib.request
from bootstrap_support import M,LAB,FORK,api,require
from bootstrap_verifier import verify
from release_policy import CHECK,APP_ID,validate_check,owner_approved
BOT='skimbee-hermes-bridge[bot]'

def write(path,method,data):
    require(path in ('pulls','check-runs') and method=='POST','Lab may author/attest, never publish fork code')
    request=urllib.request.Request('https://api.github.com/repos/'+FORK+'/'+path,method=method,data=json.dumps(data).encode(),headers={'Authorization':'Bearer '+os.environ['APP_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(request,timeout=30) as r:return json.load(r)

def exact_pr(create=False):
    rows=api(FORK,'pulls?state=open&base=main&head=Skimbee:'+M['branch']+'&per_page=100')
    require(len(rows)<=1,'PR ambiguity')
    if not rows and create:
        policy=json.loads(pathlib.Path('bootstrap-issuer-policy.json').read_text())
        body='## Zusammengefasste Release-Abnahme\n\nExakter Kandidat: `'+M['candidate']+'`\nBasis: `'+M['base']+'`\n\nErsetzt den GitHub-Schedule durch den bereits geprüften externen Stunden-Trigger und ergänzt einen streng begrenzten Lock-Metadaten-Schritt. Nur fehlende explizite false-Ausnahmen für bereits gelockte Pakete dürfen ergänzt werden; Paketdaten, Versionen und Hashes bleiben unverändert. Der Helper stammt vom vertrauenswürdigen Ausgangs-Commit, nicht aus eintreffendem Upstream. Korrekturen werden vor den weiterhin obligatorischen Lock-/SDK-/Regressionstests committed und an die Original-Evidence gebunden. No-change bleibt erfolgreich. Publisher-/Provenienzlogik und Schutzregeln werden nicht gelockert. Dieser genaue Commit hat eigene frische Tests; frühere Evidence wird nicht auf ihn übertragen.\n\n### Neue Evidence\n- Isolierte SDK-/Bridge-Regressionsprüfung und echter Dashboard-Updateweg: https://github.com/'+LAB+'/actions/runs/'+str(policy['acceptance_run'])+'\n- Exakte Branch-CI: https://github.com/'+FORK+'/actions/runs/'+str(policy['fork_ci_run'])+'\n- Separate App-Rollen; ursprüngliche Run-/Attempt-/Artifact-Bindung; gestoppter externer Snapshot; force:false.\n\n### Human Gate\nBitte diesen exakten Head als Codeowner prüfen und APPROVE verwenden. Nicht den Merge-Button nutzen: veröffentlicht wird ausschließlich die identische getestete SHA über den geschützten Reference-Pfad. Keine neue Admin-Ausnahme, keine Rechteausweitung der App, kein Produktivremote-Wechsel und keine Retention-Aktivierung.\n\nDie bestehende Publikationsfreigabe wird nicht verändert. Der produktive Hermes-Checkout und die pausierte Retention bleiben unangetastet. Der alte GitHub-Zeitplan wird erst durch Übernahme dieses exakten, freigegebenen Commits entfernt.'
        created=write('pulls','POST',{'title':'Bridge: externer Stunden-Trigger und begrenzte Lock-Metadatenkorrektur','head':M['branch'],'base':'main','body':body,'draft':False,'maintainer_can_modify':False})
        rows=[created]
    require(len(rows)==1,'Bootstrap PR missing')
    pr=api(FORK,'pulls/'+str(rows[0]['number']))
    require(pr['state']=='open' and pr['draft'] is False and pr['head']['sha']==M['candidate'] and pr['head']['ref']==M['branch'] and pr['head']['repo']['full_name']==FORK and pr['base']['ref']=='main' and pr['base']['repo']['full_name']==FORK,'Exact PR binding')
    require(pr['user']['login']==BOT and pr['user']['type']=='Bot','App PR author')
    return pr

def main():
    require(os.environ['GITHUB_REPOSITORY']==LAB and os.environ['GITHUB_REF']=='refs/heads/lab-controller','Trusted lab only')
    proof=verify();digest=hashlib.sha256(json.dumps(proof,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    external='reviewed-bootstrap:'+str(proof['acceptance_run']['id'])+':'+str(proof['acceptance_run']['attempt'])+':'+digest
    details='https://github.com/'+LAB+'/actions/runs/'+str(proof['acceptance_run']['id'])
    mode=os.environ['MODE'];require(api(FORK,'branches/main')['protected'] is True,'Main protection missing')
    if mode=='author':
        pr=exact_pr(create=True);print('BOOTSTRAP_OWNER_REVIEW',pr['html_url'],M['candidate']);return
    pr=exact_pr()
    if mode=='attest':
        check=write('check-runs','POST',{'name':CHECK,'head_sha':M['candidate'],'status':'completed','conclusion':'success','external_id':external,'details_url':details,'output':{'title':'Fresh exact bootstrap evidence verified','summary':'New isolated SDK/Bridge tests and native Dashboard update passed for this exact commit. Original run/attempt/artifact and bundle/receipt bindings plus both stopped tracked-tree snapshots independently verified. Owner approval still required. Proof SHA-256 '+digest}})
        validate_check(api(FORK,'check-runs/'+str(check['id'])),M['candidate'],external,details)
        print('BOOTSTRAP_CHECK_ISSUED',check['id'],M['candidate']);return
    raise ValueError('Lab bootstrap channel is author/attest only; publishing is forbidden')
if __name__=='__main__':main()
