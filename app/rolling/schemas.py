from __future__ import annotations
from dataclasses import asdict,dataclass
from typing import Any
@dataclass(frozen=True)
class RollingWindowResult:
    window_id:str; window_type:str; start_date:str|None; end_date:str|None; sample_size:int; usable_sample_size:int; insufficient_sample:bool; records_included:list[str]; records_excluded:list[str]; exclusion_reasons:dict[str,int]; status:str
    def to_dict(self)->dict[str,Any]: return asdict(self)
