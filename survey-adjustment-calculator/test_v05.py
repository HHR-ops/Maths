"""Numerical and file-boundary verification for the v0.5 workflows."""
import base64
from copy import deepcopy
import io
import json
import math
import unittest

import numpy as np
from openpyxl import Workbook

from adjustment import solve, AdjustmentError
from bulk_import import read_tables, preview_import, template
from calculation_steps import matrix_steps, network_steps
from desktop import Api
from diagnostics import diagnose, holm
from examples import EXAMPLES
from network import Network, FAMILIES, MODEL_NAMES, adjust_network, example_network, ARCSEC


def csv_table(text, name='test.csv'):
    return read_tables(name, base64.b64encode(text.encode('utf-8-sig')).decode())['tables'][0]


def repeated_height():
    net = Network()
    net.add_point('A', H=100, fixed=['H']); net.add_point('B', H=100)
    for i in range(10): net.add_observation('height', ['A', 'B'], 1.010 if i == 9 else 1., sigma=.001)
    return net


class DiagnosticTests(unittest.TestCase):
    def test_holm_known_adjusted_probabilities_and_missing_residual(self):
        self.assertEqual(holm([.01, .04, .03, None]), [.03, .06, .06, None])

    def test_single_blunder_is_identified_and_recalculation_changes_result(self):
        net = repeated_height(); sol = adjust_network(net, design=False)
        data = diagnose(sol.result, labels=sol.model.labels, groups=sol.model.groups)
        self.assertEqual(data['flagged_observations'], ['O10'])
        self.assertAlmostEqual(sol.points['B']['H'], 101.001, places=10)
        self.assertAlmostEqual(data['rows'][-1]['standardized'], -math.sqrt(90), places=8)
        self.assertTrue(data['global_test']['rejected'])
        net.observations[-1]['enabled'] = False
        after = adjust_network(net, design=False)
        clean = diagnose(after.result, labels=after.model.labels, groups=after.model.groups)
        self.assertAlmostEqual(after.points['B']['H'], 101., places=10)
        self.assertEqual(clean['flagged_observations'], [])
        self.assertEqual(after.model.stats['n'], 9)

    def test_posterior_scale_does_not_mask_a_blunder(self):
        net = repeated_height()
        prior = adjust_network(net, design=False, precision='prior')
        posterior = adjust_network(net, design=False, precision='posterior')
        a = diagnose(prior.result); b = diagnose(posterior.result)
        self.assertEqual(a['rows'], b['rows'])
        self.assertEqual(a['global_test'], b['global_test'])

    def test_chi_square_known_df_one_quantiles(self):
        r = solve('condition', A=[[1, 1]], w=[1], precision='prior')
        g = diagnose(r)['global_test']
        self.assertAlmostEqual(g['lower'], .000982069117175, places=12)
        self.assertAlmostEqual(g['upper'], 5.023886187314888, places=10)

    def test_correlated_gnss_joint_test_matches_analytic_quadratic_form(self):
        net = Network('GNSS网'); net.add_point('A', fixed=['X', 'Y', 'Z']); net.add_point('B', X=10, Y=20, Z=3)
        cov = np.array([[4, 1, .2], [1, 9, .4], [.2, .4, 16]])*1e-6
        error = np.array([.02, -.015, .01]); exact = np.array([10., 20., 3.])
        net.add_observation('gnss', ['A', 'B'], exact.tolist(), covariance=cov.tolist())
        net.add_observation('gnss', ['A', 'B'], (exact+error).tolist(), covariance=cov.tolist())
        sol = adjust_network(net, design=False)
        data = diagnose(sol.result, groups=sol.model.groups)
        expected = float(error@np.linalg.solve(cov, error)/2)
        for group in data['groups']:
            self.assertEqual(group['rank'], 3)
            self.assertTrue(group['correlated'])
            self.assertAlmostEqual(group['statistic'], expected, places=7)

    def test_statistics_invariant_under_units_and_angular_rows_display_arcseconds(self):
        args = dict(A=[[1, 1, 1]], w=[12], P=[1, 2, 1], precision='prior')
        original = solve('condition', **args)
        scaled = solve('condition', A=args['A'], w=np.asarray(args['w'])*ARCSEC, P=np.asarray(args['P'])/ARCSEC**2, precision='prior')
        a = diagnose(original); b = diagnose(scaled, angular=[True]*3)
        np.testing.assert_allclose([r['standardized'] for r in a['rows']], [r['standardized'] for r in b['rows']], rtol=1e-12)
        np.testing.assert_allclose([r['display_residual'] for r in b['rows']], [-4.8, -2.4, -4.8])
        self.assertTrue(all(r['unit'] == '″' for r in b['rows']))

    def test_zero_redundancy_design_and_unobservable_residual(self):
        r = solve('indirect', B=[[1]], l=[1], precision='prior')
        self.assertFalse(diagnose(r)['available'])
        self.assertFalse(diagnose(r, design=True)['available'])
        r = solve('indirect', B=[[1], [0]], l=[1, .1], precision='prior')
        d = diagnose(r)
        self.assertFalse(d['rows'][0]['testable'])
        self.assertIsNone(d['rows'][0]['p_adjusted'])
        self.assertTrue(d['rows'][1]['testable'])
        with self.assertRaises(AdjustmentError): diagnose(r, alpha=0)


class ImportTests(unittest.TestCase):
    def test_all_seven_xlsx_templates_roundtrip_and_adjust(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                file = template(family)
                tables = read_tables(file['filename'], file['content_base64'])['tables']
                old = example_network(family).to_dict(); before = deepcopy(old)
                preview = preview_import(old, tables, policy='replace')
                self.assertTrue(preview['ok'], preview['errors'])
                self.assertEqual(old, before)
                self.assertEqual(preview['added_points'], 4)
                self.assertEqual(preview['warnings'], [])
                result = adjust_network(Network.from_dict(preview['project']), design=False)
                self.assertEqual(result.model.stats['defect'], 0)

    def test_points_and_observations_csv_are_order_independent(self):
        pointfile, obsfile = template('GNSS网', 'points'), template('GNSS网', 'observations')
        tables = read_tables(obsfile['filename'], obsfile['content_base64'])['tables']+read_tables(pointfile['filename'], pointfile['content_base64'])['tables']
        data = preview_import(Network('GNSS网').to_dict(), tables)
        self.assertTrue(data['ok'], data['errors'])
        self.assertEqual(data['statistics']['n'], 15)
        self.assertIsNotNone(data['project']['observations'][0]['covariance'])

    def test_custom_mapping_units_and_boolean_fixed_fields(self):
        table = csv_table('标识,高(mm),已知\nA,100000,是\nB,101200,否\n')
        table.update(type='points', mapping={'name': 0, 'H': 1, 'fixed': 2})
        data = preview_import(Network().to_dict(), [table])
        self.assertTrue(data['ok'], data['errors'])
        self.assertAlmostEqual(data['project']['points']['A']['H'], 100.)
        self.assertEqual(data['project']['points']['A']['fixed'], ['H'])

    def test_angle_dms_and_sigma_units_convert_consistently(self):
        project = example_network('边角网').to_dict(); project['observations'] = []
        table = csv_table('编号,类型,起点,终点,观测值,标准差,标准差单位\nTEST,方位角,A,C,30:00:00,0.001,deg\n')
        data = preview_import(project, [table])
        self.assertTrue(data['ok'], data['errors'])
        obs = data['project']['observations'][0]
        self.assertAlmostEqual(obs['value'], 30.)
        self.assertEqual(obs['sigma'], [3.6])

    def test_gnss_six_covariance_fields_and_component_sigmas(self):
        project = example_network('GNSS网').to_dict(); project['observations'] = []
        table = csv_table('编号,类型,起点,终点,DX(mm),DY(mm),DZ(mm),σX(mm),σY(mm),σZ(mm)\nT,GNSS基线,A,B,1000,2000,3000,2,3,4\n')
        data = preview_import(project, [table])
        self.assertTrue(data['ok'], data['errors'])
        obs = data['project']['observations'][0]
        self.assertEqual(obs['value'], [1., 2., 3.])
        self.assertEqual(obs['sigma'], [.002, .003, .004])
        table = csv_table('编号,类型,起点,终点,DX,DY,DZ,Cxx,Cxy,Cxz,Cyy,Cyz,Czz,协方差单位\nT,gnss,A,B,1,2,3,4,1,0,9,0,16,mm2\n')
        data = preview_import(project, [table])
        self.assertTrue(data['ok'], data['errors'])
        np.testing.assert_allclose(data['project']['observations'][0]['covariance'], np.array([[4,1,0],[1,9,0],[0,0,16]])*1e-6)

    def test_duplicate_points_unknown_points_and_bad_covariances_are_atomic(self):
        project = example_network().to_dict(); original = deepcopy(project)
        table = csv_table('点号,H\nNEW,123\nA,999\n')
        data = preview_import(project, [table])
        self.assertFalse(data['ok']); self.assertIsNone(data['project']); self.assertEqual(project, original)
        self.assertEqual(data['errors'][0]['row'], 3)
        table = csv_table('编号,类型,起点,终点,观测值,标准差\nTEST,高差,A,MISSING,1,0.001\n')
        self.assertFalse(preview_import(project, [table])['ok'])
        gnss = example_network('GNSS网').to_dict(); gnss['observations'] = []
        table = csv_table('编号,类型,起点,终点,DX,DY,DZ,Cxx,Cyy,Czz\nT,gnss,A,B,1,2,3,-1,1,1\n')
        self.assertFalse(preview_import(gnss, [table])['ok'])

    def test_formula_invalid_format_encoding_and_size_boundaries(self):
        book = Workbook(); sheet = book.active; sheet.append(['点号', 'H']); sheet.append(['A', '=100+1'])
        stream = io.BytesIO(); book.save(stream)
        tables = read_tables('formula.xlsx', base64.b64encode(stream.getvalue()).decode())['tables']
        self.assertFalse(preview_import(Network().to_dict(), tables)['ok'])
        for name, content in [('old.xls', 'AAAA'), ('bad.xlsx', 'AAAA'), ('bad.csv', '!')]:
            with self.subTest(name=name), self.assertRaises(AdjustmentError): read_tables(name, content)
        encoded = base64.b64encode('点号\tH\nA\t100\n'.encode('utf-16')).decode()
        self.assertEqual(read_tables('utf16.tsv', encoded)['tables'][0]['rows'][0][0], 'A')
        with self.assertRaises(AdjustmentError): read_tables('large.csv', base64.b64encode(b'a'*(4*1024*1024+1)).decode())


class StepTests(unittest.TestCase):
    def test_all_four_manual_models_have_solvable_normal_equations(self):
        api = Api()
        for method, example in EXAMPLES.items():
            with self.subTest(method=method):
                response = api.rpc('matrix_solve', {'model': method, 'data': example})
                self.assertTrue(response['ok'], response)
                out = response['data']; self.assertEqual(len(out['steps']), 5)
                normal = out['steps'][2]
                matrices = normal['matrices']
                if method == 'condition':
                    k = np.linalg.solve(matrices['S = A Q Aᵀ']['data'], matrices['−w']['data'])
                    v = np.asarray(out['details']['Q = P⁻¹'])@np.asarray(out['details']['A']).T@k
                    np.testing.assert_allclose(v, out['v'], atol=1e-12)
                elif method == 'condition_parameters':
                    answer = np.linalg.solve(matrices['增广系数 [S B; Bᵀ 0]']['data'], matrices['右端项 [−w; 0]']['data'])
                    np.testing.assert_allclose(answer[-len(out['x']):], out['x'], atol=1e-12)
                elif method == 'indirect':
                    np.testing.assert_allclose(np.linalg.solve(matrices['N = Bᵀ P B']['data'], matrices['u = Bᵀ P l']['data']), out['x'], atol=1e-12)
                else:
                    answer = np.linalg.solve(matrices['增广系数 [N Cᵀ; C 0]']['data'], matrices['右端项 [u; −d]']['data'])
                    np.testing.assert_allclose(answer[:len(out['x'])], out['x'], atol=1e-12)

    def test_network_steps_preserve_geometry_labels_and_iteration_history(self):
        for family in FAMILIES:
            net = example_network(family, measured=True)
            sol = adjust_network(net, design=False)
            steps = network_steps(net, sol)
            self.assertEqual(len(steps), 7)
            self.assertEqual(len(steps[5]['iterations']), sol.iterations)
            self.assertEqual(steps[1]['matrices']['B₀ · 初始观测系数']['rows'][0]['id'], 'O1')
            np.testing.assert_allclose(steps[5]['matrices']['ΔX · 坐标总改正数']['data'], sol.corrections)
            self.assertLess(sol.iteration_trace[-1]['max_correction'], 1e-8)

    def test_four_method_comparison_uses_the_same_constraints(self):
        net = repeated_height(); net.constraints = [{'terms': {'B.H': 1}, 'value': 101.001}]
        result = Api().rpc('compare_methods', {'project': net.to_dict(), 'design': False})
        self.assertTrue(result['ok'], result)
        for row in result['data']['results']:
            self.assertLess(row['max_coordinate_difference'], 1e-8)
            self.assertLess(row['max_residual_difference'], 1e-8)


if __name__ == '__main__': unittest.main()
