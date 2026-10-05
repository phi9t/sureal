"""Recover complete native semantic support through bounded immutable replay."""
import json
from pathlib import Path
from dataset.scientific_dataset import iter_scene_records
from evidence.source_snapshot import file_sha256
from segmentation.semantic_support import semantic_support


def archive_semantic_support(archive, publication, *, expected_publication_sha256, usage):
    arguments = dict(expected_publication_sha256=expected_publication_sha256,
                     usage=usage, max_record_bytes=128*1024**2)
    result = semantic_support(iter_scene_records(archive, publication, **arguments))
    # Independently reopen the immutable archive, using a literal count loop
    # rather than the producer's bincount/semantic_support implementation.
    reference = [0] * 23
    records = annotated = unannotated = 0
    frames = set()
    for record in iter_scene_records(archive, publication, **arguments):
        records += 1
        labels = record['targets'].get('segmentation')
        if labels is None:
            unannotated += 1
            continue
        annotated += 1
        identity = record['identity']
        frames.add((identity['context'], identity['timestamp']))
        for label in labels[:, 1]:
            reference[int(label)] += 1
    if (result['native_counts'] != reference or result['eligible_point_elements'] != sum(reference[1:])
            or result['annotated_returns'] != annotated or result['unannotated_returns'] != unannotated
            or result['annotated_frames'] != len(frames)):
        raise ValueError('independent archive semantic accounting differs')
    publication = Path(publication)
    if file_sha256(publication) != expected_publication_sha256:
        raise ValueError('publication changed during independent replay')
    pub = json.loads(publication.read_text())
    result.update(scene=pub['scene'], publication_sha256=expected_publication_sha256,
                  archive_sha256=pub['archive']['sha256'],
                  independent_reference_records=records,
                  recovery_scope='two bounded immutable archive passes; no model or ontology remapping')
    return result
