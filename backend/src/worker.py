from pathlib import Path
import redis,traceback
from sqlalchemy import select
from src.config.settings import REDIS_URL
from src.config.database import Session
from src.models import ScheduleRun,DurationScenario,ScenarioComparison
from src.services.analysis import analyze
from src.services.paired import compare
client=redis.Redis.from_url(REDIS_URL);heartbeat=Path('/artifacts/worker-heartbeat')
def execute(id):
 with Session() as db:
  run=db.get(ScheduleRun,id)
  if not run or run.status not in ('queued','running'):return
  run.status='running';db.commit()
  try:
   scenario=db.get(DurationScenario,run.scenario_id);run.result=analyze(scenario.snapshot,scenario);run.status='completed'
  except Exception as e:run.error=str(e);run.status='failed';traceback.print_exc()
  db.commit()
def execute_comparison(id):
 with Session() as db:
  item=db.get(ScenarioComparison,id)
  if not item or item.status not in ('queued','running'):return
  item.status='running';db.commit()
  try:
   item.result=compare(item.base_snapshot,item.compare_snapshot,item.samples,item.seed);item.status='completed'
  except Exception as e:item.error=str(e);item.status='failed';traceback.print_exc()
  db.commit()
with Session() as db:
 for id in db.scalars(select(ScheduleRun.id).where(ScheduleRun.status.in_(['queued','running']))):client.lpush('package-criticality:jobs',id)
 for id in db.scalars(select(ScenarioComparison.id).where(ScenarioComparison.status.in_(['queued','running']))):client.lpush('package-criticality:jobs','cmp:'+id)
while True:
 heartbeat.touch();job=client.brpop('package-criticality:jobs',timeout=1)
 if job:
  token=job[1].decode()
  if token.startswith('cmp:'):execute_comparison(token[4:])
  else:execute(token)
