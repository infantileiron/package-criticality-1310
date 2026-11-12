from sqlalchemy import String,Integer,JSON,ForeignKey,Text
from sqlalchemy.orm import Mapped,mapped_column
from src.config.database import Base
class ScenarioComparison(Base):
 __tablename__='scenario_comparisons'
 id:Mapped[str]=mapped_column(String(80),primary_key=True)
 name:Mapped[str]=mapped_column(String(160),unique=True)
 base_scenario_id:Mapped[str]=mapped_column(ForeignKey('duration_scenarios.id'))
 compare_scenario_id:Mapped[str]=mapped_column(ForeignKey('duration_scenarios.id'))
 base_version:Mapped[int]=mapped_column(Integer)
 compare_version:Mapped[int]=mapped_column(Integer)
 samples:Mapped[int]=mapped_column(Integer)
 seed:Mapped[int]=mapped_column(Integer)
 base_snapshot:Mapped[dict]=mapped_column(JSON)
 compare_snapshot:Mapped[dict]=mapped_column(JSON)
 status:Mapped[str]=mapped_column(String(32))
 result:Mapped[dict]=mapped_column(JSON,default=dict)
 error:Mapped[str]=mapped_column(Text,default='')
 created_at:Mapped[str]=mapped_column(String(64))
