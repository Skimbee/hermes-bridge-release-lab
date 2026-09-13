import unittest
from lab import validate
class BindingTests(unittest.TestCase):
    def test_exact_binding_only(self):
        validate('a'*40,'a'*40,'b'*40,['a'*40])
        for args in [('a'*40,'c'*40,'b'*40,['a'*40]),('a'*40,'a'*40,'b'*40,['c'*40]),('a'*40,'a'*40,'a'*40,['a'*40]),('bad','bad','b'*40,['bad'])]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                validate(*args)
if __name__=='__main__': unittest.main()
