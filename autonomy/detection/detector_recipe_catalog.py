"""One-factor fixed-batch treatments; planned ideas are not manufactured runs."""
BASE={'architecture':'baseline','norm':'gn_backbone','max_points':32,'pillar_cap':20000,'learning_rate':1e-4,'clip':10.,'foreground_prior':None,'loss':'reference'}
def catalog():
 cases={'baseline':dict(BASE)}
 for name in ['deep_pfn','context_pfn','masked_pfn','residual_bev','window_bev','coarse_mlp']:cases[name]={**BASE,'architecture':name}
 cases['retain64']={**BASE,'max_points':64}
 cases['all_pillars']={**BASE,'pillar_cap':30000,'equivalence_control':True}
 for name,norm in [('full_bn','bn'),('point_ln','gn_backbone_ln_pillar'),('no_norm','no_norm')]:cases[name]={**BASE,'norm':norm}
 cases['foreground_prior']={**BASE,'foreground_prior':.01}
 cases['lr3e4']={**BASE,'learning_rate':3e-4}
 cases['no_clip']={**BASE,'clip':None}
 cases['class_balanced_focal']={**BASE,'loss':'class_balanced_positive'}
 return cases

def select_fixture(audit):
 rows=[r for r in audit['validation'] if r['uncovered_GT']==0 and all(r['covered_objects'].get(str(c)) for c in range(1,5)) and len(r['covered_objects']['4'])>=5]
 if not rows:raise ValueError('No all-class fixture with complete anchors and five cyclists')
 return min(rows,key=lambda r:(r['eligible_GT'],r['identity']))
