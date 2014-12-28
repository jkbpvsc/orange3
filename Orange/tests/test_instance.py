from math import isnan
import warnings
import unittest
from mock import MagicMock

import numpy as np
from numpy.testing import assert_array_equal

from Orange.data import \
    Instance, Domain, Unknown, \
    DiscreteVariable, ContinuousVariable, StringVariable

class TestInstance(unittest.TestCase):
    attributes = ["Feature %i" % i for i in range(10)]
    class_vars = ["Class %i" % i for i in range(1)]
    metas = [DiscreteVariable("Meta 1", values="XYZ"),
             ContinuousVariable("Meta 2"),
             StringVariable("Meta 3")]

    def mock_domain(self, with_classes=False, with_metas=False):
        attributes = self.attributes
        class_vars = self.class_vars if with_classes else []
        metas = self.metas if with_metas else []
        variables = attributes + class_vars
        return MagicMock(Domain,
                         attributes=attributes,
                         class_vars=class_vars,
                         metas=metas,
                         variables=variables)

    def create_domain(self, attributes=(), classes=(), metas=()):
        attr_vars = [ContinuousVariable(name=a) if isinstance(a, str) else a
                     for a in attributes]
        class_vars = [ContinuousVariable(name=c) if isinstance(c, str) else c
                      for c in classes]
        meta_vars = [DiscreteVariable(name=m, values=map(str, range(5)))
                     if isinstance(m, str) else m
                     for m in metas]
        domain = Domain(attr_vars, class_vars, meta_vars)
        return domain

    def test_init_x_no_data(self):
        domain = self.mock_domain()
        inst = Instance(domain)
        self.assertIsInstance(inst, Instance)
        self.assertIs(inst.domain, domain)
        self.assertEqual(inst._values.shape, (len(self.attributes), ))
        self.assertEqual(inst._x.shape, (len(self.attributes), ))
        self.assertEqual(inst._y.shape, (0, ))
        self.assertEqual(inst._metas.shape, (0, ))
        self.assertTrue(all(isnan(x) for x in inst._values))
        self.assertTrue(all(isnan(x) for x in inst._x))

    def test_init_xy_no_data(self):
        domain = self.mock_domain(with_classes=True)
        inst = Instance(domain)
        self.assertIsInstance(inst, Instance)
        self.assertIs(inst.domain, domain)
        self.assertEqual(inst._values.shape,
                         (len(self.attributes) + len(self.class_vars), ))
        self.assertEqual(inst._x.shape, (len(self.attributes), ))
        self.assertEqual(inst._y.shape, (len(self.class_vars), ))
        self.assertEqual(inst._metas.shape, (0, ))
        self.assertTrue(all(isnan(x) for x in inst._values))
        self.assertTrue(all(isnan(x) for x in inst._x))
        self.assertTrue(all(isnan(x) for x in inst._y))

    def test_init_xym_no_data(self):
        domain = self.mock_domain(with_classes=True, with_metas=True)
        inst = Instance(domain)
        self.assertIsInstance(inst, Instance)
        self.assertIs(inst.domain, domain)
        self.assertEqual(inst._values.shape,
                         (len(self.attributes) + len(self.class_vars), ))
        self.assertEqual(inst._x.shape, (len(self.attributes), ))
        self.assertEqual(inst._y.shape, (len(self.class_vars), ))
        self.assertEqual(inst._metas.shape, (3, ))
        self.assertTrue(all(isnan(x) for x in inst._values))
        self.assertTrue(all(isnan(x) for x in inst._x))
        self.assertTrue(all(isnan(x) for x in inst._y))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            assert_array_equal(inst._metas, np.array([Unknown, Unknown, None]))

    def test_init_x_arr(self):
        domain = self.create_domain(["x", DiscreteVariable("g", values="MF")])
        vals = np.array([42, 0])
        inst = Instance(domain, vals)
        assert_array_equal(inst._values, vals)
        assert_array_equal(inst._x, vals)
        self.assertEqual(inst._y.shape, (0, ))
        self.assertEqual(inst._metas.shape, (0, ))

        domain = self.create_domain()
        inst = Instance(domain, np.empty((0,)))
        self.assertEqual(inst._x.shape, (0, ))
        self.assertEqual(inst._y.shape, (0, ))
        self.assertEqual(inst._metas.shape, (0, ))


    def test_init_x_list(self):
        domain = self.create_domain(["x", DiscreteVariable("g", values="MF")])
        lst = [42, 0]
        vals = np.array(lst)
        inst = Instance(domain, vals)
        assert_array_equal(inst._values, vals)
        assert_array_equal(inst._x, vals)
        self.assertEqual(inst._y.shape, (0, ))
        self.assertEqual(inst._metas.shape, (0, ))

        domain = self.create_domain()
        inst = Instance(domain, [])
        self.assertEqual(inst._x.shape, (0, ))
        self.assertEqual(inst._y.shape, (0, ))
        self.assertEqual(inst._metas.shape, (0, ))

    def test_init_xy_arr(self):
        domain = self.create_domain(["x", DiscreteVariable("g", values="MF")],
                                    [DiscreteVariable("y", values="ABC")])
        vals = np.array([42, 0, 1])
        inst = Instance(domain, vals)
        assert_array_equal(inst._values, vals)
        assert_array_equal(inst._x, vals[:2])
        self.assertEqual(inst._y.shape, (1, ))
        self.assertEqual(inst._y[0], 1)
        self.assertEqual(inst._metas.shape, (0, ))

    def test_init_xy_list(self):
        domain = self.create_domain(["x", DiscreteVariable("g", values="MF")],
                                    [DiscreteVariable("y", values="ABC")])
        lst = [42, "M", "C"]
        vals = np.array([42, 0, 2])
        inst = Instance(domain, vals)
        assert_array_equal(inst._values, vals)
        assert_array_equal(inst._x, vals[:2])
        self.assertEqual(inst._y.shape, (1, ))
        self.assertEqual(inst._y[0], 2)
        self.assertEqual(inst._metas.shape, (0, ))

    def test_init_xym_arr(self):
        domain = self.create_domain(["x", DiscreteVariable("g", values="MF")],
                                    [DiscreteVariable("y", values="ABC")],
                                    self.metas)
        vals = np.array([42, "M", "B", "X", 43, "Foo"], dtype=object)
        inst = Instance(domain, vals)
        self.assertIsInstance(inst, Instance)
        self.assertIs(inst.domain, domain)
        self.assertEqual(inst._values.shape, (3, ))
        self.assertEqual(inst._x.shape, (2, ))
        self.assertEqual(inst._y.shape, (1, ))
        self.assertEqual(inst._metas.shape, (3, ))
        assert_array_equal(inst._values, np.array([42, 0, 1]))
        assert_array_equal(inst._x, np.array([42, 0]))
        self.assertEqual(inst._y[0], 1)
        assert_array_equal(inst._metas, np.array([0, 43, "Foo"], dtype=object))

    def test_init_xym_list(self):
        domain = self.create_domain(["x", DiscreteVariable("g", values="MF")],
                                    [DiscreteVariable("y", values="ABC")],
                                    self.metas)
        vals = [42, "M", "B", "X", 43, "Foo"]
        inst = Instance(domain, vals)
        self.assertIsInstance(inst, Instance)
        self.assertIs(inst.domain, domain)
        self.assertEqual(inst._values.shape, (3, ))
        self.assertEqual(inst._x.shape, (2, ))
        self.assertEqual(inst._y.shape, (1, ))
        self.assertEqual(inst._metas.shape, (3, ))
        assert_array_equal(inst._values, np.array([42, 0, 1]))
        assert_array_equal(inst._x, np.array([42, 0]))
        self.assertEqual(inst._y[0], 1)
        assert_array_equal(inst._metas, np.array([0, 43, "Foo"], dtype=object))

    def test_init_inst(self):
        domain = self.create_domain(["x", DiscreteVariable("g", values="MF")],
                                    [DiscreteVariable("y", values="ABC")],
                                    self.metas)
        vals = [42, "M", "B", "X", 43, "Foo"]
        inst = Instance(domain, vals)

        inst2 = Instance(domain, inst)
        assert_array_equal(inst2._values, np.array([42, 0, 1]))
        assert_array_equal(inst2._x, np.array([42, 0]))
        self.assertEqual(inst2._y[0], 1)
        assert_array_equal(inst2._metas, np.array([0, 43, "Foo"], dtype=object))

        domain2 = self.create_domain(["z",
                                      DiscreteVariable.make("g", values="MF"),
                                      self.metas[1]],
                                     [DiscreteVariable.make("y", values="ABC")],
                                     [self.metas[0], "w", domain[0]])
        inst2 = Instance(domain2, inst)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            assert_array_equal(inst2._values, np.array([Unknown, 0, 43, 1]))
            assert_array_equal(inst2._x, np.array([Unknown, 0, 43]))
            self.assertEqual(inst2._y[0], 1)
            assert_array_equal(inst2._metas, np.array([0, Unknown, 42],
                                                      dtype=object))
