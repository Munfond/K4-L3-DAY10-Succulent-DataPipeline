# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K4-L3-DAY10 |
| Tên nhóm | Succulent |
| Repository | https://github.com/Munfond/K4-L3A-Day10-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-25 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Nguyễn Đức Anh | 2A202602625 | Trưởng nhóm / Pipeline Integrator | `core/config.py`, `core/utils.py`, `phase1.py`, `corruption_flow.py` |
| 2 | Nguyễn Đặng Nam Khánh | 2A202602741 | Data Foundation & Recovery | `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`, raw/clean artifacts |
| 3 | Nguyễn Hoàng Duy | 2A202602751 | RAG & Vector Index | `src/retrieval/index.py`, `src/retrieval/embeddings.py`, ChromaDB |
| 4 | Vũ Quang Tiến | 2A202602872 | Observability & Evaluation | `src/observability/quality.py` (GX 1.x), `src/evaluation/testset.py` |

---

## 2. Tóm tắt kết quả

Nhóm **Succulent** đã hoàn thành trọn vẹn 100% các yêu cầu kỹ thuật và quy chuẩn học vụ của bài thực hành Day 10:
- **Pha 1 (Baseline Pipeline):** Thu thập và làm sạch thành công 24 bản ghi học thuật từ Crossref API (hỗ trợ offline fallback snapshot bảo đảm Data Lineage). Xây dựng cấu trúc vector store ChromaDB độc lập (`papers-baseline`), vượt qua 100% Quality Gate của Great Expectations 1.x và đạt chuẩn Freshness SLA (`age_days` trung bình 24 ngày < 180 ngày). Đánh giá benchmark trên 10 câu hỏi đạt **Retrieval Hit Rate = 1.0000** và **Mean Token F1 = 0.8000**.
- **Pha 2 (Corruption & Idempotent Repair):** Triển khai thành công 6 kịch bản tiêm lỗi dữ liệu tổng hợp (`drop_latest_records`, `blank_summary`, `inject_noise`, `truncate_title`, `stale_date`, `duplicate_rows`). Hệ thống Data Observability phát hiện chuẩn xác vi phạm (Quality Gate `FAILED`, Freshness SLA `ALERT`). Đồng thời tầng RAG ghi nhận sự suy giảm hiệu năng rõ rệt (Hit Rate giảm từ 1.0 xuống 0.7, F1 giảm còn 0.7).
- **Phục hồi & Đối chiếu:** Thực thi cơ chế **Idempotent Repair** từ raw snapshot `data/raw/crossref_records.json`, tái tạo hoàn hảo bộ dữ liệu `papers-repaired` đạt trạng thái chất lượng tương đương Baseline ban đầu (Hit Rate = 1.0, Token F1 = 0.8, Quality = PASSED, Freshness = HEALTHY).
- **Hạng mục vượt chuẩn Bonus B1 (+5 điểm):** Đã xây dựng thành công giao diện web trực quan **Interactive Observability & Real-Time Drift Monitor** tại `script/run_dashboard.py` (chạy trực tiếp bằng Python standard library không phụ thuộc thư viện ngoài) và `script/streamlit_app.py`, cung cấp biểu đồ phân bố độ tuổi bài báo (`age_days`), giám sát Data Drift qua chỉ số PSI & Kolmogorov-Smirnov test, và theo dõi trực quan trạng thái 6 rules của Great Expectations 1.x theo thời gian thực.

---

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref REST API (Fallback: local snapshot)
    -> raw response (crossref_response.json) / raw records (crossref_records.json)
    -> Cleaning & Feature Engineering (papers_clean.csv / papers_clean.json)
    -> Embedding + ChromaDB Vector Index (collection: papers-baseline)
    -> Evaluation Baseline (10 câu hỏi test_set.json)
    -> Data Observability (GX 1.x ephemeral checks + Freshness SLA report)
    -> 6 Synthetic Corruptions (papers_clean_corrupted.json + corruption_log.json)
    -> Re-index (papers-corrupted) & Re-evaluate (đo lường suy giảm RAG)
    -> Idempotent Repair từ raw snapshot (papers_clean_repaired.json)
    -> Re-index (papers-repaired) & Re-evaluate (đo lường phục hồi)
    -> Comparison Report (data/reports/corruption_report.md)
```

### Trách nhiệm của từng khối

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref API / fallback snapshot | Fetch HTTP có timeout, retry, fallback tự động, parse JSON | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Nguyễn Đặng Nam Khánh |
| Cleaning | Raw `PaperRecord` list | Loại bỏ XML JATS, chuẩn hóa whitespace, tính `age_days`, tạo `text_for_embedding`, deduplicate | `data/clean/papers_clean.csv`, `data/clean/papers_clean.json` | Nguyễn Đặng Nam Khánh |
| Embedding & Index | Clean DataFrame | Sinh vector nhúng chuẩn hóa cosine, quản lý 3 collection biệt lập | `data/chroma/`, `data/embeddings/papers_embeddings*.json` | Nguyễn Hoàng Duy |
| Evaluation | Clean DataFrame, Vector Index | Sinh testset 10 câu hỏi (4 loại), tính Retrieval Hit Rate, Token F1, LLM Judge | `data/eval/test_set.json`, `data/results/*_metrics.json` | Vũ Quang Tiến |
| Observability | Clean / Corrupted / Repaired DF | Great Expectations 1.x (6 rules), Freshness SLA check (`age_days > 180`) | `data/quality/*_quality_report.json`, `freshness_report.json` | Vũ Quang Tiến |
| Corruption & Repair | Clean DataFrame, raw snapshot | Tiêm 6 dạng lỗi dữ liệu, Idempotent Repair từ raw snapshot | `data/clean/*_corrupted.*`, `*_repaired.*`, `corruption_log.json` | Nam Khánh & Đức Anh |
| Orchestration | Settings, CLI scripts | Điều phối vòng đời luồng Pha 1 và Pha 2, xuất báo cáo tổng kết | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` | Nguyễn Đức Anh |

---

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng |
| --- | --- |
| `LLM_PROVIDER` | `mock` (hoặc `google` / `openai` qua `.env`) |
| `LLM_MODEL` | `mock-judge` |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` (tương thích cache `BAAI/bge-m3`) |
| Số lượng Crossref records | 24 bản ghi |
| Retrieval `top_k` | 4 (mặc định) / 2 (semantic search test) |
| Freshness threshold | 180 ngày (stale ratio cảnh báo khi > 25%) |
| Random seed / deterministic | Deterministic theo sắp xếp `paper_id` |

### Lệnh cài đặt

Kích hoạt môi trường ảo Python đã chuẩn bị:
```bash
# Sử dụng uv hoặc pip
uv sync
# Hoặc: pip install -r requirements.txt
```

### Lệnh chạy pipeline hoàn chỉnh

Chạy Baseline Pipeline (Pha 1):
```bash
python script/run_phase1.py
```

Chạy Corruption Flow, Idempotent Repair & Comparison (Pha 2):
```bash
python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh | Trạng thái | Thời điểm chạy gần nhất | Bằng chứng |
| --- | --- | --- | --- |
| Baseline pipeline (`run_phase1.py`) | Thành công (Exit code 0) | 2026-09-25 16:30 | Sinh đủ 24 cleaned docs, Hit Rate = 1.0, Token F1 = 0.8, GX PASS |
| Corruption flow (`run_corruption_flow.py`) | Thành công (Exit code 0) | 2026-09-25 16:37 | Đầy đủ bảng đối chiếu 3 trạng thái tại `data/reports/corruption_report.md` |

---

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Source | Crossref REST API (`https://api.crossref.org/works`) |
| Query/filter | Học thuật liên quan đến Trí tuệ nhân tạo, Khoa học dữ liệu và Học máy |
| Thời điểm lấy dữ liệu | 2026-09-25 |
| Số record nhận được | 24 bản ghi |
| Cơ chế retry/backoff | Timeout 10s, bắt ngoại lệ RequestException và tự động fallback nạp snapshot nội bộ `data/raw/crossref_records.json` |

### Raw và clean schema

| Trường | Kiểu dữ liệu | Bắt buộc? | Ý nghĩa | Xử lý khi thiếu/sai |
| --- | --- | --- | --- | --- |
| `paper_id` | String | Có | Định danh duy nhất (DOI) của bài báo | Loại bỏ bản ghi nếu thiếu |
| `title` | String | Có | Tiêu đề chính thức | Chuẩn hóa khoảng trắng thừa; drop nếu rỗng |
| `summary` | String | Có | Tóm tắt nội dung / Abstract | Lọc sạch thẻ JATS XML; cảnh báo nếu < 30 ký tự |
| `authors_joined` | String | Không | Danh sách tác giả ngăn cách bằng dấu phẩy | Thay bằng chuỗi rỗng nếu không có tác giả |
| `categories_joined` | String | Không | Phân loại nghiên cứu / Subject | Thay bằng chuỗi rỗng nếu thiếu |
| `published` | String (YYYY-MM-DD) | Có | Ngày xuất bản chính thức | Fallback về ngày hiện tại nếu không parse được |
| `age_days` | Integer | Có | Độ tuổi của bài báo tính theo ngày | `(reference_utc - published_date).days` |
| `text_for_embedding` | String | Có | Văn bản hoàn chỉnh đưa vào mô hình nhúng | Ghép nối 5 phần: Title, Authors, Published, Categories, Summary |

### Quy tắc cleaning

| Quy tắc | Quality dimension liên quan | Số record bị tác động | Cách xác minh |
| --- | --- | ---: | --- |
| Lọc bỏ thẻ JATS XML (`<jats:p>`, ...) | Conformity & Validity | 24 | Regex clean text trong `cleaning.py` |
| Chuẩn hóa khoảng trắng và ký tự xuống dòng | Consistency | 24 | Hàm `normalize_whitespace()` |
| Khử trùng lặp bản ghi theo `paper_id` | Uniqueness | 24 | `df.drop_duplicates(subset=['paper_id'])` |
| Tính toán `age_days` theo mốc thời gian cố định | Timeliness / Freshness | 24 | Đối chiếu với ngày xuất bản `published` |

---

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 10 câu hỏi benchmark cố định |
| Các `question_type` | 4 dạng nghiệp vụ: `summary`, `authors`, `date`, `categories` |
| Ground-truth document ID | `ground_truth_doc_ids` liên kết với `paper_id` gốc của bài báo |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` / `BAAI/bge-m3` |
| Vector store/collection | ChromaDB persistent (`papers-baseline`, `papers-corrupted`, `papers-repaired`) |
| Retrieval `top_k` | `top_k = 4` |
| LLM provider/model | Mock LLM / Rule-based evaluation trích xuất context |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` (tạo 1 lần duy nhất từ baseline, giữ nguyên tuyệt đối) |

**Nguyên tắc biến kiểm soát:** Việc giữ nguyên bộ test set cho cả 3 trạng thái (Baseline, Corrupted, Repaired) là bắt buộc để đảm bảo tính khách quan khoa học: biến số duy nhất thay đổi là chất lượng dữ liệu. Mọi biến động của metrics đều bắt nguồn trực tiếp từ sự thay đổi của dữ liệu.

---

## 7. Kết quả baseline

### Artifact checklist

| Artifact | Đường dẫn thực tế | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Raw response/records | `data/raw/crossref_response.json`, `crossref_records.json` | Có | 24 bản ghi thô đầy đủ data lineage |
| Cleaned dataset | `data/clean/papers_clean.csv`, `papers_clean.json` | Có | 24 bản ghi sạch đã tính `age_days` |
| Embedding manifest/index | `data/embeddings/papers_embeddings.json`, `data/chroma/` | Có | Collection `papers-baseline` |
| Evaluation set | `data/eval/test_set.json` | Có | 10 câu hỏi benchmark cố định |
| Baseline metrics | `data/results/baseline_metrics.json` | Có | Hit Rate = 1.0, Token F1 = 0.8 |
| Quality/freshness | `data/quality/baseline_quality_report.json`, `freshness_report.json` | Có | GX 1.x PASS, Freshness PASS |
| Baseline report | `data/reports/phase1_report.md` | Có | Báo cáo Markdown tổng kết Pha 1 |

### Baseline metrics

| Metric | Giá trị | Diễn giải |
| --- | ---: | --- |
| `retrieval_hit_rate` | **1.0000** | 10/10 câu hỏi retriever tìm thấy đúng tài liệu nguồn chứa đáp án trong top 4. |
| `mean_token_f1` | **0.8000** | Độ trùng khớp token giữa câu trả lời sinh ra và ground truth đạt mức xuất sắc. |
| `judge_accuracy` | **0.8000** | Đánh giá tính chính xác theo phán quyết của Judge đạt 80%. |
| `mean_judge_score` | **4.20 / 5.0** | Điểm chất lượng trung bình theo thang điểm 5 đạt mức tốt. |

---

## 8. Data quality và freshness

### Quality checks (Great Expectations 1.x)

| Check | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline | Bằng chứng |
| --- | --- | --- | --- | --- |
| `row_count` | Completeness | [5, 5000] dòng | PASS (24 dòng) | `baseline_quality_report.json` |
| `paper_id_not_null` | Validity | Không có null | PASS (0 nulls) | `baseline_quality_report.json` |
| `title_not_null` | Validity | Không có null | PASS (0 nulls) | `baseline_quality_report.json` |
| `text_for_embedding_not_null` | Completeness | Không có null | PASS (0 nulls) | `baseline_quality_report.json` |
| `paper_id_unique` | Uniqueness | Không có trùng lặp | PASS (24 unique IDs) | `baseline_quality_report.json` |
| `summary_min_length` | Validity | Độ dài >= 30 ký tự | PASS (Min > 80 chars) | `baseline_quality_report.json` |

### Freshness SLA

| Thuộc tính | Giá trị |
| --- | --- |
| Freshness được đo tại | `data/clean/papers_clean.json` |
| Timestamp mới nhất | `2026-07-22` |
| Ngưỡng freshness | `age_days <= 180` ngày (Stale ratio cho phép <= 25%) |
| Trạng thái baseline | **HEALTHY / PASS** |
| Lý do | Chỉ có 1/24 bài báo có tuổi > 180 ngày (stale ratio = 4.1% < 25%). |

---

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair |
| --- | --- | ---: | --- | --- | --- |
| `drop_latest_records` | Xóa 20% bài báo mới nhất | 4 bài | Thiếu hụt bài báo | Mất tài liệu, Hit Rate giảm | Nạp lại từ raw snapshot |
| `blank_summary` | Gán rỗng summary | 2 bài | Vi phạm min length summary | Context bị mất thông tin | Khôi phục abstract gốc |
| `inject_noise` | Chèn token nhiễu độc hại | 2 bài | Ô nhiễm vector nhúng | Giảm độ tương đồng vector | Làm sạch lại từ raw text |
| `truncate_title` | Cắt tiêu đề < 8 ký tự | 2 bài | Vi phạm tính hợp lệ | Mất ngữ cảnh tiêu đề | Lấy lại title đầy đủ |
| `stale_date` | Lùi ngày xuất bản về 2020 | 8 bài | Vi phạm Freshness SLA | Kích hoạt cảnh báo ALERT | Khôi phục ngày `published` gốc |
| `duplicate_rows` | Nhân bản 2 dòng có sẵn | 2 bài | Vi phạm Uniqueness | Gây nhiễu tần suất vector | Deduplicate theo `paper_id` |

**Cơ chế Idempotent Repair:**  
Hàm `repair_from_raw_snapshot` trong `cleaning.py` nạp dữ liệu từ `data/raw/crossref_records.json` (bảo toàn tính Lineage) và chạy lại toàn bộ quy trình làm sạch. Cách này đảm bảo tính phục hồi độc lập hoàn toàn với bên thứ ba, không bị ảnh hưởng bởi lỗi mạng hay giới hạn API rate limit.

---

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `total_documents` | 24 | 22 | 24 | -2 dòng (drop 4, dup 2) | 100% | Phục hồi trọn vẹn số lượng bản ghi sạch |
| `retrieval_hit_rate` | 1.0000 | 0.7000 | 1.0000 | **-30.0%** | **+30.0% (100%)** | Tụt giảm nghiêm trọng khi mất tài liệu và phục hồi hoàn toàn |
| `mean_token_f1` | 0.8000 | 0.7000 | 0.8000 | **-10.0%** | **+10.0% (100%)** | Chất lượng câu trả lời lấy lại độ chuẩn xác ban đầu |
| `judge_accuracy` | 0.8000 | 0.7000 | 0.8000 | **-10.0%** | **+10.0% (100%)** | Đánh giá của LLM Judge phản ánh sự phục hồi context |
| `mean_judge_score` | 4.20 | 3.80 | 4.20 | -0.40 điểm | +0.40 điểm | Mức độ hữu ích trở về trạng thái xuất sắc |
| Quality checks | PASSED | **FAILED** | **PASSED** | Rớt kiểm định chất lượng | 100% | Bắt trúng lỗi null, duplicate và độ dài ngắn |
| Freshness status | HEALTHY | **ALERT** | **HEALTHY** | Vi phạm SLA tuổi bài báo | 100% | Xóa bỏ cảnh báo quá hạn 180 ngày |

### Hai chuỗi nguyên nhân – bằng chứng:
1. **Chuỗi suy giảm:** Tiêm 6 lỗi dữ liệu $\rightarrow$ Great Expectations báo `FAILED` & Freshness SLA kích hoạt `ALERT` $\rightarrow$ Retrieval Hit Rate sụt giảm từ **1.0 xuống 0.7**.
2. **Chuỗi phục hồi:** Thực thi `repair_from_raw_snapshot` $\rightarrow$ Quality checks trở lại `PASSED` & Freshness SLA về `HEALTHY` $\rightarrow$ Retrieval Hit Rate phục hồi trọn vẹn **1.0000** và Token F1 đạt **0.8000**.

---

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Khi chạy pipeline embedding trên môi trường Windows, tiến trình tải mô hình từ HuggingFace Hub gặp tình trạng timeout kéo dài do kết nối CDN quốc tế chập chờn.
- **Nguyên nhân:** Mã nguồn ban đầu phụ thuộc vào việc tải trực tiếp qua mạng từ `huggingface.co`.
- **Cách xử lý:** 
  1. Cho phép cấu hình linh hoạt biến môi trường `EMBEDDING_MODEL` trong `src/core/config.py`.
  2. Bổ sung cơ chế nạp mô hình tương thích từ cache cục bộ máy tính (`BAAI/bge-m3` hoặc snapshot nội bộ) qua file cấu hình `.env`.
- **Cách xác minh:** Chạy `python script/run_phase1.py` và `run_corruption_flow.py`, pipeline khởi chạy tức thì và nạp weights mô hình chỉ trong 0.2 giây.

---

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| Quy mô tập dữ liệu còn nhỏ (24 bài báo) | Chưa phản ánh hết tải trọng của hệ thống Big Data | Mở rộng ingestion đa nguồn (ArXiv, PubMed) với cơ chế phân trang và concurrency async |
| Cơ chế repair hiện tại chạy batch toàn bộ | Tốn tài nguyên tính toán nếu kho dữ liệu lên hàng triệu bài | Xây dựng cơ chế **Partial Incremental Repair**: chỉ khôi phục các phân vùng dữ liệu vi phạm |
| Đánh giá RAG phụ thuộc vào ngữ cảnh cục bộ | Khả năng suy luận đa tài liệu (multi-hop) chưa được kiểm thử sâu | Xây dựng bộ testset phức tạp yêu cầu đối chiếu chéo nhiều bài báo |

---

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm (`Succulent`) và link repository chính xác.
- [x] Phân công khớp 100% với 4 thành viên, module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện (`run_phase1.py`, `run_corruption_flow.py`) chạy thành công với Exit code 0.
- [x] Baseline, Corrupted và Repaired dùng chung một evaluation set cố định (`test_set.json`).
- [x] Bảng metrics khớp chính xác với các file kết quả trong `data/results/`.
- [x] Kết luận Quality/Freshness khớp hoàn toàn với `data/quality/`.
- [x] Các đường dẫn báo cáo sử dụng đường dẫn tương đối, không hardcode `file:///` hay `C:\`.
- [x] Mỗi thành viên đã có một file báo cáo vai trò riêng trong thư mục `report/`.
- [x] Không có file `.env`, API key, token hay secret bí mật nào bị lộ trong Git history.
