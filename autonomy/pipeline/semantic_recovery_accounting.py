"""Independent retained semantic accounting checks; not archive authenticity admission."""
import math

def verify_accounting(value, expected):
    def require(condition):
        if not condition: raise ValueError('semantic recovery accounting differs')
    def number(n):
        require(type(n) is int and n >= 0)
        return n
    def histogram(h):
        require(isinstance(h,list) and len(h)==23)
        return [number(n) for n in h]
    for field,key in [('scene','scene'),('membership','membership'),('publication_sha256','publication_manifest_sha256'),('archive_sha256','archive_sha256'),('source_report_sha256','report_sha256')]:
        require(value.get(field)==expected[key])
    counts=histogram(value['native_counts'])
    require(number(value['labeled_point_elements'])==sum(counts))
    require(number(value['eligible_point_elements'])==sum(counts[1:]))
    records=number(value['independent_reference_records'])
    require(records==expected['records'])
    annotated=number(value['annotated_returns'])
    require(annotated+number(value['unannotated_returns'])==records)
    require(number(value['empty_annotated_returns'])<=annotated)
    frames=value['frame_counts'];require(isinstance(frames,list))
    require(number(value['annotated_frames'])==len(frames))
    summed=[0]*23;seen=set()
    for frame in frames:
        identity=(frame['context'],frame['timestamp'])
        require(identity[0]==expected['scene'] and type(identity[1]) is int and identity not in seen)
        seen.add(identity)
        for i,n in enumerate(histogram(frame['native_counts'])):summed[i]+=n
    require(summed==counts and len(frames)<=annotated)
    resources=value['worker_resources']
    require(type(resources['peak_rss_kib']) is int and resources['peak_rss_kib']>0)
    elapsed=resources['elapsed_seconds']
    require(type(elapsed) in (int,float) and math.isfinite(elapsed) and elapsed>=0)
    require(resources['rss_scope']=='worker_process_peak')
    return {'records':records,'eligible_point_elements':sum(counts[1:]),'annotated_frames':len(frames)}
