import logging
import os
import json
from typing import Optional, List, Dict, Any, Union
from backend.core.config import TELECOM_PACKAGES_FILE
from backend.tools.schemas import TelecomPackage

logger = logging.getLogger(__name__)

_cached_packages: Optional[List[TelecomPackage]] = None


def load_package_data(force_reload: bool = False) -> List[TelecomPackage]:
    """Tải và parse dữ liệu các gói cước từ file cấu hình TELECOM_PACKAGES_FILE với in-memory cache."""
    global _cached_packages
    if _cached_packages is not None and not force_reload:
        return _cached_packages

    package_data = []
    try:
        if os.path.exists(TELECOM_PACKAGES_FILE):
            with open(TELECOM_PACKAGES_FILE, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            for item in raw_data:
                meta = item.get("metadata", {})
                try:
                    price = meta.get("gia_vnd", 0)
                    cycle = meta.get("chu_ky_d", 0)
                    data_gb = meta.get("trung_binh_ngay", 0)
                    package_data.append(TelecomPackage(
                        package_name=str(meta.get("ten_goi", "")),
                        price_vnd=float(price) if price != "" else 0.0,
                        cycle_days=int(cycle) if cycle != "" else 0,
                        data_gb_per_day=float(data_gb) if data_gb != "" else 0.0
                    ))
                except (ValueError, TypeError) as row_err:
                    logger.warning("Skipping invalid telecom package entry %s: %s", meta, row_err)
    except Exception as e:
        logger.error("Error reading package file: %s", e)

    _cached_packages = package_data

    # Đồng bộ với app_state nếu đang chạy trong tiến trình FastAPI
    try:
        from backend.core.state import app_state
        app_state.telecom_packages = package_data
    except Exception:
        pass

    return _cached_packages


def execute_search_telecom_packages(
    package_name: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    cycle_days_min: Optional[int] = None,
    cycle_days_max: Optional[int] = None,
    data_gb_per_day_min: Optional[float] = None,
    data_gb_per_day_max: Optional[float] = None,
    data: Optional[List[Union[TelecomPackage, Dict[str, Any]]]] = None
) -> str:
    """Tìm kiếm và đề xuất các gói cước điện thoại dựa trên tiêu chí và sắp xếp tối ưu."""
    if data is not None:
        package_list = data
    else:
        try:
            from backend.core.state import app_state
            package_list = getattr(app_state, "telecom_packages", None) or load_package_data()
        except Exception:
            package_list = load_package_data()

    results = []
    for item in package_list:
        pkg_name = item.package_name if isinstance(item, TelecomPackage) else item["package_name"]
        price_val = item.price_vnd if isinstance(item, TelecomPackage) else item["price_vnd"]
        cycle_val = item.cycle_days if isinstance(item, TelecomPackage) else item["cycle_days"]
        data_val = item.data_gb_per_day if isinstance(item, TelecomPackage) else item["data_gb_per_day"]

        if package_name and package_name.upper() not in pkg_name.upper():
            continue
        if price_min is not None and price_val < price_min:
            continue
        if price_max is not None and price_val > price_max:
            continue
        if cycle_days_min is not None and cycle_val < cycle_days_min:
            continue
        if cycle_days_max is not None and cycle_val > cycle_days_max:
            continue
        if data_gb_per_day_min is not None and data_val < data_gb_per_day_min:
            continue
        if data_gb_per_day_max is not None and data_val > data_gb_per_day_max:
            continue

        formatted = {
            "Package Name": pkg_name,
            "Price (VND)": price_val,
            "Cycle (days)": cycle_val,
            "Data per day (GB)": data_val
        }
        results.append((formatted, cycle_val, price_val))

    if not results:
        return json.dumps({"error": "Không tìm thấy gói cước nào thoả mãn."}, ensure_ascii=False)

    target = sum(v) / len(v) if (v := {cycle_days_min, cycle_days_max} - {None}) else None
    if target:
        results = sorted(results, key=lambda x: (abs(x[1] - target), x[2]))
    else:
        results = sorted(results, key=lambda x: x[2])

    output = []
    for r in results:
        output.append(r[0])
    return json.dumps(output, ensure_ascii=False, indent=2)
