import unittest
import numpy as np
from .candidate import scale_proposal


class ProposalTests(unittest.TestCase):
    def test_gain_preserves_direction_and_shrinks_bounded_correction(self):
        proposal = dict(status='CORRECT', correction_xy_m=[.024, -.032], confidence_passed=True)
        result = scale_proposal(proposal, .5)
        np.testing.assert_allclose(result['correction_xy_m'], [.012, -.016])
        self.assertEqual(proposal['correction_xy_m'], [.024, -.032])
        self.assertTrue(result['confidence_passed'])

    def test_non_actionable_proposal_cannot_be_activated(self):
        result = scale_proposal(dict(status='KEEP_NOMINAL', confidence_passed=False), .5)
        self.assertEqual(result['status'], 'KEEP_NOMINAL')
        self.assertNotIn('correction_xy_m', result)

    def test_invalid_or_over_limit_corrections_are_rejected(self):
        for delta in [[.041, 0.], [float('nan'), 0.], [0.]]:
            with self.assertRaises(ValueError):
                scale_proposal(dict(status='CORRECT', correction_xy_m=delta), .5)
        for gain in [0., -.1, 1.1, float('nan')]:
            with self.assertRaises(ValueError):
                scale_proposal(dict(status='KEEP_NOMINAL'), gain)


if __name__ == '__main__':
    unittest.main()
