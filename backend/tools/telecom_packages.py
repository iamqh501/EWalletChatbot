import os
import json
from typing import Optional, List, Dict, Any
from backend.core.config import DOCS_DIR


def load_package_data() -> List[Dict[str, Any]]:
    """Tải và parse dữ liệu các gói cước từ file docs/goi_cuoc.json."""
    package_data = []
    try:
        json_path = os.path.join(DOCS_DIR, "goi_cuoc.json")
        with open(json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        for item in raw_data:
            meta = item.get("metadata", {})
            try:
                price = meta.get("gia_vnd", 0)
                cycle = meta.get("chu_ky_d", 0)
                data_gb = meta.get("trung_binh_ngay", 0)
                package_data.append({
                    "package_name": str(meta.get("ten_goi", "")),
                    "price_vnd": float(price) if price != "" else 0.0,
                    "cycle_days": int(cycle) if cycle != "" else 0,
                    "data_gb_per_day": float(data_gb) if data_gb != "" else 0.0
                })
            except (ValueError, TypeError):
                pass
    except Exception as e:
        print(f"Error reading package file: {e}")
    return package_data


def execute_search_telecom_packages(
    package_name: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    cycle_days_min: Optional[int] = None,
    cycle_days_max: Optional[int] = None,
    data_gb_per_day_min: Optional[float] = None,
    data_gb_per_day_max: Optional[float] = None,
    data: Optional[List[Dict[str, Any]]] = None
) -> str:
    """Tìm kiếm và đề xuất các gói cước điện thoại dựa trên tiêu chí và sắp xếp tối ưu."""
    package_list = data if data is not None else load_package_data()
    results = []
    for item in package_list:
        if package_name and package_name.upper() not in item["package_name"].upper():
            continue
        if price_min is not None and item["price_vnd"] < price_min:
            continue
        if price_max is not None and item["price_vnd"] > price_max:
            continue
        if cycle_days_min is not None and item["cycle_days"] < cycle_days_min:
            continue
        if cycle_days_max is not None and item["cycle_days"] > cycle_days_max:
            continue
        if data_gb_per_day_min is not None and item["data_gb_per_day"] < data_gb_per_day_min:
            continue
        if data_gb_per_day_max is not None and item["data_gb_per_day"] > data_gb_per_day_max:
            continue

        formatted = {
            "Package Name": item["package_name"],
            "Price (VND)": item["price_vnd"],
            "Cycle (days)": item["cycle_days"],
            "Data per day (GB)": item["data_gb_per_day"]
        }
        results.append((formatted, item["cycle_days"], item["price_vnd"]))

    if not results:
        return json.dumps({"error": "Không tìm thấy gói cước nào thoả mãn."}, ensure_ascii=False)

    target = sum(v) / len(v) if (v := {cycle_days_min, cycle_days_max} - {None}) else None
    if target:
        results = sorted(results, key=lambda x: (abs(x[1] - target), x[2]))
    else:
        results = sorted(results, key=lambda x: x[2])

    return json.dumps({"matched_plans": [x[0] for x in results]}, ensure_ascii=False)
