import json
from math import exp, sqrt
from pathlib import Path
import unittest

import numpy as np

from adjustment import AdjustmentError, solve
from desktop import Api
from theory import experiment


def metrics(result):
    return {m['label']: m['value'] for m in result['metrics']}


class TheoryTests(unittest.TestCase):
    def test_normal_reference_probabilities(self):
        for k, expected in [(1, .682689492137086), (2, .954499736103642), (3, .997300203936740)]:
            self.assertAlmostEqual(metrics(experiment('normal', {'k': k}))['区间内概率']/100, expected, 14)

    def test_correlated_sum_difference(self):
        for b, variance in [(1, 37), (-1, 13)]:
            result = metrics(experiment('propagation', {'s1': 3, 's2': 4, 'rho': .5, 'b': b}))
            self.assertAlmostEqual(result['输出标准差'], sqrt(variance))
        self.assertEqual(metrics(experiment('propagation', {'s1': 3, 's2': 3, 'rho': 1, 'b': -1}))['输出方差'], 0)

    def test_weighted_mean_matches_existing_adjustment_engine(self):
        result = solve('indirect', B=np.ones((3, 1)), l=np.array([10., 12., 9.]),
                       P=np.diag([1., .25, 1.]), observed=np.array([10., 12., 9.]))
        lesson = experiment('weighted-mean', {})
        values = metrics(lesson)
        self.assertAlmostEqual(values['加权平均值'], 88/9)
        self.assertAlmostEqual(values['先验均值标准差'], 2/3)
        self.assertAlmostEqual(values['vᵀPv'], 17/9)
        self.assertAlmostEqual(values['加权平均值'], result.x[0])
        np.testing.assert_allclose(lesson['plot']['residuals'], result.v, atol=1e-13)

    def test_ellipse_hand_eigenvalues_and_direction(self):
        result = experiment('ellipse', {'sx': 2, 'sy': 2, 'rho': .375, 'coverage': 'standard'})
        self.assertAlmostEqual(result['plot']['major'], sqrt(5.5))
        self.assertAlmostEqual(result['plot']['minor'], sqrt(2.5))
        self.assertAlmostEqual(result['plot']['azimuth'], 45)
        self.assertAlmostEqual(metrics(result)['联合覆盖率'], 100*(1-exp(-.5)))

    def test_known_covariance_confidence_factor(self):
        result = metrics(experiment('ellipse', {'coverage': '95'}))
        self.assertAlmostEqual(result['半轴倍率 k'], sqrt(-2*np.log(.05)), 13)

    def test_posterior_ellipse_uses_f_not_chi_square(self):
        result = metrics(experiment('ellipse', {'source': 'posterior', 'dof': 10, 'coverage': '95'}))
        # F(2,f) has CDF 1-(f/(f+2x))**(f/2); invert analytically.
        expected = sqrt(10*(.05**(-2/10)-1))
        self.assertAlmostEqual(result['半轴倍率 k'], expected, 12)
        standard = metrics(experiment('ellipse', {'source': 'posterior', 'dof': 10, 'coverage': 'standard'}))
        self.assertAlmostEqual(standard['联合覆盖率'], 100*(1-(10/11)**5))
        self.assertNotAlmostEqual(standard['联合覆盖率'], 100*(1-exp(-.5)), 3)
        self.assertAlmostEqual(metrics(experiment('ellipse', {'source': 'prior', 'dof': ''}))['半轴倍率 k'],
                               sqrt(-2*np.log(.05)))

    def test_circle_has_no_unique_axis(self):
        result = experiment('ellipse', {'sx': 2, 'sy': 2, 'rho': 0})
        self.assertIsNone(result['plot']['azimuth'])
        self.assertNotIn('长轴方位角', metrics(result))

    def test_chi_square_two_dof_closed_form(self):
        result = experiment('global-test', {'omega': 8, 'dof': 2, 'sigma0': 2, 'alpha': .05})
        values = metrics(result)
        self.assertAlmostEqual(values['检验统计量 T'], 2)
        self.assertAlmostEqual(values['区间下限'], -2*np.log(.975))
        self.assertAlmostEqual(values['区间上限'], -2*np.log(.025))
        self.assertAlmostEqual(values['双侧 p 值'], 2*exp(-1))
        self.assertFalse(result['plot']['rejected'])
        self.assertTrue(experiment('global-test', {'omega': 1000})['plot']['rejected'])

    def test_invalid_input_is_rejected(self):
        cases = [('normal', {'k': ''}), ('normal', {'k': float('nan')}),
                 ('normal', {'k': True}), ('propagation', {'rho': 1.01}),
                 ('propagation', {'b': .5}), ('weighted-mean', {'s1': 0}),
                 ('ellipse', {'rho': 1}), ('ellipse', {'source': 'bad'}),
                 ('ellipse', {'coverage': 1}), ('global-test', {'dof': 1.5}),
                 ('global-test', {'sigma0': 0}), ('unknown', {})]
        for kind, inputs in cases:
            with self.subTest(kind=kind, inputs=inputs), self.assertRaises(AdjustmentError):
                experiment(kind, inputs)

    def test_rpc_json_boundary(self):
        api = Api()
        for kind in ['normal', 'propagation', 'ellipse', 'global-test', 'weighted-mean']:
            reply = api.rpc('theory_experiment', {'kind': kind, 'inputs': {}})
            self.assertTrue(reply['ok'], reply)
            json.dumps(reply, allow_nan=False)
        self.assertFalse(api.rpc('theory_experiment', {'kind': 'ellipse', 'inputs': {'rho': 1}})['ok'])

    def test_knowledge_cross_references_and_coverage(self):
        doc = json.loads((Path(__file__).parent/'frontend/src/knowledge.json').read_text(encoding='utf-8'))
        articles = {a['id']: a for a in doc['articles']}
        sources = {s['id'] for s in doc['sources']}
        self.assertEqual(len(doc['chapters']), 6)
        self.assertEqual(len(articles), 13)
        for c in doc['chapters']:
            for key in c['articles']: self.assertEqual(articles[key]['chapter'], c['id'])
        for a in articles.values():
            self.assertTrue(all(key in articles for key in a['related']))
            self.assertTrue(set(a['sources']) <= sources)
            self.assertTrue(0 <= a['quiz']['answer'] < len(a['quiz']['options']))
        self.assertIn('39.35', json.dumps(articles['confidence'], ensure_ascii=False))
        self.assertIn('Holm', json.dumps(articles['diagnostics'], ensure_ascii=False))


if __name__ == '__main__':
    unittest.main()
