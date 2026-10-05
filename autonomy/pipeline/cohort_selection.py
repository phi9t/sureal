"""Deterministic segment-level selection, independent of model outcomes."""
import hashlib


def select_cohorts(training,validation,*,excluded,train_count,dev_count,validation_count):
    if len(set(training))!=len(training) or len(set(validation))!=len(validation):raise ValueError('duplicate source segment')
    if set(training)&set(validation):raise ValueError('official partitions overlap')
    if any(not isinstance(n,int) or n<=0 for n in [train_count,dev_count,validation_count]):raise ValueError('invalid cohort counts')
    key=lambda name:(hashlib.sha256(('sureal-perception-v1:'+name).encode()).hexdigest(),name)
    tr=sorted(set(training)-set(excluded),key=key);va=sorted(set(validation)-set(excluded),key=key)
    if len(tr)<train_count+dev_count or len(va)<validation_count:raise ValueError('insufficient eligible segments')
    return {'train':tr[:train_count],'development':tr[train_count:train_count+dev_count],'validation':va[:validation_count]}
