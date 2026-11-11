import unittest
from harness import t03_curriculum as C
class CurriculumTests(unittest.TestCase):
    def test_cell_partitions_are_spatially_disjoint(self):
        grid=C.cells({'x_centers_m':[.28,.34,.40],'y_centers_m':[.25,.32,.39],'jitter_m':.008})
        for a in grid:
            for b in grid:
                if a['partition']==b['partition']:continue
                self.assertTrue(any(abs(x-y)>a['jitter_xy_m']+b['jitter_xy_m'] for x,y in zip(a['center_xy_m'],b['center_xy_m'])))
    def test_recipe_cannot_relax_limits(self):
        with self.assertRaises(ValueError):C.recipe_reply({'action':{'op':'done'},'state':{'parameters':{'hand_kp':999}}})
