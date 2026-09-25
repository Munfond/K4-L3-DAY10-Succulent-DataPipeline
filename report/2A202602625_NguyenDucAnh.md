# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Đức Anh |
| MSSV | 2A202602625 |
| Khóa/Lớp | K4-L3-DAY10 |
| Tên nhóm | Succulent |
| Vai trò chính | Trưởng nhóm & Điều phối Pipeline |
| Repository | https://github.com/Munfond/K4-L3A-Day10-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-25 |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Hệ thống cấu hình & Artifacts | `src/core/config.py`, `src/core/utils.py` | Biến môi trường (`.env`), tham số pipeline | Lớp `Settings`, `Paths` và các tiện ích `ensure_artifact_dirs`, I/O JSON/CSV an toàn | Hoàn thành |
| Baseline Pipeline Orchestration | `src/pipelines/phase1.py`, `script/run_phase1.py` | Raw data, settings | Quy trình 6 bước tự động tạo clean data, ChromaDB index, reports | Hoàn thành |
| Corruption & Repair Orchestration | `src/pipelines/corruption_flow.py`, `script/run_corruption_flow.py` | Clean data, raw snapshot, settings | Quy trình 5 bước mô phỏng 6 dạng lỗi, kiểm định suy giảm RAG và so sánh 3 trạng thái | Hoàn thành |
| Quản lý chất lượng & Đóng góp | Toàn bộ repository | Commit history, GitHub branches | Giám sát Contributor tracking trên GitHub `main`, đảm bảo artifacts nhất quán | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Tích hợp Contract liên module | Thành viên 2 (Ingestion), Thành viên 3 (Retrieval), Thành viên 4 (Observability) | Đảm bảo schema DataFrame, manifest ChromaDB và metrics JSON ăn khớp 100%, không bị lỗi gãy pipeline. |
| Xử lý cấu hình mô hình cục bộ | Thành viên 3 (RAG & Vector Index) | Hỗ trợ nạp mô hình offline từ HuggingFace cache cục bộ, giúp pipeline chạy mượt mà không bị timeout mạng. |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Chuẩn hóa cấu hình tập trung | `src/core/config.py` | Đối tượng `Settings` chứa toàn bộ đường dẫn `Paths`, LLM provider, embedding model, top_k | Chạy `s = load_settings()` trong REPL |
| Orchestration Pha 1 (Baseline) | `src/pipelines/phase1.py` | `data/reports/phase1_report.md`, `data/results/baseline_metrics.json` | `python script/run_phase1.py` (Exit code 0) |
| Orchestration Pha 2 (Corruption & Repair) | `src/pipelines/corruption_flow.py` | `data/reports/corruption_report.md`, `corrupted_metrics.json`, `repaired_metrics.json` | `python script/run_corruption_flow.py` (Exit code 0) |
| Bảo đảm Idempotency | `phase1.py`, `corruption_flow.py` | Pipeline chạy lặp lại nhiều lần không sinh rác, tự động làm sạch collection cũ | Chạy liên tiếp 2 lần các script, kết quả hoàn toàn trùng khớp |

**Output cụ thể bàn giao:**  
Báo cáo phân tích định lượng 3 trạng thái tại `data/reports/corruption_report.md` thể hiện rõ nét tác động của dữ liệu bẩn và sự phục hồi hoàn hảo sau sửa chữa.

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Xây dựng một pipeline dữ liệu học thuật cho RAG đòi hỏi sự phối hợp chặt chẽ giữa 4 module độc lập (Ingestion, Retrieval, Observability, Evaluation). Nếu không có kiến trúc điều phối tập trung và cơ chế đảm bảo tính Idempotent (chạy lại không làm sai lệch trạng thái), hệ thống sẽ dễ rơi vào tình trạng phân mảnh đường dẫn (path mismatch), rò rỉ dữ liệu giữa các lần chạy, hoặc không thể so sánh khách quan hiệu năng RAG giữa dữ liệu sạch và dữ liệu bẩn.

### Cách triển khai
1. **Kiến trúc Cấu hình Bất biến (Immutable Settings):** Sử dụng `pydantic` / `dataclass` đóng gói toàn bộ đường dẫn trong `Paths` theo cấu trúc thư mục chuẩn (`data/raw`, `data/clean`, `data/chroma`, `data/eval`, `data/results`, `data/reports`).
2. **Quản lý Vòng đời Pipeline (Lifecycle Orchestration):**
   - **Pha 1 (Baseline Flow):** Điều phối tuyến tính tuần tự: Thu thập $\rightarrow$ Làm sạch $\rightarrow$ Đánh chỉ mục ChromaDB $\rightarrow$ Kiểm định Great Expectations 1.x & Freshness SLA $\rightarrow$ Tạo Test set $\rightarrow$ Đánh giá RAG $\rightarrow$ Xuất báo cáo Phase 1.
   - **Pha 2 (Corruption & Repair Flow):** Điều phối luồng so sánh: Tiêm lỗi $\rightarrow$ Đánh chỉ mục collection `papers-corrupted` $\rightarrow$ Đo lường suy giảm RAG $\rightarrow$ Kích hoạt Idempotent Repair từ raw snapshot $\rightarrow$ Đánh chỉ mục collection `papers-repaired` $\rightarrow$ Đo lường phục hồi $\rightarrow$ Xuất bảng đối chiếu 3 trạng thái.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Tham số dòng lệnh, file cấu hình `.env`, raw snapshot data |
| Output | Bộ artifacts hoàn chỉnh trong `data/` và 2 báo cáo Markdown tổng kết |
| Module phụ thuộc | Phụ thuộc vào `ingestion`, `retrieval`, `observability`, `evaluation` |
| Module sử dụng output | Giám khảo / Trợ giảng đánh giá qua `script/run_phase1.py` và `script/run_corruption_flow.py` |
| Điều kiện lỗi cần xử lý | Mất mạng (chuyển fallback snapshot), collection ChromaDB đã tồn tại (xóa và tạo mới sạch sẽ), lỗi đường dẫn |

### Cách xác minh
```bash
python script/run_phase1.py
python script/run_corruption_flow.py
```
- **Kết quả mong đợi:** Cả 2 lệnh thoát với exit code 0, in toàn bộ các bước thành công và bảng so sánh 3 trạng thái.
- **Kết quả thực tế:** Exit code 0, sinh đầy đủ các file metrics JSON và 2 báo cáo Markdown.

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn chiến lược lưu trữ và quản lý ChromaDB collections giữa 3 giai đoạn Baseline, Corrupted và Repaired.
- **Các phương án đã cân nhắc:**
  1. Dùng chung một collection duy nhất và ghi đè / xóa vector giữa các bước.
  2. Tạo 3 collection hoàn toàn biệt lập (`papers-baseline`, `papers-corrupted`, `papers-repaired`) với cơ chế tái tạo sạch (drop & recreate trước khi nạp).
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Giúp cô lập triệt để không gian vector, tránh rò rỉ dữ liệu giữa dữ liệu sạch và dữ liệu bẩn, đảm bảo khả năng kiểm tra lại độc lập từng collection bất kỳ lúc nào mà không làm ảnh hưởng lẫn nhau.
- **Bằng chứng:** Kết quả truy vấn RAG trên `papers-corrupted` phản ánh trung thực sự suy giảm chỉ số (Hit Rate giảm từ 1.0 xuống 0.7), không bị lẫn vector sạch từ baseline.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Quá trình tải mô hình embedding mặc định qua mạng bị timeout/nghẽn kết nối HTTPS đến Hugging Face Hub trên môi trường Windows.
- **Lệnh tái hiện:** `python script/run_phase1.py` (treo ở bước tải weights MiniLM).
- **Nguyên nhân gốc:** Mạng chập chờn khi kết nối tới CDN quốc tế của HuggingFace.
- **Cách xử lý:** Bổ sung cơ chế cấu hình biến môi trường `EMBEDDING_MODEL` trong `core/config.py` và hỗ trợ nạp mô hình tương thích đã có sẵn trong cache cục bộ máy tính (`BAAI/bge-m3` hoặc nạp local snapshot), kết hợp với cấu hình trong `.env`.
- **Cách xác minh sau khi sửa:** Chạy lại `python script/run_phase1.py`, mô hình nạp ngay lập tức chỉ trong 0.5s, pipeline chạy trơn tru đến đích.
- **Điều học được:** Mọi pipeline dữ liệu production cần phải có phương án fallback ngoại tuyến hoặc cấu hình linh hoạt qua biến môi trường để chống chịu sự cố kết nối ngoại vi.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index:** Dữ liệu thô từ Crossref API (hoặc fallback snapshot) $\rightarrow$ parse thành `crossref_records.json` $\rightarrow$ làm sạch HTML/whitespace, tính `age_days`, tạo `text_for_embedding` 5 phần, loại trùng $\rightarrow$ xuất `papers_clean.json` $\rightarrow$ chia văn bản, sinh vector nhúng và nạp vào ChromaDB collection.
2. **Evaluation set và ground-truth document IDs:** Test set 10 câu hỏi chứa ID bài báo nguồn (`ground_truth_doc_ids`). Khi Agent truy vấn, hệ thống đối chiếu top-k ID được retrieve với ground-truth ID để tính **Hit Rate**, và đối chiếu câu trả lời sinh ra với câu trả lời mẫu để tính **Token F1**.
3. **Quality checks khác freshness monitoring:**
   - Quality checks (Great Expectations): Kiểm tra tính toàn vẹn tĩnh của schema (null, unique, kiểu dữ liệu, độ dài).
   - Freshness monitoring (SLA): Giám sát tính thời sự động của dữ liệu dựa trên độ tuổi (`age_days > 180`), phát hiện dữ liệu bị cũ/lỗi thời dù schema vẫn hợp lệ.
4. **Vì sao phải dùng cùng test set cho cả 3 trạng thái:** Để đảm bảo nguyên tắc biến kiểm soát (controlled experiment) trong khoa học dữ liệu; chỉ có dữ liệu đầu vào thay đổi thì sự thay đổi của metrics mới phản ánh chính xác tác động của chất lượng dữ liệu.
5. **Tiêu chí repair thành công:** Dữ liệu phục hồi phải vượt qua 100% Quality Gate của GX 1.x, Freshness SLA đạt trạng thái `HEALTHY`, và chỉ số Retrieval Hit Rate phục hồi về mức ban đầu (1.0000).

---

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.7000 | 1.0000 | Khi mất bản ghi và noise summary, hit rate sụt giảm mạnh 30%; sau repair đã phục hồi tuyệt đối. |
| `mean_token_f1` | 0.8000 | 0.7000 | 0.8000 | Chất lượng câu trả lời bị kéo tụt do context bị cắt xén; sau sửa chữa đã lấy lại độ chính xác cao nhất. |
| `judge_accuracy` | 0.8000 | 0.7000 | 0.8000 | LLM Judge ghi nhận sự suy giảm tương ứng khi retriever cung cấp sai ngữ cảnh. |
| `mean_judge_score` | 4.20 | 3.80 | 4.20 | Điểm đánh giá trung bình phản ánh đúng mức độ hữu ích của câu trả lời. |
| Quality checks | PASSED | FAILED | PASSED | Great Expectations phát hiện chuẩn xác các vi phạm về null, duplicate và độ dài ngắn. |
| Freshness status | HEALTHY | ALERT | HEALTHY | Cảnh báo vi phạm SLA ngay lập tức khi tuổi bài báo bị đẩy lên quá 180 ngày. |

### Kết luận từ số liệu
1. **Chuỗi suy giảm:** Tiêm 6 lỗi dữ liệu $\rightarrow$ Quality checks phát hiện FAILED & Freshness kích hoạt ALERT $\rightarrow$ Retrieval Hit Rate tụt từ 1.0 xuống 0.7.
2. **Chuỗi phục hồi:** Thực thi Idempotent Repair từ raw snapshot $\rightarrow$ Quality checks trở lại PASSED & Freshness về HEALTHY $\rightarrow$ Retrieval Hit Rate phục hồi trọn vẹn 1.0 và Token F1 đạt 0.8.

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất
1. **Về Data Pipeline:** Tính **Idempotency** (tính lũy thừa) là xương sống của mọi pipeline; một pipeline tốt phải có khả năng chạy lại an toàn ở bất kỳ thời điểm nào mà không làm biến dạng dữ liệu.
2. **Về Data Quality/Observability:** Ngay cả khi code không hề có lỗi (no runtime error), dữ liệu bẩn vẫn gây ra hiện tượng **Silent Failure** nghiêm trọng cho tầng ứng dụng.
3. **Về Ảnh hưởng đến RAG Agent:** "Garbage in, Garbage out" — RAG Agent phụ thuộc sống còn vào chất lượng của context retrieved; suy giảm ở tầng dữ liệu sẽ nhân đôi sự suy giảm ở tầng sinh câu trả lời.

### Nếu có thêm thời gian
Tôi sẽ tích hợp **Automated Self-Healing Pipeline**: Khi Great Expectations phát hiện vi phạm quality gate, pipeline sẽ tự động cô lập phân vùng dữ liệu lỗi và tự động kích hoạt tiến trình Idempotent Repair mà không cần con người can thiệp thủ công.

---

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Đức Anh  
**Ngày xác nhận:** 2026-09-25
