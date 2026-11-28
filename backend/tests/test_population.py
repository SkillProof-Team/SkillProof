"""Population contract tested with real sessions, migrations and persisted reports."""
import json
import unittest
from contextlib import closing

import test_reports

from app.catalog import DIMENSION_IDS
from app.db import connect, dump


class PopulationTests(unittest.TestCase):
    setUp = test_reports.ReportTests.setUp
    register = test_reports.ReportTests.register
    insert_attempt = test_reports.ReportTests.insert_attempt

    def population(self, role='backend'):
        response = self.client.get(f'/api/roles/{role}/population')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def update_scores(self, attempt_id, score):
        with closing(connect(self.settings)) as con:
            report = json.loads(con.execute('SELECT report_json FROM attempts WHERE id=?', (attempt_id,)).fetchone()[0])
            report['id'] = attempt_id
            for d in report['dimensions']:
                d['score'] = score
            con.execute('UPDATE attempts SET report_json=? WHERE id=?', (dump(report), attempt_id))

    def test_weighted_math_retake_changes_deletion_and_role_isolation(self):
        self.update_scores('attempt-1', 20)
        with closing(connect(self.settings)) as con:
            con.execute("UPDATE users SET role='admin' WHERE id=?", (self.auth['user']['id'],))
        config = {'preset': dict.fromkeys(DIMENSION_IDS, 80), 'weight': 2}
        csrf = {'X-CSRF-Token': self.auth['csrfToken']}
        response = self.client.put('/api/admin/roles/backend/population', json=config, headers=csrf)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['vector'], dict.fromkeys(DIMENSION_IDS, 60))
        self.insert_attempt('attempt-2', 'submitted', dump(self.report))
        self.update_scores('attempt-2', 50)
        data = self.population()
        self.assertEqual(data['sampleCount'], 1)
        self.assertEqual(data['vector'], dict.fromkeys(DIMENSION_IDS, 70))
        with closing(connect(self.settings)) as con:
            con.execute("UPDATE attempts SET report_json='{}' WHERE id='attempt-2'")
        self.assertEqual(self.population()['vector'], dict.fromkeys(DIMENSION_IDS, 60))
        self.assertEqual(self.population('frontend')['sampleCount'], 0)
        with closing(connect(self.settings)) as con:
            con.execute("DELETE FROM attempts WHERE status='submitted'")
        data = self.population()
        self.assertEqual(data['source'], 'preset')
        self.assertEqual(data['sampleCount'], 0)
        self.assertEqual(data['vector'], config['preset'])
        self.assertEqual(set(data), {'roleId','sampleCount','vector','preset','weight','source','updatedAt'})

    def test_auth_validation_and_sample_only_mean(self):
        self.update_scores('attempt-1', 25)
        self.assertEqual(self.population()['source'], 'samples')
        self.assertEqual(self.population()['vector'], dict.fromkeys(DIMENSION_IDS, 25))
        payload = {'preset': dict.fromkeys(DIMENSION_IDS, 50), 'weight': 0}
        url = '/api/admin/roles/backend/population'
        self.assertEqual(self.client.put(url, json=payload, headers={'X-CSRF-Token':self.auth['csrfToken']}).status_code, 403)
        with closing(connect(self.settings)) as con:
            con.execute("UPDATE users SET role='admin' WHERE id=?", (self.auth['user']['id'],))
        self.assertEqual(self.client.put(url, json=payload).status_code, 403)
        payload['preset']['database'] = 101
        self.assertEqual(self.client.put(url, json=payload, headers={'X-CSRF-Token':self.auth['csrfToken']}).status_code, 422)
        self.assertEqual(self.client.get('/api/roles/missing/population').status_code, 404)
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/api/roles/backend/population').status_code, 401)

    def test_second_user_counts_once_and_mean_is_per_user(self):
        from fastapi.testclient import TestClient
        self.update_scores('attempt-1', 20)
        owner = self.auth
        other = self.enterContext(TestClient(self.app))
        self.auth = self.register(other, 'second@example.invalid')
        self.insert_attempt('second-result', 'submitted', dump(self.report))
        self.update_scores('second-result', 80)
        self.auth = owner
        data = self.population()
        self.assertEqual(data['sampleCount'], 2)
        self.assertEqual(data['vector'], dict.fromkeys(DIMENSION_IDS, 50))
        with closing(connect(self.settings)) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM population_vectors').fetchone()[0], 2)
