# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Vũ Quang Tiến |
| MSSV | 2A202602872 |
| Khóa/Lớp | K4 |
| Tên nhóm | Succulent |
| Vai trò chính | Observability & Evaluation |
| Repository | https://github.com/Munfond/K4-L3A-Day10-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Quality Gate GX 1.x | `src/observability/quality.py`: `run_data_quality_checks` | Clean DataFrame | Báo cáo chất lượng JSON và trạng thái pass/fail | Hoàn thành |
| Freshness SLA | `src/observability/quality.py`: `build_freshness_report` | `published`, `age_days` | Báo cáo freshness JSON | Hoàn thành |
| Benchmark test set | `src/evaluation/testset.py`: `build_test_set` | Clean DataFrame | `data/eval/test_set.json` gồm 10 câu hỏi | Hoàn thành |
| Markdown reporting | `src/observability/reporting.py` | Metrics, quality và freshness payload | Báo cáo phase 1 và so sánh corruption/repair | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Xác minh môi trường | Toàn bộ pipeline | Cài PyTorch bản CPU để tránh phụ thuộc CUDA; smoke test thư viện cốt lõi thành công. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Kiểm định chất lượng | `quality.py` | 6 rule GX: row count, ba trường bắt buộc, unique `paper_id`, độ dài summary | Chạy DataFrame mẫu hợp lệ, `success=True`. |
| Freshness monitoring | `quality.py` | Tính số/tỷ lệ stale, mốc mới nhất/cũ nhất, cờ `is_fresh` | DataFrame mẫu với `age_days=24` trả `is_fresh=True`. |
| Sinh benchmark | `testset.py` | 10 records, đủ `summary`, `authors`, `date`, `categories` | Smoke test xác nhận 10 câu và đủ bốn `question_type`. |
| Sinh báo cáo | `reporting.py` | Markdown cho baseline và baseline/corrupted/repaired | Hàm đã chạy với payload kiểm thử. |

Artifact kiểm thử được tạo trong thư mục tạm rồi loại bỏ, vì chúng dùng dữ liệu giả lập. Artifact chính thức chỉ được tạo khi nhóm chạy baseline và corruption flow trên raw/clean dataset thật.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

RAG có thể vẫn trả lời trôi chảy khi dữ liệu thiếu, cũ, rỗng hoặc bị trùng. Phần việc của tôi đặt một quality gate trước vector index, theo dõi dữ liệu quá hạn và tạo một benchmark cố định để có bằng chứng định lượng cho baseline, corruption và repair.

### Cách triển khai

Quality Gate sử dụng `gx.get_context(mode="ephemeral")`, tạo Pandas datasource, dataframe asset, batch definition và batch hoàn toàn trong RAM theo API Great Expectations 1.x. Các expectation kiểm tra row count 5–5000; `paper_id`, `title`, `text_for_embedding` không null; `paper_id` không trùng; và `summary` có ít nhất 30 ký tự. Kết quả từng expectation cùng trạng thái tổng hợp được ghi JSON.

Freshness report xác định bài stale bằng `age_days > 180`. Nếu stale ratio vượt 25%, `is_fresh` là `False`. Test set được tạo deterministically bằng cách sắp xếp `paper_id`, nên các lần chạy trên cùng cleaned dataset tạo câu hỏi và ground-truth ID ổn định. Reporting chỉ nhận payload của pipeline và ghi Markdown, không tự suy diễn metrics.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Clean DataFrame có `paper_id`, `title`, `summary`, `text_for_embedding`, `authors_joined`, `published`, `categories_joined`, `age_days`. |
| Output | Quality/freshness JSON; test set JSON; phase-1 và comparison Markdown. |
| Module phụ thuộc | `core.config`, `core.utils`, Great Expectations 1.x, pandas. |
| Module sử dụng output | `phase1.py`, `corruption_flow.py`, `evaluation.metrics.py` và báo cáo nhóm. |
| Điều kiện lỗi cần xử lý | Thiếu cột contract hoặc số paper dưới 4 sẽ raise `ValueError` rõ ràng thay vì tạo output sai. |

### Cách xác minh

```bash
source .venv/bin/activate
python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); print(run_data_quality_checks(df, s, 'baseline')['success'])"
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); print(len(build_test_set(pd.read_json(s.paths.clean_json), s.paths.eval_testset)))"
```

- **Kết quả đã xác minh:** Môi trường import thành công; smoke test DataFrame hợp lệ cho quality gate trả `True`, test set có 10 câu thuộc đủ bốn nhóm.
- **Artifact/log chính thức:** Sẽ nằm ở `data/quality/`, `data/eval/test_set.json` và `data/reports/` sau khi pipeline hoàn chỉnh được chạy.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Great Expectations có các API datasource cũ không tương thích với GX 1.x.
- **Các phương án đã cân nhắc:** Dùng API cũ `context.sources.pandas_default`; hoặc dùng ephemeral context với `data_sources.add_pandas()`.
- **Phương án đã chọn:** Ephemeral context GX 1.x.
- **Lý do:** Đúng yêu cầu bài lab, không tạo cấu hình GX rác trên ổ đĩa và cho phép mỗi run kiểm định chính xác DataFrame đầu vào.
- **Bằng chứng:** Smoke test đã tạo batch từ Pandas DataFrame và sáu expectation trả trạng thái pass.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `OSError: libcudart.so.13: cannot open shared object file` khi import PyTorch.
- **Lệnh tái hiện:** `python -c "import torch"` trong `.venv`.
- **Nguyên nhân gốc:** Wheel PyTorch CUDA được cài trên máy không có CUDA runtime.
- **Cách xử lý:** Thay bằng wheel `torch 2.14.0+cpu` tương thích Python 3.13.
- **Cách xác minh sau khi sửa:** `python -c "import torch; print(torch.__version__)"` in `2.14.0+cpu`; smoke test môi trường in `Môi trường sẵn sàng`.
- **Điều học được:** Cần xác nhận loại wheel (CPU/GPU) ngay khi thiết lập môi trường cho pipeline embedding.

## 7. Hiểu biết về luồng end-to-end

1. Crossref được lấy/lưu raw, làm sạch thành schema chuẩn cùng `text_for_embedding`, qua quality gate, sau đó được embedding và nạp vào collection ChromaDB.
2. Mỗi câu trong evaluation set liên kết với `ground_truth_doc_ids`; retrieval hit kiểm tra document đúng có trong kết quả truy xuất, còn answer được so với `ground_truth` bằng Token F1 và judge.
3. Quality checks kiểm tra tính hợp lệ/cấu trúc dữ liệu tại thời điểm chạy; freshness monitoring đo rủi ro dữ liệu cũ theo `age_days` và SLA.
4. Cùng test set giữ cố định biến câu hỏi và đáp án, nên chênh lệch metric phản ánh dữ liệu/index chứ không phải đề khác nhau.
5. Repair thành công khi artifact repaired qua quality/freshness gate và metrics repaired phục hồi về gần baseline trong comparison report.

## 8. Phân tích kết quả

Metrics chính thức chưa được điền vì `phase1.py` và `corruption_flow.py` vẫn là phần tích hợp của nhóm cần chạy trên dữ liệu thật. Không ghi số liệu giả lập vào báo cáo.

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | Chưa chạy | Chưa chạy | Chưa chạy | Đọc từ các JSON metrics khi integration hoàn thành. |
| `mean_token_f1` | Chưa chạy | Chưa chạy | Chưa chạy | So sánh trên cùng test set. |
| Quality checks | Chưa chạy | Chưa chạy | Chưa chạy | Corruption phải kích hoạt ít nhất một rule. |
| Freshness status | Chưa chạy | Chưa chạy | Chưa chạy | Stale-date scenario phải ảnh hưởng freshness. |

## 9. Điều học được và hướng cải thiện

1. Data quality cần được kiểm tra trước index để chặn silent failure.
2. Freshness là tín hiệu vận hành riêng, không thay thế kiểm định schema/nội dung.
3. Benchmark cố định giúp đánh giá hiệu quả repair một cách công bằng.

Nếu có thêm thời gian, tôi sẽ bổ sung dashboard hiển thị kết quả GX, stale ratio và metrics qua ba trạng thái, đồng thời theo dõi trend freshness theo từng run.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận đã nêu đều phân biệt rõ giữa smoke test và metrics chưa chạy.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Vũ Quang Tiến  
**Ngày xác nhận:** 2026-09-25
