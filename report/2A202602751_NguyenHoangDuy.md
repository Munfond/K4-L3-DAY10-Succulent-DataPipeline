# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Hoàng Duy |
| MSSV | 2A202602751 |
| Khóa/Lớp | K4-L3-DAY10 |
| Tên nhóm | Succulent |
| Vai trò chính | RAG & Vector Index |
| Repository | https://github.com/Munfond/K4-L3A-Day10-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-25 |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Embedding Generator | `src/retrieval/embeddings.py`: `MiniLMEmbeddings` | Model name từ `Settings` và danh sách text | Vector embedding 384 chiều đã chuẩn hóa cosine (`normalize_embeddings=True`), cache qua `lru_cache` | Hoàn thành |
| Local Vector Index | `src/retrieval/index.py`: `LocalEmbeddingIndex`, `SearchResult` | Clean DataFrame chứa `text_for_embedding`, `Settings` | ChromaDB persistent collection, manifest JSON trong `data/embeddings/`, API tìm kiếm `search()`, `semantic_search()`, `lookup()` | Hoàn thành |
| Quản lý 3 Collection ChromaDB | `src/retrieval/index.py` | Dữ liệu sạch, dữ liệu bẩn và dữ liệu phục hồi | 3 collections độc lập: `papers-baseline`, `papers-corrupted`, `papers-repaired` | Hoàn thành |
| Unit Test Retrieval | `tests/test_retrieval_index.py` | Fake embeddings và ChromaDB tạm | 6 unit tests kiểm tra build, search, load, idempotency và error handling | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Hỗ trợ Agent QA Retrieval | Thành viên 1 & Thành viên 4 | Cung cấp hàm `lookup()` theo exact `paper_id` và title giúp QA Agent và LLM Judge trích xuất thông tin chính xác phục vụ đánh giá. |
| Hỗ trợ Ingestion Schema Contract | Thành viên 2 (Ingestion & Cleaning) | Thống nhất định dạng trường `text_for_embedding` gồm 5 trường để đảm bảo chất lượng semantic similarity cao nhất. |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Quản lý mô hình embedding | `embeddings.py` | Mô hình sinh vector nhúng chuẩn hóa, tái sử dụng qua cache không tải lại | Chạy unit test kiểm tra embedding caching |
| Xây dựng ChromaDB Index | `index.py` | Đánh chỉ mục 24 tài liệu đầy đủ metadata, hỗ trợ `build_from_clean()` | Lệnh kiểm tra `semantic_search('machine learning', top_k=2)` trả về 2 kết quả |
| Cô lập 3 collections | `index.py` | `data/chroma/`, `data/embeddings/papers_embeddings*.json` | Manifest lưu cấu hình 3 không gian vector độc lập |
| Kiểm thử đơn vị module retrieval | `tests/test_retrieval_index.py` | Bộ test hoàn chỉnh kiểm tra tính đúng đắn | `pytest tests/test_retrieval_index.py` (6 passed) |

**Output cụ thể bàn giao:**  
Hệ thống vector store bền vững trong `data/chroma/` với 3 collection độc lập phục vụ trực tiếp cho việc đối chứng khoa học giữa 3 pha Baseline, Corrupted và Repaired.

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Hệ thống RAG phụ thuộc trực tiếp vào tầng Vector Index để tìm kiếm các tài liệu liên quan ngữ nghĩa. Các thách thức kỹ thuật cần xử lý gồm:
1. Tránh tràn RAM và tải lại mô hình lặp đi lặp lại khi khởi tạo index nhiều lần.
2. Xử lý kịch bản dữ liệu bẩn có các dòng trùng lặp (`duplicate rows`) khiến ChromaDB bị lỗi trùng khóa chính (duplicate primary key).
3. Đảm bảo tính Idempotent: khi re-index không được để lại các vector rác (ghost vectors) của lần chạy trước.

### Cách triển khai
1. **Embedding Caching & Cosine Normalization:** Sử dụng `functools.lru_cache` bao bọc instance `SentenceTransformer`. Mọi vector sinh ra đều bật cờ `normalize_embeddings=True` để chuẩn hóa độ dài L2 về 1, cho phép tính cosine similarity bằng dot product với không gian khoảng cách `cosine` của ChromaDB.
2. **Quy tắc sinh Document ID chống xung đột:** Gán ID có cấu trúc `f"{paper_id}::{row_index}"`. Phần `paper_id` giúp đối chiếu với `ground_truth_doc_ids` trong testset; phần `row_index` cho phép index cả các dòng bị duplicate trong giai đoạn corrupted mà không gây crash ChromaDB.
3. **Rebuild Idempotency:** Trong phương thức `build()`, hệ thống luôn gọi `client.delete_collection(name=collection_name)` trước khi `create_collection`, bảo đảm collection được làm mới tinh khiết 100%.
4. **Cơ chế nạp tự động `build_from_clean()`:** Cho phép nạp trực tiếp từ `papers_clean.json` / `papers_clean.csv`, tự động đồng bộ manifest và nạp vector vào ChromaDB.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Clean DataFrame chứa `text_for_embedding`, `paper_id`, `title`, metadata |
| Output | Collection ChromaDB, manifest JSON trong `data/embeddings/`, đối tượng `SearchResult` |
| Module phụ thuộc | Phụ thuộc vào `core.config`, `core.utils` |
| Module sử dụng output | `retrieval.qa`, `retrieval.agent`, `evaluation.metrics` |
| Điều kiện lỗi cần xử lý | DataFrame rỗng, thiếu cột bắt buộc, top_k <= 0, collection chưa tồn tại |

### Cách xác minh
```bash
# Kiểm tra khởi tạo và semantic search
python -c "from core.config import load_settings; from retrieval.index import LocalEmbeddingIndex; s=load_settings(); idx=LocalEmbeddingIndex(s, collection_name='papers-baseline'); idx.build_from_clean(); res=idx.semantic_search('machine learning', top_k=2); print(f'Tín hiệu hoàn thành: Tìm thấy {len(res)} tài liệu liên quan')"

# Kiểm tra unit test
python -m pytest tests/test_retrieval_index.py -q
```
- **Kết quả mong đợi:** In tín hiệu tìm thấy 2 tài liệu và 6 tests đều passed.
- **Kết quả thực tế:** Khớp 100% mong đợi (`Tín hiệu hoàn thành: Tìm thấy 2 tài liệu liên quan`, `6 passed`).

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn phương pháp xử lý ID văn bản khi lưu vào ChromaDB trong bối cảnh dữ liệu có thể bị tiêm lỗi trùng lặp (duplicate rows).
- **Các phương án đã cân nhắc:**
  1. Dùng trực tiếp `paper_id` làm ID trong ChromaDB.
  2. Dùng ID ghép `f"{paper_id}::{index}"`.
- **Phương án đã chọn:** Phương án 2 (`paper_id::row_index`).
- **Lý do:** Nếu dùng Phương án 1, khi pipeline tiêm lỗi trùng dòng ở Pha 2, ChromaDB sẽ ném ngoại lệ `DuplicateIDError` làm gãy ngang pipeline. Dùng ID ghép vừa giúp ChromaDB chấp nhận các bản ghi nhân bản để kiểm thử tác động của dữ liệu bẩn, vừa dễ dàng phân tách lấy lại `paper_id` gốc để tính Retrieval Hit Rate.
- **Bằng chứng:** Pha 2 (`run_corruption_flow.py`) đánh chỉ mục thành công 22 bản ghi (bao gồm 2 bản ghi nhân bản) mà không gặp bất kỳ lỗi xung đột ID nào.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```text
  TypeError: LocalEmbeddingIndex.__init__() missing 2 required positional arguments: 'documents' and 'persist_path'
  ```
- **Lệnh tái hiện:** Chạy lệnh kiểm tra của giảng viên:
  ```bash
  python -c "from core.config import load_settings; from retrieval.index import LocalEmbeddingIndex; s=load_settings(); idx=LocalEmbeddingIndex(s, collection_name='papers-baseline'); idx.build_from_clean(); res=idx.semantic_search('machine learning', top_k=2); print(...)"
  ```
- **Nguyên nhân gốc:** Hàm khởi tạo `__init__` ban đầu bắt buộc phải truyền cả `documents` và `persist_path`, đồng thời lớp `LocalEmbeddingIndex` chưa có phương thức `build_from_clean()` và alias `semantic_search()`.
- **Cách xử lý:** 
  1. Linh hoạt hóa `__init__` cho phép `documents` và `persist_path` nhận giá trị `None` và tự động fallback về đường dẫn mặc định trong `settings`.
  2. Bổ sung phương thức `build_from_clean(clean_path)` đọc trực tiếp từ `clean_json` / `clean_csv`.
  3. Thêm alias method `semantic_search(query, top_k)` trỏ tới hàm `search()`.
- **Cách xác minh sau khi sửa:** Lệnh kiểm tra chạy thành công ngay lập tức và in: `Tín hiệu hoàn thành: Tìm thấy 2 tài liệu liên quan`.
- **Điều học được:** Khi thiết kế API cho thư viện hoặc module dùng chung, cần đảm bảo tính công thái học (ergonomics) với các tham số mặc định hợp lý để tương thích linh hoạt với nhiều cách thức gọi khác nhau.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index:** Dữ liệu thô thu thập từ Crossref $\rightarrow$ lưu raw snapshot $\rightarrow$ module cleaning chuẩn hóa text, tính `age_days`, tạo `text_for_embedding` $\rightarrow$ truyền sang `LocalEmbeddingIndex` $\rightarrow$ mô hình SentenceTransformer sinh vector 384 chiều $\rightarrow$ lưu vào ChromaDB collection cùng siêu dữ liệu (metadata).
2. **Evaluation set và ground-truth document IDs:** Bộ test set 10 câu hỏi chứa trường `ground_truth_doc_ids`. Khi Agent truy vấn, kết quả top-k doc ID trả về từ ChromaDB được so sánh với `ground_truth_doc_ids` để tính toán chính xác chỉ số **Retrieval Hit Rate**.
3. **Quality checks khác freshness monitoring:**
   - Quality checks (Great Expectations): Đánh giá tính toàn vẹn cấu trúc tĩnh của bảng dữ liệu (không chứa null, schema hợp lệ, không trùng lặp).
   - Freshness monitoring: Đánh giá tính giá trị động theo thời gian (dữ liệu có bị lỗi thời, quá hạn 180 ngày hay không).
4. **Vì sao phải dùng cùng test set cho cả 3 trạng thái:** Để đảm bảo tính khách quan và khoa học (nguyên tắc biến kiểm soát). Giữ cố định câu hỏi và ground truth giúp đo lường chính xác mức độ ảnh hưởng của dữ liệu bẩn và mức độ phục hồi của dữ liệu sửa chữa.
5. **Tiêu chí repair thành công:** Quá trình repair được công nhận thành công khi dữ liệu sạch được nạp lại vào collection `papers-repaired`, vượt qua Quality Gate, Freshness SLA đạt HEALTHY, và chỉ số Retrieval Hit Rate phục hồi trở lại mức 1.0000.

---

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.7000 | 1.0000 | Ở pha corrupted, do 20% bài báo mới bị drop và text summary bị làm bẩn, Hit Rate giảm mạnh còn 70%; sau khi repair đã phục hồi tuyệt đối 100%. |
| `mean_token_f1` | 0.8000 | 0.7000 | 0.8000 | Sự suy giảm của context retrieved kéo theo câu trả lời bị thiếu thông tin chính xác; phục hồi lại 0.8 sau repair. |
| `judge_accuracy` | 0.8000 | 0.7000 | 0.8000 | LLM Judge đánh giá độ chính xác giảm tương ứng khi retriever cung cấp sai context. |
| `mean_judge_score` | 4.20 | 3.80 | 4.20 | Điểm đánh giá hữu ích giảm từ 4.2 xuống 3.8 và phục hồi trở lại 4.2. |
| Quality checks | PASSED | FAILED | PASSED | Bắt đúng các lỗi null và duplicate ở pha corrupted. |
| Freshness status | HEALTHY | ALERT | HEALTHY | Cảnh báo đúng khi tuổi bài báo vượt ngưỡng 180 ngày. |

### Kết luận từ số liệu
1. **Chuỗi suy giảm:** Tiêm lỗi cắt bớt bài báo và chèn noise $\rightarrow$ ChromaDB truy xuất sai tài liệu $\rightarrow$ Retrieval Hit Rate tụt từ 1.0 xuống 0.7 và Token F1 giảm còn 0.7.
2. **Chuỗi phục hồi:** Idempotent Repair tái tạo vector store `papers-repaired` $\rightarrow$ ChromaDB lấy lại đầy đủ tài liệu nguồn $\rightarrow$ Hit Rate phục hồi trọn vẹn 1.0000.

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất
1. **Về Vector Search:** Chất lượng của Vector Search phụ thuộc hoàn toàn vào cấu trúc của văn bản đưa vào nhúng (`text_for_embedding`); làm sạch văn bản kỹ lưỡng là tiền đề quan trọng nhất để vector thể hiện đúng ngữ nghĩa.
2. **Về Quản lý Vector Store:** Phải luôn tách biệt các không gian vector (collections) khi thử nghiệm hoặc kiểm thử dữ liệu để tránh tình trạng "ô nhiễm chéo" (cross-contamination) giữa dữ liệu sạch và dữ liệu bẩn.
3. **Về Tác động đến RAG:** Tầng Retrieval là nút thắt cổ chai của hệ thống RAG; retriever không tìm thấy tài liệu đúng thì mô hình ngôn ngữ lớn (LLM) dù thông minh đến đâu cũng không thể sinh câu trả lời chính xác.

### Nếu có thêm thời gian
Tôi sẽ triển khai **Hybrid Search kết hợp Re-ranking**: Kết hợp giữa Dense Retrieval (Vector ChromaDB) và Sparse Retrieval (BM25), sau đó đưa qua một mô hình Cross-Encoder Re-ranker để tối ưu hóa thứ hạng tài liệu liên quan lên vị trí top 1.

---

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Hoàng Duy  
**Ngày xác nhận:** 2026-09-25
