# Viet Dataverse — Codex guidance

Trao đổi với người dùng bằng tiếng Việt. Giữ code, comment và commit message bằng tiếng Anh theo convention hiện có.

## Safety

- Không hiển thị, log hoặc đưa vào chat bất kỳ giá trị nào từ `.env`, connection string, API key, password hay token. Có thể dùng bí mật theo cách không làm lộ giá trị.
- Giữ nguyên thay đổi không liên quan của người dùng. Không sửa `logo.png` nếu task không yêu cầu.
- Khi thông tin pháp lý, quy định, giá, đối thủ hoặc nguồn dữ liệu hiện hành ảnh hưởng quyết định, phải kiểm tra nguồn mới và phân biệt rõ fact với inference.

## Source of truth

- Đọc `BACKLOG.md` khi người dùng nói `Làm <ID>`; coi item tương ứng là acceptance criteria, rồi kiểm tra code hiện tại trước khi triển khai.
- Đọc `.claude/rules/DESIGN.md` trước mọi thay đổi UI/CSS/HTML. Phần 10 áp dụng cho mobile, phần 11 cho marketplace, phần 12 cho app shell/routing, phần 13 cho standalone pages.
- Đọc `.claude/rules/KNOWLEDGE_PACK_SPEC.md` khi tạo, sửa hoặc review knowledge pack.
- Đọc `.claude/knowledge/product_position_knowledge_market.md` cho quyết định về Agent Market; đọc `.claude/knowledge/product_position_opendata.md` cho Open Data/API.

## Architecture

Luồng chính: Python crawlers → PostgreSQL/Neon → FastAPI (`be/`) → static HTML/Chart.js (`fe/`). Sản phẩm gồm Open Data và Agent Market trong cùng SPA.

- `be/main.py`: app entry, router registration, static mount.
- `be/routers/`: API theo domain.
- `be/core/`, `be/services/`: config, engine, auth, credit, storage.
- `be/migrations/`: SQL và runner migration một lần.
- `crawl_tools/`: crawler độc lập theo nguồn/asset.
- `fe/partials/`: source of truth cho HTML.
- `fe/index.html`: generated artifact; không sửa trực tiếp.
- `fe/app.js`, `fe/app.knowledge.js`, `fe/style.css`, `fe/auth.js`: frontend không có Node build step.

## Working rules

- Locate bằng `rg` và đọc vùng liên quan trước khi sửa; không dựa vào line count hoặc path cũ trong tài liệu Claude.
- Với task thay đổi/build: triển khai hoàn chỉnh, không để stub/TODO, rồi verify tương xứng với rủi ro.
- Với task diagnose/review: chỉ báo nguyên nhân hoặc finding; không tự sửa nếu người dùng chưa yêu cầu.
- Change nhỏ và scoped; không refactor tiện tay.
- Nếu task xuyên DB/API/FE, làm theo thứ tự migration/schema → backfill → crawler/service → API/static JSON → FE → CI/test.
- Trước khi kết thúc mọi task, thực hiện documentation close-out theo `CODEX.md`: rà và cập nhật status/hành vi/đường dẫn/lệnh/schema/deploy state trong tất cả tài liệu liên quan; không tuyên bố hoàn tất khi docs còn mô tả trạng thái cũ.

## Backend and data invariants

- Mỗi crawl table có `id SERIAL PRIMARY KEY`, `period`, `crawl_time`, `source`, `group_name`, tất cả `NOT NULL`.
- Dùng `UNIQUE (entity_key, period)` và index trên `period`.
- Không dùng `MAX(id)+1`. Dùng `INSERT ... ON CONFLICT DO NOTHING|UPDATE` và `conn.commit()` rõ ràng.
- Crawler phải parse → validate range/completeness (ít nhất 3 numeric values hợp lệ) → store; validation fail thì exit non-zero và không ghi partial rows.
- SQL có input phải parameterized. Không hardcode DB URL.
- Giữ response API nhất quán với domain hiện tại; baseline là `success`, `source`, `count`, `data`, và thêm pagination metadata khi endpoint hỗ trợ pagination.
- Enforce auth, tier cutoff và authorization ở server, không chỉ ở client.

## Frontend invariants

- Sửa `fe/partials/*`, sau đó chạy `python3 fe/build.py`; không sửa `fe/index.html` trực tiếp.
- Trước thay đổi style, kiểm tra CSS class, inline HTML, template literal trong JS, Chart.js options và CSS variables.
- Dùng URL tương đối; destroy chart cũ trước `new Chart()`; giữ locale `vi-VN` và cache fetch-once hiện có.
- Bảo toàn state logic trong `_updateSidebarStateAsync()` khi đụng seller/auth sidebar.
- Không đưa user input thô vào `innerHTML`; không dùng `eval()`.
- Giữ warm design tokens từ DESIGN.md. Badge `VD Official` nằm ở seller footer, không đặt cạnh title.

## Verification

- Frontend markup: `python3 fe/build.py`, kiểm tra generated diff và JS syntax nếu có sửa JS.
- Backend: chạy test/lint có sẵn theo phạm vi; nếu repo chưa có test phù hợp, thực hiện import/compile hoặc request-level smoke check không cần secret.
- Crawler/DB: test parser và validator bằng fixture hoặc input cục bộ trước; không chạy write vào production DB nếu người dùng không yêu cầu rõ.
- Báo rõ phần đã test và phần cần user kiểm tra thủ công.
