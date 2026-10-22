"""Independent expectations for representative networks and datum information."""
from copy import deepcopy
import unittest
import numpy as np

from network import Network, FAMILIES, MODEL_NAMES, NETWORK_EXAMPLES, example_network, linearize, adjust_network
from bulk_import import template, read_tables, preview_import
from desktop import Api

EXPECTED = {
    "水准网": (6,3,3,3,0,5),
    "导线网": (7,4,3,4,0,6),
    "GNSS网": (27,15,12,18,3,6),
    "测边网": (6,5,1,6,1,4),
    "测角网": (12,6,6,6,0,5),
    "边角网": (11,4,7,4,0,4),
    "坐标观测网": (18,6,12,6,0,3),
}


def counts(stats):
    return tuple(stats[k] for k in ('n','t','r','parameters','constraints','points'))


class RepresentativeExamples(unittest.TestCase):
    def test_networks_have_distinct_geometry_and_correct_counts(self):
        geometries=set()
        for family in FAMILIES:
            net=example_network(family)
            self.assertEqual(counts(linearize(net).stats), EXPECTED[family])
            self.assertEqual(net.name, NETWORK_EXAMPLES[family]['title'])
            geometries.add(tuple((p['X'],p['Y']) for p in net.points.values()))
            kinds={o['kind'] for o in net.observations}
            if family=='测边网': self.assertEqual(kinds, {'distance'})
            if family=='测角网': self.assertEqual(kinds, {'angle'})
            if family=='坐标观测网': self.assertEqual(kinds, {'coordinate'})
        self.assertEqual(len(geometries),7)

    def test_all_examples_and_methods_agree_in_design_and_measurement(self):
        for family in FAMILIES:
            for measured in (False,True):
                net=example_network(family,measured)
                reference=adjust_network(net,design=not measured)
                for method in MODEL_NAMES:
                    with self.subTest(family=family,measured=measured,method=method):
                        net.method=method
                        solution=adjust_network(net,design=not measured)
                        self.assertEqual(counts(solution.model.stats),EXPECTED[family])
                        self.assertEqual(solution.model.stats['defect'],0)
                        np.testing.assert_allclose(solution.corrections,reference.corrections,atol=1e-7)
                        np.testing.assert_allclose(solution.result.qxx,reference.result.qxx,atol=1e-10)

    def test_datum_constraints_are_real_and_fixed_points_are_not_counted_twice(self):
        for family, defect in [('GNSS网',3),('测边网',1)]:
            net=example_network(family)
            self.assertEqual(linearize(net).stats['constraints'],defect)
            net.constraints=[]
            self.assertEqual(linearize(net).stats['defect'],defect)
        self.assertEqual(sum(len(p['fixed']) for p in example_network('水准网').points.values()),2)
        self.assertEqual(linearize(example_network('水准网')).stats['constraints'],0)

    def test_disabling_a_gnss_baseline_updates_scalar_counts(self):
        net=example_network('GNSS网')
        net.observations[0]['enabled']=False
        m=linearize(net)
        self.assertEqual((m.stats['n'],m.stats['t'],m.stats['r']), (24,15,9))
        self.assertEqual(m.stats['constraints'],3)

    def test_xlsx_and_three_csv_tables_preserve_example_constraints(self):
        for family in FAMILIES:
            for form in ('xlsx','csv'):
                with self.subTest(family=family,form=form):
                    tables=[]
                    for kind in (['xlsx'] if form=='xlsx' else ['constraints','observations','points']):
                        file=template(family,kind)
                        tables.extend(read_tables(file['filename'],file['content_base64'])['tables'])
                    result=preview_import(Network(family).to_dict(),tables,policy='replace')
                    self.assertTrue(result['ok'],result['errors'])
                    self.assertEqual(counts(result['statistics']),EXPECTED[family])
                    self.assertEqual(result['project']['constraints'],example_network(family).constraints)

    def test_bad_constraint_import_is_atomic(self):
        import base64
        original=example_network('水准网').to_dict()
        before=deepcopy(original)
        for value in ['missing.H:1 = 100','B.H:1  = invalid','B.H:1 = 1\nC.H:1 = 2']:
            import csv,io
            output=io.StringIO();writer=csv.writer(output);writer.writerow(['限制方程']);writer.writerow([value])
            file=base64.b64encode(output.getvalue().encode()).decode()
            tables=read_tables('constraints.csv',file)['tables']
            preview=preview_import(original,tables)
            self.assertFalse(preview['ok'])
            self.assertIsNone(preview['project'])
            self.assertEqual(original,before)

    def test_old_four_point_project_stays_compatible(self):
        net=Network('水准网','旧版四点项目')
        for name,X,Y,H in [('A',0,0,100),('B',0,120,101.2),('C',90,130,102),('D',100,10,101.5)]:
            net.add_point(name,X=X,Y=Y,H=H,fixed=['H'] if name=='A' else [])
        for a,b in [('A','B'),('B','C'),('C','D'),('D','A'),('A','C')]:net.add_observation('height',[a,b])
        result=Api().rpc('validate',{'project':net.to_dict()})
        self.assertTrue(result['ok'])
        self.assertEqual(counts(linearize(Network.from_dict(result['data'])).stats),(5,3,2,3,0,4))

    def test_examples_are_deterministic_and_independent(self):
        for family in FAMILIES:
            a=example_network(family,True);b=example_network(family,True)
            self.assertEqual(a.to_dict(),b.to_dict())
            a.observations[0]['enabled']=False
            self.assertTrue(b.observations[0]['enabled'])


if __name__=='__main__':unittest.main()
