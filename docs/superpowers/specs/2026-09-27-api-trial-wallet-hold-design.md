# Dùng thử 7 ngày gói API, trừ từ ví, có khoá tiền — thiết kế

**Ngày:** 2026-09-27
**Trạng thái:** đã chốt với chủ sản phẩm, chưa triển khai

## Vì sao tồn tại

PayOS đang dùng là **link thanh toán một lần**; `/api/v1/plans` trả thẳng
`auto_renew: false`. Không có thẻ lưu lại nên **không thể tự động trừ tiền** khi
hết dùng thử. Polar.sh làm được (thẻ lưu lúc checkout, tự charge khi hết trial,
Việt Nam có trong danh sách nhận payout) nhưng phí cố định 0,50 USD trên một sản
phẩm 45.000đ ≈ 1,76 USD là **35% doanh thu**, và Polar thu bằng thẻ quốc tế —
thứ phần lớn khách Việt không dùng.

Nên nguồn tiền của trial là **ví credit đã có sẵn** trong
`KNOWLEDGE_MARKET_DB`, dùng lại `platform_subscriptions` +
`run_billing_cycle` vốn đã chạy cho Fuel Forecast.

## Yêu cầu (chủ sản phẩm, 2026-09-27)

1. **Không trừ tiền tại thời điểm bắt đầu dùng thử.** Đây là điều kiện để trấn
   an khách.
2. **Bắt buộc kiểm tra ví có tối thiểu bằng giá 1 tháng** trước khi cho bắt đầu.
   Không đủ thì hiện thông báo **nói rõ con số còn thiếu**, không cho bắt đầu.
3. **Khoá đúng số tiền đó trong suốt kỳ dùng thử.** Trong 7 ngày, số tiền bị
   khoá không được dùng để mua thứ khác, để ví không thể cạn xuống dưới mức tối
   thiểu trước ngày thu tiền.
4. **Phải có ô tick xác nhận** cho phép trừ tiền khi hết hạn dùng thử, và
   **việc đồng ý phải được ghi lại trong DB** (ai, lúc nào, đồng ý trừ bao
   nhiêu, vào ngày nào).
5. Luồng thanh toán quốc tế (Polar) để tối ưu sau, không nằm trong phạm vi này.

## Quyết định thiết kế

### Khoá tiền = bảng `credit_holds`, không phải trừ rồi hoàn

Trừ trước rồi hoàn lại sẽ vi phạm yêu cầu 1 (tiền rời ví ngay) và làm bẩn
`credit_ledger` bằng một cặp bút toán không phản ánh giao dịch thật. Thay vào đó
`credit_balance.balance` giữ nguyên, và **số dư khả dụng** =
`balance − tổng các hold đang hiệu lực`.

**Hệ quả bắt buộc:** mọi chỗ quyết định chi tiền phải đổi sang đọc số dư khả
dụng. Có đúng ba chỗ: `credit.purchase_product`, `subscription.subscribe`,
`subscription._charge`. Bỏ sót một chỗ là hold không bảo vệ được gì.

### Trial là một trạng thái của subscription, không phải bảng riêng

Thêm `status='trialing'` và cột `trial_end` vào `platform_subscriptions`.
`run_billing_cycle` vốn đã quét theo `status` + `current_period_end`; trial chỉ
là một nhánh quyết định nữa trong `_decide_renewal`, hàm thuần đã có test.

### Ghi nhận đồng ý = bảng append-only `trial_consents`

Không dùng cột boolean trên `platform_subscriptions`: một cột boolean bị ghi đè
khi khách huỷ rồi đăng ký lại, và khi có tranh chấp "tôi không hề đồng ý cho trừ
tiền" thì thứ cần là **bằng chứng tại thời điểm đó**, không phải trạng thái hiện
tại. Bảng này chỉ ghi thêm, không sửa, không xoá.

### Hai database, không có transaction chung

Ví ở `KNOWLEDGE_MARKET_DB`; quyền API (`users.current_plan`,
`users.premium_expiry`, `users.user_level`) ở `USER_DB`. Không thể commit chung.

Thứ tự bắt buộc: **ghi bên ví trước, cấp quyền sau.** Nếu bước cấp quyền hỏng,
khách đã bị khoá tiền nhưng chưa có quyền — trạng thái này **tự sửa được** ở lần
chạy cron kế tiếp vì việc cấp quyền là idempotent (đặt `premium_expiry` bằng
`trial_end`, không cộng dồn). Làm ngược lại thì khách có quyền mà không có hold —
mất tiền thật.

## Ngoài phạm vi

- Polar / thanh toán quốc tế.
- Tự động nạp ví.
- Trial cho sản phẩm Knowledge Market (chỉ áp dụng cho gói API).
