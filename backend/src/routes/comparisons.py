from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from src.config.database import db_session
from src.controllers.auth import current_user,writer
from src.models import ScenarioComparison
from src.schemas.comparison import ComparisonInput
from src.services import comparisons as service
from src.utils.serialization import rows,serialize
router=APIRouter(prefix='/comparisons')
@router.get('')
def listing(db=Depends(db_session),user=Depends(current_user)):return rows(db.scalars(select(ScenarioComparison).order_by(ScenarioComparison.created_at.desc())))
@router.post('')
def create(payload:ComparisonInput,db=Depends(db_session),user=Depends(writer)):return service.create(db,payload)
@router.get('/{id}')
def detail(id:str,db=Depends(db_session),user=Depends(current_user)):
 item=db.get(ScenarioComparison,id)
 if not item:raise HTTPException(404,'配对比较不存在')
 return serialize(item)
@router.post('/{id}/rerun')
def rerun(id:str,db=Depends(db_session),user=Depends(writer)):return service.rerun(db,id)
