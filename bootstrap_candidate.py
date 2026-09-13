"""Fresh bootstrap candidate tests inside the accepted container boundary."""
import hashlib,importlib.util,json,os,pathlib,subprocess
from bootstrap_support import ROOT,M,current,identity,source,manifest_hash

def main():
    run=current();inputs=ROOT/'e2e-input';repo,manifest,bundle=source(inputs)
    (inputs/'binding.json').write_text(json.dumps({'candidate':M['candidate']}))
    spec=importlib.util.spec_from_file_location('trusted_container_controller',ROOT/'container-e2e/controller.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
    name='bootstrap-tests-'+str(run['id']);volume=name+'-data';network=name+'-net';started=False
    try:
        c.cmd(['docker','network','create','--subnet','172.30.220.0/24',network])
        c.cmd(['sudo','iptables','-I','INPUT','1','-s','172.30.220.0/24','-j','DROP'])
        c.cmd(['sudo','iptables','-I','INPUT','1','-s','172.30.220.0/24','-m','conntrack','--ctstate','ESTABLISHED,RELATED','-j','ACCEPT'])
        for dest in ['0.0.0.0/8','10.0.0.0/8','100.64.0.0/10','127.0.0.0/8','169.254.0.0/16','172.16.0.0/12','192.0.0.0/24','192.168.0.0/16','198.18.0.0/15','224.0.0.0/4','240.0.0.0/4']:
            c.cmd(['sudo','iptables','-I','DOCKER-USER','1','-s','172.30.220.0/24','-d',dest,'-j','REJECT'])
        c.cmd(['sudo','iptables','-I','DOCKER-USER','1','-s','172.30.220.0/24','-m','conntrack','--ctstate','ESTABLISHED,RELATED','-j','ACCEPT'])
        c.cmd(['docker','volume','create',volume])
        c.cmd(['docker','create','--name',name,'--init','--user','10001:10001','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true','--pids-limit=512','--memory=5g','--cpus=2','--log-driver=local','--log-opt=max-size=2m','--log-opt=max-file=2','--network',network,'--mount','type=volume,source='+volume+',target=/work','--tmpfs=/tmp:rw,nosuid,nodev,size=512m,mode=1777','bridge-e2e-toolchain:local'])
        config=json.loads(c.capture(['docker','inspect',name]))[0]
        assert config['HostConfig']['ReadonlyRootfs'] and config['HostConfig']['CapDrop']==['ALL'] and not config['HostConfig']['Privileged'] and config['Config']['User']=='10001:10001'
        assert len(config['Mounts'])==1 and config['Mounts'][0]['Name']==volume
        c.cmd(['docker','cp',str(repo),name+':/work/fixture.git'],timeout=240)
        c.cmd(['docker','start',name]);started=True
        command='mkdir -p /work/home/.hermes && git config --global --add safe.directory /work/fixture.git && git clone --no-hardlinks /work/fixture.git /work/client && cd /work/client && uv lock --check && uv sync --frozen --extra hindsight --extra dev && uv pip install --python .venv/bin/python pytest-asyncio==1.3.0 && .venv/bin/python -c \'from importlib.metadata import version; assert version("hindsight-client")=="0.9.2"\' && .venv/bin/python -m unittest discover -s scripts/bridge -p "test_*.py" -v && .venv/bin/python scripts/bridge/check_workflows.py && bash scripts/run_tests.sh tests/plugins/memory/test_hindsight_pin_contract.py tests/plugins/memory/test_hindsight_provider.py tests/test_packaging_metadata.py tests/tools/test_lazy_deps.py tests/tools/test_lazy_deps_managed.py tests/tools/test_lazy_deps_durable_target.py tests/hermes_cli/test_update_upstream_prompt_noninteractive.py'
        c.logged(['docker','exec',name,'sh','-c',command],ROOT/'evidence/bootstrap-tests-untrusted.log',1800)
        c.cmd(['docker','stop','--time','10',name]);started=False
        assert not json.loads(c.capture(['docker','inspect','--format','{{json .State}}',name]))['Running']
        inspected=c.capture(['docker','run','--rm','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true','--user','10001:10001','--pids-limit=32','--memory=256m','--mount','type=volume,source='+volume+',target=/snapshot,readonly','--interactive','bridge-e2e-toolchain:local','python3','-I','-c',(ROOT/'container-e2e/inspect_snapshot.py').read_text()],input=json.dumps({'candidate':M['candidate'],'manifest':manifest}),timeout=180)
        result=json.loads(inspected);assert result['tracked_files_verified']==len(manifest) and result['tracked_tree_matches'] is True
        receipt={'schema':'bootstrap-1','purpose':'reviewed-control-and-runtime-bootstrap','repository':M['repository'],'base':M['base'],'candidate':M['candidate'],'tree':M['tree'],'upstream':M['upstream'],'source_run':identity(run),'source_job':'candidate','manifest_sha256':manifest_hash(),'bundle_sha256':hashlib.sha256(bundle.read_bytes()).hexdigest(),'tests_process_exit':0,'sdk_version_asserted':'0.9.2','snapshot':result}
        (inputs/'receipt.json').write_text(json.dumps(receipt,indent=2))
        print(json.dumps({'bootstrap_candidate_passed':True,'candidate':M['candidate'],'tracked_files':len(manifest)}))
    finally:
        if started:subprocess.run(['docker','stop','--time','10',name],capture_output=True,timeout=30)
        path=ROOT/'evidence/bootstrap-tests-untrusted.log'
        if path.exists():
            import re
            text=path.read_text(errors='replace')[-18000:]
            text=re.sub(r'(?im)^.*(?:token|password|secret|api.key|authorization).*$','[REDACTED]',text)
            (ROOT/'evidence/bootstrap-tests-diagnostic.txt').write_text(text)
if __name__=='__main__':main()
