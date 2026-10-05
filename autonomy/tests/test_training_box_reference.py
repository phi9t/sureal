"""Hand-derived distributions for the separate native quantile verifier."""
import copy
from pathlib import Path
import tempfile
import unittest

from pipeline.training_box_reference import verify_training_box_distributions


def native(scene, timestamp, category, length, width, height, center_z):
    return {'key.segment_context_name': scene, 'key.frame_timestamp_micros': timestamp,
            'key.laser_object_id': 'actor', '[LiDARBoxComponent].type': category,
            '[LiDARBoxComponent].box.center.x': 0., '[LiDARBoxComponent].box.center.y': 0.,
            '[LiDARBoxComponent].box.center.z': center_z,
            '[LiDARBoxComponent].box.size.x': length, '[LiDARBoxComponent].box.size.y': width,
            '[LiDARBoxComponent].box.size.z': height, '[LiDARBoxComponent].box.heading': .2}


class IndependentBoxDistributionTests(unittest.TestCase):
    def membership(self):
        return {s: {'official_split': 'training', 'research_splits': ['train']} for s in ['a', 'b', 'c', 'd']}

    def sources(self):
        return [
            {'scene': 'a', 'expected_rows': 2, 'rows': [native('a', 10, 1, 2., 1., 1., -2.),
                                                       native('a', 20, 1, 10., 5., 3., 6.)]},
            {'scene': 'b', 'expected_rows': 1, 'rows': [native('b', 30, 2, .5, .4, 1.8, 9.)]},
            {'scene': 'c', 'expected_rows': 1, 'rows': [native('c', 40, 0, 1., 1., 1., 1.)]},
            {'scene': 'd', 'expected_rows': 0, 'rows': []},
        ]

    def report(self):
        absent = {'box_rows': 0, 'unique_tracks': 0, 'median_length_width_height_center_z': None,
                  'p10_length_width_height_center_z': None, 'p90_length_width_height_center_z': None}
        return {'rows': 3, 'frames': 3, 'observed_scenes': ['a', 'b'], 'native_rows': 4,
                'completed_sources': ['a', 'b', 'c', 'd'], 'outside_box_class_counts': {'0': 1},
                'source_completion': [
                    {'scene': 'a', 'native_rows': 2, 'eligible_box_rows': 2, 'outside_box_class_counts': {}},
                    {'scene': 'b', 'native_rows': 1, 'eligible_box_rows': 1, 'outside_box_class_counts': {}},
                    {'scene': 'c', 'native_rows': 1, 'eligible_box_rows': 0, 'outside_box_class_counts': {'0': 1}},
                    {'scene': 'd', 'native_rows': 0, 'eligible_box_rows': 0, 'outside_box_class_counts': {}}],
                'classes': {
                    '1': {'box_rows': 2, 'unique_tracks': 1,
                          'median_length_width_height_center_z': [6., 3., 2., 2.],
                          'p10_length_width_height_center_z': [2.8, 1.4, 1.2, -1.2],
                          'p90_length_width_height_center_z': [9.2, 4.6, 2.8, 5.2]},
                    '2': {'box_rows': 1, 'unique_tracks': 1,
                          'median_length_width_height_center_z': [.5, .4, 1.8, 9.],
                          'p10_length_width_height_center_z': [.5, .4, 1.8, 9.],
                          'p90_length_width_height_center_z': [.5, .4, 1.8, 9.]},
                    '3': copy.deepcopy(absent), '4': copy.deepcopy(absent)}}

    def check(self, sources=None, report=None, membership=None):
        return verify_training_box_distributions(
            self.sources() if sources is None else sources,
            reported=self.report() if report is None else report,
            membership=self.membership() if membership is None else membership,
            expected_scenes=['a', 'b', 'c', 'd'])

    def test_literal_native_distributions_verified_independent_of_source_order(self):
        result = self.check(sources=self.sources()[::-1])
        self.assertEqual(result['completed_sources'], 4)
        self.assertEqual(result['native_rows'], 4)
        self.assertEqual(result['eligible_box_rows'], 3)

    def test_wrong_quantiles_track_deduplication_and_bottom_z_refused(self):
        for field, value in [('median_length_width_height_center_z', [6., 3., 2., 1.]),
                             ('p10_length_width_height_center_z', [2., 1., 1., -2.]),
                             ('box_rows', 1), ('unique_tracks', 2)]:
            report = self.report()
            report['classes']['1'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(report=report)

    def test_missing_class_defaults_or_nonfinite_statistics_refused(self):
        for value in [[0., 0., 0., 0.], [float('nan')] * 4, [True] * 4]:
            report = self.report()
            report['classes']['3']['median_length_width_height_center_z'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.check(report=report)

    def test_corrupt_completion_counts_and_scene_support_refused(self):
        for field, value in [('native_rows', 5), ('rows', True), ('frames', 2),
                             ('completed_sources', ['a', 'b', 'c']), ('observed_scenes', ['a']),
                             ('outside_box_class_counts', {'0': 2}), ('source_completion', [])]:
            report = self.report()
            report[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(report=report)

    def test_omitted_extra_duplicate_and_non_training_sources_refused(self):
        base = self.sources()
        for sources in [base[:-1], base + [base[0]], base + [{'scene': 'extra', 'expected_rows': 0, 'rows': []}]]:
            with self.subTest(sources=sources), self.assertRaises(ValueError):
                self.check(sources=sources)
        membership = self.membership()
        membership['d'] = {'official_split': 'training', 'research_splits': ['development']}
        with self.assertRaises(ValueError):
            self.check(membership=membership)

    def test_changed_source_measurement_and_inventory_refused(self):
        sources = self.sources()
        sources[0]['rows'][0]['[LiDARBoxComponent].box.size.x'] = 20.
        with self.assertRaises(ValueError):
            self.check(sources=sources)
        sources = self.sources()
        sources[2]['expected_rows'] = 2
        with self.assertRaises(ValueError):
            self.check(sources=sources)

    def test_unknown_rows_still_require_valid_geometry_and_context(self):
        for field, value in [('[LiDARBoxComponent].box.size.x', 0.),
                             ('[LiDARBoxComponent].box.heading', float('inf')),
                             ('key.segment_context_name', 'a'), ('key.frame_timestamp_micros', True)]:
            sources = self.sources()
            sources[2]['rows'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(sources=sources)

    def test_duplicate_unknown_rows_refused_even_when_report_counts_are_adjusted(self):
        sources = self.sources()
        sources[2]['rows'].append(copy.deepcopy(sources[2]['rows'][0]))
        sources[2]['expected_rows'] = 2
        report = self.report()
        report['native_rows'] = 5
        report['outside_box_class_counts'] = {'0': 2}
        report['source_completion'][2].update(native_rows=2, outside_box_class_counts={'0': 2})
        with self.assertRaises(ValueError):
            self.check(sources=sources, report=report)

    def test_late_reader_failure_does_not_accept_partial_report(self):
        def interrupted():
            yield native('d', 50, 1, 1., 1., 1., 1.)
            raise OSError('independent source read interrupted')
        sources = self.sources()
        sources[3] = {'scene': 'd', 'expected_rows': 2, 'rows': interrupted()}
        with self.assertRaises(OSError):
            self.check(sources=sources)

    def test_producer_and_reference_reopen_parquet_independently(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        from pipeline.training_box_sources import training_box_statistics_from_sources
        schema = pa.schema([
            ('key.segment_context_name', pa.string()), ('key.frame_timestamp_micros', pa.int64()),
            ('key.laser_object_id', pa.string()), ('[LiDARBoxComponent].type', pa.int8()),
            ('[LiDARBoxComponent].box.center.x', pa.float64()),
            ('[LiDARBoxComponent].box.center.y', pa.float64()),
            ('[LiDARBoxComponent].box.center.z', pa.float64()),
            ('[LiDARBoxComponent].box.size.x', pa.float64()),
            ('[LiDARBoxComponent].box.size.y', pa.float64()),
            ('[LiDARBoxComponent].box.size.z', pa.float64()),
            ('[LiDARBoxComponent].box.heading', pa.float64()),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            sources = self.sources()
            for source in sources:
                pq.write_table(pa.Table.from_pylist(source['rows'], schema=schema),
                               Path(tmp) / (source['scene'] + '.parquet'))

            def decoded(batch_size):
                for source in sources:
                    path = Path(tmp) / (source['scene'] + '.parquet')

                    def rows(path=path):
                        for batch in pq.ParquetFile(path).iter_batches(batch_size=batch_size):
                            yield from batch.to_pylist()

                    yield {'scene': source['scene'], 'expected_rows': source['expected_rows'], 'rows': rows()}

            producer = training_box_statistics_from_sources(
                decoded(1), membership=self.membership(), expected_scenes=['a', 'b', 'c', 'd'])
            self.assertEqual(producer['classes']['1']['median_length_width_height_center_z'], [6., 3., 2., 2.])
            result = self.check(sources=decoded(2), report=producer)
        self.assertEqual(result['completed_sources'], 4)
        self.assertEqual(result['native_rows'], 4)
        self.assertEqual(result['eligible_box_rows'], 3)


if __name__ == '__main__':
    unittest.main()
