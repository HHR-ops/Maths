"""Verify the new JSON/HTTP boundary, including real solver round trips."""
import json
import re
import tempfile
import unittest
import urllib.error
import urllib.request

import numpy as np

from desktop import Api, start_server
from examples import EXAMPLES
from network import example_network
from pathlib import Path


class DesktopBoundaryTests(unittest.TestCase):
    def setUp(self): self.api = Api()

    def test_correlated_gnss_json_round_trip(self):
        project = example_network('GNSS网', measured=True).to_dict()
        response = self.api.rpc('solve', {'project': project, 'design': False, 'precision': 'posterior'})
        self.assertTrue(response['ok'], response)
        out = json.loads(json.dumps(response, allow_nan=False))['data']
        self.assertEqual(out['statistics']['n'], 15)
        self.assertGreater(out['result']['qxx'][0][1], 0)
        self.assertTrue(all('m3D' in p for p in out['point_precision']))
        np.testing.assert_allclose(np.asarray(out['matrices']['N = Bᵀ P B']),
                                   np.asarray(out['matrices']['B · 观测方程系数']).T @ np.asarray(out['matrices']['P · 权阵']) @ np.asarray(out['matrices']['B · 观测方程系数']))

    def test_no_shared_calculation_state(self):
        first = example_network('水准网').to_dict()
        second = example_network('GNSS网').to_dict()
        a = self.api.rpc('analyze', {'project': first})
        b = self.api.rpc('analyze', {'project': second})
        c = self.api.rpc('analyze', {'project': first})
        self.assertEqual(a, c)
        self.assertEqual(b['data']['statistics']['parameters'], 9)

    def test_empty_design_remains_editable(self):
        project = example_network().to_dict()
        project['points'] = {}; project['observations'] = []
        self.assertTrue(self.api.rpc('analyze', {'project': project})['ok'])
        self.assertFalse(self.api.rpc('solve', {'project': project})['ok'])

    def test_missing_measurements_and_invalid_covariance_are_actionable(self):
        project = example_network('GNSS网').to_dict()
        missing = self.api.rpc('solve', {'project': project, 'design': False})
        self.assertFalse(missing['ok'])
        self.assertIn('观测', missing['error'])
        project['observations'][0]['covariance'][0][0] = -1
        bad = self.api.rpc('validate', {'project': project})
        self.assertFalse(bad['ok'])
        self.assertIn('正定', bad['error'])

    def test_matrix_output_contains_precision_and_old_example(self):
        result = self.api.rpc('matrix_solve', {'model': 'indirect', 'data': EXAMPLES['indirect']})
        self.assertTrue(result['ok'], result)
        np.testing.assert_allclose(result['data']['parameters'], [101.016, 102.014])
        self.assertEqual(len(result['data']['std_x']), 2)
        self.assertIn('report', result['data'])

    def test_unsafe_matrix_and_unknown_file_rejected(self):
        self.assertFalse(self.api.rpc('validate', {'project': {'format': 'survey-network-result'}})['ok'])
        data = dict(EXAMPLES['condition'], A="__import__('os')")
        self.assertFalse(self.api.rpc('matrix_solve', {'model': 'condition', 'data': data})['ok'])

    def test_constraint_edits_validate_before_returning_project(self):
        project = example_network().to_dict()
        valid = self.api.rpc('constraints', {'project': project, 'text': 'B.H:1 C.H:1 = 203.2'})
        self.assertTrue(valid['ok'], valid)
        self.assertEqual(len(project['constraints']), 0)
        bad = self.api.rpc('constraints', {'project': project, 'text': 'missing.H:1 = 2'})
        self.assertFalse(bad['ok'])

    def test_extraction_preserves_limits_initial_coordinates_and_measurements(self):
        project = example_network('水准网', measured=True).to_dict()
        project['constraints'] = [{'terms': {'B.H': 1, 'C.H': 1}, 'value': 203.2}]
        extracted = self.api.rpc('extract', {'project': project, 'design': False, 'precision': 'prior'})
        self.assertTrue(extracted['ok'], extracted)
        doc = extracted['data']
        self.assertEqual(doc['model'], 'indirect_constraints')
        result = self.api.rpc('matrix_solve', {'model': doc['model'], 'data': doc['data']})
        self.assertTrue(result['ok'], result)
        np.testing.assert_allclose(sum(result['data']['parameters'][:2]), 203.2, atol=1e-10)
        self.assertTrue(doc['data']['observed'])
        incomplete = example_network().to_dict()
        self.assertFalse(self.api.rpc('extract', {'project': incomplete, 'design': False})['ok'])
        preview = self.api.rpc('analyze', {'project': incomplete, 'design': False})['data']
        self.assertEqual(len(preview['missing_observations']), 5)
        self.assertNotIn('l · 常数项', preview['matrices'])

    def test_draft_persistence_is_atomic_and_rejects_older_updates(self):
        task_tmp = Path(__file__).parent/'.tmp'
        task_tmp.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=task_tmp) as folder:
            api = Api(folder)
            workspace = {'project': example_network().to_dict(), 'drafts': EXAMPLES}
            self.assertTrue(api.rpc('save_workspace', {'sequence': 2, 'workspace': workspace})['ok'])
            older = {'project': example_network('GNSS网').to_dict()}
            self.assertTrue(api.rpc('save_workspace', {'sequence': 1, 'workspace': older})['ok'])
            restored = Api(folder).rpc('load_workspace')['data']
            self.assertEqual(restored, workspace)
            self.assertFalse((Path(folder)/'workspace.tmp').exists())

    def test_loopback_api_requires_token_and_host(self):
        server, url = start_server(self.api)
        try:
            html = urllib.request.urlopen(url).read().decode('utf-8')
            token = re.search(r'window.__SURVEY_TOKEN__="([^"]+)"', html).group(1)
            data = json.dumps({'op': 'bootstrap'}).encode()
            def request(**headers):
                return urllib.request.urlopen(urllib.request.Request(url+'/api', data=data, headers=headers))
            with self.assertRaises(urllib.error.HTTPError) as denied: request()
            self.assertEqual(denied.exception.code, 403)
            with self.assertRaises(urllib.error.HTTPError): request(**{'X-Survey-Token': token, 'Origin': 'https://example.com'})
            with self.assertRaises(urllib.error.HTTPError): request(**{'X-Survey-Token': token, 'Host': 'attacker.example'})
            self.assertTrue(json.load(request(**{'X-Survey-Token': token}))['ok'])
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(url+'/../../desktop.py')
        finally:
            server.shutdown(); server.server_close()


if __name__ == '__main__': unittest.main()
