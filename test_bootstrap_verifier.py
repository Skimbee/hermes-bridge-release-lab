import copy,unittest
import bootstrap_verifier as v
from bootstrap_support import M
class BootstrapEvidenceTests(unittest.TestCase):
    def fixture(self):
        run={'repository':{'full_name':v.LAB},'id':1,'run_attempt':1,'workflow_id':99,'path':v.PATH,'head_sha':'a'*40,'head_branch':'lab-controller','event':'workflow_dispatch','status':'completed','conclusion':'success'}
        policy={'acceptance_run':1,'acceptance_controller':'a'*40,'workflow_id':99,'manifest_sha256':v.manifest_hash()}
        ca={'id':2,'digest':'sha256:'+'b'*64,'expired':False}
        snapshot={'post_head':M['candidate'],'tracked_files_verified':1,'tracked_tree_matches':True,'candidate_stopped':True}
        receipt={'schema':'bootstrap-1','purpose':'reviewed-control-and-runtime-bootstrap','repository':M['repository'],'base':M['base'],'candidate':M['candidate'],'tree':M['tree'],'upstream':M['upstream'],'source_run':v.identity(run),'source_job':'candidate','manifest_sha256':policy['manifest_sha256'],'bundle_sha256':'c'*64,'tests_process_exit':0,'sdk_version_asserted':'0.9.2','snapshot':snapshot}
        b={'schema':'bootstrap-e2e-1','purpose':receipt['purpose'],'manifest_sha256':policy['manifest_sha256'],'candidate_run':v.identity(run),'candidate_job':{'name':'candidate','status':'completed','conclusion':'success'},'candidate_artifact':{'id':2,'run_id':1,'digest':ca['digest'],'expired':False},'candidate':M['candidate'],'bundle_sha256':receipt['bundle_sha256'],'pre_head':M['client_base'],'publication_enabled':False,'dashboard_identity':v.identity(run)}
        result={**b,**snapshot,'passed':True,'reconnected':True,'dashboard_run':v.identity(run),'browser_sandbox_requested':True,'browser_sandbox_status':'PID namespaces Yes Seccomp-BPF sandbox Yes','observed_receipt':{'pre_sha':M['client_base'],'post_sha':M['candidate'],'outcome':'success'}}
        return [run,ca,receipt,b,result,policy]
    def test_complete_original_fresh_bootstrap_bindings(self):v.validate(*self.fixture())
    def test_mutation_matrix(self):
        for index,key,value in [(0,'conclusion','failure'),(0,'head_sha','f'*40),(0,'run_attempt',2),(0,'path','old.yml'),(1,'id',3),(1,'expired',True),(2,'candidate','f'*40),(2,'tests_process_exit',1),(2,'schema',1),(3,'schema',2),(4,'passed',False),(4,'candidate_stopped',False),(4,'post_head','f'*40),(4,'browser_sandbox_requested',False)]:
            values=copy.deepcopy(self.fixture());values[index][key]=value
            with self.subTest(index=index,key=key),self.assertRaises(ValueError):v.validate(*values)
if __name__=='__main__':unittest.main()
