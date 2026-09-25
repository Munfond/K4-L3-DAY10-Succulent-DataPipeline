# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Đặng Nam Khánh |
| MSSV | 2A202602741 |
| Khóa/Lớp | K4-L3-DAY10 |
| Tên nhóm | Succulent |
| Vai trò chính | Phụ trách Ingestion, Làm sạch & Phục hồi dữ liệu |
| Repository | https://github.com/Munfond/K4-L3A-Day10-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-25 |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Crossref Ingestion & Fallback | `src/ingestion/crossref.py`: `fetch_source_records`, `load_raw_records`, `parse_crossref_payload` | Crossref REST API query hoặc local snapshot file | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` (24 bản ghi) | Hoàn thành |
| Data Cleaning & Feature Engineering | `src/ingestion/cleaning.py`: `build_clean_dataframe` | Danh sách `PaperRecord` raw | `data/clean/papers_clean.csv`, `data/clean/papers_clean.json` (24 dòng sạch) | Hoàn thành |
| Idempotent Repair Engine | `src/ingestion/cleaning.py`: `repair_from_raw_snapshot` | `data/raw/crossref_records.json` | `data/clean/papers_clean_repaired.csv`, `data/clean/papers_clean_repaired.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Phối hợp với RAG & Vector Index | Thành viên 3 (RAG & Vector Index) | Thống nhất cấu trúc trường `text_for_embedding` đúng 5 phần để sinh embedding vector tối ưu cho ChromaDB. |
| Phối hợp với Observability & Quality | Thành viên 4 (Observability) | Đảm bảo tính toán trường `age_days` chuẩn UTC và không chứa giá trị Null để vượt qua các rule của Great Expectations 1.x. |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Thu thập dữ liệu nguồn | `crossref.py` | 24 bản ghi học thuật chuẩn quốc tế, hỗ trợ fallback offline 100% | Lệnh kiểm tra CP0 in đủ 24 bài báo |
| Làm sạch và chuẩn hóa schema | `cleaning.py` | 24 dòng sạch: bỏ thẻ JATS XML, chuẩn hóa whitespace, tính `age_days`, tạo `text_for_embedding` | Lệnh kiểm tra CP1 in `Clean thành công 24 dòng` |
| Phục hồi dữ liệu nguồn | `cleaning.py` | Tái tạo dữ liệu sạch sau khi bị phá hoại bằng 6 kịch bản corruption | Chạy Idempotent Repair trong `corruption_flow.py` |

**Output cụ thể bàn giao:**  
Hai bộ artifact cốt lõi bảo đảm Data Lineage:
- `data/raw/crossref_records.json`: Chứa 24 bản ghi thô làm điểm tựa nguồn (Single Source of Truth).
- `data/clean/papers_clean.json`: Chứa dữ liệu đã xử lý chuẩn chỉ, sẵn sàng cho embedding và evaluation.

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Dữ liệu thu thập từ các API bên ngoài (như Crossref) thường xuyên gặp các vấn đề:
1. Phụ thuộc mạng không ổn định (rate limit, timeout, mất mạng).
2. Dữ liệu thô chứa thẻ HTML/XML (JATS XML tags như `<jats:p>`, `<jats:italic>`), khoảng trắng thừa, ngày tháng không đồng nhất.
3. Nguy cơ dữ liệu bị biến đổi hoặc làm bẩn trong quá trình lưu trữ mà không có khả năng khôi phục về trạng thái nguyên bản.

### Cách triển khai
1. **Thu thập có cơ chế Fallback ngoại tuyến (`crossref.py`):**
   - Hàm `fetch_source_records` ưu tiên gọi API trực tiếp với timeout và headers định danh.
   - Nếu xảy ra lỗi mạng hoặc API trả về mã lỗi, hàm tự động bắt ngoại lệ và kích hoạt cơ chế fallback đọc từ `data/raw/crossref_records.json` hoặc parse từ `crossref_response.json`.
2. **Làm sạch và mô hình hóa dữ liệu (`cleaning.py`):**
   - Loại bỏ toàn bộ các thẻ JATS XML bằng regex.
   - Tính toán trường `age_days = (reference_datetime - published_date).days`.
   - Sinh trường `text_for_embedding` kết hợp có cấu trúc:
     ```text
     Title: <title>
     Authors: <authors_joined>
     Published: <published>
     Categories: <categories_joined>
     Summary: <summary>
     ```
   - Khử trùng lặp bản ghi dựa trên khóa chính `paper_id`.
3. **Cơ chế Idempotent Repair:**
   - Hàm `repair_from_raw_snapshot` nạp lại snapshot thô từ `data/raw/crossref_records.json` và tái thực thi quy trình làm sạch. Quá trình này hoàn toàn khép kín cục bộ, không phụ thuộc vào internet, đảm bảo tính lũy thừa (chạy n lần vẫn ra cùng một kết quả sạch duy nhất).

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | JSON response từ Crossref API hoặc file snapshot `crossref_records.json` |
| Output | DataFrame sạch và các file CSV/JSON trong `data/clean/` |
| Module phụ thuộc | Phụ thuộc vào `core.config`, `core.utils` |
| Module sử dụng output | `retrieval.index` (nhận `text_for_embedding`), `observability.quality` (kiểm định schema và `age_days`) |
| Điều kiện lỗi cần xử lý | Mất kết nối internet, bản ghi thiếu trường dữ liệu, ngày tháng sai định dạng |

### Cách xác minh
```bash
# Kiểm tra Ingestion & Fallback
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); print(f'Tín hiệu hoàn thành: Đã nạp {len(fetch_source_records(s))} bài báo')"

# Kiểm tra Cleaning & Schema
python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng')"
```
- **Kết quả mong đợi:** Cả 2 lệnh in đúng tín hiệu hoàn thành với 24 bản ghi.
- **Kết quả thực tế:** Khớp 100% với mong đợi.

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn chiến lược lưu trữ dữ liệu thô phục vụ cho việc khôi phục (Data Recovery).
- **Các phương án đã cân nhắc:**
  1. Chỉ lưu duy nhất 1 file thô nguyên bản của API (`crossref_response.json`).
  2. Lưu trữ 2 cấp độ raw artifacts: `crossref_response.json` (toàn bộ payload API) và `crossref_records.json` (danh sách bản ghi đã parse chuẩn hóa).
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Giữ nguyên vẹn Data Lineage từ phản hồi gốc của bên thứ 3, đồng thời tạo một snapshot thô đã parse giúp tiến trình Idempotent Repair có thể thực hiện tức thì mà không cần tốn thời gian parse lại JSON lồng nhau phức tạp của API.
- **Bằng chứng:** Hàm `repair_from_raw_snapshot` thực thi chỉ mất chưa đầy 0.05 giây để phục hồi hoàn toàn 24 bài báo khi chạy script `run_corruption_flow.py`.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Văn bản trong trường `summary` lấy từ Crossref chứa nhiều thẻ JATS XML như `<jats:p>`, `<jats:italic>`, `<jats:bold>`, dẫn đến trường `summary_chars` bị sai lệch và làm ô nhiễm ngữ nghĩa khi đưa vào mô hình vector embedding.
- **Lệnh tái hiện:** Xem nội dung thô trong `data/raw/crossref_records.json`.
- **Nguyên nhân gốc:** Crossref API trả về phần abstract theo chuẩn xuất bản NISO JATS XML.
- **Cách xử lý:** Bổ sung bước xử lý regex `re.sub(r"<[^>]+>", " ", text)` kết hợp chuẩn hóa khoảng trắng thừa trong hàm làm sạch `clean_text`.
- **Cách xác minh sau khi sửa:** Toàn bộ 24 bài báo sau khi làm sạch không còn bất kỳ ký tự XML nào, văn bản tự nhiên, mạch lạc.
- **Điều học được:** Tầng Data Ingestion luôn phải giả định dữ liệu từ bên ngoài là "không đáng tin cậy" về mặt format và cần phải có bước thanh lọc kỹ lưỡng trước khi đưa vào các tầng tiếp theo.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index:** Dữ liệu bắt đầu từ yêu cầu HTTP tới Crossref API $\rightarrow$ lưu snapshot thô $\rightarrow$ qua module cleaning để bóc tách text, chuẩn hóa trường, tính ngày tuổi $\rightarrow$ ghép thành `text_for_embedding` $\rightarrow$ truyền sang module Retrieval để biến đổi thành vector 384 chiều và lưu trữ vào ChromaDB.
2. **Evaluation set và ground-truth document IDs:** Test set 10 câu hỏi gắn liền với `paper_id` của từng bài báo gốc. Điều này giúp đánh giá chính xác xem hệ thống Retrieval có lấy đúng tài liệu chứa thông tin hay không (Hit Rate).
3. **Quality checks khác freshness monitoring:**
   - Quality checks đảm bảo tính đúng đắn về hình thức và cấu trúc dữ liệu (không có null, không có bản ghi trùng lặp, đủ số lượng).
   - Freshness monitoring đảm bảo giá trị nghiệp vụ theo thời gian của dữ liệu (dữ liệu không được quá cũ so với ngưỡng SLA 180 ngày).
4. **Vì sao phải dùng cùng test set cho cả 3 trạng thái:** Dùng cùng một thước đo cố định giúp cô lập biến số duy nhất là chất lượng của dữ liệu, từ đó chứng minh được mối quan hệ nhân quả giữa dữ liệu bẩn và sự sụt giảm chất lượng của RAG Agent.
5. **Tiêu chí repair thành công:** Báo cáo so sánh thể hiện các chỉ số của giai đoạn Repaired tương đương hoàn toàn với giai đoạn Baseline ban đầu (Hit Rate = 1.0, Token F1 = 0.8, Quality = PASSED, Freshness = HEALTHY).

---

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.7000 | 1.0000 | Bị sụt giảm 30% khi bị drop bài báo và làm bẩn text; phục hồi lại 100% sau repair. |
| `mean_token_f1` | 0.8000 | 0.7000 | 0.8000 | Chất lượng câu trả lời phục hồi nguyên trạng sau khi tái thiết dữ liệu sạch. |
| `judge_accuracy` | 0.8000 | 0.7000 | 0.8000 | Đánh giá của Judge phục hồi về mức 80% độ chính xác. |
| `mean_judge_score` | 4.20 | 3.80 | 4.20 | Điểm judge trung bình phục hồi từ 3.8 lên 4.2. |
| Quality checks | PASSED | FAILED | PASSED | Phát hiện vi phạm chất lượng dữ liệu khi bị tiêm lỗi và pass lại sau khi sửa chữa. |
| Freshness status | HEALTHY | ALERT | HEALTHY | Khắc phục được cảnh báo quá hạn tuổi bài báo sau khi khôi phục snapshot chuẩn. |

### Kết luận từ số liệu
1. **Chuỗi suy giảm:** Dữ liệu bị làm bẩn (cắt tiêu đề, xóa tóm tắt, trùng lặp, đẩy lùi ngày) $\rightarrow$ Great Expectations báo FAILED và Freshness báo ALERT $\rightarrow$ Retrieval Hit Rate sụt giảm nghiêm trọng xuống 0.7.
2. **Chuỗi phục hồi:** Thực thi `repair_from_raw_snapshot` $\rightarrow$ Tái lập toàn bộ 24 dòng sạch $\rightarrow$ Great Expectations đạt PASSED, Freshness về HEALTHY $\rightarrow$ Retrieval Hit Rate phục hồi về 1.0000.

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất
1. **Về Data Pipeline:** **Data Lineage** (Truy vết nguồn gốc dữ liệu) là nguyên tắc bất di bất dịch; không bao giờ được ghi đè trực tiếp lên dữ liệu nguồn nếu không có snapshot bảo lưu.
2. **Về Data Quality/Observability:** Cần phải thiết lập các chốt chặn kiểm định (Quality Gates) ngay sau bước Ingestion/Cleaning để ngăn chặn dữ liệu rác lan truyền xuống các tầng sau (Data Leakage).
3. **Về Phục hồi dữ liệu:** Cơ chế **Idempotent Repair** từ raw snapshot là giải pháp tối ưu nhất để xử lý thảm họa dữ liệu, giúp hệ thống tự phục hồi mà không phụ thuộc vào các dịch vụ bên ngoài.

### Nếu có thêm thời gian
Tôi sẽ xây dựng cơ chế **Incremental Ingestion & Deduplication nâng cao**: Tự động phát hiện các bài báo mới được xuất bản thông qua Crossref Cursor / Polling định kỳ, kết hợp đối chiếu vector similarity để loại bỏ các bản thảo (preprint) trùng lặp trước khi nạp vào kho dữ liệu.

---

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Đặng Nam Khánh  
**Ngày xác nhận:** 2026-09-25
