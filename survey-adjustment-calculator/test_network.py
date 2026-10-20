import json
import math
import unittest
from copy import deepcopy

import numpy as np
from numpy.testing import assert_allclose

from adjustment import AdjustmentError,MODEL_NAMES
from network import (Network,FAMILIES,ARCSEC,linearize,adjust_network,automatic_matrices,
                     example_network,parse_constraints,angle_degrees,wrap)


class NetworkCases(unittest.TestCase):
    def test_seven_design_networks(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                net=example_network(family); s=adjust_network(net)
                self.assertTrue(s.model.stats["solvable"])
                self.assertEqual(s.model.stats["n"]-s.model.stats["t"],s.model.stats["r"])
                self.assertEqual(s.result.precision_sigma,1)
                self.assertIsNone(s.result.posterior_sigma)
                self.assertTrue(np.any(s.result.qxx>0))
                assert_allclose(s.result.qvv+s.result.q_adjusted,s.model.Q,atol=1e-10)

    def test_seven_measurement_networks(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                net=example_network(family,True); s=adjust_network(net,False,"posterior")
                self.assertLess(s.iterations,15)
                self.assertGreater(s.result.posterior_sigma,0)
                self.assertTrue(all(math.isfinite(v) for p in s.point_precision for k,v in p.items() if k!="point"))

    def test_four_methods_equivalent_with_nonlinear_geometry(self):
        for family in ("水准网","导线网","GNSS网","测角网"):
            net=example_network(family,True)
            reference=adjust_network(net,False)
            for method in MODEL_NAMES:
                with self.subTest(family=family,method=method):
                    net.method=method; s=adjust_network(net,False)
                    assert_allclose(s.corrections,reference.corrections,atol=1e-8)
                    assert_allclose(s.result.qxx,reference.result.qxx,atol=1e-10)

    def test_jacobians_by_central_differences(self):
        net=Network("边角网")
        for name,X,Y in [("A",5,8),("B",55,27),("C",23,94)]:net.add_point(name,X,Y)
        for kind,pts in [("distance",["A","B"]),("azimuth",["B","C"]),("angle",["A","B","C"]),("coordinate",["C"])]:net.add_observation(kind,pts)
        m=linearize(net)
        numeric=np.zeros_like(m.B); eps=1e-4
        for j,(p,a) in enumerate(m.keys):
            plus=deepcopy(net.points);minus=deepcopy(net.points);plus[p][a]+=eps;minus[p][a]-=eps
            delta=linearize(net,plus).predicted-linearize(net,minus).predicted
            delta[m.angular]=(delta[m.angular]+math.pi)%(2*math.pi)-math.pi
            numeric[:,j]=delta/(2*eps)
        assert_allclose(m.B,numeric,rtol=1e-7,atol=1e-9)

    def test_exact_trilateration(self):
        net=Network("测边网")
        net.add_point("A",0,0,fixed=("X","Y"));net.add_point("B",0,10,fixed=("X","Y"));net.add_point("C",6.2,7.7)
        net.add_observation("distance",["A","C"],10,sigma=.01)
        net.add_observation("distance",["B","C"],math.sqrt(40),sigma=.01)
        s=adjust_network(net,False,"prior")
        assert_allclose([s.points["C"]["X"],s.points["C"]["Y"]],[6,8],atol=1e-8)
        self.assertEqual(s.model.stats["r"],0)
        self.assertIsNone(s.result.posterior_sigma)

    def test_gnss_correlated_weighted_solution(self):
        net=Network("GNSS网");net.add_point("A",1,2,Z=3,fixed=("X","Y","Z"));net.add_point("B",0,0,Z=0)
        Q1=np.array([[4,1,0],[1,9,2],[0,2,16]])*.000001;Q2=np.diag([9,4,25])*.000001
        v1=np.array([10.01,20.02,30.03]);v2=np.array([10,20,30])
        net.add_observation("gnss",["A","B"],v1.tolist(),covariance=Q1.tolist())
        net.add_observation("gnss",["A","B"],v2.tolist(),covariance=Q2.tolist())
        s=adjust_network(net,False,"prior");P1,P2=np.linalg.inv(Q1),np.linalg.inv(Q2)
        expected=np.linalg.solve(P1+P2,P1@v1+P2@v2)+[1,2,3]
        assert_allclose([s.points["B"][a] for a in net.axes],expected,atol=1e-10)
        assert_allclose(s.result.qxx,np.linalg.inv(P1+P2),atol=1e-13)
        self.assertEqual(s.model.stats["n"],6)

    def test_level_rank_and_fix_counts(self):
        net=example_network();net.points["A"]["fixed"]=[]
        m=linearize(net);self.assertEqual(m.stats["defect"],1);self.assertEqual(m.stats["parameters"],4)
        with self.assertRaisesRegex(AdjustmentError,"基准"):adjust_network(net)
        net.points["A"]["fixed"]=["H"]
        m=linearize(net);self.assertEqual(m.stats["defect"],0);self.assertEqual(m.stats["parameters"],3)
        net.observations[-1]["enabled"]=False
        self.assertEqual(linearize(net).stats["n"],4)

    def test_distance_free_network_has_three_datum_defects(self):
        net=example_network("测边网")
        for p in net.points.values():p["fixed"]=[]
        self.assertEqual(linearize(net).stats["defect"],3)

    def test_constraints_and_fixed_values(self):
        net=Network("水准网");net.add_point("A",H=100,fixed=("H",));net.add_point("B",H=100);net.add_point("C",H=100)
        net.add_observation("height",["A","B"],[1.02]);net.add_observation("height",["A","C"],[2.01]);net.add_observation("height",["B","C"],[1],sigma=1/math.sqrt(2))
        # Unit weights to match an independent, exactly known constrained example.
        for o in net.observations[:2]:o["sigma"]=1
        net.constraints=parse_constraints("B.H:1 C.H:1 = 203")
        reference=None
        for method in MODEL_NAMES:
            net.method=method;s=adjust_network(net,False,"prior")
            assert_allclose([s.points[p]["H"] for p in ("B","C")],[101.001,101.999])
            self.assertEqual(s.model.stats["constraints"],1);self.assertEqual(s.model.stats["t"],1);self.assertEqual(s.model.stats["r"],2)
            if reference is not None:assert_allclose(s.corrections,reference,atol=1e-10)
            reference=s.corrections

    def test_fixed_term_folded_into_constraint(self):
        net=example_network();net.constraints=parse_constraints("A.H:1 B.H:1 = 201.2")
        m=linearize(net);self.assertAlmostEqual(m.d[0],0)
        self.assertEqual(m.stats["constraints"],1)

    def test_all_fixed(self):
        net=example_network()
        for p in net.points.values():p["fixed"]=["H"]
        s=adjust_network(net)
        self.assertEqual(s.model.stats["t"],0);self.assertEqual(s.model.stats["r"],5)
        assert_allclose(s.result.q_adjusted,0)

    def test_empty_and_one_point_counts(self):
        net=Network();self.assertEqual(linearize(net).stats["n"],0)
        net.add_point();self.assertEqual(linearize(net).stats["defect"],1)

    def test_angular_wrap_crosses_zero(self):
        net=Network("测角网");net.add_point("A",0,0,fixed=("X","Y"));net.add_point("B",10,0,fixed=("X","Y"))
        net.add_observation("azimuth",["A","B"],359.9999)
        self.assertAlmostEqual(linearize(net).l[0]/ARCSEC,-.36,places=6)

    def test_joint_covariance_in_relative_height_precision(self):
        net=example_network();s=adjust_network(net)
        p={k:i for i,k in enumerate(s.model.keys)};obs=net.observations[1];a,b=obs["points"]
        Q=s.result.qxx;ia,ib=p[a,"H"],p[b,"H"]
        expected=math.sqrt(Q[ia,ia]+Q[ib,ib]-2*Q[ia,ib])
        match=next(p for p in s.relative_precision if p["observation"]==obs["id"])
        self.assertAlmostEqual(match["sigma"],expected)

    def test_conditions_annihilate_design(self):
        m=linearize(example_network("边角网"));mat=automatic_matrices(m);A=mat["A · 条件系数（零空间基）"]
        assert_allclose(A@m.B,0,atol=1e-12)
        self.assertEqual(A.shape[0],m.stats["r"])

    def test_project_json_roundtrip(self):
        for family in FAMILIES:
            net=example_network(family,True);doc=json.loads(json.dumps(net.to_dict(),ensure_ascii=False))
            reloaded=Network.from_dict(doc)
            assert_allclose(linearize(net).B,linearize(reloaded).B)
            self.assertEqual(net.to_dict(),reloaded.to_dict())

    def test_reject_missing_real_values(self):
        with self.assertRaisesRegex(AdjustmentError,"尚无实测值"):adjust_network(example_network(),False)

    def test_reject_indefinite_covariance(self):
        net=Network("GNSS网");net.add_point("A");net.add_point("B",X=1)
        with self.assertRaises(AdjustmentError):net.add_observation("gnss",["A","B"],covariance=[[1,2,0],[2,1,0],[0,0,1]])

    def test_deletion_removes_incident_observations_and_constraints(self):
        net=example_network();net.constraints=parse_constraints("B.H:1 = 101.2");net.remove_point("B")
        self.assertFalse(any("B" in o["points"] for o in net.observations));self.assertFalse(net.constraints)

    def test_dms_parser(self):
        self.assertAlmostEqual(angle_degrees("12:30:00"),12.5)
        self.assertAlmostEqual(angle_degrees("−12".replace("−","-")),-12)
        self.assertAlmostEqual(angle_degrees("-0:30:0"),-.5)
        for s in ("12:60:0","1:2:3:4","eval(x)"):
            with self.assertRaises(AdjustmentError):angle_degrees(s)

    def test_reject_duplicate_constraints(self):
        net=example_network();net.constraints=parse_constraints("B.H:1 = 101\nB.H:2 = 202")
        with self.assertRaisesRegex(AdjustmentError,"限制"):linearize(net)

    def test_design_nominal_coordinates_must_satisfy_exact_constraints(self):
        net=example_network();net.constraints=parse_constraints("B.H:1 = 300")
        with self.assertRaisesRegex(AdjustmentError,"近似坐标"):adjust_network(net)

    def test_gnss_large_cartesian_offset_and_3d_precision(self):
        net=example_network("GNSS网",True);reference=adjust_network(net,False)
        offset=[3800000.,4100000.,3900000.]
        for p in net.points.values():
            for a,d in zip(net.axes,offset):p[a]+=d
        shifted=adjust_network(net,False)
        assert_allclose(shifted.result.qxx,reference.result.qxx,atol=1e-12)
        for before,after in zip(reference.point_precision,shifted.point_precision):
            self.assertAlmostEqual(after["m3D"],math.sqrt(after["mX"]**2+after["mY"]**2+after["mZ"]**2))
            self.assertAlmostEqual(after["m3D"],before["m3D"])


if __name__=="__main__":unittest.main(verbosity=2)
