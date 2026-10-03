"""Fail-closed parser for the pinned default 3D detection CLI.

Expected breakdown names must come from the frozen evaluation configuration,
not from the output being validated. This parser is not a LET/2D adapter.
"""
import math
import re


def parse_result(exit_code, stdout, stderr, expected_breakdowns):
    expected=set(expected_breakdowns)
    if exit_code != 0 or stderr.strip() or not expected:
        raise ValueError('evaluator failed, emitted diagnostics, or lacks configuration')
    lines=[line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines or not re.fullmatch(r'\d+ examples found\.',lines[0]):
        raise ValueError('missing native example count')
    metrics={}
    for line in lines[1:]:
        match=re.fullmatch(r'(.+): \[mAP ([^\]]+)\] \[mAPH ([^\]]+)\]',line)
        if match is None:
            raise ValueError('unrecognized metric output')
        name,ap,aph=match.groups()
        if name not in expected or name in metrics:
            raise ValueError('unexpected or duplicate breakdown')
        values=[float(ap),float(aph)]
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in values):
            raise ValueError('invalid metric value')
        metrics[name]=dict(zip(('AP','APH'),values))
    if set(metrics)!=expected:
        raise ValueError('incomplete metric breakdowns')
    return {'examples':int(lines[0].split()[0]),'metrics':metrics}
