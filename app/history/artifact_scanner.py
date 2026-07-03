from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from .artifact_normalizer import normalize_artifact
TEXT_SUFFIX={'.txt','.md','.log'}; JSON_SUFFIX={'.json','.jsonl'}
def _iter_paths(paths:list[str])->list[Path]:
    out=[]
    for raw in paths:
        p=Path(raw).expanduser()
        if not p.exists(): continue
        if p.is_dir(): out += [x for x in p.rglob('*') if x.is_file() and x.stat().st_size < 2_000_000]
        elif p.is_file() and p.stat().st_size < 2_000_000: out.append(p)
    return out
def scan_artifacts(paths:list[str], source_kind:str="real_runtime") -> dict[str,Any]:
    records=[]; warnings=[]; errors=[]; malformed=0; unsupported=0; loaded=0
    for p in _iter_paths(paths):
        suffix=p.suffix.lower()
        try:
            if suffix in JSON_SUFFIX:
                if suffix=='.jsonl':
                    payloads=[json.loads(line) for line in p.read_text(encoding='utf-8',errors='replace').splitlines() if line.strip()]
                else: payloads=[json.loads(p.read_text(encoding='utf-8',errors='replace'))]
            elif suffix in TEXT_SUFFIX:
                payloads=[p.read_text(encoding='utf-8',errors='replace')[:20000]]
            else:
                unsupported+=1; warnings.append(f"unsupported file skipped: {p}"); continue
            for payload in payloads:
                rec=normalize_artifact(payload,str(p),source_kind).to_dict(); records.append(rec); loaded+=1
                if rec['artifact_type']=='unknown': unsupported+=1
        except Exception as exc:
            malformed+=1; records.append(normalize_artifact({"error_type":exc.__class__.__name__,"source_path":str(p)},str(p),source_kind,malformed=True).to_dict())
    return {"scanned_paths":paths,"found_count":len(_iter_paths(paths)),"loaded_count":loaded,"malformed_count":malformed,"unsupported_count":unsupported,"records":records,"warnings":warnings,"errors":errors,"side_effects":{"read_only":True,"source_files_modified":False,"production_db_write":False,"secrets_read":False,"line_sent":False,"email_sent":False,"dashboard_published":False,"production_pipeline_run":False}}
def missing_path_result(path:str)->dict[str,Any]:
    return {"scanned_paths":[path],"found_count":0,"loaded_count":0,"malformed_count":0,"unsupported_count":0,"records":[],"warnings":[f"missing path: {path}"],"errors":[],"side_effects":{"read_only":True}}
