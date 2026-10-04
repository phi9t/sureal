"""Reproducible native positive/R1/R2 controls, separate from milestone admission."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import sys
sys.dont_write_bytecode=True

from audit_support.cases import queue_restore, check_auxiliary_closure
from audit_support.evidence import artifact, sqlite_projection
from audit_support.facts import require
from audit_support.raw_git import sha256, strict_json, write_new
from audit_support.recovery import reconstruct_queue
from audit_support.search_index import check_physical_search_closure


def ref(path):
    return {'path':str(path),'sha256':sha256(path)}


def refusal(call):
    try:
        call()
    except ValueError as error:
        return str(error)
    raise AssertionError('Native corruption accepted')


def deleted_control(fresh,output):
    path=output/'owned-deleted-payload.db';shutil.copyfile(fresh,path)
    marker='independentforeignhistoricalpayloadneedle'
    connection=sqlite3.connect(path)
    try:
        connection.execute("INSERT INTO issues_fts(rowid,title,body,comments) VALUES(999999,?,'','')",(marker,))
        connection.commit()
        require(connection.execute('SELECT rowid FROM issues_fts WHERE issues_fts MATCH ?',(marker,)).fetchall()==[(999999,)],
                'Native insert did not produce the controlled foreign posting')
        connection.execute("INSERT INTO issues_fts(issues_fts,rowid,title,body,comments) VALUES('delete',999999,?,'','')",(marker,))
        connection.commit()
        require(not connection.execute('SELECT rowid FROM issues_fts WHERE issues_fts MATCH ?',(marker,)).fetchall(),
                'Native delete did not remove the controlled foreign active posting')
        blocks=[row[0] for row in connection.execute('SELECT id,block FROM issues_fts_data') if marker.encode() in row[1]]
        require(blocks,'Control did not leave foreign bytes in current SQL shadow rows')
        require(connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok','Control damaged native integrity')
    finally:
        connection.close()
    before=sqlite_projection(ref(fresh));after=sqlite_projection(ref(path))
    require(before['search_index']==after['search_index'],'Control unexpectedly changed active search')
    reason=refusal(lambda:check_physical_search_closure(after,before))
    return {'database':ref(path),'marker':marker,'current_shadow_row_ids':blocks,
            'matching_before_delete':[999999],'matching_after_delete':[],
            'active_semantics_unchanged':True,'physical_payload_refusal':reason}


def run(args):
    output=Path(args.output);require(output.is_absolute() and not output.exists(),'New absolute control output required')
    output.mkdir(mode=0o700)
    tool={'path':args.kata,'sha256':args.kata_sha256};artifact(tool)
    manifest_path=Path(args.restore_manifest);data=strict_json(manifest_path)
    source_refs=[ref(manifest_path)]+[data[key] for key in ('source_db','restored_db','native_baseline_db','export')]
    for source_ref in source_refs:artifact(source_ref)
    case=output/'native-restore-case';case.mkdir()
    write_new(case/'independent-oracle.json',{'schema_version':1,'raw_root':str(manifest_path.parent),
                                           'fixture_manifest':ref(manifest_path)})
    admission={'tools':{'kata':tool},'kata':{'native_baseline_db':data['native_baseline_db']},
               'authors':{'auditor':args.owner}}
    positive=queue_restore(case,admission=admission,reconstruction_root=output/'native-v1-reconstruction')
    proof=strict_json(artifact(positive['independent_native_reconstruction']))
    recovered=sqlite_projection(proof['database'])
    source=sqlite_projection(data['source_db']);baseline=sqlite_projection(data['native_baseline_db'])
    r2={'path':args.review_r2_db,'sha256':args.review_r2_sha256}
    r2_reason=refusal(lambda:check_auxiliary_closure(source,sqlite_projection(r2),baseline,data['selected_project_uid'],recovered))
    own=deleted_control(artifact(proof['database']),output)
    # A separate literal Unicode/comment export exercises native import order,
    # rather than assuming the one-shot in-memory semantic layout is physical.
    records=[json.loads(line) for line in artifact(data['export']).read_text().splitlines()]
    first=next(row['data'] for row in records if row['kind']=='issue')
    first['title']='Café geometry';first['body']='coöperative LiDAR range'
    comments=[]
    for identity,body in [(20,'Über ordered second comment'),(10,'naïve first comment')]:
        comments.append({'kind':'comment','data':{'id':identity,'uid':f'{identity:026d}',
             'issue_id':first['id'],'issue_uid':first['uid'],'author':'independent-native-oracle',
             'body':body,'created_at':'2026-10-04T00:00:00.000Z'}})
    position=max(index for index,row in enumerate(records) if row['kind']=='issue')+1
    records[position:position]=comments
    unicode_export=output/'unicode-comments.jsonl'
    with unicode_export.open('x') as stream:
        for row in records:stream.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
    one,one_receipt=reconstruct_queue(ref(unicode_export),tool,output/'unicode-recovery-1',args.owner)
    two,two_receipt=reconstruct_queue(ref(unicode_export),tool,output/'unicode-recovery-2',args.owner)
    require(len(one['tables']['comments'])==2,'Native replay omitted Unicode/comment control')
    require(any(term=='cafe' for term,_,_,_ in one['search_index']['instances']),
            'Native Unicode tokenizer positive absent')
    check_physical_search_closure(one,two)
    unicode_deleted=deleted_control(artifact(strict_json(artifact(one_receipt))['database']),output/'unicode-recovery-1')
    for source_ref in source_refs:artifact(source_ref)
    report={'schema_version':1,'kind':'independent-native-recovery-controls','owner':args.owner,
            'source_inputs':source_refs,'native_tool':tool,'native_restore_positive':positive,
            'exact_reviewer_R2':{'database':r2,'refusal':r2_reason},'owned_deleted_payload':own,
            'unicode_comments':{'first':one_receipt,'second':two_receipt,'physical_positive':True,
                                'deleted_payload_control':unicode_deleted},
            'original_sources_unchanged':True,'live_milestone_accepted':False}
    write_new(output/'native-controls.json',report)
    print(json.dumps({'schema_version':1,'outcome':'ok','report':ref(output/'native-controls.json')},sort_keys=True))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('restore-manifest','kata','kata-sha256','review-r2-db','review-r2-sha256','output','owner'):
        parser.add_argument('--'+name,required=True)
    run(parser.parse_args())


if __name__=='__main__':
    main()
