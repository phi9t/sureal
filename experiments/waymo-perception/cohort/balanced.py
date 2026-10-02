"""Training-label-only coverage selection, independent of model outcomes."""
import hashlib

def uncovered_count(report):
 count=report['eligible_targets_without_positive_anchor']
 if count!=len(report['uncovered_object_ids']):raise ValueError('Uncovered count/identity mismatch')
 return count

def coverage_summary(frames):
 result={}
 for category in map(str,range(1,5)):
  tracks=set();scenes=set();count=0;support_frames=0
  for f in frames:
   scene=f['identity'].split(':')[0];ids=f['objects'][category]
   if ids:scenes.add(scene);support_frames+=1
   tracks.update((scene,x) for x in ids);count+=len(ids)
  result[category]={'eligible_objects':count,'unique_tracks':len(tracks),'frames':support_frames,'scenes':len(scenes)}
 return result

def select_balanced(frames):
 if len({f['identity'] for f in frames})!=len(frames):raise ValueError('Duplicate frame identity')
 pending=sorted(frames,key=lambda f:hashlib.sha256(('balanced-v1:'+f['identity']).encode()).hexdigest());selected=[]
 targets={'eligible_objects':16,'unique_tracks':8,'frames':8,'scenes':4}
 # Scarce-category novelty dominates until its coverage targets are met.
 available=coverage_summary(frames);weights={c:1/max(1,available[c]['unique_tracks']) for c in available}
 while pending and len(selected)<16:
  before=coverage_summary(selected)
  def gain(f):
   after=coverage_summary(selected+[f]);return sum(weights[c]*sum((min(after[c][k],goal)-min(before[c][k],goal))/goal for k,goal in targets.items()) for c in before)
  best=max(pending,key=gain);selected.append(best);pending.remove(best)
 coverage=coverage_summary(selected)
 if len(selected)!=16 or any(values[k]<goal for values in coverage.values() for k,goal in targets.items()):raise ValueError('Cannot meet balanced 16-frame coverage; report missing support without relaxing gates')
 return selected
