"""AGENTS.md rules that a check can enforce; each failure message names the supported way."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HARNESS = ROOT / 'experiments/grow_up_harness_v2'
CALIBRATION = {
    'artifacts.py', 'check_vla_prepose_clearance.py', 'grow.py', 'grow_t02.py', 'isolation_precheck.py',
    'local_artifact_cycle.py', 'mapping_export.py', 'mapping_holdout.py', 'migrate_library_v2.py',
    'reference_runners.py', 'render_episode.py', 'render_t03_episode.py', 'render_t03_saved.py', 't01_agent_pilot.py',
    't01_code_policy.py', 't01_controls.py', 't01_motion.py', 't01_vla_policy.py', 't01_vla_prepose.py',
    't01_vla_response.py', 't02_execution.py', 't02_slot_check.py', 't03.py', 't03_focus.py', 'tabletop.py',
}
FROZEN = ('experiments/t0_agent_v1', 'experiments/cordis_t01', 'experiments/grow_up_v2/isolation',
          ':(glob)grasp_optimization/*.py')


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), '-c', 'core.fileMode=false', *args],
                          check=True, capture_output=True, text=True).stdout.split()


def frozen_changes(root):
    """Frozen dependency files that differ from the baseline commit or were added since."""
    base = git(root, 'rev-list', '--max-parents=0', 'HEAD')[-1]
    return git(root, 'diff', '--name-only', base, '--', *FROZEN) + git(
        root, 'ls-files', '--others', '--exclude-standard', '--', *FROZEN)


class RepoRulesTest(unittest.TestCase):
    def test_no_new_calibration_scripts(self):
        added = {p.name for p in (HARNESS / 'calibration').glob('*.py')} - CALIBRATION
        self.assertFalse(added, f'{sorted(added)}: the T01-T04 flow adds a subcommand to calibration/tabletop.py '
                                '(old T03 line: calibration/t03.py) instead of a new per-round script')

    def test_no_second_harness(self):
        self.assertEqual([p.name for p in (ROOT / 'experiments').glob('grow_up_harness_v[3-9]*')], [],
                         'grow_up_harness_v2 is the only harness; artifact versions come from content identity')

    def test_frozen_dependencies_are_unchanged(self):
        self.assertEqual(frozen_changes(ROOT), [], 'frozen dependencies are read-only; adapt them in the harness')


if __name__ == '__main__':
    unittest.main()
