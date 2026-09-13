import copy, unittest
from provenance import verify

def fixture():
    c={'repository':'Skimbee/hermes-agent','id':11,'attempt':1,'workflow_id':101,'path':'.github/workflows/bridge-hourly-pilot.yml','controller':'a'*40,'status':'completed','conclusion':'success','event':'workflow_dispatch'}
    d={**c,'id':22,'workflow_id':102,'path':'.github/workflows/bridge-dashboard-e2e.yml'}
    a={'id':33,'run_id':11,'digest':'sha256:'+'b'*64,'expired':False}
    b={'id':44,'run_id':22,'digest':'sha256:'+'c'*64,'expired':False}
    receipt={'candidate':'d'*40,'base':'a'*40,'bundle_sha256':'e'*64,'run_id':11,'attempt':1,'controller':'a'*40}
    result={'schema':2,'candidate_run':c.copy(),'candidate_artifact':a.copy(),'dashboard_run':{k:v for k,v in d.items() if k not in ('status','conclusion')},'candidate':'d'*40,'bundle_sha256':'e'*64,'passed':True,'reconnected':True,'post_head':'d'*40,'pre_head':'f'*40}
    return dict(candidate_run=c,dashboard_run=d,candidate_artifact=a,dashboard_artifact=b,receipt=receipt,result=result,current_main='a'*40,expected_candidate_workflow=101,expected_dashboard_workflow=102,expected_client_base='f'*40)

class ProvenanceTests(unittest.TestCase):
    def test_complete_synthetic_binding(self):
        self.assertEqual(verify(**fixture())['candidate'],'d'*40)
    def test_mismatch_matrix(self):
        mutations=[('candidate_run','repository','wrong/repo'),('candidate_run','attempt',2),('candidate_run','workflow_id',999),('dashboard_run','workflow_id',999),('dashboard_run','attempt',2),('dashboard_run','event','pull_request'),('dashboard_run','status','in_progress'),('dashboard_run','controller','f'*40),('candidate_artifact','id',999),('candidate_artifact','digest','sha256:'+'f'*64),('candidate_artifact','expired',True),('dashboard_artifact','run_id',999),('dashboard_artifact','expired',True),('receipt','bundle_sha256','f'*64),('receipt','base','f'*40),('result','post_head','f'*40),('result','pre_head','a'*40),('result','passed',1),('result','reconnected',False),('result','schema',1)]
        for key,field,value in mutations:
            with self.subTest(key=key,field=field):
                data=fixture();data[key][field]=value
                with self.assertRaises(ValueError):verify(**data)
    def test_stale_main(self):
        data=fixture();data['current_main']='f'*40
        with self.assertRaises(ValueError):verify(**data)
    def test_missing_binding(self):
        data=fixture(); del data['result']['candidate_artifact']
        with self.assertRaises(ValueError):verify(**data)
if __name__=='__main__':unittest.main()
