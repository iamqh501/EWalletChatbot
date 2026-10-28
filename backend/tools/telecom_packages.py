import logging
import os
import json
from typing import Optional, List
from backend.core.config import TELECOM_PACKAGES_FILE
from backend.tools.schemas import TelecomPackage, ToolResultItem

logger = logging.getLogger(__name__)


def load_package_data() -> List[TelecomPackage]:
    """Tải và parse dữ liệu các gói cước từ file cấu hình TELECOM_PACKAGES_FILE."""
    package_data: List[TelecomPackage] = []
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

    return package_data


def execute_search_telecom_packages(
    package_name: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    cycle_days_min: Optional[int] = None,
    cycle_days_max: Optional[int] = None,
    data_gb_per_day_min: Optional[float] = None,
    data_gb_per_day_max: Optional[float] = None,
    packages: Optional[List[TelecomPackage]] = None
) -> ToolResultItem:
    """Tìm kiếm, sắp xếp tối ưu các gói cước điện thoại dựa trên tiêu chí và đóng gói ToolResultItem."""
    package_list = packages if packages is not None else load_package_data()

    results = []
    for item in package_list:
        pkg_name = item.package_name
        price_val = item.price_vnd
        cycle_val = item.cycle_days
        data_val = item.data_gb_per_day

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
        res_text = json.dumps({"error": "Không tìm thấy gói cước nào thoả mãn."}, ensure_ascii=False)
    else:
        target = sum(v) / len(v) if (v := {cycle_days_min, cycle_days_max} - {None}) else None
        if target:
            results = sorted(results, key=lambda x: (abs(x[1] - target), x[2]))
        else:
            results = sorted(results, key=lambda x: x[2])

        output = [r[0] for r in results]
        res_text = json.dumps(output, ensure_ascii=False, indent=2)

    ctx_block = f"Kết quả tra cứu gói cước viễn thông:\n{res_text}"

    args_dict = {
        "package_name": package_name,
        "price_min": price_min,
        "price_max": price_max,
        "cycle_days_min": cycle_days_min,
        "cycle_days_max": cycle_days_max,
        "data_gb_per_day_min": data_gb_per_day_min,
        "data_gb_per_day_max": data_gb_per_day_max
    }
    args_str = ", ".join([f"{k}={repr(v)}" for k, v in args_dict.items() if v is not None])
    short_res = res_text[:2500] + "..." if len(res_text) > 2500 else res_text
    tool_log = f"**[GỌI TOOL]**\n\n`search_telecom_packages({args_str})`\n\n```\n{short_res}\n```\n"

    return ToolResultItem(
        tool="search_telecom_packages",
        context_block=ctx_block,
        tool_log=tool_log,
        data=res_text
    )
