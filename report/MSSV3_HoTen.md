# Báo cáo cá nhân — Thành viên 3: RAG & Vector Index

> Đổi tên file MSSV3_HoTen.md theo MSSV và họ tên thực tế trước khi nộp.

## 1. Thông tin cá nhân


| Thông tin         | Nội dung                                                                |
| ------------------ | ------------------------------------------------------------------------ |
| Họ và tên       | Nguyễn Hoàng Duy                                                       |
| MSSV               | 2A202602751                                                              |
| Khóa/Lớp         | K4-L3-DAY10                                                              |
| Vai trò           | RAG & Vector Index                                                       |
| Repository         | https://github.com/Munfond/K4-L3A-Day10-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-25                                                               |

## 2. Phạm vi sở hữu


| Module/deliverable          | Input                                                             | Output                                                                                        | Trạng thái                           |
| --------------------------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | -------------------------------------- |
| src/retrieval/embeddings.py | Tên model từ Settings.embedding_model và văn bản cần nhúng | Vector list[float] đã chuẩn hóa; model được cache theo tên                            | Hoàn thành                           |
| src/retrieval/index.py      | Clean DataFrame có schema paper và text_for_embedding           | ChromaDB persistent index, manifest trong data/embeddings/, kết quả tìm kiếm có metadata | Hoàn thành                           |
| Ba collection ChromaDB      | Baseline/corrupted/repaired embedding manifest                    | papers-baseline, papers-corrupted, papers-repaired                                            | Hoàn thành trong contract của index |
| Test retrieval              | Fake SentenceTransformer và ChromaDB tạm                        | 6 test kiểm tra build/search/load/idempotent behavior                                        | Hoàn thành                           |

## 3. Kết quả kỹ thuật

- MiniLMEmbeddings dùng model cấu hình từ Settings; model được cache bằng lru_cache để các index không tải lại cùng một model.
- Document embeddings và query embeddings đều gọi normalize_embeddings=True.
- Index yêu cầu các cột paper_id, title, summary, authors_joined, categories_joined, published, abs_url, pdf_url và text_for_embedding.
- Document ID có dạng paper_id::row_index. Phần paper_id giữ liên kết với ground_truth_doc_ids; row_index cho phép index corrupted data có duplicate rows mà không tạo ID ChromaDB trùng nhau.
- Metadata truy vấn gồm paper ID, title, published date, authors, categories, summary và URL.
- build() xóa rồi tạo lại collection cùng tên trước khi nạp vector. Cách này giúp rebuild baseline/corrupted/repaired không giữ lại vector cũ.
- Tên collection được suy ra từ manifest path trong Settings, nhờ đó ba trạng thái dùng ba không gian vector độc lập.
- search() kiểm tra top_k, giới hạn số kết quả theo số document hiện có và chuyển cosine distance thành score trong khoảng [0, 1].
- lookup() hỗ trợ tìm chính xác theo paper_id hoặc title, không phân biệt hoa thường và bỏ khoảng trắng đầu/cuối.

## 4. Contract tích hợp

Luồng upstream tạo clean DataFrame và cột text_for_embedding. Pipeline gọi:

baseline = LocalEmbeddingIndex.build(
clean_df,
settings,
settings.paths.embeddings_json,
)
Corrupted và repaired flow dùng lần lượt settings.paths.corrupted_embeddings_json và settings.paths.repaired_embeddings_json. Mỗi manifest ghi backend, model, persist path, collection name và danh sách document/metadata để LocalEmbeddingIndex.load() mở lại index.

## 5. Cách xác minh

.\.venv\Scripts\python.exe -m pytest tests\test_retrieval_index.py -q --basetemp=.pytest-tmp
Kết quả thực tế: 6 passed.

Các test đã xác minh:

1. Model embedding được cache và vector trả về là Python list.
2. Từ chối model name, document text, query rỗng.
3. Từ chối DataFrame rỗng hoặc thiếu schema bắt buộc.
4. Build/search/load giữ đúng collection, manifest và metadata.
5. Baseline/corrupted/repaired dùng ba collection riêng.
6. Rebuild không để lại document cũ và top_k phải là số nguyên dương.

## 6. Giới hạn xác minh

Chưa chạy được baseline end-to-end trong commit này vì crossref.py, cleaning.py, testset.py và các pipeline orchestration vẫn là phần việc TODO của các owner khác. Vì vậy chưa ghi số liệu retrieval_hit_rate, mean_token_f1 hoặc số lượng 24 document như một kết quả đã chạy. Khi upstream hoàn thành, cần chạy lại:

.\.venv\Scripts\python.exe script\run_phase1.py
.\.venv\Scripts\python.exe script\run_corruption_flow.py
và đối chiếu các manifest/collection với data/results/ và data/reports/.

## 7. Quyết định kỹ thuật

- Bối cảnh: Corruption flow có thể tạo duplicate rows và chạy rebuild nhiều lần.
- Lựa chọn: Dùng ID paper_id::row_index và xóa/tạo lại collection khi build.
- Lý do: Vẫn giữ được paper ID phục vụ đánh giá, đồng thời ChromaDB không bị duplicate ID và không còn ghost vectors sau repair.
- Bằng chứng: Test test_build_uses_separate_collections_and_rebuild_is_idempotent kiểm tra đủ ba collection và số document sau rebuild.

## 8. Cam kết

- [X]  Phần code và test trong phạm vi RAG/vector index đã được xác minh.
- [X]  Không thay đổi crossref.py, cleaning.py, testset.py, quality.py hoặc pipeline orchestration.
- [X]  Không đưa API key, token hay nội dung .env vào code/report.
- [ ]  Cần thay [Họ và tên], [MSSV] và đổi tên file trước khi nộp.
