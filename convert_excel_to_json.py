import sys
import pandas as pd
import json

# Ép kiểu encoding của sys.stdout sang utf-8 để tránh lỗi khi in tiếng Việt trên CMD Windows
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def excel_to_json(excel_path, json_path):
    try:
        # Đọc file Excel
        df = pd.read_excel(excel_path)
        
        # Thay thế các giá trị NaN (ô trống) thành chuỗi rỗng
        df = df.fillna("")
        
        json_data = []
        for index, row in df.iterrows():
            metadata = {}
            
            # Quét tất cả các cột tự động dựa theo file Excel
            for col in df.columns:
                val = row[col]
                
                # Xử lý định dạng dữ liệu (vd: ép kiểu giá tiền về dạng int thay vì float)
                if col == 'gia_vnd' and val != "":
                    metadata[col] = int(val)
                elif isinstance(val, float) and val.is_integer():
                    # Các số nguyên bị pandas nhận diện là float (vd: 1.0) -> chuyển về string "1"
                    metadata[col] = str(int(val))
                else:
                    metadata[col] = str(val) if val != "" else ""

            # Tạo object theo cấu trúc chuẩn có id và metadata
            item = {
                "id": f"pkg_{index + 1:03d}",
                "metadata": metadata
            }
            json_data.append(item)

        # Ghi dữ liệu ra file JSON
        # Sử dụng ensure_ascii=False để hiển thị đúng Tiếng Việt, không bị mã hoá \u
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
            
        print(f"Đã chuyển đổi thành công {len(json_data)} gói cước từ '{excel_path}' sang '{json_path}'.")

    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")

if __name__ == "__main__":
    # Đường dẫn file đầu vào và đầu ra
    excel_file = 'docs/goi_cuoc.xlsx'
    json_file = 'docs/goi_cuoc.json'
    
    excel_to_json(excel_file, json_file)
