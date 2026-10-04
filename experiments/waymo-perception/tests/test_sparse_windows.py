import unittest
import numpy as np
from pipeline.sparse_windows import partition_sparse_windows

class SparseWindowTests(unittest.TestCase):
    def test_boundaries_batches_and_padding_retain_every_voxel_once(self):
        coordinates=np.array([[0,0,0],[0,0,1],[0,1,1],[0,0,2],[1,0,0]],dtype=np.int64)
        r=partition_sparse_windows(coordinates,window_shape=(2,2),shift=(0,0))
        self.assertEqual(r['tokens'],5)
        ids=np.concatenate([b['token_indices'][b['valid_mask']] for b in r['buckets'].values()])
        np.testing.assert_array_equal(np.sort(ids),np.arange(5))
        self.assertTrue(all(np.all(b['token_indices'][~b['valid_mask']]==-1) for b in r['buckets'].values()))
        self.assertEqual(r['windows'],3)
        self.assertLessEqual(sum(b['token_indices'].size for b in r['buckets'].values()),10)
    def test_shift_crosses_boundaries_without_cyclic_edge_wrap(self):
        coordinates=np.array([[0,0,0],[0,0,1],[0,0,2],[0,0,3]])
        r=partition_sparse_windows(coordinates,window_shape=(2,2),shift=(0,1))
        groups=[]
        for b in r['buckets'].values():
            groups.extend(tuple(row[valid]) for row,valid in zip(b['token_indices'],b['valid_mask']))
        self.assertEqual(set(groups),{(0,),(1,2),(3,)})
    def test_permutation_preserves_geometric_membership(self):
        coordinates=np.array([[0,0,0],[0,1,1],[0,4,3],[1,0,0]])
        def groups(c):
            r=partition_sparse_windows(c,window_shape=(2,2),shift=(1,1))
            return sorted(tuple(sorted(tuple(c[i]) for i in row[valid])) for b in r['buckets'].values()
                          for row,valid in zip(b['token_indices'],b['valid_mask']))
        self.assertEqual(groups(coordinates),groups(coordinates[[2,0,3,1]]))
    def test_empty_and_invalid_contracts(self):
        self.assertEqual(partition_sparse_windows(np.empty((0,3),dtype=np.int64),window_shape=(2,2),shift=(0,0))['buckets'],{})
        for c in [np.array([[0,0,0],[0,0,0]]),np.array([[0.,0.,0.]]),np.array([[0,-1,0]])]:
            with self.assertRaises(ValueError):partition_sparse_windows(c,window_shape=(2,2),shift=(0,0))
