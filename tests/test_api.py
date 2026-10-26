import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
import app as service

BASE=json.loads((Path(__file__).parent/'treasury_fixtures.json').read_text(encoding='utf-8'))[1]['input']


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.original_data=service.DATA
        service.DATA=Path(cls.temp.name)
        cls.client=TestClient(service.app,base_url='http://127.0.0.1')
        cls.token=cls.client.get('/api/session').json()['token']

    @classmethod
    def tearDownClass(cls):
        cls.client.close();service.DATA=cls.original_data;cls.temp.cleanup()

    def post(self,kind,p):
        return self.client.post('/api/'+kind,json=p,headers={'X-BondLab-Token':self.token})

    def test_calculator_and_audit_roundtrip(self):
        response=self.post('calculate',BASE)
        self.assertEqual(response.status_code,200,response.text)
        r=response.json();self.assertAlmostEqual(r['clean_price'],100.11415,places=6)
        saved=self.client.get('/api/runs/'+r['run_id']).json()
        self.assertEqual(saved['input'],BASE)
        self.assertEqual(saved['output']['clean_price'],r['clean_price'])
        self.assertIn(r['run_id'],[row['run_id'] for row in self.client.get('/api/runs').json()['runs']])

    def test_token_required(self):
        self.assertEqual(self.client.post('/api/calculate',json=BASE).status_code,403)

    def test_cross_origin_rejected(self):
        r=self.client.post('/api/calculate',json=BASE,headers={'X-BondLab-Token':self.token,'Origin':'https://evil.example'})
        self.assertEqual(r.status_code,403)

    def test_foreign_host_rejected(self):
        self.assertEqual(self.client.get('/',headers={'Host':'evil.example'}).status_code,403)

    def test_validation_errors(self):
        for p in [[],dict(BASE,face=-1),dict(BASE,frequency=3)]:
            self.assertEqual(self.post('calculate',p).status_code,422)

    def test_no_nan_json(self):
        r=self.client.post('/api/calculate',content='{"face":NaN}',headers={'X-BondLab-Token':self.token,'Content-Type':'application/json'})
        self.assertEqual(r.status_code,422)

    def test_bad_json(self):
        r=self.client.post('/api/calculate',content='{',headers={'X-BondLab-Token':self.token,'Content-Type':'application/json'})
        self.assertEqual(r.status_code,422)

    def test_home_security_headers(self):
        r=self.client.get('/')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.headers['X-Frame-Options'],'DENY')
        self.assertIn('nonce-',r.headers['Content-Security-Policy'])
        self.assertIn('<script nonce=',r.text)

    def test_snapshot_backtest(self):
        r=self.post('backtest',dict(mode='snapshot',start='2010-01-01',end='2025-12-31'))
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['periods'],191)
        self.assertEqual(len(r.json()['metadata']['sha256']),64)
        self.assertEqual(len(r.json()['cost_sensitivity']),4)

    def test_bills_and_portfolio(self):
        p={'face':1000,'settlement_date':'2024-11-12','maturity_date':'2024-12-10','discount_rate':4.515}
        self.assertEqual(self.post('bill',p).status_code,200)
        self.assertEqual(self.post('portfolio',{'bonds':[BASE,BASE]}).status_code,200)

    def test_missing_run(self):
        self.assertEqual(self.client.get('/api/runs/'+'0'*32).status_code,404)

    def test_invalid_curve_tenor(self):
        for curve in [[],{'NaN':4},{'-1':4}]:
            self.assertEqual(self.post('carry',{'curve':curve}).status_code,422)

    def test_database_connection_closed_after_success(self):
        with service.connection() as con:
            con.execute('SELECT 1').fetchone()
        with self.assertRaises(sqlite3.ProgrammingError):
            con.execute('SELECT 1')

    def test_database_connection_closed_after_exception(self):
        try:
            with service.connection() as con:
                raise ValueError('Simulated failed operation')
        except ValueError:
            pass
        with self.assertRaises(sqlite3.ProgrammingError):
            con.execute('SELECT 1')


if __name__=='__main__':unittest.main()
