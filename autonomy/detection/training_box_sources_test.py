"""Native-source completeness and geometry contracts, with literal expectations."""
import copy
from pathlib import Path
import tempfile
import unittest

from detection.training_box_sources import training_box_statistics_from_sources


def row(scene='a', timestamp=1, category=1, box=(0., 0., 10., 4., 2., 1., 0.)):
    names = ('center.x', 'center.y', 'center.z', 'size.x', 'size.y', 'size.z', 'heading')
    result = {f'[LiDARBoxComponent].box.{name}': value for name, value in zip(names, box)}
    result.update({'key.segment_context_name': scene, 'key.frame_timestamp_micros': timestamp,
                   'key.laser_object_id': 'track', '[LiDARBoxComponent].type': category})
    return result


class NativeSourceStatisticsTests(unittest.TestCase):
    def membership(self):
        return {s: {'official_split': 'training', 'research_splits': ['train']} for s in ['a', 'b', 'c']}

    def sources(self):
        return [
            {'scene': 'a', 'expected_rows': 3, 'rows': [row(), row(timestamp=2, box=(0., 0., 30., 8., 4., 3., 0.)),
                                                       row(timestamp=3, box=(0., 0., 50., 12., 6., 5., 0.))]},
            {'scene': 'b', 'expected_rows': 1, 'rows': [row(scene='b', category=0)]},
            {'scene': 'c', 'expected_rows': 0, 'rows': []},
        ]

    def run_sources(self, sources, membership=None, expected=None):
        return training_box_statistics_from_sources(
            sources, membership=self.membership() if membership is None else membership,
            expected_scenes=['a', 'b', 'c'] if expected is None else expected)

    def test_complete_native_statistics_include_empty_and_unknown_class_sources(self):
        report = self.run_sources(self.sources())
        self.assertEqual(report['completed_sources'], ['a', 'b', 'c'])
        self.assertEqual(report['native_rows'], 4)
        self.assertEqual(report['outside_box_class_counts'], {'0': 1})
        self.assertEqual(report['rows'], 3)
        self.assertEqual(report['classes']['1']['unique_tracks'], 1)
        self.assertEqual(report['classes']['1']['median_length_width_height_center_z'], [8., 4., 3., 30.])
        self.assertEqual(report['classes']['1']['p10_length_width_height_center_z'], [4.8, 2.4, 1.4, 14.])
        self.assertEqual(report['classes']['1']['p90_length_width_height_center_z'], [11.2, 5.6, 4.6, 46.])
        self.assertIsNone(report['classes']['2']['median_length_width_height_center_z'])

    def test_missing_extra_and_duplicate_sources_refused(self):
        base = self.sources()
        for sources in [base[:-1], base + [base[0]], base + [{'scene': 'extra', 'expected_rows': 0, 'rows': []}]]:
            with self.subTest(sources=sources), self.assertRaises(ValueError):
                self.run_sources(sources)

    def test_selection_cannot_silently_omit_admitted_training_source(self):
        with self.assertRaises(ValueError):
            self.run_sources(self.sources()[:-1], expected=['a', 'b'])
        with self.assertRaises(ValueError):
            self.run_sources(self.sources(), expected=['a', 'b', 'c', 'c'])

    def test_non_training_membership_refused_even_for_empty_source(self):
        for group in [{'official_split': 'validation', 'research_splits': ['validation']},
                      {'official_split': 'training', 'research_splits': ['development']}]:
            membership = self.membership()
            membership['c'] = group
            with self.subTest(group=group), self.assertRaises(ValueError):
                self.run_sources(self.sources(), membership=membership)

    def test_row_inventory_mismatch_refused(self):
        for count in [2, 4, -1, True]:
            sources = self.sources()
            sources[0]['expected_rows'] = count
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.run_sources(sources)

    def test_wrong_context_and_invalid_native_keys_refused(self):
        for key, value in [('key.segment_context_name', 'b'), ('key.frame_timestamp_micros', True),
                           ('key.frame_timestamp_micros', -1), ('key.laser_object_id', ''),
                           ('[LiDARBoxComponent].type', True)]:
            sources = self.sources()
            sources[0]['rows'][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.run_sources(sources)

    def test_unknown_category_cannot_hide_duplicate_or_bad_geometry(self):
        for mutation in ['duplicate', 'nan', 'zero_dimension', 'missing_field']:
            sources = self.sources()
            target = sources[1]['rows'][0]
            if mutation == 'duplicate':
                sources[1]['rows'].append(copy.deepcopy(target))
                sources[1]['expected_rows'] = 2
            elif mutation == 'nan':
                target['[LiDARBoxComponent].box.heading'] = float('nan')
            elif mutation == 'zero_dimension':
                target['[LiDARBoxComponent].box.size.x'] = 0.
            else:
                del target['[LiDARBoxComponent].box.center.z']
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.run_sources(sources)

    def test_late_source_read_failure_cannot_return_partial_statistics(self):
        def truncated():
            yield row(scene='c')
            raise OSError('fixture source read interrupted')
        sources = self.sources()
        sources[2] = {'scene': 'c', 'expected_rows': 2, 'rows': truncated()}
        with self.assertRaises(OSError):
            self.run_sources(sources)

    def test_streamed_native_parquet_keeps_dimensions_and_center_z(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        table = pa.table({
            'key.segment_context_name': ['a'],
            'key.frame_timestamp_micros': pa.array([123456], type=pa.int64()),
            'key.laser_object_id': ['native-track'],
            '[LiDARBoxComponent].type': pa.array([2], type=pa.int8()),
            '[LiDARBoxComponent].box.center.x': [1.],
            '[LiDARBoxComponent].box.center.y': [2.],
            '[LiDARBoxComponent].box.center.z': [12.],
            '[LiDARBoxComponent].box.size.x': [6.],
            '[LiDARBoxComponent].box.size.y': [3.],
            '[LiDARBoxComponent].box.size.z': [2.],
            '[LiDARBoxComponent].box.heading': [.5],
        })
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'native.parquet'
            pq.write_table(table, path)

            def rows():
                for batch in pq.ParquetFile(path).iter_batches(batch_size=1):
                    yield from batch.to_pylist()

            report = self.run_sources(
                [{'scene': 'a', 'expected_rows': 1, 'rows': rows()}],
                membership={'a': self.membership()['a']}, expected=['a'])
        self.assertEqual(report['native_rows'], 1)
        self.assertEqual(report['classes']['2']['median_length_width_height_center_z'], [6., 3., 2., 12.])
        self.assertEqual(report['completed_sources'], ['a'])


if __name__ == '__main__':
    unittest.main()
