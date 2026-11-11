import json
import tempfile
import unittest
from pathlib import Path

from harness import t03_handoff as H


def episode(task='t', arm='code', success=False, stage=None, invoked=(), fired=()):
    return {'task': task, 'arm': arm, 'success': success, 'stage': stage,
            'leaf_invoked': list(invoked), 'triggered': list(fired)}


class StageOrderTests(unittest.TestCase):

    def test_unknown_stage_is_rejected(self):
        with self.assertRaises(ValueError):
            H.stage_index('grasp')
        with self.assertRaises(ValueError):
            H.summarize([episode(stage='grasp')])
        with self.assertRaises(ValueError):
            H.summarize([episode(invoked=['grasp'])])

    def test_handoff_fields_are_named_for_every_gated_stage(self):
        for stage, fields in H.HANDOFF.items():
            self.assertIn(stage, H.STAGES)
            self.assertTrue(fields)


class RegistrationGateTests(unittest.TestCase):
    def test_missing_focus_blocks(self):
        gate = H.validate_registration({})
        self.assertFalse(gate['ok'])
        self.assertIn('focuses_missing', gate['errors'])

    def test_each_focus_needs_its_own_trigger(self):
        gate = H.validate_registration({'focuses': [
            {'stage': 'locate', 'mechanism_trigger': 'residual consensus rejected'},
            {'stage': 'close_and_test'},
        ], 'handoff': {}})
        self.assertFalse(gate['ok'])
        self.assertIn('focus[1].mechanism_trigger_missing', gate['errors'])

    def test_several_focuses_are_allowed(self):
        cfg = {'focuses': [
            {'stage': 'locate', 'mechanism_trigger': 'a'},
            {'stage': 'approach', 'mechanism_trigger': 'b'},
            {'stage': 'close_and_test', 'mechanism_trigger': 'c'},
        ], 'handoff': {'approach': ['x'], 'close_and_test': ['y']}}
        gate = H.validate_registration(cfg)
        self.assertTrue(gate['ok'], gate['errors'])
        self.assertEqual(gate['focus_stages'], ['locate', 'approach', 'close_and_test'])

    def test_focus_count_is_capped(self):
        cfg = {'focuses': [{'stage': s, 'mechanism_trigger': 'x'} for s in H.STAGES[:4]],
               'handoff': {s: ['x'] for s in H.STAGES}}
        self.assertIn('too_many_focuses', H.validate_registration(cfg)['errors'])

    def test_duplicate_focus_stage_is_rejected(self):
        cfg = {'focuses': [{'stage': 'locate', 'mechanism_trigger': 'a'},
                           {'stage': 'locate', 'mechanism_trigger': 'b'}],
               'handoff': {}}
        self.assertIn('duplicate_focus_stage', H.validate_registration(cfg)['errors'])

    def test_handoff_covers_every_stage_up_to_the_deepest_focus(self):
        cfg = {'focuses': [{'stage': 'close_and_test', 'mechanism_trigger': 'x'}],
               'handoff': {'approach': ['x']}}
        self.assertEqual(H.handoff_gaps(cfg), ['close_and_test'])


class EpisodeReadingTests(unittest.TestCase):
    def test_declined_leaf_is_invoked_but_not_triggered(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'obstacle_approach.json').write_text(json.dumps(
                {'calls': [{'selected': 'default'}]}), encoding='utf-8')
            self.assertEqual(H.read_decisions(d), {'approach': (True, False)})

    def test_no_record_means_not_invoked(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(H.read_decisions(d), {})
            Path(d, 'locate_branch.json').write_text(json.dumps({'attempts': []}), encoding='utf-8')
            self.assertEqual(H.read_decisions(d), {})

    def test_alternative_route_counts_as_triggered(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'obstacle_approach.json').write_text(json.dumps(
                {'calls': [{'selected': 'away_0.04_side_0.00'}]}), encoding='utf-8')
            self.assertEqual(H.read_decisions(d), {'approach': (True, True)})

    def test_two_stages_are_reported_separately(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'locate_branch.json').write_text(json.dumps(
                {'attempts': [{'route': 'primary'}, {'route': 'leaf'}]}), encoding='utf-8')
            Path(d, 'obstacle_approach.json').write_text(json.dumps(
                {'calls': [{'selected': 'default'}]}), encoding='utf-8')
            self.assertEqual(H.read_decisions(d),
                             {'locate': (True, True), 'approach': (True, False)})
            self.assertEqual(H.decision_stage(d), 'approach')


class FocusTests(unittest.TestCase):
    def test_upstream_failures_are_unattributed_not_blamed(self):
        rows = H.summarize([
            episode('a', stage='locate', invoked=['locate'], fired=['locate']),
            episode('b', stage='preflight'),
            episode('c', success=True, invoked=['approach'], fired=['approach']),
        ])
        f = H.focus(rows, ['approach'], [])
        self.assertEqual(f['upstream_blocked'], 2)
        self.assertEqual(f['upstream_stages'], ['locate', 'preflight'])
        self.assertEqual(f['by_focus']['approach']['reached'], 1)
        self.assertEqual(f['by_focus']['approach']['triggered'], 1)
        texts = ' '.join(p['finding'] for p in H.priorities(f))
        self.assertIn('unattributed', texts)

    def test_each_focus_is_counted_independently(self):
        rows = H.summarize([
            episode('a', success=True, invoked=['locate', 'approach'], fired=['locate']),
            episode('b', stage='close_and_test', invoked=['locate', 'approach'], fired=['approach']),
        ])
        f = H.focus(rows, ['locate', 'approach'], [])
        self.assertEqual(f['by_focus']['locate']['triggered'], 1)
        self.assertEqual(f['by_focus']['locate']['triggered_succeeded'], 1)
        self.assertEqual(f['by_focus']['approach']['triggered'], 1)
        self.assertEqual(f['by_focus']['approach']['triggered_succeeded'], 0)

    def test_untriggered_focus_is_flagged_while_another_passes(self):
        rows = H.summarize([
            episode('a', success=True, invoked=['locate', 'approach'], fired=['locate']),
        ])
        f = H.focus(rows, ['locate', 'approach'], [])
        findings = {p['finding']: p['level'] for p in H.priorities(f)}
        self.assertTrue(any('approach: leaf invoked in 1 episodes, branch fired in 0' in k
                            for k in findings))
        self.assertTrue(any('locate: branch fired 1 times, 1 full success' in k for k in findings))

    def test_fired_but_never_succeeded_sends_reader_downstream(self):
        rows = H.summarize([episode('a', stage='close_and_test', invoked=['approach'], fired=['approach'])])
        f = H.focus(rows, ['approach'], [])
        self.assertEqual(f['by_focus']['approach']['triggered_succeeded'], 0)
        self.assertEqual(f['downstream_stages'], ['close_and_test'])
        self.assertTrue(any('failed after the last focus' in p['finding'] for p in H.priorities(f)))

    def test_focus_requires_a_stage(self):
        with self.assertRaises(ValueError):
            H.focus([], [], [])

    def test_card_reports_per_focus_table(self):
        rows = H.summarize([episode('a', stage='close_and_test',
                                    invoked=['locate', 'approach'], fired=['approach'])])
        text = H.card(H.focus(rows, ['locate', 'approach'], []), notes=['note'])
        self.assertIn('| locate |', text)
        self.assertIn('| approach |', text)
        self.assertIn('note', text)


class PacketTests(unittest.TestCase):
    def test_packet_lists_every_open_stage_with_its_trigger(self):
        cfg = {'focuses': [{'stage': 'locate', 'mechanism_trigger': 'residual rejected'},
                           {'stage': 'close_and_test', 'mechanism_trigger': 'alignment over threshold'}],
               'handoff': {'approach': ['x'], 'close_and_test': ['y']}}
        text = H.packet_block(cfg, 'episodes 12')
        self.assertIn('1. locate — trigger: residual rejected', text)
        self.assertIn('2. close_and_test — trigger: alignment over threshold', text)
        self.assertIn('reported separately', text)
        self.assertIn('closed: evaluator, guards, budgets, task set', text)
        self.assertIn('episodes 12', text)

    def test_packet_allows_reporting_a_blocker_without_fixing_it(self):
        text = H.packet_block({'focuses': [{'stage': 'approach', 'mechanism_trigger': 'x'}], 'handoff': {}})
        self.assertIn('report it as a blocker rather than fixing it in this round', text)

    def test_packet_marks_unset(self):
        self.assertIn('1. UNSET', H.packet_block({}))


if __name__ == '__main__':
    unittest.main()
