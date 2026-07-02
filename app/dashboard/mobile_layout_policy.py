"""Mobile-first layout policy for repo-side preview rendering."""
from __future__ import annotations
from typing import Any, Dict

def preview_metadata() -> Dict[str, Any]:
    return {
        "preview_type": "repo_side_static_mobile_first",
        "production_publish_allowed": False,
        "target_width": "iPhone/mobile first",
        "css_policy": "inline_css_no_external_cdn",
        "javascript_required": False,
        "safe_output_locations": ["templates/dashboard_intelligence_preview.example.html"],
        "forbidden_output_locations": ["/var/www/stock-ai-dashboard"],
    }
