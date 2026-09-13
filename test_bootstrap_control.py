import os,unittest
from unittest.mock import patch
import bootstrap_control as c
class BootstrapScopeTests(unittest.TestCase):
    def test_lab_cannot_write_fork_refs_or_settings(self):
        for path,method in [('git/refs/heads/main','PATCH'),('git/refs','POST'),('branches/main/protection','PUT'),('contents/x','PUT')]:
            with self.subTest(path=path),patch.object(c.urllib.request,'urlopen') as request,self.assertRaisesRegex(ValueError,'never publish'):
                c.write(path,method,{})
            request.assert_not_called()
    def test_publish_operation_is_forbidden(self):
        with patch.dict(os.environ,{'GITHUB_REPOSITORY':c.LAB,'GITHUB_REF':'refs/heads/lab-controller','MODE':'publish'}),patch.object(c,'verify',return_value={'acceptance_run':{'id':1,'attempt':1}}),patch.object(c,'api',return_value={'protected':True}),patch.object(c,'exact_pr',return_value={}),patch.object(c,'write') as writes,self.assertRaisesRegex(ValueError,'publishing is forbidden'):
            c.main()
        writes.assert_not_called()
if __name__=='__main__':unittest.main()
