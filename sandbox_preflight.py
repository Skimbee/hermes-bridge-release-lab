"""Hosted-runner-only hostile sandbox preflight. No Hermes E2E claim."""
import json,os,pathlib,subprocess
IMAGE='python:3.11-slim-bookworm@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84'
ATTACK=r'''
import json,os,pathlib,socket
results={}
results['nonroot']=os.getuid()!=0
status=pathlib.Path('/proc/self/status').read_text()
results['no_caps']='CapEff:\t0000000000000000' in status
results['no_new_privileges']='NoNewPrivs:\t1' in status
results['seccomp_filter']='Seccomp:\t2' in status
results['no_docker_socket']=not pathlib.Path('/var/run/docker.sock').exists()
results['no_host_controller']=not pathlib.Path(os.environ['PROBE_HOST_PATH']).exists()
results['no_host_via_pid1']=not pathlib.Path('/proc/1/root'+os.environ['PROBE_HOST_PATH']).exists()
results['no_actions_environment']=not any(k.startswith(('ACTIONS_','GITHUB_','RUNNER_')) for k in os.environ)
try:
    pathlib.Path('/usr/local/sandbox-write-probe').write_text('bad')
    results['rootfs_write_blocked']=False
except OSError: results['rootfs_write_blocked']=True
pathlib.Path('/work/probe').write_text('allowed')
results['scratch_writable']=pathlib.Path('/work/probe').read_text()=='allowed'
results['no_default_route']=not any(line.split()[1]=='00000000' for line in pathlib.Path('/proc/net/route').read_text().splitlines()[1:])
s=socket.socket(); s.settimeout(2)
try:
    s.connect(('169.254.169.254',80)); results['metadata_access_blocked']=False
except OSError: results['metadata_access_blocked']=True
finally:s.close()
print(json.dumps(results))
raise SystemExit(0 if all(results.values()) else 1)
'''
def main():
    if os.environ.get('GITHUB_REPOSITORY')!='Skimbee/hermes-bridge-release-lab' or os.environ.get('GITHUB_REF')!='refs/heads/lab-controller' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise RuntimeError('Hosted laboratory only')
    sentinel=pathlib.Path.cwd()/'trusted-controller-sentinel'; sentinel.write_text('external controller untouched\n')
    name='bridge-isolation-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']
    subprocess.run(['docker','pull',IMAGE],check=True,timeout=180)
    subprocess.run(['docker','create','--name',name,'--read-only','--user','65532:65532','--cap-drop=ALL','--security-opt=no-new-privileges:true','--network=none','--pids-limit=64','--memory=256m','--cpus=1','--log-driver=local','--log-opt=max-size=1m','--log-opt=max-file=1','--tmpfs=/work:rw,nosuid,nodev,noexec,size=16m,mode=1777','--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777','--env','PROBE_HOST_PATH='+str(sentinel),IMAGE,'python3','-I','-c',ATTACK],check=True,timeout=30)
    # Inspect trusted runtime config, not solely the attack process report.
    config=json.loads(subprocess.check_output(['docker','inspect',name],timeout=15))[0]
    hc=config['HostConfig']
    assert hc['ReadonlyRootfs'] and not hc['Privileged'] and hc['NetworkMode']=='none'
    assert hc['CapDrop']==['ALL'] and hc['PidMode']=='' and not hc['Binds'] and not config['Mounts']
    assert config['Config']['User']=='65532:65532'
    assert hc['Memory']==268435456 and hc['PidsLimit']==64
    run=subprocess.run(['docker','start','--attach',name],capture_output=True,text=True,timeout=30)
    assert len(run.stdout)<8192 and len(run.stderr)<8192
    if run.returncode!=0 or not run.stdout.strip():
        raise RuntimeError(json.dumps({'sandbox_start_exit':run.returncode,'diagnostic':run.stderr[:4096]}))
    results=json.loads(run.stdout)
    assert all(v is True for v in results.values()) and len(results)==12,results
    state=json.loads(subprocess.check_output(['docker','inspect','--format','{{json .State}}',name],timeout=15))
    assert state['ExitCode']==0 and not state['Running'] and not state['OOMKilled']
    assert sentinel.read_text()=='external controller untouched\n'
    report={'schema':1,'run_id':os.environ['GITHUB_RUN_ID'],'controller':os.environ['GITHUB_SHA'],'image':IMAGE,'checks':results,'host_sentinel_unchanged':True,'runtime_config_verified':True,'network':'none','rootless_runtime':False,'dashboard_e2e':False}
    pathlib.Path('sandbox-preflight-result.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))
if __name__=='__main__':main()
