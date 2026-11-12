import uuid,redis
from fastapi import HTTPException
from sqlalchemy import select
from src.models import ScenarioComparison,DurationScenario
from src.config.settings import REDIS_URL
from src.utils.serialization import serialize
from src.utils.time import now

def _enqueue(id):
 redis.Redis.from_url(REDIS_URL).lpush('package-criticality:jobs','cmp:'+id)

def create(db,payload):
 base=db.get(DurationScenario,payload.base_scenario_id)
 if not base:raise HTTPException(404,'基准情景不存在')
 compare=db.get(DurationScenario,payload.compare_scenario_id)
 if not compare:raise HTTPException(404,'对比情景不存在')
 if db.scalar(select(ScenarioComparison).where(ScenarioComparison.name==payload.name)):raise HTTPException(409,'配对比较名称已存在')
 item=ScenarioComparison(id=str(uuid.uuid4()),name=payload.name,base_scenario_id=base.id,compare_scenario_id=compare.id,base_version=base.version,compare_version=compare.version,samples=payload.samples,seed=payload.seed,base_snapshot=base.snapshot,compare_snapshot=compare.snapshot,status='queued',result={},error='',created_at=now())
 db.add(item);db.commit()
 try:_enqueue(item.id)
 except redis.RedisError:
  item.status='failed';item.error='后台队列不可用，请重试';db.commit();raise HTTPException(503,item.error)
 return serialize(item)

def rerun(db,id):
 item=db.get(ScenarioComparison,id)
 if not item:raise HTTPException(404,'配对比较不存在')
 item.status='queued';item.error='';db.commit()
 try:_enqueue(item.id)
 except redis.RedisError:
  item.status='failed';item.error='后台队列不可用，请重试';db.commit();raise HTTPException(503,item.error)
 return serialize(item)
