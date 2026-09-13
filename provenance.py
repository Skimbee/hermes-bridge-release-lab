"""Fail-closed provenance contract. Caller supplies independently fetched metadata.

This module does not authenticate GitHub, verify ZIP bytes, inspect bundles,
or prove process isolation. Those are mandatory separate verifier steps.
Never populate missing result bindings from the API: they must originate in
an authenticated external controller's original evidence.
"""
import re

def require(condition, reason):
    if not condition: raise ValueError(reason)

def verify(*,candidate_run,dashboard_run,candidate_artifact,dashboard_artifact,
           receipt,result,current_main,expected_candidate_workflow,
           expected_dashboard_workflow,expected_client_base):
    try:
        def sha(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{40}',value) is not None
        require(sha(current_main) and sha(expected_client_base),'invalid trusted commit')
        for run,wid,path in [(candidate_run,expected_candidate_workflow,'.github/workflows/bridge-hourly-pilot.yml'),(dashboard_run,expected_dashboard_workflow,'.github/workflows/bridge-dashboard-e2e.yml')]:
            require(run['repository']=='Skimbee/hermes-agent','repository')
            require(type(run['id']) is int and run['id']>0 and type(run['attempt']) is int and run['attempt']>0,'run identity')
            require(type(wid) is int and wid>0 and run['workflow_id']==wid and run['path']==path,'workflow identity')
            require(run['controller']==current_main,'controller or stale base')
            require(run['status']=='completed' and run['conclusion']=='success','run not successful')
        require(candidate_run['event'] in ('schedule','workflow_dispatch'),'candidate event')
        require(dashboard_run['event']=='workflow_dispatch','dashboard event')
        for artifact,run in [(candidate_artifact,candidate_run),(dashboard_artifact,dashboard_run)]:
            require(type(artifact['id']) is int and artifact['id']>0 and artifact['run_id']==run['id'],'artifact identity')
            require(artifact['expired'] is False,'expired artifact')
            require(isinstance(artifact['digest'],str) and re.fullmatch('sha256:[0-9a-f]{64}',artifact['digest']) is not None,'invalid artifact digest')
        require(receipt['base']==current_main and receipt['controller']==current_main,'receipt controller')
        require(receipt['run_id']==candidate_run['id'] and receipt['attempt']==candidate_run['attempt'],'receipt run')
        require(sha(receipt['candidate']) and receipt['candidate']!=current_main,'candidate identity')
        require(isinstance(receipt['bundle_sha256'],str) and re.fullmatch('[0-9a-f]{64}',receipt['bundle_sha256']) is not None,'bundle digest')
        require(type(result['schema']) is int and result['schema']==2,'legacy evidence cannot be promoted')
        require(result['candidate_run']==candidate_run,'candidate run binding')
        require(result['candidate_artifact']==candidate_artifact,'candidate artifact binding')
        # A controller cannot truthfully know its own final GitHub conclusion
        # before emitting its artifact. Bind identity only; final success above
        # must come independently from GitHub after the run completes.
        identity_keys=('repository','id','attempt','workflow_id','path','controller','event')
        require(result['dashboard_run']=={k:dashboard_run[k] for k in identity_keys},'dashboard run binding')
        require(result['candidate']==receipt['candidate'] and result['post_head']==receipt['candidate'],'result candidate')
        require(result['bundle_sha256']==receipt['bundle_sha256'],'result bundle')
        require(result['pre_head']==expected_client_base,'client base')
        require(result['passed'] is True and result['reconnected'] is True,'dashboard failed')
        return {'candidate':receipt['candidate'],'base':current_main,
                'candidate_run':candidate_run,'candidate_artifact':candidate_artifact,
                'dashboard_run':dashboard_run,'dashboard_artifact':dashboard_artifact,
                'provenance_valid':True,'publication_enabled':False}
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError('Missing or malformed provenance') from exc
