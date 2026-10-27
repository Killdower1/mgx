import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'nicegui_template'))
from services import mitra_portfolio as m


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.original = {'version': 1, 'partners': [
            {'id': 'P-01', 'name': 'Widi Official', 'aliases': ['Wijaya'],
             'investments': [], 'outlets': [{'name': 'Old Site', 'state': 'excluded'}]},
            {'id': 'P-02', 'name': 'CSN', 'aliases': [], 'investments': [], 'outlets': []}]}

    def test_idempotent_safe_and_manual_assignment(self):
        rows = [{'name': 'Old Site', 'is_franchise': 1, 'investor_name': 'Wijaya'},
                {'name': 'New Widi', 'is_franchise': 1, 'investor_name': 'Wijaya'},
                {'name': 'No Owner', 'is_franchise': 1, 'partner_id': 'unrelated'},
                {'name': 'Not Kemitraan', 'is_franchise': 0, 'investor_name': 'Wijaya'}]
        doc, counts = m.discover_outlets(self.original, rows, '2026-10-27')
        self.assertEqual(counts, {'assigned': 1, 'unassigned': 1})
        self.assertNotIn('unassigned_outlets', self.original)
        self.assertEqual(doc['partners'][0]['outlets'][0]['state'], 'excluded')
        self.assertEqual(doc['partners'][0]['outlets'][1]['state'], 'candidate')
        again, counts = m.discover_outlets(doc, rows, '2026-10-28')
        self.assertEqual(counts, {'assigned': 0, 'unassigned': 0})
        self.assertEqual(again, doc)
        m.assign_unassigned(doc, 'No Owner', 'P-01')
        self.assertEqual(len(doc['unassigned_outlets']), 0)
        self.assertEqual(doc['partners'][0]['outlets'][-1]['state'], 'candidate')
        self.assertEqual(m.reconcile(doc, [], '2026-10')[0]['returned'], 0)

    def test_ambiguous_owner_stays_unassigned(self):
        doc = copy.deepcopy(self.original)
        doc['partners'][1]['aliases'] = ['Wijaya']
        out, counts = m.discover_outlets(doc, [{'name': 'X', 'is_franchise': 1,
                                                 'investor_name': 'Wijaya'}], '2026-10-27')
        self.assertEqual(counts['unassigned'], 1)
        self.assertEqual(out['unassigned_outlets'][0]['investor_hint'], 'Wijaya')


if __name__ == '__main__':
    unittest.main()
