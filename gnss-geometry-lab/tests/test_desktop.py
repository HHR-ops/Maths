import base64
from copy import deepcopy
import http.client
import json
from pathlib import Path
import re
import tempfile
import unittest
from desktop import Api, validate_project, start_server

ROOT=Path(__file__).resolve().parents[1]
def project():
    scene={'name':'测试场景','satellites':[{'id':'S01','azimuth':30.,'elevation':45.,'enabled':True}],'mask':10,'sigma':1,'confidence':'standard','obstruction':{'enabled':False,'start':330,'width':50,'height':40}}
    return {'format':'gnss-geometry-lab','version':1,'scene':scene,'snapshots':[]}
class HostTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'qa');self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_project_validation_and_independent_copy(self):
        p=project();copy=validate_project(p);self.assertEqual(p,copy);copy['scene']['sigma']=4;self.assertEqual(p['scene']['sigma'],1)
    def test_reject_invalid_coordinates_and_types(self):
        for key,value in [('azimuth',float('nan')),('elevation',91),('enabled',1),('id','<script>')]:
            p=project();p['scene']['satellites'][0][key]=value
            with self.assertRaises(ValueError):validate_project(p)
    def test_reject_duplicate_ids_and_invalid_parameters(self):
        p=project();p['scene']['satellites'].append(deepcopy(p['scene']['satellites'][0]))
        with self.assertRaises(ValueError):validate_project(p)
        for key,value in [('mask',90),('sigma',0),('confidence','68')]:
            p=project();p['scene'][key]=value
            with self.assertRaises(ValueError):validate_project(p)
    def test_store_is_atomic_and_ignores_stale_sequences(self):
        api=Api(self.root);p=project();api.store({'project':p,'sequence':2})
        q=project();q['scene']['sigma']=5;api.store({'project':q,'sequence':1})
        self.assertEqual(api.load()['scene']['sigma'],1)
        q['scene']['sigma']=-1
        with self.assertRaises(ValueError):api.store({'project':q,'sequence':3})
        self.assertEqual(api.load()['scene']['sigma'],1);self.assertFalse((self.root/'workspace.tmp').exists())
    def test_corrupt_draft_does_not_block_startup(self):
        (self.root/'workspace.json').write_text('{"broken":',encoding='utf-8');self.assertIsNone(Api(self.root).load())
    def test_native_save_utf8_csv_binary_and_cancel(self):
        class Window:
            def create_file_dialog(self,*args,**kwargs):return [str(target)]
        api=Api();api._window=Window();target=self.root/'project.json'
        self.assertTrue(api.save_file('中文','test.json')['ok']);self.assertEqual(target.read_text(encoding='utf-8'),'中文')
        target=self.root/'export.csv';self.assertTrue(api.save_file('a,b','export.csv')['ok']);self.assertTrue(target.read_bytes().startswith(b'\xef\xbb\xbf'))
        target=self.root/'image.png';self.assertTrue(api.save_file(base64.b64encode(b'abc').decode(),'image.png','base64')['ok']);self.assertEqual(target.read_bytes(),b'abc')
        api._window.create_file_dialog=lambda *a,**k:None
        self.assertTrue(api.save_file('x','x.json')['cancelled'])
    def test_browser_test_storage_does_not_write(self):
        api=Api();api.store({'project':project(),'sequence':1});self.assertIsNone(api.load())
    def test_loopback_session_host_origin_and_path_guards(self):
        (self.root/'index.html').write_text('<head></head>',encoding='utf-8')
        api=Api();server,url=start_server(api,assets=self.root)
        conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
        try:
            conn.request('GET','/');response=conn.getresponse();self.assertEqual(response.status,200);html=response.read().decode()
            token=re.search(r'__GNSS_TOKEN__="([^"]+)"',html)[1]
            payload=json.dumps({'project':project(),'sequence':1})
            for headers,expected in [({},403),({'X-GNSS-Token':'wrong'},403),({'X-GNSS-Token':token,'Origin':'https://evil.test'},403),({'X-GNSS-Token':token},200)]:
                conn.request('POST','/api/workspace',payload,headers);response=conn.getresponse();self.assertEqual(response.status,expected);response.read()
            conn.request('GET','/',headers={'Host':'evil.test'});response=conn.getresponse();self.assertEqual(response.status,403);response.read()
            conn.request('GET','/../../desktop.py');response=conn.getresponse();self.assertEqual(response.status,404);response.read()
            conn.request('POST','/api/workspace','{}',{'X-GNSS-Token':token});response=conn.getresponse();self.assertEqual(response.status,400);response.read()
        finally:conn.close();server.shutdown();server.server_close()
    def test_embedded_draft_cannot_close_script_tag(self):
        (self.root/'index.html').write_text('<head></head>',encoding='utf-8')
        p=project();p['scene']['name']='</script><script>alert(1)</script>'
        api=Api(self.root);api.store({'project':p,'sequence':1})
        server,url=start_server(api,assets=self.root);conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
        try:
            conn.request('GET','/');response=conn.getresponse();html=response.read().decode()
            self.assertNotIn('</script><script>alert',html);self.assertIn(r'\u003c/script>',html)
        finally:conn.close();server.shutdown();server.server_close()
if __name__=='__main__':unittest.main()
