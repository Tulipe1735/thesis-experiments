import contextlib
import io
import json
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

from calibration import tabletop


def row(tool, visible_ok, truth_ok, recoverable=None):
    value = {'tool': tool, 'visible_ok': visible_ok, 'truth_ok': truth_ok}
    if recoverable is not None:
        value['recoverable'] = recoverable
    return value


class TallyTest(unittest.TestCase):
    def test_counts_detected_undetected_and_recoverable_failures(self):
        table = tabletop.tally([
            ('TP04', [row('locate', True, True), row('grasp', True, True), row('place', True, False, True)]),
            ('TP04', [row('locate', True, True), row('grasp', False, False, False)]),
            ('TP04', [row('locate', True, False, False)]),
        ])
        self.assertEqual(table[('TP04', 'locate')], dict(reached=3, ok=2, failed=1, detected=0, undetected=1, recoverable=0))
        self.assertEqual(table[('TP04', 'grasp')], dict(reached=2, ok=1, failed=1, detected=1, undetected=0, recoverable=0))
        self.assertEqual(table[('TP04', 'place')], dict(reached=1, ok=0, failed=1, detected=0, undetected=1, recoverable=1))


class BucketTest(unittest.TestCase):
    def test_near_grid_cells_are_near_and_dataset_cells_are_far(self):
        def instance(x, y):
            return {'objects': [{'is_target': False, 'position_m': [0.34, 0.32, 0.96]},
                                {'is_target': True, 'position_m': [x, y, 0.96]}]}
        self.assertEqual(tabletop.reach_bucket(instance(0.272, 0.398)), 'near')
        self.assertEqual(tabletop.reach_bucket(instance(0.41, 0.32)), 'far')
        self.assertEqual(tabletop.reach_bucket(instance(-0.1, -0.3)), 'far')


class ContactCategoryTest(unittest.TestCase):
    def test_names_robot_part_and_other_side(self):
        robot = {'left_wrist_yaw_link', 'left_hand_palm_link', 'left_elbow_link', 'pelvis'}
        objects = {'tray': 'tray', 'distractor_2': 'distractor'}
        cases = [(('left_wrist_yaw_link', 'fruit_1'), 'left_wrist->target'),
                 (('worktable', 'left_hand_palm_link'), 'left_hand->scene:worktable'),
                 (('left_elbow_link', 'tray'), 'left_arm->tray'),
                 (('distractor_2', 'pelvis'), 'robot_other->distractor'),
                 (('left_wrist_yaw_link', 'left_hand_palm_link'), 'left_wrist->self:left_hand')]
        for bodies, expected in cases:
            self.assertEqual(tabletop.contact_category(bodies, robot, 'fruit_1', objects), expected)


class SameEpisodeTest(unittest.TestCase):
    def test_array_bytes_and_records_are_compared_but_not_the_trajectory_file_hash(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / 'a', Path(folder) / 'b'
            for f, digest, last in ((a, 'x', 1.), (b, 'y', 1.)):
                f.mkdir()
                np.savez_compressed(f / 'integration_states.npz', time=np.array([0., .05]),
                                    integration_state=np.array([[0., last]]))
                np.savez_compressed(f / 'boundary_states.npz', state=np.zeros((1, 2)))
                for name in ('actions.json', 'execution.json', 'tools.json'):
                    (f / name).write_text('[]')
                (f / 'verdict.json').write_text(json.dumps({'goal_satisfied': False, 'trajectory_sha256': digest}))
                (f / 'result.json').write_text(json.dumps(dict(success=False, error=None, commands=3, worker_calls=1,
                                                               simulation_s=1., wall_s=digest)))
            self.assertTrue(all(tabletop.same_episode(a, b).values()))
            np.savez_compressed(b / 'other.npz', time=np.array([0., .05]),
                                integration_state=np.array([[0., np.nextafter(1., 2.)]]))
            (b / 'other.npz').replace(b / 'integration_states.npz')
            self.assertFalse(tabletop.same_episode(a, b)['integration_states.npz'])


class NodeRowsTest(unittest.TestCase):
    def test_last_checkpoint_marks_the_failed_node(self):
        checkpoints = [{'done': k} for k in range(5)]
        trial = {4: {'attribution': {'class': 'untestable'}}}
        rows = tabletop.node_rows('TP01', checkpoints, {'stage': 'approach'}, trial)
        self.assertEqual([r['passed'] for r in rows], [True] * 4 + [False])
        self.assertEqual(rows[-1], {'node': 4, 'passed': False, 'attribution': {'class': 'untestable'}})
        self.assertEqual(len(tabletop.node_rows('TP01', [{'done': k} for k in range(8)], None, {})), 7)
        self.assertEqual(tabletop.node_rows('TP01', [], {'stage': 'hand_open'}, {}), [])


class PrepareTest(unittest.TestCase):
    def test_missing_preregistration_stops_before_creating_a_run(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            path.write_text(json.dumps({'output': 'outputs/never_created', 'instances': {'TP01': []}}))
            with self.assertRaisesRegex(ValueError, 'missing preregistration'):
                tabletop.prepare(path)
            self.assertFalse((tabletop.ROOT / 'outputs/never_created').exists())

    def test_instances_and_generate_are_exclusive(self):
        registered = {k: ['x'] for k in ('prediction', 'falsification')}
        registered.update(baselines={'a': 1}, caps={'a': 1}, episode_caps={'a': 1}, kernel_bundle='b',
                          output='outputs/never_created')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            for extra in ({}, {'instances': {'TP01': ['a']}, 'generate': {'seed_start': {'TP01': 1}}}):
                path.write_text(json.dumps({**registered, **extra}))
                with self.assertRaisesRegex(ValueError, 'exactly one of instances or generate'):
                    tabletop.prepare(path)
            path.write_text(json.dumps({**registered, 'generate': {'grid': {}, 'count': 1, 'seed_start': {'TP01': 1}}}))
            with self.assertRaisesRegex(ValueError, 'near bucket grid'):
                tabletop.prepare(path)
            self.assertFalse((tabletop.ROOT / 'outputs/never_created').exists())

    def test_registered_near_config_generates_eight_disjoint_seeds_per_template(self):
        config = json.loads((tabletop.ROOT / 'experiments/grow_up_harness_v2/configs/tabletop_kernel_near_20261113_001.json').read_text())
        spec = config['generate']
        self.assertEqual(spec['grid'], tabletop.NEAR_GRID)
        self.assertEqual((spec['count'], set(spec['seed_start'])), (8, set(tabletop.TEMPLATES)))
        seeds = [s + i for s in spec['seed_start'].values() for i in range(spec['count'])]
        self.assertEqual(len(set(seeds)), len(seeds))

    def test_registered_config_lists_only_frozen_training_instances(self):
        config = json.loads((tabletop.ROOT / 'experiments/grow_up_harness_v2/configs/tabletop_kernel_20261113_001.json').read_text())
        manifest = json.loads((tabletop.ROOT / config['dataset'] / 'train/manifest.json').read_text())
        listed = {e['id']: e['template_id'] for e in manifest['instances']}
        for template, ids in config['instances'].items():
            self.assertEqual(len(ids), 8)
            self.assertTrue(all(listed[i] == template for i in ids))

    def test_reused_seeds_stop_before_creating_a_run(self):
        config = json.loads((tabletop.CONFIGS / 'tabletop_kernel_near_20261113_001.json').read_text())
        config['output'] = 'outputs/never_created'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, 'already registered by'):
                tabletop.prepare(path)
        self.assertFalse((tabletop.ROOT / 'outputs/never_created').exists())


class SeedReuseTest(unittest.TestCase):
    def config(self, name):
        return json.loads((tabletop.CONFIGS / name).read_text())

    def test_e2_rerun_reuses_stage0_seeds_and_must_declare_it(self):
        config = self.config('tabletop_kernel_near_20261115_002.json')
        self.assertEqual(set(tabletop.seed_reuse(config)), {'outputs/tabletop_kernel_near_20261113_001',
                                                            'outputs/tabletop_kernel_near_20261115_001'})
        config['replicates'] = ['outputs/tabletop_kernel_near_20261113_001', 'outputs/tabletop_kernel_near_20261115_001']
        self.assertEqual(tabletop.seed_reuse(config), {})

    def test_replication_cannot_change_the_generate_spec(self):
        config = self.config('tabletop_kernel_near_20261115_002.json')
        config['replicates'] = ['outputs/tabletop_kernel_near_20261113_001', 'outputs/tabletop_kernel_near_20261115_001']
        config['generate'] = {**config['generate'], 'count': 9}
        self.assertEqual(len(tabletop.seed_reuse(config)), 2)

    def test_fresh_seed_range_is_free(self):
        config = self.config('tabletop_kernel_near_20261113_001.json')
        config.update(output='outputs/fresh', generate={**config['generate'], 'seed_start': {'TP01': 9990100}})
        self.assertEqual(tabletop.seed_reuse(config), {})


class WrittenSinceTest(unittest.TestCase):
    def test_lists_only_files_changed_after_the_epoch(self):
        with tempfile.TemporaryDirectory() as folder:
            old, new = Path(folder) / 'old.json', Path(folder) / 'sub' / 'new.json'
            old.write_text('{}')
            os.utime(old, (1, 1))
            new.parent.mkdir()
            new.write_text('{}')
            self.assertEqual(tabletop.written_since([folder], time.time() - 60), [str(new)])


class KernelUnchangedTest(unittest.TestCase):
    spec = {'version': 'K_v1', 'checks': {'grasp': [0.01, 2]}, 'bundle': {'path': 'b.json'}}

    def test_recorded_interface_passes_after_json_round_trip(self):
        live = {**self.spec, 'checks': {'grasp': (0.01, 2)}}
        with mock.patch.object(tabletop, 'kernel_spec', return_value=live):
            tabletop.check_kernel_unchanged(json.loads(json.dumps(self.spec)))

    def test_threshold_changed_after_prepare_stops_the_kernel(self):
        live = {**self.spec, 'checks': {'grasp': [0.02, 2]}}
        with mock.patch.object(tabletop, 'kernel_spec', return_value=live):
            with self.assertRaisesRegex(RuntimeError, "KERNEL_CHANGED_AFTER_PREPARE: \\['checks'\\]"):
                tabletop.check_kernel_unchanged(self.spec)


class KernelRerunTest(unittest.TestCase):
    def rerun(self, run):
        with mock.patch.dict(sys.modules, {'harness.kernel': types.ModuleType('harness.kernel')}), \
                mock.patch.object(tabletop, 'check_kernel_unchanged'):
            tabletop.kernel(run)

    def test_interrupted_episode_voids_the_batch_and_is_never_rerun(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            for name, value in (('tasks.json', [{'id': 'a', 'template': 'TP01', 'ready': True}]),
                                ('kernel.json', {}), ('config.json', {})):
                (run / name).write_text(json.dumps(value))
            (run / 'episodes/a/engineering').mkdir(parents=True)
            (run / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in (
                {'event': 'physical_started', 'task': 'a', 'arm': 'negative'},
                {'event': 'physical_completed', 'task': 'a', 'arm': 'negative', 'success': False},
                {'event': 'physical_started', 'task': 'a', 'arm': 'engineering'})))
            with self.assertRaisesRegex(RuntimeError, "INTERRUPTED: \\[\\('a', 'engineering'\\)\\]"):
                self.rerun(run)
            with self.assertRaisesRegex(RuntimeError, 'BATCH_INVALID'):
                self.rerun(run)
            log = tabletop.events(run)
            self.assertEqual([e['reason'] for e in log if e['event'] == 'batch_invalid'], ['INTERRUPTED'])
            self.assertEqual(sum(e['event'] == 'physical_started' for e in log), 2)


class ReportTest(unittest.TestCase):
    def run_folder(self, folder, *events):
        run = Path(folder)
        (run / 'tasks.json').write_text(json.dumps([{'id': 'a', 'template': 'TP01', 'bucket': 'near', 'ready': True}]))
        (run / 'tasks/a').mkdir(parents=True)
        (run / 'tasks/a/instance.json').write_text(json.dumps({'objects': [{'is_target': True, 'position_m': [.34, .32, 0]}]}))
        (run / 'kernel.json').write_text(json.dumps({'version': 'K_v1'}))
        (run / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
        return run

    def report(self, run):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            tabletop.report(run)
        return out.getvalue()

    done = {'event': 'physical_completed', 'task': 'a', 'arm': 'engineering', 'success': False}

    def test_rerun_of_a_finished_report_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as folder:
            run = self.run_folder(folder, self.done)
            self.report(run)
            before = (run / 'report.json').read_text()
            self.report(run)
            self.assertEqual((run / 'report.json').read_text(), before)

    def test_old_run_report_is_never_rewritten(self):
        # Stage-0 _002 kept a report without reach buckets; rerunning report would have replaced it.
        with tempfile.TemporaryDirectory() as folder:
            run = self.run_folder(folder, self.done)
            (run / 'report.json').write_text(json.dumps({'kernel': 'K_v1', 'tasks': {'TP01': {}}}))
            before = (run / 'report.json').read_text()
            with self.assertRaisesRegex(FileExistsError, 'read-only'):
                self.report(run)
            self.assertEqual((run / 'report.json').read_text(), before)

    def test_report_during_the_batch_does_not_block_the_final_report(self):
        # RunLifecycle FinalReportAlwaysWritten: report by hand mid-batch, then the batch finishes.
        with tempfile.TemporaryDirectory() as folder:
            run = self.run_folder(folder)
            self.assertIn('PARTIAL', self.report(run))
            self.assertFalse((run / 'report.json').exists())
            with (run / 'events.jsonl').open('a') as stream:
                stream.write(json.dumps(self.done) + '\n')
            self.report(run)
            self.assertEqual(json.loads((run / 'report.json').read_text())['batch_invalid'], [])

    def test_invalid_batch_prints_no_success_rate(self):
        with tempfile.TemporaryDirectory() as folder:
            run = self.run_folder(folder, {'event': 'batch_invalid', 'reason': 'NEGATIVE_CONTROL_FAILED'})
            printed = self.report(run)
            self.assertIn('BATCH_INVALID NEGATIVE_CONTROL_FAILED', printed)
            self.assertNotIn('full success', printed)
            self.assertEqual(json.loads((run / 'report.json').read_text())['batch_invalid'], ['NEGATIVE_CONTROL_FAILED'])


if __name__ == '__main__':
    unittest.main()
