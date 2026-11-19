import contextlib
import io
import json
import os
import shutil
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

    def test_agent_decision_logs_join_the_comparison_without_cache_use(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / 'a', Path(folder) / 'b'
            for f, cached in ((a, False), (b, True)):
                f.mkdir()
                for name in ('integration_states.npz', 'boundary_states.npz'):
                    np.savez_compressed(f / name, state=np.zeros((1, 2)))
                for name in ('actions.json', 'execution.json', 'tools.json'):
                    (f / name).write_text('[]')
                (f / 'verdict.json').write_text(json.dumps({'trajectory_sha256': str(cached)}))
                (f / 'result.json').write_text(json.dumps(dict(success=False, error=None, commands=3, worker_calls=1,
                                                               simulation_s=1.)))
                (f / 'decisions.json').write_text(json.dumps([{'text': '{"stop": "done"}', 'cached': cached,
                                                                'wall_time_s': 0. if cached else 4.}]))
            self.assertTrue(tabletop.same_episode(a, b)['decisions.json'])
            (b / 'decisions.json').write_text(json.dumps([{'text': '{"stop": "give_up"}', 'cached': True}]))
            self.assertFalse(tabletop.same_episode(a, b)['decisions.json'])


class VlmScoringTest(unittest.TestCase):
    def test_colour_baseline_finds_the_largest_matching_component(self):
        import numpy as np
        image = np.zeros((20, 30, 3), np.uint8)
        image[2:4, 2:4] = (200, 20, 15)
        image[10:16, 20:26] = (180, 15, 10)
        image[10:16, 5:9] = (20, 60, 200)
        self.assertEqual(tabletop.colour_baseline(image, [.69, .055, .037, 1.], min_pixels=5), [22.5, 12.5])
        self.assertIsNone(tabletop.colour_baseline(image, [.69, .055, .037, 1.], min_pixels=40))

    def test_hit_needs_a_target_pixel_and_confident_misses_are_counted(self):
        mask = [[False] * 4, [False, True, True, False]]
        answer = {'outcome': 'answer', 'point_px': [1.6, 1.2], 'confidence': .9}
        self.assertEqual(tabletop.score(answer, mask, .7), {'outcome': 'answer', 'hit': True, 'high_confidence_error': False})
        miss = dict(answer, point_px=[3.5, 1.5])
        self.assertTrue(tabletop.score(miss, mask, .7)['high_confidence_error'])
        self.assertFalse(tabletop.score(dict(miss, confidence=.5), mask, .7)['high_confidence_error'])
        self.assertFalse(tabletop.score({'outcome': 'abstain'}, mask, .7)['hit'])


class NodeRowsTest(unittest.TestCase):
    def test_last_checkpoint_marks_the_failed_node(self):
        checkpoints = [{'done': k} for k in range(5)]
        trial = {4: {'attribution': {'class': 'untestable'}}}
        rows = tabletop.node_rows('TP01', checkpoints, {'stage': 'approach'}, trial)
        self.assertEqual([r['passed'] for r in rows], [True] * 4 + [False])
        self.assertEqual(rows[-1], {'node': 4, 'passed': False, 'attribution': {'class': 'untestable'}})
        self.assertEqual(len(tabletop.node_rows('TP01', [{'done': k} for k in range(8)], None, {})), 7)
        self.assertEqual(tabletop.node_rows('TP01', [], {'stage': 'hand_open'}, {}), [])


class SweepTest(unittest.TestCase):
    @staticmethod
    def record(call, ok, args=None, executed=True, outcome=None):
        return {'decision': {'call': call, 'args': args or {}},
                'outcome': dict({'executed': executed, 'ok': ok}, **(outcome or {}))}

    def test_first_locates_stop_at_the_first_grasp_and_skip_refused_calls(self):
        vlm = {'method': 'vlm', 'query': 'the red fruit on the table'}
        decisions = [self.record('locate', False, {'method': 'colour'}), self.record('grasp', False, executed=False),
                     self.record('locate', True, vlm), self.record('grasp', False),
                     {'decision': {'retry': True}, 'outcome': {'executed': True, 'ok': True}},
                     self.record('locate', True, {'method': 'colour'})]
        self.assertEqual(tabletop.first_locates(decisions), [{'method': 'colour'}, vlm])

    def test_screen_row_names_the_stop_guard_contact_and_preflight_stages(self):
        guard = {'failure': {'message': 'approach_open_04: STOPPED', 'guard': 'FORBIDDEN_CONTACT'},
                 'stages': ['preflight', 'prepare', 'preflight', 'approach'],
                 'diagnosis': {'guard_detail': {'robot_link': 'left_wrist_yaw_link', 'touched': 'distractor_2',
                                                'palm_position_pelvis_m': [.27, .36, .3]}}}
        row = tabletop.screen_row([self.record('locate', True), self.record('grasp', False, outcome=guard)], None, None)
        self.assertEqual((row['nodes'], row['failed_node'], row['stopped'], row['guard'], row['touched'],
                          row['speed_joints']),
                         (['locate', 'grasp'], 'grasp', 'approach_open_04: STOPPED', 'FORBIDDEN_CONTACT',
                          'distractor_2', None))
        rejected = {'failure': {'message': 'APPROACH_PREFLIGHT_REJECTED'}, 'stages': ['preflight']}
        preflight = {'trials': [{'failed_at': {'stage': 'orient_clear'}}, {'failed_at': {'stage': 'above_target'}},
                                {'failed_at': {'stage': 'orient_clear'}}]}
        grasp = [self.record('locate', True), self.record('grasp', False, outcome=rejected)]
        row = tabletop.screen_row(grasp, {'reachable': False, 'reason': 'trials failed'}, preflight)
        self.assertEqual((row['preflight_reason'], row['preflight_failed_at']),
                         ('trials failed', ['above_target', 'orient_clear']))
        # The first preflight only previews the preparation move and writes no trials file.
        row = tabletop.screen_row(grasp, {'reachable': False, 'reason': 'preparation preview failed'}, None)
        self.assertEqual((row['preflight_reason'], row['preflight_failed_at']), ('preparation preview failed', None))
        done = tabletop.screen_row([self.record('locate', True), self.record('grasp', True)], None, None)
        self.assertEqual((done['failed_node'], done['stopped']), (None, None))

    def test_unregistered_or_oversized_plans_stop_before_creating_a_run(self):
        base = {'output': 'outputs/never_created_sweep', 'prediction': ['p'], 'falsification': ['f'],
                'episode_caps': {'brain_calls': 12}, 'tasks_from': 'outputs/x', 'caps': {'episodes': 3},
                'candidates': {'top_down': {'approach_mode': 'top_down'}}, 'plan': {'TP04_near_1': ['top_down']}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            for change, message in (({'prediction': []}, 'missing preregistration'),
                                    ({'plan': {'TP04_near_1': ['other']}}, 'unknown candidate'),
                                    ({'candidates': {'baseline': {}}, 'plan': {'TP04_near_1': ['baseline']}},
                                     'called baseline'),
                                    ({'caps': {'episodes': 1}}, 'exceeds caps.episodes')):
                path.write_text(json.dumps({**base, **change}))
                with self.assertRaisesRegex(ValueError, message):
                    tabletop.sweep(path)
            self.assertFalse((tabletop.ROOT / base['output']).exists())


class PrepareTest(unittest.TestCase):
    def test_missing_preregistration_stops_before_creating_a_run(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            path.write_text(json.dumps({'output': 'outputs/never_created', 'instances': {'TP01': []}}))
            with self.assertRaisesRegex(ValueError, 'missing preregistration'):
                tabletop.prepare(path)
            self.assertFalse((tabletop.ROOT / 'outputs/never_created').exists())

    def test_agent_arm_needs_a_brain_and_known_arms(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            base = {'output': 'outputs/never_created', 'instances': {'TP01': ['x']}, 'kernel_bundle': 'b',
                    'prediction': ['x'], 'falsification': ['x'], 'baselines': {'x': 1}, 'caps': {'wall_s': 1},
                    'episode_caps': {'simulation_s': 1}}
            for arms, message in ((['agent'], 'brain'), (['engineering', 'push'], 'arms'), ([], 'arms'),
                                  (['agent', 'agent'], 'arms')):
                path.write_text(json.dumps({**base, 'arms': arms}))
                with self.assertRaisesRegex(ValueError, message):
                    tabletop.prepare(path)
            no_forks = {**base, 'arms': ['agent'], 'brain': {'model': 'm'},
                        'episode_caps': {'simulation_s': 1, 'brain_calls': 4}}
            path.write_text(json.dumps(no_forks))
            with self.assertRaisesRegex(ValueError, 'forks'):
                tabletop.prepare(path)
            self.assertFalse((tabletop.ROOT / 'outputs/never_created').exists())

    def test_agent_resume_check_needs_a_brain_and_a_decision_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            base = {'output': 'outputs/never_created', 'column': 'agent', 'prediction': ['x'], 'falsification': ['x'],
                    'tasks': ['t'], 'tasks_from': 'outputs/none', 'episode_caps': {'simulation_s': 1}}
            for config, missing in ((base, 'brain'), ({**base, 'brain': {'model': 'm'}}, 'brain_calls'),
                                    ({**base, 'brain': {'model': 'm'}, 'episode_caps': {'brain_calls': 4}}, 'forks')):
                path.write_text(json.dumps(config))
                with self.assertRaisesRegex(ValueError, 'missing preregistration: .*' + missing):
                    tabletop.checkpoints(path)
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
    # The E2 rerun against the runs registered before it; later replications (e.g. the K2 G0 rerun) add to the live set.
    EARLIER = ('tabletop_kernel_near_20261113_001.json', 'tabletop_kernel_near_20261115_001.json',
               'tabletop_kernel_near_20261115_002.json')

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.configs = Path(folder.name)
        for name in self.EARLIER:
            shutil.copy(tabletop.CONFIGS / name, self.configs / name)

    def config(self, name):
        return json.loads((tabletop.CONFIGS / name).read_text())

    def test_e2_rerun_reuses_stage0_seeds_and_must_declare_it(self):
        config = self.config('tabletop_kernel_near_20261115_002.json')
        self.assertEqual(set(tabletop.seed_reuse(config, self.configs)), {'outputs/tabletop_kernel_near_20261113_001',
                                                                          'outputs/tabletop_kernel_near_20261115_001'})
        config['replicates'] = ['outputs/tabletop_kernel_near_20261113_001', 'outputs/tabletop_kernel_near_20261115_001']
        self.assertEqual(tabletop.seed_reuse(config, self.configs), {})

    def test_replication_cannot_change_the_generate_spec(self):
        config = self.config('tabletop_kernel_near_20261115_002.json')
        config['replicates'] = ['outputs/tabletop_kernel_near_20261113_001', 'outputs/tabletop_kernel_near_20261115_001']
        config['generate'] = {**config['generate'], 'count': 9}
        self.assertEqual(len(tabletop.seed_reuse(config, self.configs)), 2)

    def test_k2_g0_rerun_declares_every_earlier_near_run(self):
        self.assertEqual(tabletop.seed_reuse(self.config('tabletop_kernel_near_20261117_001.json')), {})

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


class KernelPackageTest(unittest.TestCase):
    package = {'primitive': 'p', 'prompt_sha256': 's', 'lift': 'l',
               'vlm': {'endpoint': 'e', 'model': 'm', 'digest': 'd', 'ollama': '1', 'options': {}}}

    def spec(self, live, hand_rule=None):
        import harness
        from harness import vlm_locate
        kernel = types.SimpleNamespace(VERSION='K_v1', VLM_VERSION='K_v2', TOOLS={}, CHAINS={}, CHECKS={}, LEAVES={})
        library = types.SimpleNamespace(read_bundle=lambda path: {'bundle_id': 'b@1', 'components': {}, 'sources': {}})
        hand = types.SimpleNamespace(VERSION='palm-v2')
        reads = {tabletop.ROOT / tabletop.OBJECT_RECIPE: {'recipe': {}}, tabletop.ROOT / 'k.json': self.package}
        with mock.patch.dict(sys.modules, {'harness.kernel': kernel, 'harness.library': library,
                                           'harness.hand_support': hand}), \
                mock.patch.object(harness, 'kernel', kernel, create=True), \
                mock.patch.object(harness, 'library', library, create=True), \
                mock.patch.object(harness, 'hand_support', hand, create=True), \
                mock.patch.object(vlm_locate, 'identity', return_value=live), \
                mock.patch.object(vlm_locate, 'LIFT', live.get('lift', 'l')), \
                mock.patch.object(tabletop, 'read', side_effect=reads.__getitem__), \
                mock.patch.object(tabletop, 'sha', return_value='h'):
            return tabletop.kernel_spec('b.json', 'k.json', hand_rule)

    def test_package_matching_the_live_model_makes_a_k_v2_spec(self):
        spec = self.spec({'digest': 'd', 'ollama': '1', 'primitive': 'p', 'prompt_sha256': 's', 'size': 3})
        self.assertEqual(spec['version'], 'K_v2')
        self.assertEqual((spec['vlm']['digest'], spec['vlm']['package']), ('d', {'path': 'k.json', 'sha256': 'h'}))

    def test_other_weights_or_server_stop_prepare(self):
        for changed in ({'digest': 'x'}, {'ollama': '2'}, {'prompt_sha256': 't'}, {'lift': 'older'}):
            live = {'digest': 'd', 'ollama': '1', 'primitive': 'p', 'prompt_sha256': 's', **changed}
            with self.assertRaisesRegex(RuntimeError, 'VLM_PACKAGE_MISMATCH'):
                self.spec(live)

    def test_resume_check_reads_the_recorded_package(self):
        recorded = {'version': 'K_v2', 'bundle': {'path': 'b.json'}, 'vlm': {'package': {'path': 'k.json'}},
                    'hand_rule': 'palm-v2'}
        with mock.patch.object(tabletop, 'kernel_spec', return_value=recorded) as live:
            tabletop.check_kernel_unchanged(recorded)
        live.assert_called_once_with('b.json', 'k.json', 'palm-v2')

    def test_hand_rule_is_recorded_only_when_it_is_the_implemented_one(self):
        live = {'digest': 'd', 'ollama': '1', 'primitive': 'p', 'prompt_sha256': 's'}
        self.assertNotIn('hand_rule', self.spec(live))
        self.assertEqual(self.spec(live, 'palm-v2')['hand_rule'], 'palm-v2')
        with self.assertRaisesRegex(ValueError, 'not the implemented palm-v2'):
            self.spec(live, 'palm-v3')


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
        (run / 'config.json').write_text(json.dumps({}))
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

    def test_hand_rule_run_reports_the_v1_count_alongside(self):
        with tempfile.TemporaryDirectory() as folder:
            run = self.run_folder(folder, {**self.done, 'success': True})
            (run / 'kernel.json').write_text(json.dumps({'version': 'K_v2', 'hand_rule': 'palm-v2'}))
            (run / 'episodes/a/engineering').mkdir(parents=True)
            (run / 'episodes/a/engineering/tools.json').write_text(json.dumps([row('grasp', True, True)]))
            (run / 'episodes/a/engineering/result.json').write_text(json.dumps({'success': True, 'success_v1': False}))
            self.assertIn('TP01/near: 1/1 full success, v1 hand rule 0 (listed 1)', self.report(run))
            saved = json.loads((run / 'report.json').read_text())
            self.assertEqual((saved['hand_rule'], saved['tasks']['TP01/near']['success_v1']), ('palm-v2', 0))

    def test_two_arm_run_waits_for_both_and_pairs_them(self):
        with tempfile.TemporaryDirectory() as folder:
            run = self.run_folder(folder, self.done)
            (run / 'config.json').write_text(json.dumps({'arms': ['engineering', 'agent']}))
            self.assertIn('PARTIAL', self.report(run))
            for arm, success in (('engineering', False), ('agent', True)):
                out = run / 'episodes/a' / arm
                out.mkdir(parents=True)
                (out / 'tools.json').write_text(json.dumps([row('grasp', True, success)]))
                error = None if success else {'type': 'ActionFailure', 'stage': 'approach'}
                (out / 'result.json').write_text(json.dumps({'success': success, 'error': error, 'agent': {
                    'nodes': ['locate', 'locate', 'grasp'], 'stop': 'done', 'brain_calls': 4}}))
            (run / 'episodes/a/agent/decisions.json').write_text(json.dumps([
                {'decision': {'call': 'locate', 'args': {'method': 'colour'}}, 'outcome': {'executed': True, 'ok': False}},
                {'decision': {'call': 'grasp', 'args': {}}, 'outcome': {'executed': False, 'ok': False}},
                {'decision': {'call': 'locate', 'args': {'method': 'vlm', 'query': 'q'}},
                 'outcome': {'executed': True, 'ok': True}},
                {'decision': {'stop': 'done'}, 'outcome': None}]))
            with (run / 'events.jsonl').open('a') as stream:
                stream.write(json.dumps({**self.done, 'arm': 'agent', 'success': True}) + '\n')
            printed = self.report(run)
            self.assertIn('== agent column', printed)
            saved = json.loads((run / 'report.json').read_text())
            self.assertEqual(saved['column'], 'engineering + agent')
            self.assertEqual({a: c['tasks']['TP01/near']['success'] for a, c in saved['columns'].items()},
                             {'engineering': 0, 'agent': 1})
            (pair,) = saved['pairs']
            self.assertEqual(pair['engineering']['error'], 'ActionFailure@approach')
            self.assertEqual((pair['agent']['locate'], pair['agent']['refused'], pair['agent']['stop']),
                             (['colour', 'vlm'], 1, 'done'))
            self.assertFalse(pair['equivalent'])
            self.assertNotIn('physics_equal', pair)

    def test_agent_only_run_counts_success_after_retry_apart_from_the_first_pass(self):
        with tempfile.TemporaryDirectory(dir=tabletop.ROOT / 'outputs') as folder:
            agent_done = {**self.done, 'arm': 'agent'}
            run = self.run_folder(folder, agent_done)
            (run / 'config.json').write_text(json.dumps({'arms': ['agent']}))
            out, branch = run / 'episodes/a/agent', run / 'episodes/a/agent/branches/01'
            branch.mkdir(parents=True)
            first = [{'decision': {'call': 'locate', 'args': {'method': 'colour'}}, 'outcome': {'executed': True, 'ok': True}},
                     {'decision': {'call': 'grasp', 'args': {}}, 'outcome': {'executed': True, 'ok': False}},
                     {'decision': {'retry': True}, 'outcome': {'executed': True, 'ok': True}}]
            (out / 'decisions.json').write_text(json.dumps(first))
            (out / 'tools.json').write_text(json.dumps([row('locate', True, True), row('grasp', False, False)]))
            (out / 'result.json').write_text(json.dumps({'success': False, 'error': None, 'agent': {
                'nodes': ['locate', 'grasp'], 'stop': 'retry', 'brain_calls': 3}}))
            (branch / 'result.json').write_text(json.dumps({'success': True, 'error': None, 'agent': {
                'nodes': ['locate', 'locate', 'grasp'], 'stop': 'done', 'brain_calls': 6}}))
            resumed = 'outputs/x/episodes/a/agent/checkpoints/01_locate.pkl.gz'
            (out / 'retry.json').write_text(json.dumps({'branches': [
                {'folder': str(branch.relative_to(tabletop.ROOT)), 'resumed': resumed}], 'success': True, 'error': None}))
            printed = self.report(run)
            self.assertIn('TP01/near: 0/1 full success, after retries 1 (1 forks) (listed 1)', printed)
            saved = json.loads((run / 'report.json').read_text())
            self.assertEqual((saved['tasks']['TP01/near']['success'], saved['tasks']['TP01/near']['success_after_retry']),
                             (0, 1))
            (pair,) = saved['pairs']
            self.assertEqual(pair['agent']['locate'], ['colour'])
            self.assertEqual(pair['agent']['retry'], {'forks': 1, 'success': True, 'branches': [
                {'resumed': '01_locate', 'nodes': ['locate', 'locate', 'grasp'], 'stop': 'done', 'success': True,
                 'error': None}]})
            self.assertNotIn('equivalent', pair)

    def test_equivalent_pair_compares_only_the_physical_records(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            for arm, error in (('engineering', {'type': 'ActionFailure', 'stage': 'approach'}), ('agent', None)):
                out = run / 'episodes/a' / arm
                out.mkdir(parents=True)
                for name in ('integration_states.npz', 'boundary_states.npz'):
                    np.savez_compressed(out / name, state=np.ones((1, 2)))
                (out / 'actions.json').write_text('[]')
                (out / 'execution.json').write_text(json.dumps({'error': error}))
                (out / 'tools.json').write_text(json.dumps([row('locate', True, True), row('grasp', False, False)]))
                (out / 'verdict.json').write_text(json.dumps({'trajectory_sha256': arm}))
                (out / 'result.json').write_text(json.dumps({'success': False, 'error': error, 'commands': 1,
                    'worker_calls': 1, 'simulation_s': 1., 'agent': {'nodes': ['locate', 'grasp'], 'stop': 'give_up',
                                                                     'brain_calls': 3}}))
            (run / 'episodes/a/agent/decisions.json').write_text(json.dumps([
                {'decision': {'call': 'locate', 'args': {'method': 'colour'}}, 'outcome': {'executed': True, 'ok': True}},
                {'decision': {'call': 'grasp', 'args': {}}, 'outcome': {'executed': True, 'ok': False}},
                {'decision': {'stop': 'give_up'}, 'outcome': None}]))
            got = tabletop.pair(run, {'id': 'a', 'template': 'TP01', 'bucket': 'near'}, ['engineering', 'agent'])
            self.assertEqual((got['equivalent'], got['physics_equal']), (True, True))
            np.savez_compressed(run / 'episodes/a/agent/boundary_states.npz', state=np.zeros((1, 2)))
            got = tabletop.pair(run, {'id': 'a', 'template': 'TP01', 'bucket': 'near'}, ['engineering', 'agent'])
            self.assertFalse(got['physics_equal'])

    def test_invalid_batch_prints_no_success_rate(self):
        with tempfile.TemporaryDirectory() as folder:
            run = self.run_folder(folder, {'event': 'batch_invalid', 'reason': 'NEGATIVE_CONTROL_FAILED'})
            printed = self.report(run)
            self.assertIn('BATCH_INVALID NEGATIVE_CONTROL_FAILED', printed)
            self.assertNotIn('full success', printed)
            self.assertEqual(json.loads((run / 'report.json').read_text())['batch_invalid'], ['NEGATIVE_CONTROL_FAILED'])


if __name__ == '__main__':
    unittest.main()
