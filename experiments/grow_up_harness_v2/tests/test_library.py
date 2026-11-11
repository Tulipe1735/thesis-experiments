import contextlib
import copy
import io
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from harness import artifact_mapping as M, artifact_v2 as A, t03_evaluator as E
from harness import artifact as V1
from harness.library import Library, read_bundle, write_bundle
from calibration import artifacts, t03, t03_focus

LIBRARY = M.ROOT / 'experiments/grow_up_harness_v2/library'


class LibraryTests(unittest.TestCase):
    def test_t01_freeze_does_not_require_its_historical_initial_files(self):
        with patch.object(V1, 'load', side_effect=AssertionError('historical initial consulted')):
            bundle = Library(LIBRARY).freeze('t01')
        self.assertEqual(bundle['family'], 'T01')

    def test_imported_programs_keep_original_artifact_refs_and_code(self):
        config = json.loads((M.ROOT / 'experiments/grow_up_harness_v2/configs/artifact_mapping_repair_20261110.json').read_text())
        for name, family in [('t01', 'T01'), ('t02', 'T02')]:
            frozen = Library(LIBRARY).freeze(name)
            original = M.project(family, config[family])
            self.assertEqual(frozen['ref'], original.ref)
            self.assertEqual(frozen['views']['code'], original.code)
        for name, run in [('t03_base', 't03_frozen_eval_20261111_001'),
                          ('t03_temporal', 't03_locate_scale_20261111_006'),
                          ('t03_route', 't03_obstacle_leaf_20261111_001'),
                          ('t03_pose', 't03_obstacle_pose_20261111_001')]:
            path = M.ROOT / 'experiments/grow_up_harness_v2/runs' / run
            root = json.loads((path / 'root.json').read_text())
            original = M.project('T03', {'store': str(path / 'store'), 'artifact_ref': root['ref']})
            # Migration compatibility uses the historical recipe as a fixture;
            # the working library is intentionally editable after migration.
            with tempfile.TemporaryDirectory() as directory:
                fixture = Path(directory) / 'library'
                shutil.copytree(LIBRARY, fixture)
                grasp = yaml.safe_load((path / 'store/artifacts' /
                                       (root['components']['grasp_ref'] + '.yaml')).read_text())
                digest = grasp['implementation']['source_sha256']
                source = (path / 'store/sources' / (digest + '.py')).read_text()
                grasp['implementation'] = {'language': 'python', 'source': 't03_adaptive_recipe.py'}
                (fixture / 'artifacts/t03_adaptive_recipe.yaml').write_text(yaml.safe_dump(grasp))
                (fixture / 'artifacts/t03_adaptive_recipe.py').write_text(source)
                frozen = Library(fixture).freeze(name)
            # Runtime executes only leaf sources and runtime versions; node placement and
            # contract wording are metadata, so compatibility is checked on what executes.
            self.assertEqual(frozen['components'].keys(), root['components'].keys())
            for role, old in root['components'].items():
                new = frozen['components'][role]
                if not role.endswith('_ref'):
                    self.assertEqual(new, old)
                    continue
                stored = yaml.safe_load((path / 'store/artifacts' / (old + '.yaml')).read_text())
                self.assertEqual(frozen['artifacts'][new]['implementation']['source_sha256'],
                                 stored['implementation']['source_sha256'], (name, role))
            self.assertTrue(original.code)

    def test_t03_roots_sit_on_task_node_and_leaves_chain_by_contract(self):
        library = Library(LIBRARY)
        bundle = library.freeze('t03_pose')
        artifacts = bundle['artifacts']
        self.assertEqual(artifacts[bundle['ref']]['task_node'], 'T03')
        leaf_nodes = {artifacts[r]['task_node'] for k, r in bundle['components'].items() if k.endswith('_ref')}
        self.assertNotIn('T03', leaf_nodes)
        order = ['locate_ref', 'approach_ref', 'grasp_ref', 'placement_ref', 'finish_ref']
        for before, after in zip(order, order[1:]):
            post = set(artifacts[bundle['components'][before]]['contract']['post'])
            pre = set(artifacts[bundle['components'][after]]['contract']['pre'])
            self.assertTrue(post & pre, (before, after))

    def test_moving_library_and_leaf_files_preserves_release_identity(self):
        original = Library(LIBRARY).freeze('t03_pose')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'moved'
            shutil.copytree(LIBRARY, root)
            library = Library(root)
            key = library.tree['programs']['t03_pose']['components']['locate_ref']
            old = root / library.tree['artifacts'][key]
            data = yaml.safe_load(old.read_text())
            source = old.parent / data['implementation']['source']
            target = root / 'perception'
            target.mkdir()
            source.rename(target / 'selector.py')
            data['implementation']['source'] = 'selector.py'
            (target / 'selector.yaml').write_text(yaml.safe_dump(data))
            old.unlink()
            library.tree['artifacts'][key] = 'perception/selector.yaml'
            library.save_tree()
            self.assertEqual(Library(root).freeze('t03_pose'), original)

    def test_leaf_edit_changes_only_that_component_and_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(LIBRARY, root, dirs_exist_ok=True)
            library = Library(root)
            before = library.freeze('t03_pose')
            key = library.tree['programs']['t03_pose']['components']['locate_ref']
            metadata = root / library.tree['artifacts'][key]
            source = metadata.parent / yaml.safe_load(metadata.read_text())['implementation']['source']
            source.write_text(source.read_text() + '\n# explicit new candidate revision\n')
            after = library.freeze('t03_pose')
            changed = {k for k in before['components'] if before['components'][k] != after['components'][k]}
            self.assertEqual(changed, {'locate_ref'})
            self.assertNotEqual(before['ref'], after['ref'])
            self.assertNotEqual(before['bundle_id'], after['bundle_id'])

    def test_unused_artifacts_and_provenance_parents_are_not_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(LIBRARY, root, dirs_exist_ok=True)
            library = Library(root)
            before = library.freeze('t03_pose')
            (root / 'unrelated.py').write_text('does not even parse !!!')
            (root / 'artifacts/hand_open.yaml').parent.joinpath('unrelated.yaml').write_text('invalid: [')
            self.assertEqual(library.freeze('t03_pose'), before)
            self.assertEqual(len(before['artifacts']), 7)
            self.assertNotIn('store', json.dumps(before['views']['manifest']['provenance']))

    def test_bundle_load_needs_no_library_store_or_hash_scan(self):
        frozen = Library(LIBRARY).freeze('t03_pose')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bundle.json'
            write_bundle(path, frozen)
            with patch.object(A, 'Store', side_effect=AssertionError('old store consulted')), \
                    patch('hashlib.sha256', side_effect=AssertionError('hashing on load')):
                mapped = M.project('T03', {'bundle': path})
                self.assertEqual(mapped.code, frozen['views']['code'])
            self.assertEqual(artifacts.verify(path), frozen['bundle_id'])
            with self.assertRaises(FileExistsError):
                write_bundle(path, frozen)

    def test_explicit_verification_detects_bundle_corruption(self):
        frozen = Library(LIBRARY).freeze('t03_pose')
        frozen['views']['code'] += '\nchanged = True\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bundle.json'
            write_bundle(path, frozen)
            with self.assertRaisesRegex(ValueError, 'content changed'):
                artifacts.verify(path)


class RunnerTests(unittest.TestCase):
    def config(self):
        return {'focuses': [{'stage': 'preflight', 'mechanism_trigger': 'default route rejected by observed can clearance'}],
                'handoff': {}, 'caps': {'wall_s': 1000, 'physical_episodes': 4, 'model_calls': 0}}

    def test_only_registered_stage_changes_are_allowed(self):
        library = Library(LIBRARY)
        bundles = {'parent': library.freeze('t03_route'), 'candidate': library.freeze('t03_pose')}
        t03.validate_bundles(self.config(), bundles)
        changed = copy.deepcopy(bundles)
        changed['candidate']['components']['grasp_ref'] = 'other@000000000000'
        with self.assertRaises(KeyError):
            t03.validate_bundles(self.config(), changed)
        config = self.config()
        config['focuses'][0]['stage'] = 'locate'
        with self.assertRaisesRegex(ValueError, 'outside focuses'):
            t03.validate_bundles(config, bundles)

    def test_unsupported_runtime_and_evaluator_are_rejected(self):
        bundle = Library(LIBRARY).freeze('t03_pose')
        for field, value in [('evaluator', 'other-evaluator'), ('components', {**bundle['components'], 'approach_runtime': 'unknown'})]:
            changed = copy.deepcopy(bundle)
            changed[field] = value
            with self.assertRaises(ValueError):
                t03.validate_bundles(self.config(), {'candidate': changed})

    def test_holdout_stays_closed_without_full_same_bundle_training_success(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / 'events.jsonl').write_text('')
            (run / 'artifacts.json').write_text(json.dumps({'candidate': {'bundle_id': 'current'}}))
            with patch.object(t03, 'generate') as generate:
                with self.assertRaisesRegex(RuntimeError, 'HOLDOUT_LOCKED'):
                    t03.batch(run, 'holdout')
                generate.assert_not_called()
            episode = run / 'train/task/code'
            episode.mkdir(parents=True)
            (episode / 'verdict.json').write_text(json.dumps({'verified_task_success': False, 'evaluator_version': E.VERSION}))
            (episode / 'root_binding.json').write_text(json.dumps({'bundle_id': 'current'}))
            self.assertFalse(t03.training_success(run))
            (episode / 'verdict.json').write_text(json.dumps({'verified_task_success': True, 'evaluator_version': E.VERSION}))
            (episode / 'root_binding.json').write_text(json.dumps({'bundle_id': 'other-candidate'}))
            self.assertFalse(t03.training_success(run))
            (episode / 'root_binding.json').write_text(json.dumps({'bundle_id': 'current'}))
            self.assertTrue(t03.training_success(run))

    def test_prepare_is_exclusive_and_does_not_require_old_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle_path = root / 'release.json'
            write_bundle(bundle_path, Library(LIBRARY).freeze('t03_pose'))
            config = {**self.config(), 'bundles': {'candidate': str(bundle_path)}, 'output': str(root / 'run'),
                'baselines': {k: 'declared' for k in ('negative', 'engineering_positive', 'original_failure', 'treatment')},
                'prediction': {'mapping': 'same source'}, 'falsification': ['mismatch'], 'consumed_dev_seeds': [],
                'train_seed_start': 713000, 'holdout_seed_start': 813000, 'train_count': 0, 'holdout_count': 0}
            path = root / 'config.json'
            path.write_text(json.dumps(config))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                run = t03.prepare(path)
                self.assertFalse((run / 'store').exists())
                self.assertNotIn('dependencies', json.loads((run / 'registration.json').read_text()))
                with self.assertRaises(FileExistsError):
                    t03.prepare(path)

    def test_direct_execution_cannot_bypass_negative_or_invalid_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / 'events.jsonl').write_text('')
            row = {'split': 'train', 'id': 'task'}
            with self.assertRaisesRegex(RuntimeError, 'NEGATIVE_CONTROL_REQUIRED'):
                t03.physical(run, row, 'code')
            (run / 'events.jsonl').write_text(json.dumps({'event': 'batch_invalid'}) + '\n')
            with self.assertRaisesRegex(RuntimeError, 'BATCH_INVALID'):
                t03.physical(run, row, 'code')

    def test_program_versions_dispatch_exact_frozen_components_to_their_native_executor(self):
        from harness import t03_finish as F, t03_locate_temporal as T
        from harness import t03_obstacle_approach as O, t03_obstacle_pose as P
        library = Library(LIBRARY)
        for name, executor, extra in [('t03_base', F, []), ('t03_temporal', T, ['locate_ref']),
                ('t03_route', O, ['locate_ref', 'approach_ref']), ('t03_pose', P, ['locate_ref', 'approach_ref'])]:
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                run = Path(directory)
                bundle = library.freeze(name)
                (run / 'config.json').write_text(json.dumps({**self.config(), 'episode_caps': {'simulation_s': 3}}))
                (run / 'registration.json').write_text(json.dumps({'start_epoch': time.time()}))
                (run / 'artifacts.json').write_text(json.dumps({'candidate': bundle}))
                (run / 'events.jsonl').write_text('')
                initial = run / 'tasks/train/task'
                initial.mkdir(parents=True)
                (initial / 'instance.json').write_text(json.dumps({'objects': [
                    {'is_target': True, 'asset': {'rgba': [1., .5, .1, 1.]}}]}))
                control = run / 'train/task/negative'
                control.mkdir(parents=True)
                (control / 'verdict.json').write_text(json.dumps({'verified_task_success': False}))
                row = {'split': 'train', 'id': 'task', 'ready': True, 'robot_initial_hash': 'saved'}
                result = {'success': False, 'error': None, 'initial_hash': 'saved'}
                def executed(*args):
                    args[1].mkdir(parents=True)
                    return result
                with patch.object(executor, 'execute', side_effect=executed) as execute:
                    self.assertEqual(t03.physical(run, row, 'code'), result)
                args = execute.call_args.args
                keys = ['grasp_ref', 'open_ref', 'placement_ref', 'finish_ref']
                expected = [bundle['sources'][bundle['artifacts'][bundle['components'][key]]
                    ['implementation']['source_sha256']] for key in keys + extra]
                self.assertEqual(list(args[2:6]) + list(args[7:]), expected)

    def test_negative_controls_are_excluded_from_focus_attribution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for arm in ('negative', 'code'):
                folder = root / 'train/task' / arm
                folder.mkdir(parents=True)
                (folder / 'verdict.json').write_text(json.dumps({'verified_task_success': False}))
            self.assertEqual([r['arm'] for r in t03_focus.episodes(root)], ['code'])

    def test_new_route_reports_attribute_selector_to_its_actual_preflight_hook(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / 'config.json').write_text(json.dumps(self.config()))
            episode = run / 'train/task/code'
            episode.mkdir(parents=True)
            (episode / 'verdict.json').write_text(json.dumps({'verified_task_success': False,
                'execution_error': {'stage': 'close_and_test'}}))
            (episode / 'obstacle_approach.json').write_text(json.dumps({'calls': [{'selected': 'top_down'}]}))
            (episode / 'root_binding.json').write_text(json.dumps({'decision_stages': {'approach': 'preflight'}}))
            focus, _card = t03_focus.focus_card(run)
            self.assertEqual(focus['by_focus']['preflight']['triggered'], 1)
            self.assertEqual(focus['by_focus']['preflight']['triggered_succeeded'], 0)


if __name__ == '__main__':
    unittest.main()
