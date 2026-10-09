"""Aligned transfer receipt contract; rehash mutations to test semantics."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from evidence.source_snapshot import file_sha256
from segmentation.semantic_recovery_receipt_aligned import verify_receipt


HERE=Path(__file__).resolve().parent
TESTDATA=HERE/'testdata/semantic_receipts/aligned'


def fixture_paths():
    source=Path(os.environ.get('SEMANTIC_RECEIPT_FIXTURE','/source'))
    code=Path(os.environ.get('SEMANTIC_RECEIPT_CODE','/experiment'))
    if (source/'receipt.json').exists():
        return source,code
    return TESTDATA/'source',TESTDATA/'code'


def remove_output_mount(receipt):
    check=receipt['checks'][0]
    if 'command' in check:
        check['command'].remove('/outputs')
    else:
        check['launch_plan']['mounts']=[
            mount for mount in check['launch_plan']['mounts']
            if mount.get('inside_path')!='/outputs'
        ]


class AlignedReceiptTests(unittest.TestCase):
    def test_aligned_contract_and_rehashed_resource_mutants(self):
        source,code=fixture_paths()
        original=json.loads((source/'receipt.json').read_text())
        mutations=[None,
                   lambda t:t.pop('transfer_contract'),
                   lambda t:t.update(transfer_alignment_bytes=8192),
                   lambda t:t.update(transfer_padding_bytes=1),
                   lambda t:t.update(file_size_limit_bytes=t['file_size_limit_bytes']+4096),
                   lambda t:t.update(working_peak_bound_bytes=t['working_peak_bound_bytes']-1),
                   lambda t:t.update(working_limit_bytes=t['working_peak_bound_bytes']-1),
                   remove_output_mount]
        for size in [original['input_identity']['archive_bytes'],2048]:
            for mutation in mutations:
                with self.subTest(size=size,mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                    root=Path(tmp)/'receipt';shutil.copytree(source,root)
                    r=copy.deepcopy(original);expected=copy.deepcopy(r['input_identity'])
                    expected['archive_bytes']=size
                    pub=json.loads((root/'input/publication.json').read_text())
                    pub['archive']['archive_bytes']=size
                    (root/'input/publication.json').write_text(json.dumps(pub))
                    expected['publication_manifest_sha256']=file_sha256(root/'input/publication.json')
                    r['input_identity']=expected
                    (root/'input/trusted.json').write_text(json.dumps(expected))
                    r['validation']['publication_sha256']=expected['publication_manifest_sha256']
                    (root/'output/support.json').write_text(json.dumps(r['validation']))
                    for n in r['artifacts']:r['artifacts'][n]=file_sha256(root/n)
                    t=r['transfer'];t['archive_bytes']=size
                    # Hand-sized cases: original archive is aligned; 2048 reserves 4096.
                    limit=size if size!=2048 else 4096
                    t.update(transfer_contract='native-direct-write-aligned-v1',transfer_alignment_bytes=4096,
                             transfer_padding_bytes=0 if size!=2048 else 2048,file_size_limit_bytes=limit,
                             working_peak_bytes_before_consumer=t['working_bytes_before']+size,
                             working_peak_bound_bytes=t['working_bytes_before']+limit)
                    if mutation==remove_output_mount:
                        mutation(r)
                    elif mutation:
                        mutation(t)
                    (root/'receipt.json').write_text(json.dumps(r))
                    args=dict(expected_sha256=file_sha256(root/'receipt.json'),
                              expected_record=expected,expected_runtime=original['runtime_lock'],
                              expected_code=original['candidate_hashes'],code_root=code)
                    if mutation:
                        with self.assertRaises(ValueError):verify_receipt(root,**args)
                    else:verify_receipt(root,**args)

if __name__=='__main__':unittest.main()
