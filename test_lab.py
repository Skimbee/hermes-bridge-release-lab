import unittest
from lab import validate
class BindingTests(unittest.TestCase):
    def test_exact_binding_only(self):
        validate('a'*40,'a'*40,'b'*40,['a'*40])
        for args in [('a'*40,'c'*40,'b'*40,['a'*40]),('a'*40,'a'*40,'b'*40,['c'*40]),('a'*40,'a'*40,'a'*40,['a'*40]),('bad','bad','b'*40,['bad'])]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                validate(*args)
    def test_merge_binding(self):
        validate('a'*40,'a'*40,'b'*40,['a'*40,'c'*40])
        for parents in ([],['c'*40,'a'*40],['a'*40,'a'*40],['a'*40,'bad'],['a'*40,'c'*40,'d'*40]):
            with self.subTest(parents=parents), self.assertRaises(ValueError):
                validate('a'*40,'a'*40,'b'*40,parents)
if __name__=='__main__': unittest.main()
