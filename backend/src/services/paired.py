"""Paired scenario comparison: common random quantiles (CRN) across two frozen snapshots.

Each task_id gets its own stdlib quantile stream keyed by (seed, task_id), so the same
task draws the same quantile u in both scenarios at sample k, and adding, removing or
reordering tasks never changes the quantiles of any other task. Durations are then
mapped per scenario through that scenario's own Beta-PERT inverse CDF, and each side
runs a fresh CPM on its own frozen edges. Deadlines never enter the computation.
"""
import hashlib,json,math,random,statistics
from src.services.cpm import cpm,TOLERANCE
from src.services.pert import quantile,validate_ranges

def _betacf(a,b,x):
 FPMIN=1e-300;qab=a+b;qap=a+1.0;qam=a-1.0;c=1.0;d=1.0-qab*x/qap
 if abs(d)<FPMIN:d=FPMIN
 d=1.0/d;h=d
 for m in range(1,201):
  m2=2*m;aa=m*(b-m)*x/((qam+m2)*(a+m2));d=1.0+aa*d
  if abs(d)<FPMIN:d=FPMIN
  c=1.0+aa/c
  if abs(c)<FPMIN:c=FPMIN
  d=1.0/d;h*=d*c;aa=-(a+m)*(qab+m)*x/((a+m2)*(qap+m2));d=1.0+aa*d
  if abs(d)<FPMIN:d=FPMIN
  c=1.0+aa/c
  if abs(c)<FPMIN:c=FPMIN
  d=1.0/d;delta=d*c;h*=delta
  if abs(delta-1.0)<=3e-14:break
 return h

def _beta_cdf(x,alpha,beta):
 if x<=0.0:return 0.0
 if x>=1.0:return 1.0
 bt=math.exp(math.lgamma(alpha+beta)-math.lgamma(alpha)-math.lgamma(beta)+alpha*math.log(x)+beta*math.log1p(-x))
 if x<(alpha+1.0)/(alpha+beta+2.0):return bt*_betacf(alpha,beta,x)/alpha
 return 1.0-bt*_betacf(beta,alpha,1.0-x)/beta

def _beta_ppf(u,alpha,beta):
 """Inverse regularized incomplete beta via safeguarded Newton; deterministic pure stdlib."""
 if u<=0.0:return 0.0
 if u>=1.0:return 1.0
 x=(alpha-1.0/3.0)/(alpha+beta-2.0/3.0) if alpha>1.0 and beta>1.0 else alpha/(alpha+beta)
 x=min(max(x,1e-12),1.0-1e-12);lo,hi=0.0,1.0;lnb=math.lgamma(alpha)+math.lgamma(beta)-math.lgamma(alpha+beta)
 for _ in range(80):
  err=_beta_cdf(x,alpha,beta)-u
  if err>0.0:hi=x
  else:lo=x
  if abs(err)<=1e-13 or hi-lo<=1e-14:break
  pdf=math.exp((alpha-1.0)*math.log(x)+(beta-1.0)*math.log1p(-x)-lnb)
  candidate=x-err/pdf if pdf>0.0 else -1.0
  x=candidate if lo<candidate<hi else 0.5*(lo+hi)
 return x

def task_quantiles(seed,task_id,samples):
 """Per-task quantile stream; keyed only by (seed, task_id), independent of task order or set."""
 rng=random.Random(f'paired|{seed}|{task_id}')
 return [rng.random() for _ in range(samples)]

def _params(tasks):
 out={}
 for t in tasks:
  a,m,b=t['a'],t['m'],t['b']
  out[t['task_id']]={'a':a,'m':m,'b':b,'point':a==b,'alpha':None if a==b else 1+4*(m-a)/(b-a),'beta':None if a==b else 1+4*(b-m)/(b-a)}
 return out

def _sampled(p,us):
 if p['point']:return [p['a']]*len(us)
 span=p['b']-p['a']
 return [p['a']+span*_beta_ppf(u,p['alpha'],p['beta']) for u in us]

def _histogram(values,low,high,samples):
 width=(high-low)/18 if high>low else 0.
 if not width:return [{'left':low,'right':high,'count':samples}]
 bins=[0]*18
 for value in values:bins[min(17,int((value-low)/width))]+=1
 return [{'left':low+i*width,'right':low+(i+1)*width,'count':count} for i,count in enumerate(bins)]

def compare(base_snapshot,compare_snapshot,samples,seed):
 if isinstance(samples,bool) or not isinstance(samples,int) or not 1<=samples<=10000:raise ValueError('invalid comparison sample count')
 if isinstance(seed,bool) or not isinstance(seed,int) or seed<0:raise ValueError('invalid seed')
 base_tasks=base_snapshot['package']['tasks'];compare_tasks=compare_snapshot['package']['tasks']
 validate_ranges(base_tasks);validate_ranges(compare_tasks)
 base_edges=[[e['predecessor'],e['successor']] for e in base_snapshot['dependencies']]
 compare_edges=[[e['predecessor'],e['successor']] for e in compare_snapshot['dependencies']]
 base=_params(base_tasks);other=_params(compare_tasks)
 cpm({k:v['m'] for k,v in base.items()},base_edges);cpm({k:v['m'] for k,v in other.items()},compare_edges)
 base_ids=set(base);other_ids=set(other)
 common=sorted(base_ids&other_ids);only_base=sorted(base_ids-other_ids);only_compare=sorted(other_ids-base_ids)
 streams={tid:task_quantiles(seed,tid,samples) for tid in sorted(base_ids|other_ids)}
 dur_base={tid:_sampled(base[tid],streams[tid]) for tid in base}
 dur_compare={tid:_sampled(other[tid],streams[tid]) for tid in other}
 finish_base=[];finish_compare=[];diffs=[]
 for k in range(samples):
  fb=cpm({tid:dur_base[tid][k] for tid in base},base_edges,TOLERANCE)['project_finish']
  fc=cpm({tid:dur_compare[tid][k] for tid in other},compare_edges,TOLERANCE)['project_finish']
  finish_base.append(fb);finish_compare.append(fc);diffs.append(fc-fb)
 ordered=sorted(diffs);ob=sorted(finish_base);oc=sorted(finish_compare)
 ahead=sum(d<-TOLERANCE for d in diffs);delayed=sum(d>TOLERANCE for d in diffs);on_par=samples-ahead-delayed
 q=lambda s:{'p05':quantile(s,.05),'p50':quantile(s,.5),'p80':quantile(s,.8),'p95':quantile(s,.95)}
 checksum=hashlib.sha256(json.dumps({'base_snapshot':base_snapshot,'compare_snapshot':compare_snapshot,'samples':samples,'seed':seed},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 return {'samples':samples,'seed':seed,'pairing':'common_random_quantiles','quantile_stream':"stdlib Random keyed by 'paired|seed|task_id'; position and task-set independent",'diff_definition':'finish_compare - finish_base per paired sample; negative means compare finishes earlier; deadlines never used','tolerance_hours':TOLERANCE,'common_tasks':common,'only_base':only_base,'only_compare':only_compare,'base':{'mean_finish':statistics.fmean(finish_base),'quantiles':q(ob)},'compare':{'mean_finish':statistics.fmean(finish_compare),'quantiles':q(oc)},'diff':{'values':diffs,'mean':statistics.fmean(diffs),'quantiles':q(ordered),'histogram':_histogram(diffs,ordered[0],ordered[-1],samples),'ahead_count':ahead,'on_par_count':on_par,'delayed_count':delayed,'denominator':samples,'ahead_ratio':ahead/samples,'on_par_ratio':on_par/samples,'delayed_ratio':delayed/samples},'finish_base':finish_base,'finish_compare':finish_compare,'assumptions':['配对口径：同一task_id在两个情景的第k个样本取相同随机分位u；分位流由 paired|seed|task_id 派生，与任务顺序和任务集合无关，任务增删或重排不改变既有任务的分位。','工期按各自情景的a/m/b经Beta-PERT(lambda=4)逆累积分布取值：a+(b-a)*I^{-1}_u(alpha,beta)，alpha=1+4(m-a)/(b-a)，beta=1+4(b-m)/(b-a)；a=m=b为点质量不抽样。逆累积由连分式+牛顿法纯标准库计算，结果确定可复现。','每侧每个样本重新计算完整CPM；工期差=对比情景完工-基准情景完工，负值为提前。截止期不参与配对计算，截止期变化不影响工期差。','比较只读取冻结在本记录中的两份情景快照；上游工作包后续更新不影响按原快照重算的结果，重算与首次计算逐位一致。','提前/持平/延后按工期差与1e-8小时容差划分；有限样本比例是抽样估计，不是交付承诺。','配对比较不修改原独立推演运行、交付复核与已批准报告。'],'checksum':checksum}
