# Frontend-specific Codex guidance

Các rule này bổ sung cho `../AGENTS.md` trong toàn bộ `fe/`.

- `partials/` là HTML source of truth; `index.html` chỉ là generated output.
- Trước khi sửa UI, đọc các section liên quan trong `../.claude/rules/DESIGN.md` và locate mọi nguồn style bằng `rg`.
- Giữ nguyên ID/class được JS dùng trừ khi cập nhật đồng bộ tất cả consumer.
- Kiểm tra ba viewport: mobile `<640px`, tablet `640–1024px`, desktop `>1024px`; touch target tối thiểu 44px.
- Với marketplace, giữ card anatomy, filter, badge, price, rating, empty/loading state và mobile bottom-sheet theo DESIGN.md §11.
- Sau thay đổi partial, chạy `python3 fe/build.py`; generated `index.html` phải được xem như kết quả build, không phải nơi sửa lỗi.
