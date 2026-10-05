"""Fixed host-only driver controls; no native/application effects."""
import importlib.util
from pathlib import Path
import unittest


class DriverControls(unittest.TestCase):
    def load(self):
        path = Path(__file__).with_name('preflight_driver.py')
        self.assertTrue(path.exists(), 'reviewed immediate preflight driver missing')
        spec = importlib.util.spec_from_file_location('driver', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_roles_have_literal_argv_and_no_shell_or_model_dispatch(self):
        driver = self.load()
        authority = {'fixture_id': 'probe-1', 'tools': {'python': '/pinned/python',
                     'systemd_run': '/pinned/systemd-run'}, 'driver_source': '/source/preflight_driver.py'}
        actual = driver.actor_argv(authority, 'observer', {'path': '/owned/base', 'sha256': 'a'*64},
                                   Path('/owned/authority'), Path('/owned/run'), Path('/owned/intent'))
        self.assertEqual(actual[:2], ['/pinned/systemd-run', '--user'])
        self.assertIn('MemoryMax=268435456', actual)
        self.assertIn('MemorySwapMax=0', actual)
        self.assertNotIn('shell', actual)
        self.assertIn('/source/preflight_driver.py', actual)
        for role in ('model', 'managed', '../bad'):
            with self.subTest(role=role), self.assertRaises(ValueError):
                driver.actor_argv(authority, role, {}, Path('/a'), Path('/b'), Path('/c'))

    def test_live_old_birth_is_preserved_as_alive(self):
        driver = self.load()
        self.assertTrue(hasattr(driver, 'post_process'), 'actual process exit readback missing')
        import os
        process = driver.guards.incarnation(os.getpid())
        proof = driver.post_process(process)
        self.assertTrue(proof['same_birth_alive'])
        self.assertEqual(proof['actual_process']['pid'], os.getpid())

    def test_actor_scope_and_original_clock_are_bound_without_reset(self):
        import time
        driver = self.load()
        self.assertTrue(hasattr(driver, 'actor_binding'), 'bounded actor binding missing')
        clock = {'started_ns': time.monotonic_ns(), 'started_ms': time.time_ns()//1000000,
                 'deadline_ms': 120000}
        base = {'kind': 'RuntimeProbeAdmission', 'resources': {}}
        actual = driver.actor_binding(base, 'observer', clock)
        self.assertEqual(actual['live_clock'], clock)
        self.assertIn('observer_scope', actual['resources'])
        self.assertNotIn('observer_scope', base['resources'])
        for role, bad in [('managed', base), ('operator', base)]:
            with self.subTest(role=role), self.assertRaises(ValueError):
                driver.actor_binding(bad, role, clock)
        with self.assertRaises(ValueError):
            driver.actor_binding(base, 'observer', {**clock, 'started_ns': clock['started_ns']-120000000001})

    def test_unreviewed_driver_authority_refuses_before_host_or_native_effects(self):
        driver = self.load()
        self.assertTrue(hasattr(driver, 'validate_driver'), 'driver admission gate missing')
        with self.assertRaises(ValueError):
            driver.validate_driver({'kind': 'ArbitraryCommandAdmission'}, 'live')

    def test_actual_failed_host_command_is_retained_with_no_retry(self):
        import sys
        import tempfile
        import json
        driver = self.load()
        self.assertTrue(hasattr(driver, 'HostCommand'), 'bounded actual host recorder missing')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            argv = [sys.executable, '-I', '-B', '-c', 'raise SystemExit(3)']
            child = driver.HostCommand(root, argv, 'component', str(root))
            ref = child.finish()
            proof = json.loads(Path(ref['path']).read_text())
            self.assertEqual(proof['exit_code'], 3)
            self.assertEqual(proof['argv'], argv)
            self.assertGreaterEqual(proof['ended_ms'], proof['started_ms'])
            self.assertTrue(Path(proof['stderr']['path']).exists())
            self.assertFalse(proof.get('native_stop_accepted', False))

    def test_exec_recipe_is_fixed_to_reviewed_role_program(self):
        driver = self.load()
        self.assertTrue(hasattr(driver, 'actor_program'), 'fixed actor exec recipe missing')
        base = {'auditor': {'source': '/admitted/observer'},
                'operator_source': {'path': '/admitted/fixture/native_stop_fixture.py'},
                'fixture_plan': {'tools': {'python': {'path': '/pinned/python'}}},
                'tools': {'python': {'path': '/pinned/python'}}}
        for role, probe in [('static', 'static-preflight'), ('observer', 'stop-capability')]:
            argv = driver.actor_program(base, role, Path('/owned/actual-auth'), Path('/owned/run'))
            self.assertEqual(argv[:3], ['/pinned/python', '-B',
                '/admitted/observer/tests/collab/audit_support/runtime_probe.py'])
            self.assertIn(probe, argv)
        with self.assertRaises(ValueError):
            driver.actor_program(base, 'managed', Path('/a'), Path('/b'))

    def test_orchestration_rejects_unadmitted_stage_before_output_creation(self):
        import tempfile
        driver = self.load()
        self.assertTrue(hasattr(driver, 'run_stage'), 'immediate handoff driver missing')
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/'not-created'
            with self.assertRaises(ValueError):
                driver.run_stage({'kind': 'ArbitraryCommandAdmission'}, 'live', output, {})
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
