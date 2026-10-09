"""Independent analytic joint-mode contract for the locked native evaluator."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from motion.cli import motion_native_cli_test as single_cli


class MotionJointCliTests(unittest.TestCase):
    def fixture(self, root):
        command = single_cli.MotionNativeCliTests().fixture(root)
        scene = root / 'scenario.textproto'
        original = scene.read_text()
        track = original.split(' tracks { ', 1)[1].split(' } tracks_to_predict', 1)[0]
        second = track.replace('id: 1 ', 'id: 2 ', 1).replace('center_y: 0', 'center_y: 10')
        scene.write_text(original + ' tracks { ' + second +
                         ' } tracks_to_predict { track_index: 1 difficulty: LEVEL_1 }')
        config = root / 'config.textproto'
        config.write_text(config.read_text().replace('max_predictions: 1', 'max_predictions: 2'))
        prediction = 'scenario_id: "analytic" multi_modal_predictions { '
        for offsets in [(0, 4), (4, 0)]:
            prediction += 'joint_predictions { confidence: 0.5 '
            for object_id, offset in enumerate(offsets, 1):
                prediction += 'trajectories { object_id: ' + str(object_id) + ' '
                prediction += ' '.join('center_x: ' + str((15+i*5)/10+offset) +
                                       ' center_y: ' + str((object_id-1)*10) for i in range(16))
                prediction += ' } '
            prediction += ' } '
        (root/'predictions.textproto').write_text(prediction + ' }')
        return command

    def test_shared_mode_average_precedes_minimization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = subprocess.run(self.fixture(root), capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads((root/'result.json').read_text())
            vehicle = single_cli.vehicle_metrics(output)
            self.assertAlmostEqual(vehicle['minAde'], 2, places=5)
            self.assertAlmostEqual(vehicle['minFde'], 2, places=5)
            count = vehicle['counts']
            self.assertEqual(count['min_ade'], 1)
            self.assertEqual(count['min_fde'], 1)

    def test_inconsistent_joint_target_ids_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            command = self.fixture(root)
            prediction = root/'predictions.textproto'
            prediction.write_text(prediction.read_text().replace('object_id: 2', 'object_id: 1', 1))
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root/'result.json').exists())


if __name__ == '__main__':
    unittest.main()
