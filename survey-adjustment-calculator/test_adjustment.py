"""Independent numeric checks: exact examples, KKT comparisons, covariance propagation."""
import unittest
import numpy as np
from numpy.testing import assert_allclose

from adjustment import AdjustmentError, parse_matrix, solve
from examples import EXAMPLES


def example(key):
    e = EXAMPLES[key]
    return {name: parse_matrix(e[name], name) for name in
            ("A", "B", "w", "l", "C", "d", "observed", "x0", "P") if e.get(name)}


class ExactCases(unittest.TestCase):
    def test_triangle(self):
        r = solve("condition", **example("condition"))
        assert_allclose(r.v, [-4.8, -2.4, -4.8])
        self.assertAlmostEqual(r.adjusted.sum(), 648000)
        self.assertEqual(r.dof, 1)
        self.assertAlmostEqual(r.weighted_sum, 57.6)

    def test_parameter_condition(self):
        r = solve("condition_parameters", **example("condition_parameters"))
        assert_allclose(r.x, [.0025])
        assert_allclose(r.parameters, [100.0025])
        assert_allclose(r.adjusted, [100.0025] * 3)
        assert_allclose(r.qxx, [[.25]])
        self.assertEqual(r.dof, 2)

    def test_level_network(self):
        r = solve("indirect", **example("indirect"))
        assert_allclose(r.parameters, [101.016, 102.014])
        assert_allclose(r.v, [-.004, .004, -.002], atol=1e-14)
        self.assertEqual(r.dof, 1)

    def test_constraint(self):
        r = solve("indirect_constraints", **example("indirect_constraints"))
        assert_allclose(r.x, [1.001, 1.999])
        self.assertAlmostEqual(r.parameters.sum(), 203)
        self.assertAlmostEqual(r.weighted_sum, .00049)
        self.assertEqual(r.dof, 2)
        assert_allclose(np.array([[1, 1]]) @ r.qxx, 0, atol=1e-14)

    def test_rank_deficiency_resolved_by_constraint(self):
        r = solve("indirect_constraints", B=[[1,-1],[1,-1]], l=[2,2.2], C=[[1,1]], d=[0])
        assert_allclose(r.x, [1.05,-1.05])
        assert_allclose(r.qxx, [[.125,-.125],[-.125,.125]])
        self.assertEqual(r.dof, 1)

    def test_no_redundancy(self):
        r = solve("indirect", B=np.eye(2), l=[2,3])
        self.assertEqual(r.dof, 0)
        self.assertIsNone(r.posterior_sigma)
        self.assertIsNone(r.std(r.qxx))
        assert_allclose(r.v, 0)

    def test_prior_with_no_redundancy(self):
        r = solve("indirect", B=np.eye(2), l=[2,3], precision="prior", sigma0=2)
        assert_allclose(r.std(r.qxx), [2,2])

    def test_condition_parameters_no_redundancy(self):
        r = solve("condition_parameters", A=np.eye(2), B=np.eye(2), w=[1,2])
        assert_allclose(r.v, 0)
        assert_allclose(r.x, [-1,-2])
        assert_allclose(r.qxx, np.eye(2))
        self.assertEqual(r.dof, 0)

    def test_fully_constrained(self):
        r = solve("indirect_constraints", B=np.eye(2), l=[1,2], C=np.eye(2), d=[-3,-4])
        assert_allclose(r.x, [3,4])
        assert_allclose(r.qxx, 0)
        assert_allclose(r.qvv, np.eye(2))
        self.assertEqual(r.dof, 2)

    def test_condition_singular_A_but_joint_model_unique(self):
        r = solve("condition_parameters", A=[[1,0],[0,0]], B=[[0],[1]], w=[2,3])
        assert_allclose(r.v, [-2,0])
        assert_allclose(r.x, [-3])
        assert_allclose(r.qxx, 0)

    def test_scaled_weights_keep_posterior_precision(self):
        args = example("indirect")
        a = solve("indirect", **args)
        args["P"] *= 100
        b = solve("indirect", **args)
        assert_allclose(a.x, b.x)
        assert_allclose(a.std(a.qxx), b.std(b.qxx))
        self.assertAlmostEqual(b.posterior_sigma, 10*a.posterior_sigma)

    def test_missing_observations_not_fabricated(self):
        r = solve("indirect", B=[[1],[1]], l=[1,2])
        self.assertIsNone(r.adjusted)
        self.assertIsNone(r.parameters)


class IndependentComparisons(unittest.TestCase):
    def test_random_condition_against_full_kkt(self):
        for seed in range(15):
            with self.subTest(seed=seed):
                rng = np.random.default_rng(seed)
                n, r, t = 6, 5, 2
                A, B, w = rng.normal(size=(r,n)), rng.normal(size=(r,t)), rng.normal(size=r)
                G = rng.normal(size=(n,n))
                P = G.T@G + np.eye(n)
                H = np.zeros((n+t,n+t))
                H[:n,:n] = P
                D = np.column_stack([A, B])
                K = np.block([[H,D.T],[D,np.zeros((r,r))]])
                expected = np.linalg.solve(K, np.r_[np.zeros(n+t), -w])
                result = solve("condition_parameters", A=A, B=B, w=w, P=P)
                assert_allclose(result.v, expected[:n], atol=1e-10)
                assert_allclose(result.x, expected[n:n+t], atol=1e-10)

    def test_random_indirect_against_full_kkt(self):
        for seed in range(15):
            with self.subTest(seed=seed):
                rng = np.random.default_rng(seed+20)
                n,t,c = 7,4,2
                B,C,l,d = rng.normal(size=(n,t)),rng.normal(size=(c,t)),rng.normal(size=n),rng.normal(size=c)
                G = rng.normal(size=(n,n)); P = G.T@G + np.eye(n)
                K = np.block([[B.T@P@B,C.T],[C,np.zeros((c,c))]])
                expected = np.linalg.solve(K, np.r_[B.T@P@l,-d])[:t]
                r = solve("indirect_constraints", B=B,l=l,C=C,d=d,P=P)
                assert_allclose(r.x, expected, atol=1e-10)
                assert_allclose(C@r.x+d, 0, atol=1e-10)

    def test_covariances_via_independent_finite_differences(self):
        rng = np.random.default_rng(904)
        for model in EXAMPLES:
            with self.subTest(model=model):
                args = example(model)
                n = args["A"].shape[1] if model.startswith("condition") else args["B"].shape[0]
                G = rng.normal(size=(n,n)); args["P"] = G.T@G+np.eye(n)
                r = solve(model, **args)
                H_v, H_x = [], []
                eps = 1e-5
                for j in range(n):
                    shifted = dict(args)
                    delta = np.eye(n)[j]*eps
                    if model.startswith("condition"):
                        shifted["w"] = args["w"].reshape(-1) + args["A"]@delta
                    else:
                        shifted["l"] = args["l"].reshape(-1) + delta
                    s = solve(model, **shifted)
                    H_v.append((s.v-r.v)/eps)
                    if r.x is not None:
                        H_x.append((s.x-r.x)/eps)
                Hv = np.array(H_v).T
                Hhat = np.eye(n) + Hv
                assert_allclose(r.qvv, Hv@r.qll@Hv.T, atol=1e-8)
                assert_allclose(r.q_adjusted, Hhat@r.qll@Hhat.T, atol=1e-8)
                assert_allclose(r.qvv+r.q_adjusted, r.qll, atol=1e-10)
                if H_x:
                    Hx = np.array(H_x).T
                    assert_allclose(r.qxx, Hx@r.qll@Hx.T, atol=1e-8)
                for Q in (r.qvv,r.q_adjusted):
                    self.assertGreaterEqual(np.linalg.eigvalsh(Q).min(), -1e-10)


class InputValidation(unittest.TestCase):
    def test_excel_and_scientific_notation(self):
        assert_allclose(parse_matrix("1\t2e-3\n3 4 # comment"), [[1,.002],[3,4]])

    def test_brackets_unicode_separators(self):
        assert_allclose(parse_matrix("[[1，2], [3，−4]]"), [[1,2],[3,-4]])

    def test_row_vector_accepted(self):
        r = solve("indirect", B=[[1],[1]], l=[[1,3]])
        assert_allclose(r.x, [2])

    def test_reject_invalid_numbers_and_shapes(self):
        for text in ("1, ,2", "1,2,", "1 2\n3", "nan", "inf", "1/3", "__import__('os')", ""):
            with self.subTest(text=text), self.assertRaises(AdjustmentError):
                parse_matrix(text)

    def test_invalid_weights(self):
        for P in ([1,0], [1,-1], [[1,2],[2,1]], [[1,1],[0,1]], [1,2,3]):
            with self.subTest(P=P), self.assertRaises(AdjustmentError):
                solve("indirect", B=[[1],[1]], l=[1,2], P=P)

    def test_rank_deficient_indirect_rejected(self):
        with self.assertRaisesRegex(AdjustmentError, "列秩不足"):
            solve("indirect", B=[[1,1],[2,2]], l=[1,2])

    def test_dependent_condition_rejected(self):
        with self.assertRaisesRegex(AdjustmentError, "不独立"):
            solve("condition", A=[[1,1],[2,2]], w=[1,2])

    def test_parameter_condition_rank_rejected(self):
        with self.assertRaises(AdjustmentError):
            solve("condition_parameters", A=np.eye(2), B=[[1,1],[1,1]], w=[1,2])

    def test_duplicate_constraints_rejected(self):
        with self.assertRaisesRegex(AdjustmentError, "不独立"):
            solve("indirect_constraints", B=np.eye(2), l=[1,2], C=[[1,1],[2,2]], d=[0,1])

    def test_dimension_errors(self):
        for kwargs in (dict(B=[[1],[1]],l=[1]), dict(B=[[1],[1]],l=[1,2],observed=[1]),
                       dict(B=[[1],[1]],l=[1,2],x0=[1,2])):
            with self.subTest(kwargs=kwargs), self.assertRaises(AdjustmentError):
                solve("indirect", **kwargs)

    def test_sigma_must_be_positive(self):
        for sigma in (0,-1,float("nan"),"bad"):
            with self.subTest(sigma=sigma), self.assertRaises(AdjustmentError):
                solve("indirect", B=[[1],[1]], l=[1,2], sigma0=sigma)


if __name__ == "__main__":
    unittest.main(verbosity=2)
