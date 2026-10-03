"""User-authorized native scoring budget, independent of training exposure."""
DEFAULT_NATIVE_SECONDS=14400
HOST_GRACE_SECONDS=300

def scoring_budget(seconds=DEFAULT_NATIVE_SECONDS):
 if type(seconds) is not int or not 600<=seconds<=DEFAULT_NATIVE_SECONDS:raise ValueError('integer native scoring bound from600to14400seconds required')
 return seconds,seconds+HOST_GRACE_SECONDS


def stage_timeout(metrics):
 if type(metrics) is not bool:raise ValueError('explicit metric stage flag required')
 return scoring_budget()[1] if metrics else 1800
