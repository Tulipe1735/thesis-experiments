import unittest

from harness import reach_trial as R


class AttributeTest(unittest.TestCase):
    enabled = {3: {'status': 'enabled'}, 0: {'status': 'enabled'}, 5: {'status': 'untestable'}}

    def test_reference_replay_is_untestable_before_any_calibration(self):
        trial = {'node': 3, 'reachable': False}
        self.assertEqual(R.attribute(trial, True, self.enabled)['class'], 'untestable')

    def test_classes_follow_calibration_and_trial(self):
        cases = [({'node': 3, 'reachable': True}, 'node'), ({'node': 3, 'reachable': False}, 'upstream'),
                 ({'node': 0, 'reachable': False}, 'kernel_gap'), ({'node': 5, 'reachable': False}, 'untestable'),
                 ({'node': 4, 'reachable': False}, 'uncalibrated')]
        for trial, expected in cases:
            self.assertEqual(R.attribute(trial, False, self.enabled)['class'], expected)
        self.assertEqual(R.attribute({'node': 3, 'reachable': False}, False, self.enabled)['to'], 2)


class CalibrateTest(unittest.TestCase):
    def test_rate_counts_only_entries_the_executor_passed(self):
        rows = ([{'node': 2, 'reachable': True, 'entry_passed': True}] * 9
                + [{'node': 2, 'reachable': False, 'entry_passed': True}]
                + [{'node': 2, 'reachable': False, 'entry_passed': False}] * 5
                + [{'node': 4, 'reachable': False, 'entry_passed': True}] * 4
                + [{'node': 6, 'reachable': True, 'entry_passed': True}])
        table = R.calibrate(rows, limit=.1, min_trials=3)
        self.assertEqual((table[2]['trials'], table[2]['unreachable'], table[2]['status']), (10, 1, 'enabled'))
        self.assertEqual(table[4]['status'], 'untestable')
        self.assertEqual(table[6]['status'], 'uncalibrated')


class AttributedRatesTest(unittest.TestCase):
    def test_upstream_failures_move_one_node_and_denominators_stay(self):
        up = {'class': 'upstream'}
        rows = [{'node': 0, 'passed': True}, {'node': 1, 'passed': False, 'attribution': up},
                {'node': 0, 'passed': True}, {'node': 1, 'passed': False, 'attribution': {'class': 'node'}},
                {'node': 0, 'passed': True}, {'node': 1, 'passed': True}]
        table = R.attributed_rates(rows)
        self.assertEqual((table[0]['reached'], table[0]['raw_p'], table[0]['attributed_p']), (3, 1., 2 / 3))
        self.assertEqual((table[1]['reached'], table[1]['raw_p'], table[1]['attributed_p']), (3, 1 / 3, 2 / 3))


if __name__ == '__main__':
    unittest.main()
