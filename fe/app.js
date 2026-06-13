        /* =========================================================
           FETCH UTILITIES — timeout + retry
        ========================================================= */
        /**
         * fetch() with an AbortController timeout.
         * @param {string} url
         * @param {RequestInit} options
         * @param {number} ms  timeout in milliseconds (default 15000)
         */
        function fetchWithTimeout(url, options = {}, ms = 15000) {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), ms);
            return fetch(url, { ...options, signal: controller.signal })
                .finally(() => clearTimeout(timer));
        }

        /**
         * Show a user-facing error inside a chart-loading container.
         * @param {HTMLElement|null} loadingEl
         * @param {string} chartType  — used to build the retry callback
         * @param {string} message    — short human-readable error
         */
        function showChartError(loadingEl, chartType, message) {
            if (!loadingEl) return;
            loadingEl.style.display = 'flex';
            loadingEl.innerHTML = `
                <div style="text-align:center;padding:2rem;color:var(--text-tertiary)">
                    <i class="fas fa-exclamation-circle" style="font-size:2rem;margin-bottom:0.75rem;display:block;color:#EF5350;opacity:0.8"></i>
                    <p style="font-size:0.9rem;color:#EF5350;margin-bottom:0.75rem">${message}</p>
                    <button onclick="loadChartData('${chartType}')"
                        style="background:rgba(201, 100, 66,0.15);color:var(--gold-accent);border:1px solid rgba(201, 100, 66,0.3);padding:6px 18px;border-radius:6px;cursor:pointer;font-size:0.8rem;">
                        Thử lại
                    </button>
                </div>`;
        }

        // Language toggle with translations (Vietnamese is primary)
        let currentLang = 'vi';

        const translations = {
            vi: {
                langBtn: 'En',
                subtitle: 'Thông tin Kinh tế',
                navDataPortal: 'Dữ Liệu Kinh Tế Mở',
                nav1sMarketPortal: 'Thời báo 1 giây',
                nav1smarketsub: 'Tờ báo quan trọng theo MRI',
                futureOutlookSubtitle: 'Phân tích chuyên sâu & Dự báo xu hướng các loại tài sản',
                navfinagent: 'Fintel AI Agent',
                navfinagentsub: 'AI Agents cho thuê',
                navDownloadApi: 'Download & API',
                navDownloadApiMeta: 'Tải dữ liệu & API access',
                navAboutTerms: 'Giới thiệu & Điều khoản',
                navAboutTermsMeta: 'Về dự án & Điều khoản',
                navPrivacy: 'Chính sách bảo mật',
                navContact: 'Liên hệ',
                navSeparator: 'Dịch vụ',
                sidebarAccount: 'Tài khoản',
                loginBtn: 'Đăng nhập',
                logoutBtn: 'Đăng xuất',
                mainTitle: 'Tải Dữ Liệu Kinh Tế Mở',
                mainSubtitle: '<strong>Tải miễn phí</strong> lịch sử giá vàng, bạc trong nước, lãi suất SBV, lãi suất gửi tiết kiệm, tỷ giá hối đoái hoàn toàn miễn phí',
                sectionTitle: 'Tải Dữ Liệu Kinh Tế Mở',
                sectionSubtitle: 'Bộ dữ liệu kinh tế vĩ mô Việt Nam chất lượng cao công khai và truy cập miễn phí cho mục đích nghiên cứu. Chi tiết về schemas và parameters tại',
                goldChart: 'Lịch Sử Giá Vàng Trong Nước',
                silverChart: 'Lịch Sử Giá Bạc (Phú Quý)',
                sbvChart: 'Lịch Sử Lãi Suất Liên Ngân Hàng',
                tdChart: 'Lịch Sử Lãi Suất Gửi Tiết Kiệm (NHTM)',
                fxrateChart: 'Tỷ Giá Trung Tâm USD/VND (NHNN)',
                globalChart: 'Xu Hướng Thị Trường Toàn Cầu (Vàng, Bạc, NASDAQ)',
                downloadTitle: 'Tải Dữ liệu Lịch Sử',
                downloadSubtitle: 'Tải dữ liệu lịch sử giá vàng trong nước, giá bạc, và dữ liệu vĩ mô tại đây',
                goldDatasetTitle: 'Tải Lịch Sử Giá Vàng',
                goldDatasetDesc: 'Tải lịch sử giá vàng trong nước. Download Vietnam historical gold price miễn phí với giá mua/bán từ nguồn uy tín.',
                silverDatasetTitle: 'Giá Bạc Phú Quý',
                silverDatasetDesc: 'Giá Bạc tại thị trường Hà Nội (Phú Quý), dữ liệu lịch sử từ 2015. Cập nhật hàng ngày giá mua và bán từ nhà phân phối bạc uy tín.',
                sbvDatasetTitle: 'Lãi Suất Liên Ngân Hàng SBV',
                sbvDatasetDesc: 'Lãi suất liên ngân hàng VND (qua đêm, 1 tuần, 2 tuần, 1-9 tháng) công bố bởi Ngân hàng Nhà nước Việt Nam.',
                tdDatasetTitle: 'Lãi Suất Gửi Tiết Kiệm',
                apiBtn: 'Đăng nhập',
                // Fintel Agent Tab
                fintelHeroBadge: 'Được hỗ trợ bởi AI tiên tiến',
                fintelHeroSubtitle: 'AI Agents chuyên biệt cho phân tích tài chính, dự báo thị trường, và tự động hóa giao dịch. Tích hợp dễ dàng qua API, nhận cảnh báo real-time qua webhook.',
                agentMarketTitle: 'Market Analysis Agent',
                agentMarketDesc: 'Phân tích thị trường tự động - Theo dõi VN-Index, phân tích kỹ thuật, nhận diện xu hướng và cảnh báo biến động bất thường 24/7.',
                agentGoldTitle: 'Gold Trading Agent',
                agentGoldDesc: 'Theo dõi giá vàng - So sánh giá vàng SJC, DOJI, PNJ với giá quốc tế, cảnh báo chênh lệch và thời điểm mua/bán tối ưu.',
                agentNewsTitle: 'News Sentiment Agent',
                agentNewsDesc: 'Phân tích tin tức - Quét tin tức tài chính 24/7, đánh giá sentiment và dự báo tác động đến thị trường VN bằng AI.',
                agentCustomTitle: 'Custom Agent',
                agentCustomDesc: 'Agent tùy chỉnh - Xây dựng AI agent theo yêu cầu riêng của doanh nghiệp: tích hợp dữ liệu nội bộ, workflow tự động, báo cáo định kỳ.',
                agentStatusComingSoon: 'Sắp ra mắt',
                agentStatusOnRequest: 'Theo yêu cầu',
                pricingTitle: 'Bảng Giá',
                pricingSubtitle: 'Chọn gói phù hợp với nhu cầu của bạn',
                pricingStarter: 'Khởi đầu',
                pricingPro: 'Chuyên nghiệp',
                pricingEnterprise: 'Doanh nghiệp',
                pricingFree: 'Miễn phí',
                pricingCustom: 'Liên hệ',
                pricingFeature1Agent: '1 Agent truy cập',
                pricingFeature3Agents: 'Tất cả 3 Agents',
                pricingFeatureCustomAgents: 'Agents tùy chỉnh',
                pricingFeature1kCalls: '1,000 lượt gọi API/tháng',
                pricingFeatureUnlimited: 'Không giới hạn API',
                pricingFeatureEmail: 'Cảnh báo qua email',
                pricingFeatureWebhook: 'Webhooks real-time',
                pricingFeatureCommunity: 'Hỗ trợ cộng đồng',
                pricingFeaturePriority: 'Hỗ trợ ưu tiên',
                pricingFeatureCustomAlerts: 'Cảnh báo tùy chỉnh',
                pricingFeatureOnPremise: 'Triển khai nội bộ',
                pricingFeatureSLA: 'Cam kết SLA',
                pricingFeatureDedicated: 'Hỗ trợ riêng',
                pricingFeaturePrivate: 'Tích hợp dữ liệu riêng',
                pricingBtnStart: 'Bắt đầu',
                pricingBtnUpgrade: 'Nâng cấp Pro',
                pricingBtnContact: 'Liên hệ Sales',
                tabGoldSilver: "Vàng & Bạc",
                tabCurrency: "Tiền tệ VN",
                tabGlobal: "Thị trường Quốc tế",
                tabMacro: 'Vĩ Mô',
                tabDownload: 'Tải xuống',
                // Chart titles & periods
                cpiChart: 'CPI Việt Nam (% YoY/năm)',
                period1y: '1 năm',
                period10y: '10 năm',
                period20y: '20 năm',
                periodAll: 'Tất cả',
                macroNotePrefix: 'Ghi chú:',
                macroNoteSuffix: 'Cập nhật hàng tháng (chưa chính thức)',
                sourceLabel: 'Nguồn:',
                sbvPanelInterbank: 'Lãi Suất Thị Trường Liên Ngân Hàng',
                sbvPanelPolicy: 'Lãi Suất Điều Hành (NHNN)',
                seoLearnMore: 'Tìm hiểu thêm về dữ liệu',
                // 1s Market Pulse
                pulseTitle: 'Thời Báo 1 Giây',
                pulseFilterSource: 'Nguồn:',
                pulseFilterMarket: 'Thị trường:',
                pulseFilterAll: 'Tất cả',
                pulseFilterReset: 'Đặt lại',
                pulseMarketGold: 'Vàng',
                pulseMarketRealEstate: 'Bất động sản',
                pulseMarketBanking: 'Ngân hàng',
                pulseMarketFX: 'Ngoại hối',
                pulseMRIPositive: 'Tích cực (+)',
                pulseMRINegative: 'Tiêu cực (-)',
                pulseFilterSentiment: 'Tâm lý:',
                pulseFilterTime: 'Thời gian:',
                pulseFilterTimeAll: 'Tất cả',
                pulseFilterTime1h: '1 giờ qua',
                pulseFilterTime24h: '24 giờ qua',
                pulseFilterTime7d: '7 ngày qua',
                pulseFiltersLabel: 'Bộ lọc nhanh:',
                pulseFiltersHint: 'Chọn thị trường bạn quan tâm để xem ngay các tin tức mới nhất đang ảnh hưởng đến thị trường đó.',
                pulseHeroGreeting: 'Xin chào, nhà đầu tư!',
                pulseHeroTitleMain: 'Nắm bắt nhịp đập thị trường',
                pulseHeroTitleAccent: 'trong 1 giây',
                pulseHeroBio: 'Theo dõi tâm lý thị trường theo thời gian thực — mỗi tin tức quốc tế được AI gắn nhãn tích cực/tiêu cực theo từng kênh đầu tư (vàng, chứng khoán, tỷ giá...), giúp bạn nắm bắt xu hướng đánh giá của thị trường ngay khi tin vừa xuất hiện.',
                pulseHeroCTAExplore: 'Khám phá 1s Pulse',
                pulseHeroCTAGuide: 'Xem hướng dẫn',
                pulseStatNoData: 'Chưa có dữ liệu 24h qua',
                pulseGuideTitle: 'Cách đọc 1s Pulse',
                pulseGuideBody: 'Mỗi tin tức được AI đọc và gắn nhãn theo kênh đầu tư liên quan (VN-Index, Vàng, Bất động sản, Ngân hàng, Ngoại hối) cùng chỉ số MRI (Market Reaction Index) — thể hiện mức độ tích cực/tiêu cực mà tin đó có thể tạo ra đối với kênh đầu tư đó. MRI dương = tin có xu hướng tích cực, MRI âm = tiêu cực; giá trị tuyệt đối càng lớn, mức độ tác động được AI đánh giá càng mạnh.',
                pulseOverviewTitle: 'Tổng quan 24h',
                pulseHotTopicsTitle: 'Chủ đề nóng',
                pulseSidebarLoading: 'Đang tải...',
                // 1s Future Outlook cards
                foFeatured: 'Báo cáo nổi bật',
                foGoldTitle: 'Dự báo Giá Vàng 2026',
                foGoldDesc: 'Phân tích chuyên sâu từ Goldman Sachs, J.P. Morgan, UBS — Mục tiêu $6,300/oz. Biểu đồ tương tác & Trình mô phỏng biến động.',
                foViewReport: 'Xem báo cáo đầy đủ',
                foRealEstateTitle: 'Bất động sản Việt Nam 2026',
                foRealEstateDesc: 'Phân tích xu hướng giá, vùng tiềm năng và dự báo thị trường.',
                foStockTitle: 'VN-Index & Cổ phiếu 2026',
                foStockDesc: 'Dự báo chỉ số, ngành tiềm năng và chiến lược phân bổ danh mục.',
                foComingSoon: 'Sắp ra mắt',
                // VN30 Score
                vn30Intro: 'Bảng xếp hạng 30 cổ phiếu VN30 theo xác suất tăng giá dự báo bởi mô hình Machine Learning. <strong style="color:var(--gold-primary);">Premium</strong> — xem đầy đủ 30 mã & lịch sử điểm từng mã.',
                vn30GateTitle: 'Xem đầy đủ 30 cổ phiếu VN30',
                vn30GateBody: 'Nâng cấp <strong style="color:var(--gold-primary);">Premium</strong> để xem toàn bộ bảng xếp hạng, lịch sử điểm số từng mã và tín hiệu mua/bán.',
                vn30GateCTA: 'Đăng nhập / Nâng cấp Premium',
                // Download tab
                dlHeading: 'Tải Dữ Liệu (CSV)',
                dlSubtitle: 'Chọn bảng dữ liệu và tải về định dạng CSV. Toàn bộ lịch sử (<code>period=all</code>).',
                dlCatMetals: 'Kim Loại Quý',
                dlCatFX: 'Tỷ Giá & Lãi Suất Tiết Kiệm',
                dlCatSBV: 'Lãi Suất NHNN & Thị Trường Quốc Tế',
                dlColName: 'Tên bảng',
                dlColDesc: 'Mô tả',
                dlColSource: 'Nguồn',
                dlFooter: '<i class="fas fa-info-circle" style="margin-right:4px;"></i> Dữ liệu cập nhật hàng ngày. CSV sử dụng encoding UTF-8, dấu phẩy (<code>,</code>) phân cách cột. Dữ liệu <span style="color:#c96442;font-weight:600;">PREMIUM</span> yêu cầu đăng nhập tài khoản Premium. Sử dụng cho mục đích tham khảo và nghiên cứu, không phải tư vấn đầu tư.',
                // About & Terms
                aboutSectionTitle: 'Giới thiệu & Điều khoản',
                aboutH1: 'Về Viet Dataverse',
                aboutP1: '<strong>Viet Dataverse</strong> là nền tảng dữ liệu kinh tế Việt Nam miễn phí, cung cấp thông tin <strong>giá vàng</strong>, <strong>giá bạc</strong>, và <strong>lãi suất ngân hàng</strong> được thu thập tự động từ các nguồn công khai uy tín.',
                aboutP2: '<strong>Giá vàng trong nước</strong> (SJC, DOJI) với dữ liệu lịch sử từ năm 2015 đến nay. <strong>Giá bạc trong nước</strong> <strong>Lãi suất liên ngân hàng</strong> do Ngân hàng Nhà nước Việt Nam (SBV) công bố. <strong>Lãi suất gửi tiết kiệm</strong> từ các ngân hàng thương mại lớn.',
                aboutP3: 'Dữ liệu được <strong>làm sạch, chuẩn hóa</strong> và lưu trữ lịch sử dài hạn để phục vụ <strong>mục đích nghiên cứu và phân tích</strong>. Bạn có thể tải dữ liệu hoàn toàn miễn phí hoặc truy cập qua <strong>API</strong>.',
                aboutDisclaimer: '<strong>Lưu ý quan trọng:</strong> Dữ liệu chỉ mang tính chất tham khảo, không phải lời khuyên đầu tư. Viet Dataverse không chịu trách nhiệm về các quyết định tài chính dựa trên dữ liệu này. Người dùng cần tự kiểm tra và chịu trách nhiệm với quyết định của mình.',
                aboutSourcesH: 'Về Nguồn Dữ Liệu & Phương Pháp Thu Thập',
                aboutSourcesP1: 'Dữ liệu trên Viet Dataverse được thu thập tự động từ <strong>các nguồn công khai, miễn phí</strong> bao gồm website của các tổ chức tài chính, công ty vàng bạc uy tín, và cơ quan nhà nước. Tất cả dữ liệu đều là <strong>thông tin công khai</strong> mà bất kỳ ai cũng có thể truy cập.',
                aboutSourcesP2: 'Giá trị gia tăng của Viet Dataverse nằm ở việc <strong>làm sạch, chuẩn hóa, lưu trữ lịch sử dài hạn</strong> và cung cấp API miễn phí để phục vụ cộng đồng nghiên cứu. Chúng tôi không sở hữu dữ liệu gốc, chỉ cung cấp dịch vụ tổng hợp và phân phối.',
                aboutTermsH: 'Điều Khoản Sử Dụng',
                aboutTermsList: '<li><strong>Mục đích:</strong> Dữ liệu chỉ phục vụ mục đích nghiên cứu, học thuật, và phân tích cá nhân. Không dùng cho mục đích thương mại trừ khi có thỏa thuận.</li><li><strong>Không phải lời khuyên tài chính:</strong> Viet Dataverse không cung cấp lời khuyên đầu tư. Mọi quyết định tài chính là trách nhiệm của người dùng.</li><li><strong>Độ chính xác:</strong> Chúng tôi nỗ lực đảm bảo độ chính xác nhưng không chịu trách nhiệm về sai sót từ nguồn gốc hoặc quá trình thu thập.</li><li><strong>Bảo vệ nguồn:</strong> Người dùng cam kết không crawl ngược lại dữ liệu từ Viet Dataverse để tạo dịch vụ cạnh tranh.</li>',
                aboutCopyright: '© 2026 Viet Dataverse. Nền tảng dữ liệu kinh tế Việt Nam mã nguồn mở. <a href="mailto:contact@vietdataverse.online" style="color: var(--gold-primary); text-decoration: none;">Liên hệ</a>',
                // Privacy Policy
                privacySectionTitle: 'Chính sách bảo mật (Privacy Policy)',
                privacyIntro: 'Chào mừng bạn đến với <strong style="color: var(--text-primary);">Viet Dataverse</strong>. Chúng tôi cam kết bảo vệ thông tin cá nhân của bạn khi sử dụng nền tảng dữ liệu kinh tế của chúng tôi.',
                privacyH1: '1. Thông tin chúng tôi thu thập',
                privacyP1: 'Để cải thiện chất lượng website, chúng tôi có thể thu thập một số thông tin người dùng như sau:',
                privacyList1: '<li><strong style="color: var(--text-primary);">Thông tin đăng nhập:</strong> Email thị thông qua hệ thống <strong>Google Integration Auth0</strong>.</li><li><strong style="color: var(--text-primary);">Dữ liệu sử dụng:</strong> Thông tin về cách bạn tương tác với web thông qua <strong>Google Analytics</strong> (Địa chỉ IP, loại trình duyệt, thời gian truy cập).</li>',
                privacyH2: '2. Sử dụng Cookie',
                privacyP2: 'Chúng tôi sử dụng cookie để lưu trữ tùy chọn ngôn ngữ và trạng thái đăng nhập của bạn nhằm cải thiện trải nghiệm sử dụng. Cookie này không được chia sẻ với bên thứ ba vì mục đích quảng cáo.',
                privacyH3: '3. Bảo mật dữ liệu',
                privacyP3: 'Chúng tôi <strong style="color: var(--text-primary);">không bán hoặc chia sẻ</strong> email cá nhân của bạn cho bên thứ ba. Dữ liệu chỉ được sử dụng để cung cấp báo cáo giá vàng và cải thiện trải nghiệm người dùng trên hệ thống Viet Dataverse.',
                privacyH4: '4. Liên hệ về quyền riêng tư',
                privacyP4: 'Nếu bạn có bất kỳ câu hỏi nào về chính sách bảo mật, vui lòng liên hệ: <a href="mailto:findatasolution@gmail.com" style="color: var(--gold-accent); text-decoration: none; font-weight: 600;">findatasolution@gmail.com</a>',
                privacyFooter: '© 2026 Viet Dataverse. Nền tảng dữ liệu kinh tế Việt Nam.',
                // Contact
                contactSectionTitle: 'Liên hệ với chúng tôi',
                contactSupportH: 'Hỗ trợ kỹ thuật & Dữ liệu',
                contactSupportP: 'Nếu bạn gặp lỗi khi tải file CSV hoặc có câu hỏi về mô hình dự báo:',
                contactAdH: 'Hợp tác quảng cáo',
                contactAdP: 'Để đặt banner trực tiếp hoặc hợp tác cung cấp dữ liệu kinh tế:',
                contactQuickHint: 'Hoặc sử dụng <strong style="color: var(--gold-accent);">Quick Request</strong> bên dưới ↓',
                // Ad request form
                adReqTitle: 'Yêu cầu quảng cáo nhanh',
                adReqSubtitle: 'Đăng banner quảng cáo trên Viet Dataverse — nhanh chóng & đơn giản',
                adStep1: 'Điền thông tin',
                adStep2: 'Thanh toán QR',
                adStep3: 'Chờ phê duyệt',
                adBrandLabel: 'Tên thương hiệu / Brand Name',
                adBannerLabel: 'Banner (Hình ảnh / Video)',
                adOptional: '(Tùy chọn)',
                adBannerSpec: 'Kích thước tối ưu: <strong style="color: var(--gold-accent);">1920×520 px</strong> (16:9). Chấp nhận: <strong style="color: var(--gold-accent);">MP4, WebM</strong> (video ≤ 10MB) hoặc <strong style="color: var(--gold-accent);">JPG, PNG, WebP, GIF</strong> (ảnh ≤ 5MB).',
                adDropzoneText: 'Kéo & thả hình ảnh hoặc video, hoặc <span style="color: var(--gold-accent); text-decoration: underline;">chọn file</span>',
                adQrTitle: 'Thanh toán bằng QR Code',
                adQrNote: 'QR sẽ được cung cấp sau khi xác nhận',
                adPackageTitle: '<strong style="color: var(--gold-accent);">Gói Banner Quảng Cáo:</strong>',
                adPackageList: '<li style="display: flex; align-items: center; gap: 0.5rem;"><i class="fas fa-check" style="color: #22C55E; font-size: 0.75rem;"></i> Hiển thị banner trên trang chủ</li><li style="display: flex; align-items: center; gap: 0.5rem;"><i class="fas fa-check" style="color: #22C55E; font-size: 0.75rem;"></i> Thời gian: đến khi số lượng view đạt limit của gói</li><li style="display: flex; align-items: center; gap: 0.5rem;"><i class="fas fa-check" style="color: #22C55E; font-size: 0.75rem;"></i> Phê duyệt trong 24 giờ</li>',
                adSubmitBtn: 'Gửi yêu cầu quảng cáo',
                adSuccessH: 'Yêu cầu đã gửi thành công!',
                adSuccessP: 'Chúng tôi sẽ xem xét yêu cầu của bạn và phản hồi qua email trong vòng <strong style="color: var(--gold-accent);">24 giờ</strong>. Vui lòng kiểm tra hộp thư (bao gồm thư rác) để nhận thông tin thanh toán QR Code.',
                // Notifications
                notifLoginTitle: 'Yêu cầu đăng nhập',
                notifLoginMessage: 'Bạn cần đăng nhập để tải dữ liệu. Vui lòng đăng nhập để tiếp tục sử dụng các tính năng của Viet Dataverse.',
                notifCancel: 'Hủy',
                notifClose: 'Đóng',
                notifSignup: 'Tạo tài khoản',
                notifApiTitle: 'API đang phát triển',
                notifApiMessage: 'Tính năng API access hiện đang trong giai đoạn phát triển. Tạo tài khoản để nhận thông báo ngay khi tính năng sẵn sàng.',
                notifApiMessageLoggedIn: 'Tính năng API access hiện đang trong giai đoạn phát triển. Bạn sẽ nhận được thông báo qua email khi tính năng sẵn sàng.',
                // Premium gate
                premiumGateTitle: 'Nội dung Premium',
                premiumGateBody: 'Báo cáo <strong style="color:#d4af37;">1s Future Outlook</strong> chỉ dành cho thành viên Premium. Nâng cấp để đọc phân tích chuyên sâu, dự báo giá vàng và toàn bộ nội dung độc quyền.',
                premiumGateCTA: 'Xem gói Premium',
                premiumGateLater: 'Để sau',
            },
            en: {
                langBtn: 'Vie',
                subtitle: 'Economic Intelligence',
                navDataPortal: 'Open Economic Data',
                nav1sMarketPortal: '1s Market Pulse',
                nav1smarketsub: 'Important updates with Market Response Index',
                futureOutlookSubtitle: 'In-depth analysis & Asset trend forecasts',
                navfinagent: 'Fintel AI Agent',
                navfinagentsub: 'AI Agents for Hire',
                navDownloadApi: 'Download & API',
                navDownloadApiMeta: 'Free Download & API',
                navAboutTerms: 'About & Terms',
                navAboutTermsMeta: 'About project & Terms',
                navPrivacy: 'Privacy Policy',
                navContact: 'Contact',
                navSeparator: 'Services',
                sidebarAccount: 'Account',
                loginBtn: 'Log in',
                logoutBtn: 'Log out',
                mainTitle: 'Download Open Economic Data',
                mainSubtitle: '<strong>Download for free</strong> Vietnam gold, silver prices, SBV interest rates and more economic research and analysis.',
                sectionTitle: 'Download Open Economic Data',
                sectionSubtitle: 'Transparent, high-quality Vietnamese macroeconomic datasets for research and analysis. All data sources are publicly documented and freely accessible. More details about parameters with',
                goldChart: 'Gold Price History (Vietnam)',
                silverChart: 'Silver Price History (Vietnam)',
                sbvChart: 'SBV Interbank Rates History',
                tdChart: 'Commercial Banks Term Deposit History',
                fxrateChart: 'SBV Central Rate (USD/VND)',
                globalChart: 'Global Market Trends (Gold, Silver, NASDAQ)',
                downloadTitle: 'Download Vietnam Historical Index',
                downloadSubtitle: 'Download historical gold price data (SJC, DOJI, PNJ), silver prices, bank interest rates for free. Access Vietnam gold price data from 2015 onwards via RESTful API.',
                goldDatasetTitle: 'Vietnam Historical Gold Price',
                goldDatasetDesc: 'Download Vietnam historical gold price data (SJC, DOJI, PNJ 24K) from 2015 to present for free. Buy/sell prices updated twice daily from reliable sources.',
                silverDatasetTitle: 'Silver Price (Phu Quy)',
                silverDatasetDesc: 'Spot silver prices (Phu Quy), historical data from 2015. Daily buy/sell prices from trusted silver distributors.',
                sbvDatasetTitle: 'SBV Interbank Rates',
                sbvDatasetDesc: 'VND interbank interest rates (overnight, 1 week, 2 weeks, 1-9 months) published by State Bank of Vietnam.',
                tdDatasetTitle: 'Term Deposit Rates',
                apiBtn: 'Login',
                // Fintel Agent Tab
                fintelHeroBadge: 'Powered by Advanced AI',
                fintelHeroSubtitle: 'Specialized AI Agents for financial analysis, market forecasting, and trade automation. Easy API integration, real-time alerts via webhook.',
                agentMarketTitle: 'Market Analysis Agent',
                agentMarketDesc: 'Automated market analysis - Track VN-Index, technical analysis, trend detection and abnormal volatility alerts 24/7.',
                agentGoldTitle: 'Gold Trading Agent',
                agentGoldDesc: 'Gold price tracking - Compare SJC, DOJI, PNJ prices with international rates, spread alerts and optimal buy/sell timing.',
                agentNewsTitle: 'News Sentiment Agent',
                agentNewsDesc: 'News analysis - Scan financial news 24/7, evaluate sentiment and predict market impact on Vietnam markets using AI.',
                agentCustomTitle: 'Custom Agent',
                agentCustomDesc: 'Custom agent - Build AI agents tailored to your business: private data integration, automated workflows, scheduled reports.',
                agentStatusComingSoon: 'Coming Soon',
                agentStatusOnRequest: 'On Request',
                pricingTitle: 'Pricing Plans',
                pricingSubtitle: 'Choose the plan that fits your needs',
                pricingStarter: 'Starter',
                pricingPro: 'Pro',
                pricingEnterprise: 'Enterprise',
                pricingFree: 'Free',
                pricingCustom: 'Custom',
                pricingFeature1Agent: '1 Agent access',
                pricingFeature3Agents: 'All 3 Agents',
                pricingFeatureCustomAgents: 'Custom Agents',
                pricingFeature1kCalls: '1,000 API calls/month',
                pricingFeatureUnlimited: 'Unlimited API calls',
                pricingFeatureEmail: 'Email alerts',
                pricingFeatureWebhook: 'Real-time webhooks',
                pricingFeatureCommunity: 'Community support',
                pricingFeaturePriority: 'Priority support',
                pricingFeatureCustomAlerts: 'Custom alerts',
                pricingFeatureOnPremise: 'On-premise deployment',
                pricingFeatureSLA: 'SLA guarantee',
                pricingFeatureDedicated: 'Dedicated support',
                pricingFeaturePrivate: 'Private data integration',
                pricingBtnStart: 'Get Started',
                pricingBtnUpgrade: 'Upgrade to Pro',
                pricingBtnContact: 'Contact Sales',
                tabGoldSilver: "Gold & Silver",
                tabCurrency: "VN Currency",
                tabGlobal: "Global Market",
                tabMacro: 'Macro',
                tabDownload: 'Download',
                // Chart titles & periods
                cpiChart: 'Vietnam CPI (% YoY)',
                period1y: '1 year',
                period10y: '10 years',
                period20y: '20 years',
                periodAll: 'All',
                macroNotePrefix: 'Note:',
                macroNoteSuffix: 'Updated monthly (unofficial)',
                sourceLabel: 'Source:',
                sbvPanelInterbank: 'Interbank Market Rates',
                sbvPanelPolicy: 'Policy Rates (SBV)',
                seoLearnMore: 'Learn more about the data',
                // 1s Market Pulse
                pulseTitle: '1s Market Pulse',
                pulseFilterSource: 'Source:',
                pulseFilterMarket: 'Market:',
                pulseFilterAll: 'All',
                pulseFilterReset: 'Reset',
                pulseMarketGold: 'Gold',
                pulseMarketRealEstate: 'Real Estate',
                pulseMarketBanking: 'Banking',
                pulseMarketFX: 'FX',
                pulseMRIPositive: 'Positive (+)',
                pulseMRINegative: 'Negative (-)',
                pulseFilterSentiment: 'Sentiment:',
                pulseFilterTime: 'Time:',
                pulseFilterTimeAll: 'All',
                pulseFilterTime1h: 'Last 1h',
                pulseFilterTime24h: 'Last 24h',
                pulseFilterTime7d: 'Last 7d',
                pulseFiltersLabel: 'Quick filters:',
                pulseFiltersHint: 'Pick a market you care about to see the latest news affecting it right now.',
                pulseHeroGreeting: 'Hello, investor!',
                pulseHeroTitleMain: 'Catch the market’s pulse',
                pulseHeroTitleAccent: 'in 1 second',
                pulseHeroBio: 'Track market sentiment in real time — every international news item is AI-tagged positive/negative for each investment channel (gold, stocks, FX...), so you can spot how the market is reacting the moment news breaks.',
                pulseHeroCTAExplore: 'Explore 1s Pulse',
                pulseHeroCTAGuide: 'View guide',
                pulseStatNoData: 'No data in the last 24h',
                pulseGuideTitle: 'How to read 1s Pulse',
                pulseGuideBody: 'Every article is read by AI and tagged with the related investment channel (VN-Index, Gold, Real Estate, Banking, FX) plus an MRI (Market Reaction Index) — how positive/negative that article could be for that channel. Positive MRI = bullish-leaning, negative MRI = bearish-leaning; the larger the absolute value, the stronger the estimated impact.',
                pulseOverviewTitle: '24h Overview',
                pulseHotTopicsTitle: 'Hot Topics',
                pulseSidebarLoading: 'Loading...',
                // 1s Future Outlook cards
                foFeatured: 'Featured Report',
                foGoldTitle: 'Gold Price Forecast 2026',
                foGoldDesc: 'In-depth analysis from Goldman Sachs, J.P. Morgan, UBS — Target $6,300/oz. Interactive charts & volatility simulator.',
                foViewReport: 'View full report',
                foRealEstateTitle: 'Vietnam Real Estate 2026',
                foRealEstateDesc: 'Price trend analysis, potential regions and market forecast.',
                foStockTitle: 'VN-Index & Stocks 2026',
                foStockDesc: 'Index forecast, promising sectors and portfolio allocation strategy.',
                foComingSoon: 'Coming Soon',
                // VN30 Score
                vn30Intro: 'Ranking of the 30 VN30 stocks by price-rise probability predicted by a Machine Learning model. <strong style="color:var(--gold-primary);">Premium</strong> — see all 30 tickers & per-ticker score history.',
                vn30GateTitle: 'See all 30 VN30 stocks',
                vn30GateBody: 'Upgrade to <strong style="color:var(--gold-primary);">Premium</strong> to see the full ranking, per-ticker score history, and buy/sell signals.',
                vn30GateCTA: 'Log in / Upgrade to Premium',
                // Download tab
                dlHeading: 'Download Data (CSV)',
                dlSubtitle: 'Pick a dataset and download it as CSV. Full history (<code>period=all</code>).',
                dlCatMetals: 'Precious Metals',
                dlCatFX: 'FX & Term Deposit Rates',
                dlCatSBV: 'SBV Policy & Global Markets',
                dlColName: 'Dataset',
                dlColDesc: 'Description',
                dlColSource: 'Source',
                dlFooter: '<i class="fas fa-info-circle" style="margin-right:4px;"></i> Data updated daily. CSV uses UTF-8 encoding, comma (<code>,</code>) as column separator. <span style="color:#c96442;font-weight:600;">PREMIUM</span> datasets require a Premium account. For reference and research only, not investment advice.',
                // About & Terms
                aboutSectionTitle: 'About & Terms',
                aboutH1: 'About Viet Dataverse',
                aboutP1: '<strong>Viet Dataverse</strong> is a free Vietnam economic data platform providing <strong>gold prices</strong>, <strong>silver prices</strong>, and <strong>bank interest rates</strong> automatically collected from reliable public sources.',
                aboutP2: '<strong>Domestic gold prices</strong> (SJC, DOJI) with historical data from 2015 to now. <strong>Domestic silver prices</strong>. <strong>Interbank rates</strong> published by the State Bank of Vietnam (SBV). <strong>Term deposit rates</strong> from major commercial banks.',
                aboutP3: 'Data is <strong>cleaned, normalised</strong> and stored with long-term history for <strong>research and analysis</strong>. You can download it for free or access it via <strong>API</strong>.',
                aboutDisclaimer: '<strong>Important notice:</strong> Data is for reference only, not investment advice. Viet Dataverse is not responsible for financial decisions made based on this data. Users must verify data independently and accept responsibility for their own decisions.',
                aboutSourcesH: 'Data Sources & Collection Method',
                aboutSourcesP1: 'Viet Dataverse data is automatically collected from <strong>public, free sources</strong> including financial institutions, reputable gold/silver companies, and government websites. All data is <strong>public information</strong> accessible to anyone.',
                aboutSourcesP2: 'The added value of Viet Dataverse lies in <strong>cleaning, normalising, and storing long-term history</strong>, plus providing a free API for the research community. We do not own the underlying data — only the aggregation and distribution.',
                aboutTermsH: 'Terms of Use',
                aboutTermsList: '<li><strong>Purpose:</strong> Data is for research, academic work, and personal analysis. Not for commercial use without agreement.</li><li><strong>Not financial advice:</strong> Viet Dataverse does not provide investment advice. All financial decisions are the user\'s responsibility.</li><li><strong>Accuracy:</strong> We strive for accuracy but are not responsible for errors in source data or collection.</li><li><strong>Source protection:</strong> Users agree not to re-crawl data from Viet Dataverse to build competing services.</li>',
                aboutCopyright: '© 2026 Viet Dataverse. Open-source Vietnam economic data platform. <a href="mailto:contact@vietdataverse.online" style="color: var(--gold-primary); text-decoration: none;">Contact</a>',
                // Privacy Policy
                privacySectionTitle: 'Privacy Policy',
                privacyIntro: 'Welcome to <strong style="color: var(--text-primary);">Viet Dataverse</strong>. We are committed to protecting your personal information when using our economic data platform.',
                privacyH1: '1. Information we collect',
                privacyP1: 'To improve the quality of the site, we may collect some user information as follows:',
                privacyList1: '<li><strong style="color: var(--text-primary);">Login info:</strong> Email via <strong>Google / Auth0</strong> integration.</li><li><strong style="color: var(--text-primary);">Usage data:</strong> How you interact with the site via <strong>Google Analytics</strong> (IP address, browser, visit time).</li>',
                privacyH2: '2. Cookie usage',
                privacyP2: 'We use cookies to store your language preference and login state to improve your experience. These cookies are not shared with third parties for advertising.',
                privacyH3: '3. Data security',
                privacyP3: 'We <strong style="color: var(--text-primary);">do not sell or share</strong> your personal email with third parties. Data is only used to deliver our reports and improve user experience on Viet Dataverse.',
                privacyH4: '4. Privacy contact',
                privacyP4: 'If you have any questions about this privacy policy, please contact: <a href="mailto:findatasolution@gmail.com" style="color: var(--gold-accent); text-decoration: none; font-weight: 600;">findatasolution@gmail.com</a>',
                privacyFooter: '© 2026 Viet Dataverse. Vietnam economic data platform.',
                // Contact
                contactSectionTitle: 'Contact us',
                contactSupportH: 'Technical & data support',
                contactSupportP: 'If you encounter CSV download errors or have questions about forecasting models:',
                contactAdH: 'Advertising partnerships',
                contactAdP: 'To book a banner directly or partner on economic data:',
                contactQuickHint: 'Or use the <strong style="color: var(--gold-accent);">Quick Request</strong> below ↓',
                // Ad request form
                adReqTitle: 'Quick Request for Advertise',
                adReqSubtitle: 'Book a banner on Viet Dataverse — fast & simple',
                adStep1: 'Fill in details',
                adStep2: 'Pay via QR',
                adStep3: 'Await approval',
                adBrandLabel: 'Brand name',
                adBannerLabel: 'Banner (image / video)',
                adOptional: '(Optional)',
                adBannerSpec: 'Recommended size: <strong style="color: var(--gold-accent);">1920×520 px</strong> (16:9). Accepted: <strong style="color: var(--gold-accent);">MP4, WebM</strong> (video ≤ 10MB) or <strong style="color: var(--gold-accent);">JPG, PNG, WebP, GIF</strong> (image ≤ 5MB).',
                adDropzoneText: 'Drag & drop an image or video, or <span style="color: var(--gold-accent); text-decoration: underline;">choose a file</span>',
                adQrTitle: 'Pay by QR code',
                adQrNote: 'QR will be provided after confirmation',
                adPackageTitle: '<strong style="color: var(--gold-accent);">Banner Advertising Package:</strong>',
                adPackageList: '<li style="display: flex; align-items: center; gap: 0.5rem;"><i class="fas fa-check" style="color: #22C55E; font-size: 0.75rem;"></i> Banner displayed on the home page</li><li style="display: flex; align-items: center; gap: 0.5rem;"><i class="fas fa-check" style="color: #22C55E; font-size: 0.75rem;"></i> Duration: until the package view limit is reached</li><li style="display: flex; align-items: center; gap: 0.5rem;"><i class="fas fa-check" style="color: #22C55E; font-size: 0.75rem;"></i> Approved within 24 hours</li>',
                adSubmitBtn: 'Submit advertising request',
                adSuccessH: 'Request submitted successfully!',
                adSuccessP: 'We will review your request and respond by email within <strong style="color: var(--gold-accent);">24 hours</strong>. Please check your inbox (including spam) for QR payment details.',
                // Notifications
                notifLoginTitle: 'Login required',
                notifLoginMessage: 'You need to log in to download data. Please sign in to continue using Viet Dataverse features.',
                notifCancel: 'Cancel',
                notifClose: 'Close',
                notifSignup: 'Create account',
                notifApiTitle: 'API in development',
                notifApiMessage: 'API access is currently in development. Create an account to be notified when it is ready.',
                notifApiMessageLoggedIn: 'API access is currently in development. You will be notified by email when it is ready.',
                // Premium gate
                premiumGateTitle: 'Premium content',
                premiumGateBody: 'The <strong style="color:#d4af37;">1s Future Outlook</strong> report is for Premium members only. Upgrade to read in-depth analysis, gold price forecasts and all exclusive content.',
                premiumGateCTA: 'View Premium plans',
                premiumGateLater: 'Later',
            }
        };

        function updateLanguage(lang) {
            currentLang = lang;
            const t = translations[lang];

            // Generic sweep — any element with [data-i18n] / [data-i18n-html] gets translated.
            // Keys that don't exist in the translations map are skipped (leaves original text).
            document.querySelectorAll('[data-i18n]').forEach(el => {
                const key = el.getAttribute('data-i18n');
                if (t[key] !== undefined) el.textContent = t[key];
            });
            document.querySelectorAll('[data-i18n-html]').forEach(el => {
                const key = el.getAttribute('data-i18n-html');
                if (t[key] !== undefined) el.innerHTML = t[key];
            });

            // Update button - Header
            document.getElementById('lang-text').textContent = t.langBtn;

            // Update button - Sidebar
            const sidebarLangText = document.getElementById('sidebar-lang-text');
            if (sidebarLangText) {
                sidebarLangText.textContent = t.langBtn;
            }
            // .brand-subtitle removed in topbar unification (DESIGN.md 12.5.3)

            // Update navigation
            const navLinks = document.querySelectorAll('.nav-link');
            navLinks.forEach(link => {
                if (link.getAttribute('data-tab') === 'data-portal') {
                    link.querySelector('h4').textContent = t.navDataPortal;
                } else if (link.getAttribute('data-tab') === '1smarket-portal') {
                    link.querySelector('h4').textContent = t.nav1sMarketPortal;
                    const meta = link.querySelector('.nav-meta');
                    if (meta) meta.textContent = t.nav1smarketsub;
                } else if (link.getAttribute('data-tab') === 'download-api') {
                    link.querySelector('h4').textContent = t.navDownloadApi;
                    const meta = link.querySelector('.nav-meta');
                    if (meta) meta.textContent = t.navDownloadApiMeta;
                }
            });

            // Update separator label
            const sep = document.querySelector('.nav-separator span');
            if (sep) sep.textContent = t.navSeparator;

            // Update sidebar bottom link
            const btmLink = document.querySelector('.sidebar-bottom-link span');
            if (btmLink) btmLink.textContent = t.navAboutTerms;

            // Update main title & subtitle (SEO optimized)
            const mainSection = document.querySelector('#data-portal .section-header');
            if (mainSection) {
                const mainTitle = mainSection.querySelector('.section-title');
                const mainSubtitle = mainSection.querySelector('.section-subtitle');
                if (mainTitle) {
                    const s = mainTitle.querySelector('[data-i18n]');
                    (s || mainTitle).textContent = t.mainTitle;
                }
                if (mainSubtitle) {
                    // Remove <strong> tags and set text content
                    mainSubtitle.innerHTML = t.mainSubtitle;
                }
            }

            // Update download section
            const downloadSection = document.querySelector('#download-api .section-header');
            if (downloadSection) {
                const dlTitle = downloadSection.querySelector('.section-title');
                const dlSubtitle = downloadSection.querySelector('.section-subtitle');
                if (dlTitle) dlTitle.textContent = t.downloadTitle;
                if (dlSubtitle) dlSubtitle.innerHTML = t.downloadSubtitle;
            }

            // Update dataset cards (only in Download tab, not Fintel Agent tab)
            const datasetCards = document.querySelectorAll('#download-api .dataset-card');
            if (datasetCards[0]) {
                const h3 = datasetCards[0].querySelector('h3');
                const desc = datasetCards[0].querySelector('.dataset-desc');
                if (h3) h3.textContent = t.goldDatasetTitle;
                if (desc) desc.innerHTML = t.goldDatasetDesc;
            }
            if (datasetCards[1]) {
                const h3 = datasetCards[1].querySelector('h3');
                const desc = datasetCards[1].querySelector('.dataset-desc');
                if (h3) h3.textContent = t.silverDatasetTitle;
                if (desc) desc.innerHTML = t.silverDatasetDesc;
            }
            if (datasetCards[2]) {
                const h3 = datasetCards[2].querySelector('h3');
                const desc = datasetCards[2].querySelector('.dataset-desc');
                if (h3) h3.textContent = t.sbvDatasetTitle;
                if (desc) desc.innerHTML = t.sbvDatasetDesc;
            }
            if (datasetCards[3]) {
                const h3 = datasetCards[3].querySelector('h3');
                const desc = datasetCards[3].querySelector('.dataset-desc');
                if (h3) h3.textContent = t.tdDatasetTitle;
                if (desc) desc.innerHTML = t.tdDatasetDesc;
            }

            // Update charts — target inner [data-i18n] span to preserve the ⓘ icon
            const chartTitles = document.querySelectorAll('.chart-title');
            const setTitle = (el, text) => {
                if (!el) return;
                const s = el.querySelector('[data-i18n]');
                (s || el).textContent = text;
            };
            setTitle(chartTitles[0], t.goldChart);
            setTitle(chartTitles[1], t.silverChart);
            setTitle(chartTitles[2], t.tdChart);
            setTitle(chartTitles[3], t.sbvChart);
            setTitle(chartTitles[4], t.fxrateChart);
            setTitle(chartTitles[5], t.globalChart);

            // Update Chart Tabs (Gold & Silver / Currency / Global)
            document.querySelectorAll('.chart-tab-btn span[data-i18n]').forEach(el => {
                const key = el.getAttribute('data-i18n');
                if (t[key]) el.textContent = t[key];
            });
            // Set HTML lang and persist choice
            document.documentElement.lang = lang;
            localStorage.setItem('lang', lang);
        }

        // Check authentication status and update UI
        function checkAuthenticationStatus() {
            const token = localStorage.getItem('auth_token');
            const userEmail = localStorage.getItem('user_email');

            const userInfo = document.getElementById('user-info');
            const loginLink = document.getElementById('login-link');
            const logoutBtn = document.getElementById('logout-btn');
            const userEmailElement = document.getElementById('user-email');

            // Sidebar elements
            const sidebarUserInfo = document.getElementById('sidebar-user-info');
            const sidebarLoginLink = document.getElementById('sidebar-login-link');
            const sidebarLogoutBtn = document.getElementById('sidebar-logout-btn');
            const sidebarUserEmail = document.getElementById('sidebar-user-email');

            if (token && userEmail) {
                // User is logged in - Header
                userInfo.style.display = 'flex';
                loginLink.style.display = 'none';
                const userAvatar = document.getElementById('user-avatar');
                if (userAvatar) {
                    userAvatar.textContent = (userEmail[0] || 'U').toUpperCase();
                    userAvatar.title = userEmail;
                }

                // User is logged in - Sidebar
                if (sidebarUserInfo) sidebarUserInfo.style.display = 'block';
                if (sidebarLoginLink) sidebarLoginLink.style.display = 'none';
                if (sidebarLogoutBtn) sidebarLogoutBtn.style.display = 'block';
                if (sidebarUserEmail) sidebarUserEmail.textContent = userEmail;
            } else {
                // User is not logged in - Header
                userInfo.style.display = 'none';
                loginLink.style.display = 'block';

                // User is not logged in - Sidebar
                if (sidebarUserInfo) sidebarUserInfo.style.display = 'none';
                if (sidebarLoginLink) sidebarLoginLink.style.display = 'block';
                if (sidebarLogoutBtn) sidebarLogoutBtn.style.display = 'none';
            }
        }
        /* =========================================================
           GLOBAL CONFIG (SAFE – NO DUPLICATE)
        ========================================================= */
        (function () {
            window.APP_CONFIG = window.APP_CONFIG || {};
            window.APP_CONFIG.API_BASE_URL =
                location.hostname === 'localhost' || location.hostname === '127.0.0.1'
                    ? 'http://localhost:8000/api/v1'
                    : 'https://api.vietdataverse.online/api/v1';

            // Prefetch gold & silver data immediately (before DOMContentLoaded)
            // These promises are consumed by loadChartData() when it runs later
            const base = window.APP_CONFIG.API_BASE_URL;
            window._prefetchPromises = {};
            // Prefetch gold/silver from static files (generated daily) — anonymous
            // visitors don't carry an API key/Bearer token, and these endpoints
            // are now metered, so the default chart must not depend on a live call.
            window._prefetchPromises['gold-1m-DOJI HN'] = fetch('./data/gold_DOJI_HN_1m.json')
                .then(r => r.ok ? r.json() : Promise.reject(r.status))
                .catch(e => { console.warn('[prefetch] gold static failed:', e); return null; });
            window._prefetchPromises['silver-1m'] = fetch('./data/silver_1m.json')
                .then(r => r.ok ? r.json() : Promise.reject(r.status))
                .catch(e => { console.warn('[prefetch] silver static failed:', e); return null; });
            // Prefetch fxrate from static file (generated daily from SBV data)
            window._prefetchPromises['fxrate-1m'] = fetch('./data/fxrate_SBV_USD_1m.json')
                .then(r => r.ok ? r.json() : Promise.reject(r.status))
                .catch(e => { console.warn('[prefetch] fxrate static failed:', e); return null; });
        })();

        /* =========================================================
           DOM READY
        ========================================================= */
        document.addEventListener('DOMContentLoaded', async () => {
            initHeaderActions();
            initMobileMenu();
            initSidebarTabs();
            initScrollSections();
            initFilterButtons();
            initNotifications();
            initPulseSidebar();
            initReportListing();
            loadMarketMovement();

            // Initialize Auth0 and check authentication status
            await initAuth0AndUpdateUI();
        });

        /* =========================================================
           AUTH0 INITIALIZATION & UI UPDATE
        ========================================================= */
        async function initAuth0AndUpdateUI() {
            try {
                // Initialize Auth0
                await initAuth0();

                // Check if user is authenticated
                const authenticated = await isAuthenticated();

                if (authenticated) {
                    // Get user info from Auth0
                    const user = await getUser();

                    // Check if user qualifies for admin override (local dev helper)
                    if (typeof checkAdminOverride === 'function') {
                        await checkAdminOverride();
                    }

                    // GA4: track login + set user identity
                    if (typeof gtag === 'function' && user) {
                        gtag('set', 'user_properties', {
                            user_email: user.email || ''
                        });
                        gtag('event', 'login', {
                            method: 'auth0',
                            user_email: user.email || '',
                            user_name: user.name || ''
                        });
                    }

                    // Sync user with backend DB by calling /me endpoint
                    // NOTE: /me route has no /api/v1 prefix — use API_BASE_URL (from auth.js)
                    try {
                        const token = await getToken();
                        const response = await fetch(`${API_BASE_URL}/me`, {
                            headers: {
                                'Authorization': `Bearer ${token}`,
                                'Content-Type': 'application/json'
                            }
                        });

                        if (response.ok) {
                            const dbUser = await response.json();
                            window._vdvUserLevel = dbUser.user_level || 'free';
                            localStorage.setItem('vdv_user_level', dbUser.user_level || 'free');
                            console.log('User synced with backend:', dbUser);
                            if (typeof window.kmCheckAdmin === 'function') window.kmCheckAdmin();
                            // Reload Market Pulse now that auth is confirmed and user_level is known
                            loadMarketPulse();
                        } else {
                            console.warn('Failed to sync user with backend:', response.status);
                        }
                    } catch (err) {
                        console.error('Error syncing user with backend:', err);
                    }

                    // Update UI to show logged-in state
                    const loginLink = document.getElementById('login-link');
                    const userInfo = document.getElementById('user-info');
                    const userEmail = document.getElementById('user-email');
                    const logoutBtn = document.getElementById('logout-btn');

                    // Header
                    if (loginLink) loginLink.style.display = 'none';
                    if (userInfo) userInfo.style.display = 'flex';
                    const emailStr = user.email || user.name || 'User';
                    const userAvatar = document.getElementById('user-avatar');
                    if (userAvatar) {
                        userAvatar.textContent = (emailStr[0] || 'U').toUpperCase();
                        userAvatar.title = emailStr;
                    }
                    if (logoutBtn) {
                        logoutBtn.addEventListener('click', () => {
                            localStorage.removeItem('vdv_user_level');
                            logout();
                        });
                    }

                    // Sidebar
                    const sidebarLoginLink = document.getElementById('sidebar-login-link');
                    const sidebarUserInfo = document.getElementById('sidebar-user-info');
                    const sidebarUserEmail = document.getElementById('sidebar-user-email');
                    const sidebarLogoutBtn = document.getElementById('sidebar-logout-btn');

                    if (sidebarLoginLink) sidebarLoginLink.style.display = 'none';
                    if (sidebarUserInfo) sidebarUserInfo.style.display = 'block';
                    if (sidebarUserEmail) sidebarUserEmail.textContent = user.email || user.name || 'User';
                    if (sidebarLogoutBtn) {
                        sidebarLogoutBtn.style.display = 'block';
                        sidebarLogoutBtn.addEventListener('click', () => {
                            logout();
                        });
                    }

                    // Admin panel link — show only for admin accounts
                    const userLevel = window._vdvUserLevel || localStorage.getItem('vdv_user_level') || 'free';
                    const sidebarFooter = document.querySelector('.sidebar-footer');

                    // API Key link — visible for every logged-in user (page gates by tier)
                    if (sidebarFooter && !sidebarFooter.querySelector('[data-vdv-dev-link]')) {
                        const devLink = document.createElement('a');
                        devLink.href = '/pages/developer.html';
                        devLink.className = 'sidebar-bottom-link';
                        devLink.dataset.vdvDevLink = '1';
                        devLink.textContent = '🔑 API Key';
                        sidebarFooter.prepend(devLink);
                    }

                    if (userLevel === 'admin') {
                        const adminLink = document.createElement('a');
                        adminLink.href = '/pages/admin.html';
                        adminLink.className = 'sidebar-bottom-link';
                        adminLink.style.cssText = 'color:var(--terracotta);font-weight:600;';
                        adminLink.textContent = '⚙ Admin Panel';
                        if (sidebarFooter) sidebarFooter.prepend(adminLink);
                    }
                }
            } catch (err) {
                console.error('Auth0 initialization failed:', err);
            }
        }

        /* =========================================================
           BANNER UPLOAD — image & video preview handlers
        ========================================================= */
        function handleBannerFile(file) {
            if (!file) return;

            const maxVideoSize = 10 * 1024 * 1024; // 10 MB
            const maxImageSize = 5 * 1024 * 1024;  // 5 MB
            const isVideo = file.type.startsWith('video/');
            const isImage = file.type.startsWith('image/');

            if (!isVideo && !isImage) {
                alert('Chỉ chấp nhận file hình ảnh (JPG, PNG, WebP, GIF) hoặc video (MP4, WebM).');
                return;
            }
            if (isVideo && file.size > maxVideoSize) {
                alert('Video quá lớn. Dung lượng tối đa là 10MB.');
                return;
            }
            if (isImage && file.size > maxImageSize) {
                alert('Hình ảnh quá lớn. Dung lượng tối đa là 5MB.');
                return;
            }

            // Show filename
            const filenameEl = document.getElementById('ad-banner-filename');
            if (filenameEl) {
                filenameEl.textContent = file.name;
                filenameEl.style.display = 'block';
            }

            // Show preview
            const previewWrap = document.getElementById('ad-banner-preview');
            const previewImg = document.getElementById('ad-banner-preview-img');
            const previewVid = document.getElementById('ad-banner-preview-video');
            const url = URL.createObjectURL(file);

            if (isVideo) {
                if (previewImg) previewImg.style.display = 'none';
                if (previewVid) {
                    previewVid.src = url;
                    previewVid.style.display = 'block';
                }
            } else {
                if (previewVid) { previewVid.style.display = 'none'; previewVid.src = ''; }
                if (previewImg) {
                    previewImg.src = url;
                    previewImg.style.display = 'block';
                }
            }
            if (previewWrap) previewWrap.style.display = 'block';
        }

        function handleBannerSelect(input) {
            if (input.files && input.files[0]) handleBannerFile(input.files[0]);
        }

        function handleBannerDrop(event) {
            const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
            handleBannerFile(file);
        }

        /* =========================================================
           HEADER ACTIONS: LANGUAGE + LOGIN
        ========================================================= */
        function initHeaderActions() {
            const sidebarLangBtn = document.getElementById('sidebar-lang-toggle');
            const ddLangBtn = document.getElementById('settings-dd-lang');

            /* ---------- LANGUAGE (ENG / VIE) ---------- */
            const savedLang = localStorage.getItem('lang') || 'vi';
            updateLanguage(savedLang);

            if (sidebarLangBtn) {
                sidebarLangBtn.addEventListener('click', () => {
                    const current = document.documentElement.lang || 'vi';
                    const next = current === 'vi' ? 'en' : 'vi';
                    updateLanguage(next);
                });
            }
            if (ddLangBtn) {
                ddLangBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const current = document.documentElement.lang || 'vi';
                    const next = current === 'vi' ? 'en' : 'vi';
                    updateLanguage(next);
                });
            }

            /* ---------- LOGIN (notification modal) ---------- */
            const loginBtn = document.getElementById('login-btn');
            if (loginBtn) {
                loginBtn.addEventListener('click', () => {
                    // Close notification overlay first
                    const overlay = document.getElementById('notification-overlay');
                    if (overlay) overlay.classList.remove('active');
                    // Use Auth0 login
                    if (typeof login === 'function') login();
                });
            }
        }

        /* =========================================================
           LANGUAGE HANDLER (UI-LEVEL, STABLE)
        ========================================================= */
        function setLanguage(lang) {
            document.documentElement.lang = lang;
            localStorage.setItem('lang', lang);

            const label = lang === 'vi' ? 'EN / VIE' : 'VIE / EN';

            // Update settings dropdown lang button
            const langText = document.getElementById('lang-text');
            if (langText) langText.textContent = label;

            // Update sidebar lang button
            const sidebarText = document.getElementById('sidebar-lang-text');
            if (sidebarText) sidebarText.textContent = label;

            document.body.setAttribute('data-lang', lang);
        }

        /* =========================================================
           MOBILE MENU
        ========================================================= */
        function initMobileMenu() {
            const toggle = document.getElementById('mobile-menu-toggle');
            const sidebar = document.querySelector('.sidebar');
            const overlay = document.getElementById('mobile-overlay');

            if (!toggle || !sidebar || !overlay) return;

            toggle.addEventListener('click', () => {
                sidebar.classList.toggle('active');
                overlay.classList.toggle('active');
            });

            overlay.addEventListener('click', () => {
                sidebar.classList.remove('active');
                overlay.classList.remove('active');
            });
        }

        /* =========================================================
           SIDEBAR TABS (main-level only)
        ========================================================= */
        let _tabDwellTimer = null;
        const TAB_LABELS = {
            'data-portal': 'Open Economic Data',
            '1smarket-portal': '1s Market Pulse',
            'download-api': 'Download & API',
            'about-terms': 'About & Terms',
            'privacy-policy': 'Privacy Policy',
            'contact': 'Contact'

        };

        function activateTab(tabId) {
            // GA4: track tab engagement (stayed 5s+)
            if (_tabDwellTimer) clearTimeout(_tabDwellTimer);
            _tabDwellTimer = setTimeout(() => {
                if (typeof gtag === 'function') {
                    gtag('event', 'tab_engaged', {
                        tab_id: tabId,
                        tab_name: TAB_LABELS[tabId] || tabId,
                        dwell_seconds: 5
                    });
                }
            }, 5000);

            // Toggle nav-links
            document.querySelectorAll('.nav-link[data-tab]').forEach(l => l.classList.remove('active'));
            const activeNav = document.querySelector(`.nav-link[data-tab="${tabId}"]`);
            if (activeNav) activeNav.classList.add('active');

            // Toggle tab-content
            document.querySelectorAll('.main-content > .tab-content').forEach(c => c.classList.remove('active'));
            const target = document.getElementById(tabId);
            if (target) target.classList.add('active');

            // Reset scroll to top when switching tabs
            const mainContent = document.querySelector('.main-content');
            if (mainContent) mainContent.scrollTop = 0;

            // Close mobile sidebar
            const sidebar = document.querySelector('.sidebar');
            const mobileOverlay = document.getElementById('mobile-overlay');
            if (sidebar) sidebar.classList.remove('active');
            if (mobileOverlay) mobileOverlay.classList.remove('active');
        }

        // ─────────────────────────────────────────────────────────────
        // Workspace routing
        // Hash format: #<workspace>/<view>[/<sub>]
        // Mapping: tab-id → workspace id
        // ─────────────────────────────────────────────────────────────
        const TAB_WORKSPACE_MAP = {
            'data-portal':        'data',
            // Legal pages — routed via footer, shown as tab-content
            'about-terms':        'data',
            'privacy-policy':     'data',
            'contact':            'data',
            'knowledge-market':   'km',
            '1smarket-portal':    'pulse'
        };

        // legal sub-view → DOM tab-id mapping (footer links use #legal/*)
        const LEGAL_VIEW_MAP = {
            'about':    'about-terms',
            'privacy':  'privacy-policy',
            'contact':  'contact',
            'dmca':     'about-terms'   // DMCA opens about-terms (takedown section); full page at /pages/takedown.html
        };

        // Legacy hash redirect map (keep for 1 release)
        const LEGACY_HASH_MAP = {
            'knowledge-market':     'km/knowledge-market',
            'tab-knowledge-market': 'km/knowledge-market',
            '1smarket-portal':      'pulse/1smarket-portal',
            // Legacy chart tab hashes → new format
            'tab-gold-silver':      'data/portal/gold-silver',
            'tab-currency':         'data/portal/currency',
            'tab-global':           'data/portal/global',
            'tab-macro':            'data/portal/macro',
            'tab-stock':            'data/portal/stock',
            'tab-download':         'data/portal/download',
            // KM sub-view legacy hashes
            'tab-library':          'km/library',
            'tab-wallet':           'km/wallet',
            'tab-seller':           'km/seller-dashboard',
        };

        // Workspaces that have no useful sidebar — hide it and go full-width
        const NO_SIDEBAR_WORKSPACES = ['data', 'pulse', 'km'];

        function setWorkspace(ws) {
            // Update workspace tab buttons
            document.querySelectorAll('.workspace-tab[data-workspace]').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.workspace === ws);
                btn.setAttribute('aria-selected', btn.dataset.workspace === ws ? 'true' : 'false');
            });

            // Update sidebar contexts
            document.querySelectorAll('.sidebar-context[data-workspace]').forEach(ctx => {
                ctx.classList.toggle('active', ctx.dataset.workspace === ws);
            });

            // Hide sidebar for workspaces that don't need it
            const container = document.querySelector('.app-container');
            if (container) {
                container.classList.toggle('no-sidebar', NO_SIDEBAR_WORKSPACES.includes(ws));
            }
        }

        function setView(viewId) {
            // Alias for activateTab — activates the correct workspace first, then the tab
            const ws = TAB_WORKSPACE_MAP[viewId] || 'data';
            setWorkspace(ws);
            activateTab(viewId);
        }

        function initSidebarTabs() {
            // Workspace tab bar clicks → pushState (back button switches workspace)
            const WORKSPACE_DEFAULT_TAB = {
                'data':  'data-portal',
                'km':    'knowledge-market',
                'pulse': '1smarket-portal',
            };
            document.querySelectorAll('.workspace-tab[data-workspace]').forEach(btn => {
                btn.addEventListener('click', () => {
                    const ws = btn.dataset.workspace;
                    setWorkspace(ws);
                    // Activate the first nav-link in this workspace if present (data),
                    // otherwise fall back to the workspace default tab (km, pulse).
                    const firstLink = document.querySelector(
                        `.sidebar-context[data-workspace="${ws}"] .nav-link[data-tab]`
                    );
                    const tabId = firstLink ? firstLink.dataset.tab : WORKSPACE_DEFAULT_TAB[ws];
                    if (tabId) {
                        activateTab(tabId);
                        history.pushState(null, '', '#' + ws + '/' + tabId);
                    } else {
                        history.pushState(null, '', '#' + ws);
                    }
                });
            });

            // Nav-link tab clicks → replaceState (no back-button spam)
            document.querySelectorAll('.nav-link[data-tab]').forEach(link => {
                link.addEventListener('click', () => {
                    const tabId = link.dataset.tab;
                    const ws = TAB_WORKSPACE_MAP[tabId] || 'data';
                    setWorkspace(ws);
                    activateTab(tabId);
                    history.replaceState(null, '', '#' + ws + '/' + tabId);
                });
            });

            // Footer data-route links → pushState (legal pages)
            document.querySelectorAll('a[data-route]').forEach(link => {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    const route = link.dataset.route; // e.g. "legal/about"
                    const parts = route.split('/');
                    const ws = parts[0];
                    const sub = parts[1] || null;
                    if (ws === 'legal' && sub && LEGAL_VIEW_MAP[sub]) {
                        const tabId = LEGAL_VIEW_MAP[sub];
                        // Legal pages show inside data workspace (existing tab-content)
                        setWorkspace('data');
                        activateTab(tabId);
                        history.pushState(null, '', '#' + route);
                    } else {
                        // Generic route — activate workspace
                        setWorkspace(ws);
                        history.pushState(null, '', '#' + route);
                    }
                });
            });

            // Footer lang toggle (sync with settings dropdown lang toggle)
            const footerLangBtn = document.getElementById('footer-lang-toggle');
            if (footerLangBtn) {
                footerLangBtn.addEventListener('click', () => {
                    const ddLangBtn = document.getElementById('settings-dd-lang');
                    if (ddLangBtn) ddLangBtn.click();
                });
            }

            // Handle URL hash on page load
            // Supports: #ws/view[/sub]  |  legacy #tabId  |  plain #tabId
            const rawHash = window.location.hash.replace('#', '');
            if (rawHash) {
                // Check legacy redirect map first
                if (LEGACY_HASH_MAP[rawHash]) {
                    const redirected = LEGACY_HASH_MAP[rawHash];
                    history.replaceState(null, '', '#' + redirected);
                    const parts = redirected.split('/');
                    const ws = parts[0];
                    const tabId = parts[1] || null;
                    const sub = parts[2] || null;
                    setWorkspace(ws);
                    if (tabId === 'portal' && ws === 'data') {
                        activateTab('data-portal');
                        if (sub) {
                            setTimeout(() => {
                                const el = document.querySelector(`[data-lazy-section="${sub}"]`);
                                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                            }, 100);
                        }
                    } else if (tabId && document.getElementById(tabId)) {
                        activateTab(tabId);
                    } else if (ws === 'km' && tabId) {
                        activateTab('knowledge-market');
                    }
                } else if (rawHash.includes('/')) {
                    // New format: ws/view[/sub]
                    const parts = rawHash.split('/');
                    const ws = parts[0];
                    const tabId = parts[1] || null;
                    const sub = parts[2] || null;
                    setWorkspace(ws);
                    if (ws === 'legal' && tabId && LEGAL_VIEW_MAP[tabId]) {
                        // Legal route: show as data workspace tab
                        setWorkspace('data');
                        activateTab(LEGAL_VIEW_MAP[tabId]);
                    } else if (ws === 'data' && tabId === 'portal') {
                        activateTab('data-portal');
                        if (sub) {
                            const chartBtn = document.querySelector(`.chart-tab-btn[data-tab="tab-${sub}"]`);
                            if (chartBtn) chartBtn.click();
                        }
                    } else if (tabId && document.getElementById(tabId)) {
                        activateTab(tabId);
                    } else if (ws === 'km' && tabId) {
                        // KM sub-view (library, wallet, seller-dashboard, etc.)
                        activateTab('knowledge-market');
                        setTimeout(function () {
                            if (window.KM && typeof window.KM._setKmNavActive === 'function') {
                                window.KM._setKmNavActive(tabId);
                            }
                            var KM_VIEW_MAP = {
                                'library':          function () { window.KM && window.KM.loadLibrary(); },
                                'wallet':           function () { window.KM && window.KM.openWallet(); },
                                'seller-dashboard': function () { window.KM && window.KM.openSellerDashboard(); },
                                'upload':           function () { window.KM && window.KM.openUploadProduct(); },
                                'earnings':         function () { window.KM && window.KM.openSellerDashboard(); },
                                'admin':            function () { window.KM && window.KM.openAdminPanel(); },
                            };
                            if (KM_VIEW_MAP[tabId]) KM_VIEW_MAP[tabId]();
                        }, 300);
                    }
                } else if (document.getElementById(rawHash)) {
                    // Plain hash — resolve workspace and activate
                    const ws = TAB_WORKSPACE_MAP[rawHash] || 'data';
                    setWorkspace(ws);
                    activateTab(rawHash);
                }
            } else {
                // No hash — default to #data/portal
                history.replaceState(null, '', '#data/portal');
                setWorkspace('data');
                activateTab('data-portal');
            }
        }

        /* =========================================================
           1s PULSE SIDEBAR — Watchlist & Filter Chips
        ========================================================= */
        var PULSE_WATCHLIST_KEY = 'viet_pulse_watchlist';

        function loadWatchlist() {
            try {
                return JSON.parse(localStorage.getItem(PULSE_WATCHLIST_KEY) || '[]');
            } catch (e) {
                return [];
            }
        }

        function saveWatchlist(items) {
            localStorage.setItem(PULSE_WATCHLIST_KEY, JSON.stringify(items));
        }

        function addToWatchlist(ticker) {
            var list = loadWatchlist();
            if (!list.find(function (i) { return i.ticker === ticker; })) {
                list.push({ ticker: ticker, addedAt: Date.now() });
                saveWatchlist(list);
                renderPulseWatchlist();
            }
        }

        function removeFromWatchlist(ticker) {
            var list = loadWatchlist().filter(function (i) { return i.ticker !== ticker; });
            saveWatchlist(list);
            renderPulseWatchlist();
        }

        function renderPulseWatchlist() {
            var container = document.getElementById('pulse-watchlist-items');
            var placeholder = document.getElementById('pulse-watchlist-placeholder');
            if (!container) return;

            var list = loadWatchlist();
            // Remove existing item rows (keep placeholder)
            container.querySelectorAll('.pulse-watchlist-item').forEach(function (el) { el.remove(); });

            if (list.length === 0) {
                if (placeholder) placeholder.style.display = '';
            } else {
                if (placeholder) placeholder.style.display = 'none';
                list.forEach(function (item) {
                    var row = document.createElement('div');
                    row.className = 'pulse-watchlist-item';
                    row.dataset.ticker = item.ticker;
                    row.innerHTML =
                        '<span class="pulse-watchlist-ticker">' + item.ticker + '</span>' +
                        '<span class="pulse-watchlist-price">—</span>' +
                        '<span class="pulse-watchlist-delta">—</span>' +
                        '<button class="pulse-watchlist-remove" title="Remove" data-ticker="' + item.ticker + '">×</button>';
                    container.insertBefore(row, placeholder || null);
                    row.querySelector('.pulse-watchlist-remove').addEventListener('click', function (e) {
                        e.stopPropagation();
                        removeFromWatchlist(item.ticker);
                    });
                });
            }
        }

        function initPulseSidebar() {
            renderPulseWatchlist();

            // Filter chip multi-toggle
            var chipContainer = document.getElementById('pulse-filter-chips');
            if (chipContainer) {
                chipContainer.addEventListener('click', function (e) {
                    var chip = e.target.closest('.pulse-filter-chip');
                    if (!chip) return;
                    var filter = chip.dataset.filter;
                    if (filter === 'all') {
                        chipContainer.querySelectorAll('.pulse-filter-chip').forEach(function (c) {
                            c.classList.toggle('active', c.dataset.filter === 'all');
                        });
                    } else {
                        chip.classList.toggle('active');
                        var anyActive = Array.from(chipContainer.querySelectorAll('.pulse-filter-chip'))
                            .some(function (c) { return c.classList.contains('active') && c.dataset.filter !== 'all'; });
                        var allChip = chipContainer.querySelector('[data-filter="all"]');
                        if (allChip) allChip.classList.toggle('active', !anyActive);
                    }
                    // TODO: dispatch filter change event to pulse feed renderer
                });
            }

            // Pulse FEED nav-items
            document.querySelectorAll('[data-pulse-view]').forEach(function (link) {
                link.addEventListener('click', function (e) {
                    e.preventDefault();
                    document.querySelectorAll('[data-pulse-view]').forEach(function (l) {
                        l.classList.remove('active');
                    });
                    link.classList.add('active');
                    var view = link.dataset.pulseView;
                    history.replaceState(null, '', '#pulse/' + view);
                    // TODO: renderPulseFeed(view) when pulse feed is implemented
                });
            });
        }

        /* =========================================================
           REPORT LISTING — DMCA Inline Action
        ========================================================= */
        function initReportListing() {
            var modal = document.getElementById('report-listing-modal');
            var submitBtn = document.getElementById('report-submit-btn');

            // Any element with data-report-listing="<listingId>" opens the modal
            document.addEventListener('click', function (e) {
                var trigger = e.target.closest('[data-report-listing]');
                if (!trigger) return;
                var listingId = trigger.dataset.reportListing;
                if (modal) {
                    modal.dataset.listingId = listingId || '';
                    modal.style.display = 'flex';
                }
            });

            if (submitBtn && modal) {
                submitBtn.addEventListener('click', function () {
                    var reason = document.getElementById('report-reason').value;
                    var description = document.getElementById('report-description').value;
                    var listingId = modal.dataset.listingId || '';
                    if (!reason) {
                        alert('Please select a reason.');
                        return;
                    }
                    // TODO: POST /api/v1/report { listingId, reason, description }
                    console.info('[report] listing=' + listingId, 'reason=' + reason, description);
                    modal.style.display = 'none';
                    document.getElementById('report-reason').value = '';
                    document.getElementById('report-description').value = '';
                });
            }
        }

        /* =========================================================
           CHART SUB-TABS (Vang & Bac / Tien te VN / Quoc te)
           WITH LAZY LOADING
        ========================================================= */
        function loadChartsForSection(sectionKey) {
            if (loadedSections[sectionKey]) return;
            loadedSections[sectionKey] = true;

            if (sectionKey === 'gold-silver') {
                const goldType = document.getElementById('goldTypeSelect')?.value || 'DOJI HN';
                Promise.all([
                    loadChartData('gold', '1m', goldType),
                    loadChartData('silver', '1m')
                ]);
            } else if (sectionKey === 'currency') {
                const bankCode = document.getElementById('bankTypeSelect')?.value || 'ACB';
                Promise.all([
                    loadChartData('td', '1y', null, bankCode),
                    loadChartData('sbv', '1m'),
                    loadChartData('fxrate', '1m')
                ]);
            } else if (sectionKey === 'global') {
                loadChartData('global', '1m');
            } else if (sectionKey === 'macro') {
                loadMacroCharts(20);
            } else if (sectionKey === 'stock') {
                loadVnindexChart('1y');
            }
        }

        function initScrollSections() {
            // Load first section immediately (above fold)
            loadChartsForSection('gold-silver');

            // IntersectionObserver for remaining sections
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (!entry.isIntersecting) return;
                    const key = entry.target.dataset.lazySection;
                    loadChartsForSection(key);
                    observer.unobserve(entry.target);
                });
            }, { rootMargin: '0px 0px 400px 0px' });

            document.querySelectorAll('[data-lazy-section]').forEach(el => {
                if (el.dataset.lazySection !== 'gold-silver') observer.observe(el);
            });
        }

        /* =========================================================
           FILTER BUTTONS & DROPDOWNS
        ========================================================= */
        function initFilterButtons() {
            // Period filter buttons
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const chart = btn.dataset.chart;
                    const period = btn.dataset.period;

                    // Update active state
                    btn.parentElement
                        ?.querySelectorAll('.filter-btn')
                        .forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');

                    // Get additional parameters
                    let goldType = null;
                    let bankCode = null;

                    if (chart === 'gold') {
                        goldType = document.getElementById('goldTypeSelect')?.value || 'DOJI HN';
                    } else if (chart === 'td') {
                        bankCode = document.getElementById('bankTypeSelect')?.value || 'ACB';
                    }

                    // Load chart data with updated period
                    loadChartData(chart, period, goldType, bankCode);
                });
            });

            // Gold type selector
            const GOLD_SOURCES = {
                'DOJI HN':    { label: '24h.com.vn', url: 'https://www.24h.com.vn/gia-vang-hom-nay-c425.html' },
                'DOJI SG':    { label: '24h.com.vn', url: 'https://www.24h.com.vn/gia-vang-hom-nay-c425.html' },
                'BTMC SJC':   { label: 'btmc.vn',    url: 'https://btmc.vn/' },
                'BTMH':       { label: 'btmc.vn',    url: 'https://btmc.vn/' },
                'Phú Quý SJC':{ label: 'phuquygroup.vn', url: 'https://www.phuquygroup.vn/gia-vang' },
            };
            function updateGoldSource(goldType) {
                const el = document.getElementById('goldChartSource');
                if (!el) return;
                const src = GOLD_SOURCES[goldType] || { label: '24h.com.vn', url: 'https://www.24h.com.vn/gia-vang-hom-nay-c425.html' };
                el.innerHTML = `Nguồn: <a href="${src.url}" target="_blank" rel="noopener">${src.label}</a>`;
            }

            const BANK_SOURCES = {
                'ACB': { label: 'acb.com.vn',       url: 'https://acb.com.vn/lai-suat-tien-gui' },
                'CTG': { label: 'vietinbank.vn',     url: 'https://www.vietinbank.vn/vi/ca-nhan/cong-cu-tien-ich/lai-suat-khcn' },
                'SHB': { label: 'shb.com.vn',        url: 'https://www.shb.com.vn/lai-suat' },
                'VCB': { label: 'vietcombank.com.vn',url: 'https://www.vietcombank.com.vn/vi/Personal/Cong-cu-Tien-ich/KHCN---Lai-suat' },
            };
            function updateTdSource(bankCode) {
                const el = document.getElementById('tdChartSource');
                if (!el) return;
                const src = BANK_SOURCES[bankCode] || BANK_SOURCES['ACB'];
                el.innerHTML = `Nguồn: <a href="${src.url}" target="_blank" rel="noopener">${src.label}</a>`;
            }

            const goldTypeSelect = document.getElementById('goldTypeSelect');
            if (goldTypeSelect) {
                goldTypeSelect.addEventListener('change', (e) => {
                    const goldType = e.target.value;
                    const activePeriodBtn = document.querySelector('.filter-btn[data-chart="gold"].active');
                    const period = activePeriodBtn?.dataset.period || '1m';
                    loadChartData('gold', period, goldType);
                    updateGoldSource(goldType);
                });
            }

            // Bank type selector
            const bankTypeSelect = document.getElementById('bankTypeSelect');
            if (bankTypeSelect) {
                bankTypeSelect.addEventListener('change', (e) => {
                    const bankCode = e.target.value;
                    const activePeriodBtn = document.querySelector('.filter-btn[data-chart="td"].active');
                    const period = activePeriodBtn?.dataset.period || '1y';
                    loadChartData('td', period, null, bankCode);
                    updateTdSource(bankCode);
                });
            }
        }

        /* =========================================================
           NOTIFICATION OVERLAYS
        ========================================================= */
        function initNotifications() {
            // Download notification - cancel
            const cancelBtn = document.getElementById('cancel-btn');
            if (cancelBtn) {
                cancelBtn.addEventListener('click', () => {
                    const overlay = document.getElementById('notification-overlay');
                    if (overlay) overlay.classList.remove('active');
                });
            }

            // API notification - cancel
            const apiCancelBtn = document.getElementById('api-cancel-btn');
            if (apiCancelBtn) {
                apiCancelBtn.addEventListener('click', () => {
                    const overlay = document.getElementById('api-notification-overlay');
                    if (overlay) overlay.classList.remove('active');
                });
            }

            // API notification - signup
            const apiSignupBtn = document.getElementById('api-signup-btn');
            if (apiSignupBtn) {
                apiSignupBtn.addEventListener('click', () => {
                    const overlay = document.getElementById('api-notification-overlay');
                    if (overlay) overlay.classList.remove('active');
                    if (typeof signup === 'function') signup();
                });
            }

            // Download buttons -> show login notification if not authenticated, or trigger download
            document.querySelectorAll('[data-download]').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const dataType = btn.dataset.download;

                    // GA4: track every download button click (regardless of auth)
                    if (typeof gtag === 'function') {
                        gtag('event', 'download_click', {
                            data_type: dataType,
                            authenticated: false // updated below if authed
                        });
                    }

                    const authed = typeof isAuthenticated === 'function' && await isAuthenticated();
                    if (!authed) {
                        // GA4: track blocked download (user not logged in)
                        if (typeof gtag === 'function') {
                            gtag('event', 'download_blocked', {
                                data_type: dataType,
                                reason: 'not_authenticated'
                            });
                        }
                        const overlay = document.getElementById('notification-overlay');
                        if (overlay) overlay.classList.add('active');
                        return;
                    }

                    // User is authenticated - trigger actual download
                    await downloadData(dataType);
                });
            });

            // API buttons -> check authentication status
            document.querySelectorAll('[data-api]').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const authed = typeof isAuthenticated === 'function' && await isAuthenticated();
                    const overlay = document.getElementById('api-notification-overlay');
                    const signupBtn = document.getElementById('api-signup-btn');

                    if (authed) {
                        // User is logged in - hide signup button
                        if (signupBtn) signupBtn.style.display = 'none';
                    } else {
                        // User is not logged in - show signup button
                        if (signupBtn) signupBtn.style.display = 'inline-flex';
                    }

                    if (overlay) overlay.classList.add('active');
                });
            });
        }

        /* =========================================================
           DOWNLOAD DATA FUNCTIONALITY
        ========================================================= */
        async function downloadData(dataType) {
            const base = window.APP_CONFIG.API_BASE_URL;

            // Map data types to API endpoints
            const endpointMap = {
                'gold': 'gold?period=all',
                'silver': 'silver?period=all',
                'sbv': 'sbv-interbank?period=all'
            };

            const endpoint = endpointMap[dataType];
            if (!endpoint) {
                console.error('Unknown data type:', dataType);
                return;
            }

            try {
                // Show loading state (optional - could add a loading indicator)
                console.log(`Downloading ${dataType} data...`);

                // Fetch data from API (đính kèm token — endpoint giờ cần auth)
                const response = await fetch(`${base}/${endpoint}`, { headers: await _authHeaders() });
                if (!response.ok) throw new Error('Failed to fetch data');

                const jsonData = await response.json();

                if (!jsonData.success || !jsonData.data) {
                    throw new Error('Invalid data format');
                }

                // Convert to CSV
                let csvContent = '';
                const data = jsonData.data;

                if (dataType === 'gold' || dataType === 'silver') {
                    // CSV header
                    csvContent = 'Date,Buy Price,Sell Price\n';

                    // CSV rows
                    for (let i = 0; i < data.dates.length; i++) {
                        csvContent += `${data.dates[i]},${data.buy_prices[i]},${data.sell_prices[i]}\n`;
                    }
                } else if (dataType === 'sbv') {
                    // CSV header
                    csvContent = 'Date,Overnight,1 Month,3 Months,Rediscount,Refinancing\n';

                    // CSV rows
                    for (let i = 0; i < data.dates.length; i++) {
                        csvContent += `${data.dates[i]},${data.overnight[i]},${data.month_1[i]},${data.month_3[i]},${data.rediscount[i]},${data.refinancing[i]}\n`;
                    }
                }

                // Create blob and trigger download
                const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                const link = document.createElement('a');
                const url = URL.createObjectURL(blob);

                link.setAttribute('href', url);
                link.setAttribute('download', `vietdataverse_${dataType}_${new Date().toISOString().split('T')[0]}.csv`);
                link.style.visibility = 'hidden';

                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                console.log(`Downloaded ${dataType} data successfully`);

                // GA4: track file download
                if (typeof gtag === 'function') {
                    gtag('event', 'file_download', {
                        file_name: `vietdataverse_${dataType}`,
                        file_type: 'csv',
                        data_type: dataType
                    });
                }

            } catch (error) {
                console.error('Download failed:', error);
                alert('Download failed. Please try again.');
            }
        }

        /* =========================================================
           DOWNLOAD DATASET (tab-download)
        ========================================================= */
        // Users may only download historical data older than 2 months.
        // Why: product rule — free users get delayed data; recent 2 months are gated.
        function _downloadCutoffISO() {
            const d = new Date();
            d.setMonth(d.getMonth() - 2);
            return d.toISOString().slice(0, 10);
        }

        function _filterBeforeCutoff(datasetId, data, cutoff) {
            if (datasetId === 'vn30-profile') return data; // static reference, no date axis

            // Parallel-array shape: { dates: [...], <metric>: [...], ... }
            if (data && Array.isArray(data.dates)) {
                const n = data.dates.length;
                const keep = [];
                for (let i = 0; i < n; i++) {
                    if (String(data.dates[i] ?? '').slice(0, 10) <= cutoff) keep.push(i);
                }
                const out = {};
                for (const k of Object.keys(data)) {
                    out[k] = Array.isArray(data[k]) && data[k].length === n
                        ? keep.map(i => data[k][i])
                        : data[k];
                }
                return out;
            }

            // Row-array shape (vn30-prices / ratios / financials)
            if (Array.isArray(data)) {
                return data.filter(r => {
                    if (r.date) return String(r.date).slice(0, 10) <= cutoff;
                    if (r.year != null && r.quarter != null) {
                        const m = r.quarter * 3;
                        const last = new Date(r.year, m, 0).getDate();
                        return `${r.year}-${String(m).padStart(2, '0')}-${String(last).padStart(2, '0')}` <= cutoff;
                    }
                    return true;
                });
            }

            return data;
        }

        // Build Authorization header từ Auth0 token — data endpoints giờ cần đăng nhập (free tier 1.000 req/tháng).
        async function _authHeaders() {
            try {
                if (typeof getToken === 'function') {
                    const t = await getToken();
                    if (t) return { Authorization: 'Bearer ' + t };
                }
            } catch (_) { /* ignore */ }
            return {};
        }

        async function downloadDataset(datasetId) {
            const base = window.APP_CONFIG.API_BASE_URL;
            const btn = event.currentTarget;
            const origHtml = btn.innerHTML;

            // Yêu cầu đăng nhập — tải dữ liệu cần tài khoản (miễn phí) để hệ thống đo được usage.
            const authed = typeof isAuthenticated === 'function' && await isAuthenticated();
            if (!authed) {
                const overlay = document.getElementById('notification-overlay');
                if (overlay) overlay.classList.add('active');
                return;
            }

            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang tải...';
            btn.disabled = true;

            try {
                let url, filename, rows2csv;

                if (datasetId.startsWith('gold-')) {
                    const type = datasetId.slice(5); // e.g. "DOJI HN"
                    url = `${base}/gold?period=all&type=${encodeURIComponent(type)}`;
                    filename = `gold_${type.replace(/ /g,'_')}`;
                    rows2csv = d => 'Date,Buy Price (VND),Sell Price (VND)\n' +
                        d.dates.map((dt,i) => `${dt},${d.buy_prices[i]},${d.sell_prices[i]}`).join('\n');

                } else if (datasetId === 'silver') {
                    url = `${base}/silver?period=all`;
                    filename = 'silver_phuquy';
                    rows2csv = d => 'Date,Buy Price (VND),Sell Price (VND)\n' +
                        d.dates.map((dt,i) => `${dt},${d.buy_prices[i]},${d.sell_prices[i]}`).join('\n');

                } else if (datasetId.startsWith('fxrate-')) {
                    const [, bank, currency] = datasetId.split('-');
                    url = `${base}/sbv-centralrate?period=all&bank=${bank}&currency=${currency}`;
                    filename = `fxrate_${bank}_${currency}`;
                    // SBV: only central rate; VCB: include buy/sell
                    const isSBV = bank === 'SBV';
                    rows2csv = isSBV
                        ? d => 'Date,Central Rate (VND/USD)\n' +
                            d.dates.map((dt,i) => `${dt},${d.usd_vnd_rate[i]??''}`).join('\n')
                        : d => 'Date,Buy Transfer (VND),Buy Cash (VND),Sell Rate (VND)\n' +
                            d.dates.map((dt,i) => `${dt},${d.usd_vnd_rate[i]??''},${d.buy_cash[i]??''},${d.sell_rate[i]??''}`).join('\n');

                } else if (datasetId.startsWith('termdepo-')) {
                    const bank = datasetId.slice(9);
                    url = `${base}/termdepo?period=all&bank=${bank}`;
                    filename = `termdepo_${bank}`;
                    rows2csv = d => 'Date,1M(%),3M(%),6M(%),12M(%),24M(%)\n' +
                        d.dates.map((dt,i) => `${dt},${d.term_1m[i]??''},${d.term_3m[i]??''},${d.term_6m[i]??''},${d.term_12m[i]??''},${d.term_24m[i]??''}`).join('\n');

                } else if (datasetId === 'sbv-interbank') {
                    url = `${base}/sbv-interbank?period=all`;
                    filename = 'sbv_interbank_rates';
                    rows2csv = d => 'Date,Overnight(%),1M(%),3M(%),6M(%),9M(%),Rediscount(%),Refinancing(%)\n' +
                        d.dates.map((dt,i) => `${dt},${d.overnight[i]??''},${d.month_1[i]??''},${d.month_3[i]??''},${d.month_6[i]??''},${d.month_9[i]??''},${d.rediscount[i]??''},${d.refinancing[i]??''}`).join('\n');

                } else if (datasetId === 'global-macro') {
                    url = `${base}/global-macro?period=all`;
                    filename = 'global_macro';
                    rows2csv = d => 'Date,Gold (USD/oz),Silver (USD/oz),NASDAQ\n' +
                        d.dates.map((dt,i) => `${dt},${d.gold_prices[i]??''},${d.silver_prices[i]??''},${d.nasdaq_prices[i]??''}`).join('\n');

                } else if (datasetId === 'vn30-profile') {
                    url = `${base}/vn30/download/profile`;
                    filename = 'vn30_company_profile';
                    rows2csv = d => 'Ticker,Company Name,Exchange,ICB Sector,ICB Industry,Market Cap (tỷ VND),Listed Date\n' +
                        d.map(r => `${r.ticker},"${r.company_name ?? ''}",${r.exchange ?? ''},${r.icb_sector ?? ''},${r.icb_industry ?? ''},${r.market_cap_billion ?? ''},${r.listed_date ?? ''}`).join('\n');

                } else if (datasetId === 'vn30-prices') {
                    url = `${base}/vn30/download/prices?period=all`;
                    filename = 'vn30_ohlcv_prices';
                    rows2csv = d => 'Ticker,Date,Open,High,Low,Close,Volume,Value (VND)\n' +
                        d.map(r => `${r.ticker},${r.date},${r.open??''},${r.high??''},${r.low??''},${r.close??''},${r.volume??''},${r.value??''}`).join('\n');

                } else if (datasetId === 'vn30-financials') {
                    url = `${base}/vn30/download/financials`;
                    filename = 'vn30_income_statement';
                    rows2csv = d => 'Ticker,Year,Quarter,Revenue (tỷ),Gross Profit (tỷ),EBIT (tỷ),Net Income (tỷ),EPS (VND)\n' +
                        d.map(r => `${r.ticker},${r.year},Q${r.quarter},${r.revenue??''},${r.gross_profit??''},${r.ebit??''},${r.net_income??''},${r.eps??''}`).join('\n');

                } else if (datasetId === 'vn30-ratios') {
                    url = `${base}/vn30/download/ratios?period=all`;
                    filename = 'vn30_financial_ratios';
                    rows2csv = d => 'Ticker,Date,P/E,P/B,P/S,ROE(%),ROA(%),EPS,Dividend Yield(%),Market Cap (tỷ)\n' +
                        d.map(r => `${r.ticker},${r.date},${r.pe??''},${r.pb??''},${r.ps??''},${r.roe??''},${r.roa??''},${r.eps??''},${r.dividend_yield??''},${r.market_cap_billion??''}`).join('\n');

                } else {
                    throw new Error('Unknown dataset: ' + datasetId);
                }

                const res = await fetch(url, { headers: await _authHeaders() });
                if (!res.ok) throw new Error(`API error ${res.status}`);
                const json = await res.json();
                if (!json.success || !json.data) throw new Error('Invalid response');

                const filtered = _filterBeforeCutoff(datasetId, json.data, _downloadCutoffISO());
                const csv = rows2csv(filtered);
                const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
                const link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = `vietdataverse_${filename}_${new Date().toISOString().slice(0,10)}.csv`;
                link.style.display = 'none';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                btn.innerHTML = '<i class="fas fa-check"></i> Done';
                setTimeout(() => { btn.innerHTML = origHtml; btn.disabled = false; }, 2000);

                if (typeof gtag === 'function') gtag('event', 'file_download', { file_name: filename, file_type: 'csv' });

            } catch (err) {
                console.error('[download]', err);
                btn.innerHTML = '<i class="fas fa-times"></i> Lỗi';
                setTimeout(() => { btn.innerHTML = origHtml; btn.disabled = false; }, 2500);
            }
        }

        /* =========================================================
           CHART RENDERING SYSTEM WITH LAZY LOADING & CACHING
        ========================================================= */

        // Store Chart.js instances
        const chartInstances = {
            gold: null,
            silver: null,
            td: null,
            sbv: null,
            fxrate: null,
            global: null
        };

        // Cache for loaded data (avoid redundant API calls)
        const chartCache = {};

        // Track which tabs have been loaded
        const loadedSections = {
            'gold-silver': false,
            'currency':    false,
            'global':      false,
            'macro':       false,
            'stock':       false
        };

        // Map chart types to their API endpoints
        const CHART_API_ENDPOINTS = {
            gold: 'gold',
            silver: 'silver',
            td: 'termdepo',
            sbv: 'sbv-interbank',
            fxrate: 'sbv-centralrate',
            global: 'global-macro'
        };

        /* =========================================================
           FETCH CHART DATA - STATIC CDN FIRST, API FALLBACK
        ========================================================= */
        async function loadChartData(chartType, period = '1m', goldType = 'DOJI HN', bankCode = 'ACB') {
            const base = window.APP_CONFIG.API_BASE_URL;
            if (!chartType) return;

            const endpoint = CHART_API_ENDPOINTS[chartType];
            if (!endpoint) { console.error('Unknown chart type:', chartType); return; }

            const cacheKey = `${chartType}-${period}-${goldType}-${bankCode}`;
            if (chartCache[cacheKey]) {
                console.log(`[${chartType}] Using cached data`);
                renderChart(chartType, chartCache[cacheKey], period);
                return;
            }

            const loadingEl = document.getElementById(`${chartType}Loading`);
            if (loadingEl) loadingEl.style.display = 'flex';

            let data = null;
            try {
                // Check for prefetched data first (fired before DOMContentLoaded)
                const prefetchKey = (chartType === 'gold') ? `gold-${period}-${goldType}` : `${chartType}-${period}`;
                if (window._prefetchPromises && window._prefetchPromises[prefetchKey]) {
                    console.log(`[${chartType}] Using prefetched promise`);
                    data = await window._prefetchPromises[prefetchKey];
                    delete window._prefetchPromises[prefetchKey]; // consume once
                }

                // Fallback: fetch from API if prefetch missed or failed
                if (!data && base) {
                    let apiUrl = `${base}/${endpoint}?period=${period}`;
                    if (chartType === 'gold' && goldType) apiUrl += `&type=${encodeURIComponent(goldType)}`;
                    if (chartType === 'td' && bankCode) apiUrl += `&bank=${encodeURIComponent(bankCode)}`;
                    if (chartType === 'fxrate') apiUrl += `&bank=SBV&currency=USD`;
                    const res = await fetchWithTimeout(apiUrl, { headers: await _authHeaders() }, 20000);
                    if (!res.ok) throw new Error(`API error: ${res.status}`);
                    data = await res.json();
                }

                if (data) { chartCache[cacheKey] = data; renderChart(chartType, data, period); }
                else { throw new Error('No data source available'); }

            } catch (e) {
                console.error(`[${chartType}] All fetch failed:`, e);
                if (chartType === 'global') {
                    if (loadingEl) loadingEl.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-tertiary)"><i class="fas fa-chart-line" style="font-size:2.5rem;margin-bottom:1rem;display:block;opacity:0.3"></i><p style="font-size:0.95rem">Dữ liệu thị trường quốc tế đang trong quá trình phát triển.</p></div>';
                } else {
                    const isTimeout = e.name === 'AbortError';
                    const errMsg = isTimeout
                        ? 'API đang khởi động, vui lòng thử lại sau vài giây'
                        : 'Không tải được dữ liệu';
                    showChartError(loadingEl, chartType, errMsg);
                }
            } finally {
                setTimeout(() => {
                    if (loadingEl && !loadingEl.querySelector('button')) {
                        loadingEl.style.display = 'none';
                    }
                }, 500);
            }
        }

        /* =========================================================
           RENDER CHART WITH CHART.JS
        ========================================================= */
        function renderChart(chartType, apiData, period) {
            const canvas = document.getElementById(`${chartType}Chart`);
            if (!canvas) {
                console.error(`Canvas not found for ${chartType}Chart`);
                return;
            }

            const ctx = canvas.getContext('2d');

            // Destroy existing chart instance if it exists
            if (chartInstances[chartType]) {
                chartInstances[chartType].destroy();
            }

            // Parse data based on chart type
            let chartData;
            if (chartType === 'gold' || chartType === 'silver') {
                chartData = parseGoldSilverData(apiData, chartType);
            } else if (chartType === 'td') {
                chartData = parseTDData(apiData);
            } else if (chartType === 'sbv') {
                chartData = parseSBVData(apiData);
                // Also render policy-rate panel
                const canvas2 = document.getElementById('sbv2Chart');
                if (canvas2) {
                    if (chartInstances['sbv2']) chartInstances['sbv2'].destroy();
                    const cfg2 = parseSBVPolicyData(apiData);
                    if (cfg2) chartInstances['sbv2'] = new Chart(canvas2.getContext('2d'), cfg2);
                }
            } else if (chartType === 'fxrate') {
                chartData = parseFxRateData(apiData);
            } else if (chartType === 'global') {
                chartData = parseGlobalData(apiData);
            }

            if (!chartData) {
                console.error(`Failed to parse data for ${chartType}`);
                return;
            }

            // Create new chart
            chartInstances[chartType] = new Chart(ctx, chartData);
        }

        /* =========================================================
           DATA PARSERS FOR DIFFERENT CHART TYPES
        ========================================================= */
        function parseGoldSilverData(apiData, chartType) {
            // API format: { success: true, data: { dates: [...], buy_prices: [...], sell_prices: [...] } }
            if (!apiData || !apiData.data || !apiData.data.dates) {
                console.warn(`No data for ${chartType}`);
                return null;
            }

            const dates = apiData.data.dates;
            const buyPrices = apiData.data.buy_prices;
            const sellPrices = apiData.data.sell_prices;

            const color = chartType === 'gold' ? '#c96442' : '#87867f';

            return {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: [
                        {
                            label: 'Buy Price (Mua vào)',
                            data: buyPrices,
                            borderColor: color,
                            backgroundColor: color + '20',
                            borderWidth: 2,
                            tension: 0.4,
                            fill: true
                        },
                        {
                            label: 'Sell Price (Bán ra)',
                            data: sellPrices,
                            borderColor: color + 'CC',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            tension: 0.4,
                            borderDash: [5, 5]
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            labels: { color: '#87867f' }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#87867f', maxRotation: 45 },
                            grid: { display: false }
                        },
                        y: {
                            ticks: { color: '#87867f' },
                            grid: { display: false }
                        }
                    }
                }
            };
        }

        function parseTDData(apiData) {
            // API format: { success: true, data: { dates: [...], term_1m: [...], term_3m: [...], ... } }
            if (!apiData || !apiData.data || !apiData.data.dates) {
                return null;
            }

            const dates = apiData.data.dates;
            const rate1m = apiData.data.term_1m;
            const rate3m = apiData.data.term_3m;
            const rate6m = apiData.data.term_6m;
            const rate12m = apiData.data.term_12m;

            return {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: [
                        {
                            label: '1 Month',
                            data: rate1m,
                            borderColor: '#42A5F5',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            tension: 0.4
                        },
                        {
                            label: '3 Months',
                            data: rate3m,
                            borderColor: '#66BB6A',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            tension: 0.4
                        },
                        {
                            label: '6 Months',
                            data: rate6m,
                            borderColor: '#FFA726',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            tension: 0.4
                        },
                        {
                            label: '12 Months',
                            data: rate12m,
                            borderColor: '#EF5350',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            tension: 0.4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            labels: { color: '#87867f' }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#87867f', maxRotation: 45 },
                            grid: { display: false }
                        },
                        y: {
                            ticks: {
                                color: '#87867f',
                                callback: function (value) {
                                    return value + '%';
                                }
                            },
                            grid: { display: false }
                        }
                    }
                }
            };
        }

        const _sbvChartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, labels: { color: '#87867f' } },
                tooltip: { mode: 'index', intersect: false }
            },
            scales: {
                x: { ticks: { color: '#87867f', maxRotation: 45 }, grid: { display: false } },
                y: {
                    ticks: { color: '#87867f', callback: v => v + '%' },
                    grid: { display: false }
                }
            }
        };

        function parseSBVData(apiData) {
            // Interbank rates: overnight (qua đêm), 1m, 9m
            if (!apiData || !apiData.data || !apiData.data.dates) return null;
            const d = apiData.data;
            return {
                type: 'line',
                data: {
                    labels: d.dates,
                    datasets: [
                        { label: 'Qua đêm (Overnight)', data: d.overnight, borderColor: '#c96442', backgroundColor: 'transparent', borderWidth: 2, tension: 0.4 },
                        { label: '1 Tháng (1M)',         data: d.month_1,   borderColor: '#42A5F5', backgroundColor: 'transparent', borderWidth: 2, tension: 0.4 },
                        { label: d.month_9 ? '9 Tháng (9M)' : '3 Tháng (3M)', data: d.month_9 ?? d.month_3, borderColor: '#66BB6A', backgroundColor: 'transparent', borderWidth: 2, tension: 0.4 }
                    ]
                },
                options: _sbvChartOptions
            };
        }

        function parseSBVPolicyData(apiData) {
            // Policy rates: rediscount, refinancing
            if (!apiData || !apiData.data || !apiData.data.dates) return null;
            const d = apiData.data;
            return {
                type: 'line',
                data: {
                    labels: d.dates,
                    datasets: [
                        { label: 'Lãi suất chiết khấu (Rediscount)', data: d.rediscount,  borderColor: '#EF5350', backgroundColor: 'transparent', borderWidth: 2, tension: 0.4 },
                        { label: 'Lãi suất tái cấp vốn (Refinancing)', data: d.refinancing, borderColor: '#AB47BC', backgroundColor: 'transparent', borderWidth: 2, tension: 0.4 }
                    ]
                },
                options: _sbvChartOptions
            };
        }

        function parseFxRateData(apiData) {
            // Support two formats:
            // - Live API: { success: true, data: { dates: [...], usd_vnd_rate: [...] } }
            // - Static file: { dates: [...], usd_vnd_rate: [...] }
            let dates, rates;
            if (apiData && apiData.data && apiData.data.dates) {
                dates = apiData.data.dates;
                rates = apiData.data.usd_vnd_rate;
            } else if (apiData && apiData.dates) {
                dates = apiData.dates;
                rates = apiData.usd_vnd_rate;
            } else {
                return null;
            }
            if (!dates || !dates.length) return null;

            return {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: [
                        {
                            label: 'USD/VND',
                            data: rates,
                            borderColor: '#c96442',
                            backgroundColor: 'rgba(201, 100, 66, 0.08)',
                            borderWidth: 2,
                            tension: 0.3,
                            fill: true,
                            pointRadius: dates.length > 60 ? 0 : 3,
                            pointHoverRadius: 5,
                            pointBackgroundColor: '#c96442'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            labels: { color: '#87867f' }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            callbacks: {
                                label: function (ctx) {
                                    return 'USD/VND: ' + ctx.parsed.y.toLocaleString('vi-VN');
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#87867f', maxRotation: 45 },
                            grid: { display: false }
                        },
                        y: {
                            ticks: {
                                color: '#87867f',
                                callback: function (value) {
                                    return value.toLocaleString('vi-VN');
                                }
                            },
                            grid: { display: false }
                        }
                    }
                }
            };
        }

        function parseGlobalData(apiData) {
            // API format: { success: true, data: { dates: [...], gold_prices: [...], silver_prices: [...], nasdaq_prices: [...] } }
            if (!apiData || !apiData.data || !apiData.data.dates) {
                return null;
            }

            const dates = apiData.data.dates;
            const goldFuture = apiData.data.gold_prices;
            const silverSpot = apiData.data.silver_prices;
            const nasdaq = apiData.data.nasdaq_prices;

            return {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: [
                        {
                            label: 'Gold Future ($/oz)',
                            data: goldFuture,
                            borderColor: '#c96442',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            tension: 0.4,
                            yAxisID: 'y'
                        },
                        {
                            label: 'Silver Spot ($/oz)',
                            data: silverSpot,
                            borderColor: '#87867f',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            tension: 0.4,
                            yAxisID: 'y1'
                        },
                        {
                            label: 'NASDAQ',
                            data: nasdaq,
                            borderColor: '#42A5F5',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            tension: 0.4,
                            yAxisID: 'y2'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    plugins: {
                        legend: {
                            display: true,
                            labels: { color: '#87867f' }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#87867f', maxRotation: 45 },
                            grid: { display: false }
                        },
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            ticks: { color: '#c96442' },
                            grid: { display: false }
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            ticks: { color: '#87867f' },
                            grid: { display: false }
                        },
                        y2: {
                            type: 'linear',
                            display: false,
                            position: 'right'
                        }
                    }
                }
            };
        }

        /* =========================================================
           MARKET MOVEMENT CARD (gold-silver section sidebar)
        ========================================================= */
        async function loadMarketMovement() {
            const base = window.APP_CONFIG.API_BASE_URL;

            function setRow(valueId, changeId, value, delta, pct, decimals) {
                const valueEl = document.getElementById(valueId);
                const changeEl = document.getElementById(changeId);
                if (!valueEl || !changeEl) return;

                valueEl.textContent = value.toLocaleString('vi-VN', {
                    minimumFractionDigits: decimals,
                    maximumFractionDigits: decimals
                });

                const sign = delta >= 0 ? '+' : '';
                changeEl.textContent = `${sign}${delta.toLocaleString('vi-VN', {
                    minimumFractionDigits: decimals,
                    maximumFractionDigits: decimals
                })} (${sign}${pct.toFixed(2)}%)`;
                changeEl.classList.remove('positive', 'negative');
                changeEl.classList.add(delta >= 0 ? 'positive' : 'negative');
            }

            function lastChange(series) {
                if (!series || series.length < 2) return null;
                const last = series[series.length - 1];
                const prev = series[series.length - 2];
                if (last == null || prev == null) return null;
                return { last, delta: last - prev, pct: (last - prev) / prev * 100 };
            }

            // USD/VND — SBV central rate
            try {
                let fxData = window._prefetchPromises && window._prefetchPromises['fxrate-1m']
                    ? await window._prefetchPromises['fxrate-1m']
                    : null;
                if (!fxData) {
                    const r = await fetchWithTimeout(`${base}/sbv-centralrate?period=7d&bank=SBV&currency=USD`, { headers: await _authHeaders() }, 15000);
                    if (r.ok) fxData = await r.json();
                }
                const rates = fxData && fxData.data ? fxData.data.usd_vnd_rate : fxData ? fxData.usd_vnd_rate : null;
                const fx = lastChange(rates);
                if (fx) setRow('mmFxValue', 'mmFxChange', fx.last, fx.delta, fx.pct, 0);
            } catch (e) {
                console.warn('[market-movement] fxrate failed:', e);
            }

            // Vàng thế giới — XAU/USD (gold future)
            try {
                const r = await fetchWithTimeout(`${base}/global-macro?period=7d`, { headers: await _authHeaders() }, 15000);
                if (r.ok) {
                    const json = await r.json();
                    const gold = lastChange(json && json.data ? json.data.gold_prices : null);
                    if (gold) setRow('mmGoldValue', 'mmGoldChange', gold.last, gold.delta, gold.pct, 2);
                }
            } catch (e) {
                console.warn('[market-movement] global-macro failed:', e);
            }

            // VN-Index
            try {
                const r = await fetchWithTimeout(`${base}/market/vnindex?period=7d`, {}, 15000);
                if (r.ok) {
                    const json = await r.json();
                    const closes = (json.data || []).map(d => d.close);
                    const vnindex = lastChange(closes);
                    if (vnindex) setRow('mmVnindexValue', 'mmVnindexChange', vnindex.last, vnindex.delta, vnindex.pct, 2);
                }
            } catch (e) {
                console.warn('[market-movement] vnindex failed:', e);
            }
        }

        /* =========================================================
           VNINDEX CHART
        ========================================================= */
        (function () {
            const API_BASE = (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || '/api/v1';
            let _vnindexChart = null;
            let _vnindexCache = {};

            window.loadVnindexChart = async function (period) {
                // Update active button
                document.querySelectorAll('[data-vnindex-period]').forEach(b => {
                    b.classList.toggle('active', b.dataset.vnindexPeriod === period);
                });

                if (_vnindexCache[period]) {
                    renderVnindex(_vnindexCache[period]);
                    return;
                }

                const loading = document.getElementById('vnindexLoading');
                if (loading) loading.style.display = 'flex';

                try {
                    const r = await fetch(`${API_BASE}/market/vnindex?period=${period}`);
                    if (!r.ok) throw new Error(`VNIndex API ${r.status}`);
                    const json = await r.json();
                    const data = json.data || [];
                    _vnindexCache[period] = data;
                    renderVnindex(data);
                } catch (e) {
                    console.error('[vnindex] fetch failed:', e);
                } finally {
                    if (loading) loading.style.display = 'none';
                }
            };

            function renderVnindex(data) {
                const canvas = document.getElementById('vnindexChart');
                if (!canvas) return;
                if (_vnindexChart) _vnindexChart.destroy();

                const labels = data.map(d => d.date);
                const closes = data.map(d => d.close);
                const first = closes[0] || 0;
                const last  = closes[closes.length - 1] || 0;
                const up    = last >= first;
                const color = up ? '#4CAF50' : '#EF5350';

                _vnindexChart = new Chart(canvas.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels,
                        datasets: [{
                            label: 'VN-Index (điểm)',
                            data: closes,
                            borderColor: color,
                            backgroundColor: up ? 'rgba(76,175,80,0.07)' : 'rgba(239,83,80,0.07)',
                            borderWidth: 2,
                            pointRadius: data.length > 60 ? 0 : 3,
                            tension: 0.3,
                            fill: true,
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: { duration: 400 },
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                mode: 'index', intersect: false,
                                callbacks: {
                                    label: ctx => `VN-Index: ${ctx.parsed.y?.toLocaleString('vi-VN')} điểm`
                                }
                            }
                        },
                        scales: {
                            x: { ticks: { color: '#87867f', font: { size: 11 }, maxTicksLimit: 10 }, grid: { display: false } },
                            y: { ticks: { color: '#87867f', font: { size: 11 } }, grid: { display: false },
                                 title: { display: true, text: 'điểm', color: '#87867f', font: { size: 10 } } }
                        }
                    }
                });
            }

            // Period button handler
            document.addEventListener('click', e => {
                const btn = e.target.closest('[data-vnindex-period]');
                if (!btn) return;
                loadVnindexChart(btn.dataset.vnindexPeriod);
            });
        })();

        /* =========================================================
           MARKET PULSE - LOAD & RENDER ARTICLES
        ========================================================= */
        const LABEL_COLORS = {
            VNINDEX: '#4CAF50',
            GOLD: '#c96442',
            REAL_ESTATE: '#FF7043',
            BANKING: '#42A5F5',
            FX: '#AB47BC'
        };

        const PULSE_LABEL_NAMES = {
            VNINDEX:     { vi: 'VN-Index',       en: 'VN-Index' },
            GOLD:        { vi: 'Vàng',           en: 'Gold' },
            REAL_ESTATE: { vi: 'Bất động sản',   en: 'Real Estate' },
            BANKING:     { vi: 'Ngân hàng',      en: 'Banking' },
            FX:          { vi: 'Ngoại hối',      en: 'FX' }
        };

        function formatPulseDate(isoStr) {
            if (!isoStr) return '';
            try {
                const d = new Date(isoStr);
                return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
            } catch { return isoStr; }
        }

        // Relative time ("5 phút trước" / "5m ago") — falls back to absolute date past 7 days
        function formatPulseRelativeTime(isoStr) {
            if (!isoStr) return '';
            const d = new Date(isoStr);
            if (isNaN(d.getTime())) return isoStr;
            const isVi = (localStorage.getItem('lang') || 'vi') === 'vi';
            const minutes = Math.floor((Date.now() - d.getTime()) / 60000);
            if (minutes < 1) return isVi ? 'Vừa xong' : 'Just now';
            if (minutes < 60) return isVi ? `${minutes} phút trước` : `${minutes}m ago`;
            const hours = Math.floor(minutes / 60);
            if (hours < 24) return isVi ? `${hours} giờ trước` : `${hours}h ago`;
            const days = Math.floor(hours / 24);
            if (days < 7) return isVi ? `${days} ngày trước` : `${days}d ago`;
            return formatPulseDate(isoStr);
        }

        function renderMriBadge(mri) {
            if (mri == null) return '';
            const isVi = (localStorage.getItem('lang') || 'vi') === 'vi';
            const cls = mri > 0 ? 'positive' : mri < 0 ? 'negative' : 'neutral';
            const label = mri > 0
                ? (isVi ? 'Tích cực' : 'Positive')
                : mri < 0
                    ? (isVi ? 'Tiêu cực' : 'Negative')
                    : (isVi ? 'Trung lập' : 'Neutral');
            const sign = mri > 0 ? '+' : '';
            const tooltip = isVi
                ? `Chỉ số phản ứng thị trường (MRI): ${sign}${mri}. Mức độ tích cực/tiêu cực mà AI đánh giá tin này tạo ra cho thị trường liên quan.`
                : `Market Reaction Index (MRI): ${sign}${mri}. AI-estimated sentiment intensity of this article for the related market.`;
            return `<span class="pulse-sentiment-badge ${cls}" title="${tooltip}">${label} · MRI ${sign}${mri}</span>`;
        }

        function renderPulseArticle(item, index) {
            const labelColor = LABEL_COLORS[item.label] || '#888';
            const rank = (index != null) ? `<span class="pulse-article-rank">${index + 1}</span>` : '';
            return `
    <article class="article-featured" style="margin-bottom:1.5rem;">
        <div class="article-header" style="padding:1.5rem 2rem 1rem;">
            <div style="display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;margin-bottom:0.75rem;">
                ${rank}
                <span class="article-tag" style="border-color:${labelColor}40;color:${labelColor};background:${labelColor}15;margin-bottom:0;">${item.label || 'NEWS'}</span>
                ${renderMriBadge(item.mri)}
                <span style="margin-left:auto;font-size:0.75rem;color:var(--stone-gray);">${formatPulseRelativeTime(item.generated_at)}</span>
            </div>
            <h2 class="article-title" style="font-size:1.5rem;margin-bottom:0.75rem;">
                <a href="${item.url || '#'}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none;">${item.title || 'Untitled'}</a>
            </h2>
            <div class="article-meta">
                <span class="meta-item">${item.source_name || ''}</span>
                <span class="meta-item">${formatPulseDate(item.generated_at)}</span>
            </div>
        </div>
        <div class="article-body" style="padding:1rem 2rem 1.5rem;">
            <div class="article-text">
                <p style="margin:0;">${item.brief_content || ''}</p>
            </div>
        </div>
    </article>`;
        }

        // Inline SVG sparkline for hero stat cards — values: array of numbers (MRI history)
        function buildPulseSparkline(values, color) {
            if (!values || values.length < 2) return '';
            const w = 100, h = 28;
            const max = Math.max(...values), min = Math.min(...values);
            const range = (max - min) || 1;
            const step = w / (values.length - 1);
            const points = values.map((v, i) => `${(i * step).toFixed(1)},${(h - ((v - min) / range) * h).toFixed(1)}`).join(' ');
            return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${points}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
        }

        // Hero stat cards — aggregate MRI sentiment per market (VN-Index, Gold) from the last 24h
        function renderPulseHero() {
            const isVi = (localStorage.getItem('lang') || 'vi') === 'vi';
            const now = Date.now();
            const dayMs = 24 * 60 * 60 * 1000;

            [{ label: 'VNINDEX', prefix: 'vnindex' }, { label: 'GOLD', prefix: 'gold' }].forEach(({ label, prefix }) => {
                const scoreEl  = document.getElementById(`pulse-stat-${prefix}-score`);
                const detailEl = document.getElementById(`pulse-stat-${prefix}-detail`);
                const sparkEl  = document.getElementById(`pulse-stat-${prefix}-spark`);
                const cardEl   = document.getElementById(`pulse-stat-${prefix}`);
                if (!scoreEl) return;

                const items = pulseDataCache
                    .filter(i => i.label === label && i.mri != null && i.generated_at)
                    .sort((a, b) => new Date(a.generated_at) - new Date(b.generated_at));
                const last24h = items.filter(i => (now - new Date(i.generated_at).getTime()) <= dayMs);

                if (!last24h.length) {
                    scoreEl.textContent = '—';
                    detailEl.textContent = isVi ? 'Chưa có dữ liệu 24h qua' : 'No data in the last 24h';
                    cardEl?.classList.remove('is-positive', 'is-negative');
                    if (sparkEl) sparkEl.innerHTML = '';
                    return;
                }

                const pos = last24h.filter(i => i.mri > 0).length;
                const neg = last24h.filter(i => i.mri < 0).length;
                const avgMri = Math.round(last24h.reduce((sum, i) => sum + i.mri, 0) / last24h.length);
                const positive = avgMri >= 0;

                scoreEl.textContent = `MRI ${avgMri > 0 ? '+' : ''}${avgMri}`;
                detailEl.textContent = isVi
                    ? `${pos} tin tích cực · ${neg} tin tiêu cực (24h)`
                    : `${pos} positive · ${neg} negative (24h)`;
                cardEl?.classList.toggle('is-positive', positive);
                cardEl?.classList.toggle('is-negative', !positive);

                if (sparkEl) {
                    const values = items.slice(-10).map(i => i.mri);
                    sparkEl.innerHTML = buildPulseSparkline(values, positive ? 'var(--coral)' : 'var(--error-red)');
                }
            });
        }

        // Sidebar: 24h overview (sentiment split) + hot topics (article counts per market)
        function renderPulseSidebar() {
            const lang = localStorage.getItem('lang') || 'vi';
            const isVi = lang === 'vi';
            const overviewEl = document.getElementById('pulse-overview-body');
            const topicsEl   = document.getElementById('pulse-hot-topics-list');
            if (!overviewEl && !topicsEl) return;

            const withMri = pulseDataCache.filter(i => i.mri != null);
            const posCount = withMri.filter(i => i.mri > 0).length;
            const negCount = withMri.filter(i => i.mri < 0).length;
            const posPct = withMri.length ? Math.round(posCount / withMri.length * 100) : 0;
            const negPct = withMri.length ? Math.round(negCount / withMri.length * 100) : 0;

            const counts = {};
            pulseDataCache.forEach(i => { counts[i.label] = (counts[i.label] || 0) + 1; });
            const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
            const topLabel = sorted.length ? (PULSE_LABEL_NAMES[sorted[0][0]]?.[lang] || sorted[0][0]) : '—';

            if (overviewEl) {
                overviewEl.innerHTML = `
<div class="pulse-overview-row"><span class="label">${isVi ? 'Tổng số tin' : 'Total articles'}</span><span class="value">${pulseDataCache.length}</span></div>
<div class="pulse-overview-row"><span class="label">${isVi ? 'Tích cực' : 'Positive'}</span><span class="value positive">${posCount} (${posPct}%)</span></div>
<div class="pulse-overview-row"><span class="label">${isVi ? 'Tiêu cực' : 'Negative'}</span><span class="value negative">${negCount} (${negPct}%)</span></div>
<div class="pulse-overview-row"><span class="label">${isVi ? 'Thị trường nổi bật' : 'Most active market'}</span><span class="value">${topLabel}</span></div>`;
            }

            if (topicsEl) {
                if (!sorted.length) {
                    topicsEl.innerHTML = `<p style="font-size:0.8125rem;color:var(--stone-gray);">${isVi ? 'Chưa có dữ liệu.' : 'No data yet.'}</p>`;
                } else {
                    topicsEl.innerHTML = sorted.slice(0, 5).map(([label, count]) => {
                        const name = PULSE_LABEL_NAMES[label]?.[lang] || label;
                        return `<div class="pulse-hot-topic-row"><span class="tag" data-pulse-topic="${label}">#${name}</span><span class="count">${count}</span></div>`;
                    }).join('');

                    topicsEl.querySelectorAll('[data-pulse-topic]').forEach(el => {
                        el.addEventListener('click', () => {
                            const sel = document.getElementById('filter-label');
                            if (sel) { sel.value = el.dataset.pulseTopic; renderFilteredPulse(); }
                        });
                    });
                }
            }
        }

        // ============================================================
        // FUTURE OUTLOOK — Premium gate
        // ============================================================
        function openPremiumReport(event, url) {
            const level = window._vdvUserLevel || 'free';
            if (level === 'premium' || level === 'premium_developer' || level === 'admin') {
                return true; // allow navigation
            }
            event.preventDefault();
            document.getElementById('premium-gate-modal').style.display = 'flex';
            return false;
        }

        document.addEventListener('DOMContentLoaded', () => {
            const modal = document.getElementById('premium-gate-modal');
            if (!modal) return;
            modal.addEventListener('click', e => {
                if (e.target === modal) modal.style.display = 'none';
            });
        });

        // Market Pulse data cache for filtering
        let pulseDataCache = [];
        let pulseGatedPreview = 1; // articles visible before gate (set from API response)

        async function _doPulseFetch(base, lang, token) {
            const container = document.getElementById('market-pulse-articles');
            if (!container) return;
            try {
                const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
                const res = await fetch(`${base}/market-pulse?lang=${lang}&limit=50`, { headers });
                if (!res.ok) {
                    if (!token) container.innerHTML = '<p style="text-align:center;color:var(--text-tertiary);padding:3rem;">Không thể tải dữ liệu.</p>';
                    return;
                }
                const json = await res.json();
                const data = json.data || [];
                if (!data.length) {
                    if (!token) container.innerHTML = '<p style="text-align:center;color:var(--text-tertiary);padding:3rem;">Chưa có bài viết nào.</p>';
                    return;
                }
                pulseDataCache = data;
                pulseGatedPreview = json.free_preview_count ?? null;
                renderPulseHero();
                renderPulseSidebar();
                renderFilteredPulse();
            } catch (e) {
                if (!token) {
                    console.error('Market Pulse fetch failed:', e);
                    const c = document.getElementById('market-pulse-articles');
                    if (c) c.innerHTML = '<p style="text-align:center;color:var(--text-tertiary);padding:3rem;">Không thể tải dữ liệu.</p>';
                }
            }
        }

        async function loadMarketPulse() {
            const base = window.APP_CONFIG.API_BASE_URL;
            if (!base) return;
            const lang = localStorage.getItem('lang') || 'vi';

            // Phase 1: fetch immediately without auth → shows guest preview fast (<1s)
            _doPulseFetch(base, lang, null);

            // Phase 2: once Auth0 resolves, re-fetch with token if logged in → unlocks full data
            getToken().then(token => {
                if (token) _doPulseFetch(base, lang, token);
            }).catch(() => {});
        }

        function _renderPulseGate(hiddenCount) {
            const lang = localStorage.getItem('lang') || 'vi';
            const isVi = lang === 'vi';
            return `
<div style="position:relative;margin:-0.5rem 0 1.5rem;z-index:10;">
  <div style="background:var(--surface-primary,#fff);border:1px solid var(--border-cream,#e8e6dc);
              border-radius:16px;padding:28px 32px;text-align:center;
              box-shadow:0 4px 24px rgba(20,20,19,.07);">
    <div style="width:40px;height:40px;background:rgba(201,100,66,.1);border-radius:50%;
                display:flex;align-items:center;justify-content:center;margin:0 auto 14px;">
      <svg viewBox="0 0 20 20" width="20" height="20" fill="none"
           stroke="var(--gold-primary,#c96442)" stroke-width="1.7"
           stroke-linecap="round" stroke-linejoin="round">
        <rect x="4" y="9" width="12" height="9" rx="2"/>
        <path d="M7 9V6a3 3 0 016 0v3"/>
      </svg>
    </div>
    <div style="font-family:'Lora',Georgia,serif;font-size:17px;font-weight:600;
                color:var(--text-primary,#141413);margin-bottom:6px;">
      ${isVi ? 'Đăng nhập để đọc tiếp' : 'Sign in to read more'}
    </div>
    <div style="font-size:13px;color:var(--text-secondary,#87867f);margin-bottom:20px;line-height:1.6;">
      ${isVi
        ? `Còn <strong style="color:var(--text-primary,#141413)">${hiddenCount} tờ báo</strong> mới nhất được phân tích bởi AI — đăng nhập miễn phí để xem đầy đủ.`
        : `<strong style="color:var(--text-primary,#141413)">${hiddenCount} more AI-analyzed articles</strong> — sign in for free to read them all.`}
    </div>
    <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
      <button onclick="login()"
              style="background:var(--gold-primary,#c96442);color:#fff;border:none;
                     border-radius:8px;padding:10px 24px;font-size:14px;font-weight:600;
                     cursor:pointer;font-family:inherit;transition:opacity .2s;"
              onmouseover="this.style.opacity='.88'" onmouseout="this.style.opacity='1'">
        ${isVi ? 'Đăng nhập miễn phí' : 'Sign in for free'}
      </button>
      <a href="/fe/pages/pricing.html"
         style="background:none;border:1px solid var(--border-cream,#e8e6dc);color:var(--text-secondary,#87867f);
                border-radius:8px;padding:10px 20px;font-size:13px;font-weight:500;
                cursor:pointer;font-family:inherit;text-decoration:none;display:inline-flex;align-items:center;">
        ${isVi ? 'Xem gói cao cấp' : 'View Pro plan'}
      </a>
    </div>
  </div>
</div>`;
        }

        function renderFilteredPulse() {
            const container = document.getElementById('market-pulse-articles');
            if (!container) return;

            const sourceFilter = document.getElementById('filter-source')?.value || '';
            const labelFilter  = document.getElementById('filter-label')?.value  || '';
            const mriFilter    = document.getElementById('filter-mri')?.value    || '';
            const timeFilter   = document.getElementById('filter-time')?.value   || '';

            let filtered = pulseDataCache;
            if (sourceFilter) filtered = filtered.filter(i => i.source_name?.includes(sourceFilter));
            if (labelFilter)  filtered = filtered.filter(i => i.label === labelFilter);
            if (mriFilter === 'positive') filtered = filtered.filter(i => i.mri > 0);
            else if (mriFilter === 'negative') filtered = filtered.filter(i => i.mri < 0);
            const timeRangeMs = { '1h': 3600000, '24h': 86400000, '7d': 604800000 }[timeFilter];
            if (timeRangeMs) {
                const now = Date.now();
                filtered = filtered.filter(i => i.generated_at && (now - new Date(i.generated_at).getTime()) <= timeRangeMs);
            }

            if (filtered.length === 0) {
                container.innerHTML = '<p style="text-align:center;color:var(--text-tertiary);padding:3rem;">Không có kết quả phù hợp.</p>';
                return;
            }

            // Wider time ranges allow more articles through (24h/7d views are meant to show
            // everything in that window, not just the latest 10).
            const displayMax = timeFilter === '7d' ? 50 : timeFilter === '24h' ? 20 : 10;
            const items = filtered.slice(0, displayMax);

            // No gate → render all normally
            if (pulseGatedPreview === null || pulseGatedPreview >= items.length) {
                container.innerHTML = items.map((item, i) => renderPulseArticle(item, i)).join('');
                return;
            }

            // Gate: first N articles clearly, then gate card, then blurred teasers
            const clearItems  = items.slice(0, pulseGatedPreview);
            const gatedItems  = items.slice(pulseGatedPreview);
            const hiddenCount = gatedItems.length;

            const clearHtml  = clearItems.map((item, i) => renderPulseArticle(item, i)).join('');
            const gateHtml   = _renderPulseGate(hiddenCount);
            const gatedHtml  = `
<div style="position:relative;pointer-events:none;user-select:none;">
  <div style="filter:blur(4px);opacity:.55;">
    ${gatedItems.map((item, i) => renderPulseArticle(item, clearItems.length + i)).join('')}
  </div>
  <div style="position:absolute;inset:0;background:linear-gradient(to bottom,transparent 0%,var(--bg-primary,#f5f4ed) 85%);"></div>
</div>`;

            container.innerHTML = clearHtml + gateHtml + gatedHtml;
        }

        // Initialize Market Pulse with filter listeners
        document.addEventListener('DOMContentLoaded', () => {
            loadMarketPulse();
            ['filter-source', 'filter-label', 'filter-mri', 'filter-time'].forEach(id => {
                document.getElementById(id)?.addEventListener('change', renderFilteredPulse);
            });
            document.getElementById('filter-reset')?.addEventListener('click', () => {
                document.getElementById('filter-source').value = '';
                document.getElementById('filter-label').value = '';
                document.getElementById('filter-mri').value = '';
                document.getElementById('filter-time').value = '';
                renderFilteredPulse();
            });
        });

        // ============================================================
        // SAVE INTEREST - Per-item bookmark buttons for tracking
        // ============================================================
        const SAVED_INTERESTS_KEY = 'vietdataverse_saved_interests';

        function getFingerprint() {
            // Simple browser fingerprint for anonymous tracking
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            ctx.textBaseline = 'top';
            ctx.font = '14px Arial';
            ctx.fillText('fingerprint', 2, 2);
            const fp = canvas.toDataURL().slice(-50);
            const nav = navigator.userAgent + navigator.language + screen.width + screen.height;
            return btoa(fp + nav).slice(0, 32);
        }

        function getSavedInterests() {
            try {
                return JSON.parse(localStorage.getItem(SAVED_INTERESTS_KEY) || '{}');
            } catch {
                return {};
            }
        }

        function setSavedInterest(interestType) {
            const saved = getSavedInterests();
            saved[interestType] = Date.now();
            localStorage.setItem(SAVED_INTERESTS_KEY, JSON.stringify(saved));
        }

        function isInterestSaved(interestType) {
            const saved = getSavedInterests();
            return !!saved[interestType];
        }

        async function saveInterest(btn, interestType) {
            if (!btn || !interestType) return;

            // Build auth headers if user is logged in
            let authHeaders = {};
            let userEmail = null;
            try {
                const token = await getToken();
                if (token) {
                    authHeaders['Authorization'] = 'Bearer ' + token;
                    const user = await getUser();
                    if (user) userEmail = user.email || null;
                }
            } catch (e) { /* anonymous fallback */ }

            // Check if already saved — toggle off (unsave)
            if (isInterestSaved(interestType)) {
                const saved = getSavedInterests();
                delete saved[interestType];
                localStorage.setItem(SAVED_INTERESTS_KEY, JSON.stringify(saved));
                btn.classList.remove('saved');
                btn.title = 'Lưu quan tâm';

                // GA4: track unsave event
                if (typeof gtag === 'function') {
                    gtag('event', 'unsave_interest', {
                        interest_type: interestType,
                        user_email: userEmail || 'anonymous'
                    });
                }

                // Notify backend to remove interest
                try {
                    await fetch(`${API_BASE}/api/v1/interest/${interestType}`, {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json', ...authHeaders },
                        body: JSON.stringify({ fingerprint: getFingerprint() })
                    });
                } catch (err) {
                    console.error('Delete interest error:', err);
                }
                return;
            }

            // Save interest
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

            try {
                const fingerprint = getFingerprint();
                await fetch(`${API_BASE}/api/v1/interest/${interestType}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', ...authHeaders },
                    body: JSON.stringify({
                        fingerprint: fingerprint,
                        email: userEmail,
                        source: 'web',
                        user_agent: navigator.userAgent,
                        language: navigator.language
                    })
                });
            } catch (err) {
                console.error('Save interest error:', err);
            }

            // GA4: track save event
            if (typeof gtag === 'function') {
                gtag('event', 'save_interest', {
                    interest_type: interestType,
                    user_email: userEmail || 'anonymous'
                });
            }

            // Always mark as saved locally (even if API fails)
            setSavedInterest(interestType);
            btn.innerHTML = '<i class="fas fa-bookmark"></i>';
            btn.classList.add('saved');
            btn.title = 'Đã lưu - Click để bỏ lưu';
            btn.disabled = false;
        }

        // Initialize all save interest buttons
        document.addEventListener('DOMContentLoaded', () => {
            document.querySelectorAll('.save-interest-btn').forEach(btn => {
                const interestType = btn.getAttribute('data-interest');
                if (!interestType) return;

                // Restore saved state
                if (isInterestSaved(interestType)) {
                    btn.classList.add('saved');
                    btn.title = 'Đã lưu - Click để bỏ lưu';
                }

                // Add click handler
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    saveInterest(btn, interestType);
                });
            });
        });

        (function () {
            const tip = document.getElementById('chart-tooltip-popup');
            let hideTimer;

            document.addEventListener('mouseover', function (e) {
                const icon = e.target.closest('.chart-info-icon');
                if (!icon) return;
                clearTimeout(hideTimer);
                const text = icon.getAttribute('data-tooltip');
                if (!text) return;
                tip.textContent = text;
                tip.classList.add('visible');
                positionTip(icon);
            });

            document.addEventListener('mouseout', function (e) {
                if (!e.target.closest('.chart-info-icon')) return;
                hideTimer = setTimeout(() => tip.classList.remove('visible'), 80);
            });

            function positionTip(icon) {
                const rect = icon.getBoundingClientRect();
                const tipW = 240;
                const gap = 10;

                // Measure real height before showing
                tip.style.width = tipW + 'px';
                const tipH = tip.offsetHeight || 60;

                // Center above the icon
                let left = rect.left + rect.width / 2 - tipW / 2;
                let top = rect.top - tipH - gap;

                // Clamp horizontally within viewport
                const vw = window.innerWidth;
                if (left < 8) left = 8;
                if (left + tipW > vw - 8) left = vw - tipW - 8;

                // Arrow offset relative to tooltip left edge
                const arrowLeft = (rect.left + rect.width / 2) - left;
                tip.style.setProperty('--arrow-left', arrowLeft + 'px');
                tip.style.left = left + 'px';
                tip.style.top = top + 'px';
            }
        })();

        /* =========================================================
           MACRO CHARTS (GSO/NSO internal API + World Bank Open Data)
           CPI source: vn_gso_cpi_monthly (nso.gov.vn) via /api/v1/macro/cpi
           GDP/Trade source: World Bank Open Data
        ========================================================= */
        (function () {
            const WB_BASE = 'https://api.worldbank.org/v2/country/VN/indicator';
            const GOLD = '#c96442';
            const RED  = '#EF5350';
            const BLUE = '#42A5F5';
            const TEAL = '#26A69A';
            const GRID = 'rgba(20, 20, 19, 0.07)';
            const FONT = { color: '#87867f', size: 11 };

            let _macroPeriod = 20; // default 20 years
            let _cpiChart = null, _gdpChart = null, _tradeChart = null;

            // ── Fetch one World Bank indicator
            async function wbFetch(indicator, years = 40) {
                const url = `${WB_BASE}/${indicator}?format=json&per_page=${years}&mrv=${years}`;
                const r = await fetch(url);
                if (!r.ok) throw new Error(`WB ${indicator} ${r.status}`);
                const json = await r.json();
                return (json[1] || [])
                    .filter(d => d.value != null)
                    .sort((a, b) => a.date.localeCompare(b.date));
            }

            // ── Slice to last N years (0 = all)
            function sliceYears(data, n) {
                return n > 0 ? data.slice(-n) : data;
            }

            // ── Common chart defaults
            function baseConfig(type, labels, datasets) {
                return {
                    type,
                    data: { labels, datasets },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: { duration: 500 },
                        plugins: {
                            legend: { labels: { color: '#87867f', font: { size: 11 }, boxWidth: 12 } },
                            tooltip: { mode: 'index', intersect: false }
                        },
                        scales: {
                            x: { ticks: FONT, grid: { display: false } },
                            y: { ticks: FONT, grid: { display: false } }
                        }
                    }
                };
            }

            // ── Fetch CPI from internal GSO API
            async function cpiFetch(view, years) {
                // Ưu tiên file tĩnh (không tốn quota, hoạt động cho khách vãng lai).
                try {
                    const file = view === 'monthly' ? 'cpi_monthly.json' : 'cpi_annual.json';
                    const sr = await fetch(`./data/${file}`);
                    if (sr.ok) {
                        const sj = await sr.json();
                        const arr = sj.data || [];
                        if (arr.length) {
                            return view === 'monthly' ? arr.slice(-12) : arr.slice(-years);
                        }
                    }
                } catch (_) { /* rơi xuống live API */ }

                // Fallback live API (endpoint /api/v1/macro — kèm token nếu đã đăng nhập).
                const base = (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || '/api/v1';
                const r = await fetch(`${base}/macro/cpi?view=${view}&years=${years}`,
                                     { headers: await _authHeaders() });
                if (!r.ok) throw new Error(`CPI API ${r.status}`);
                const json = await r.json();
                return json.data || [];
            }

            // ── CPI chart — bar (annual) or line (monthly)
            function renderCpi(data, years) {
                const canvas = document.getElementById('macroCpiChart');
                if (!canvas) return;
                if (_cpiChart) _cpiChart.destroy();

                const isMonthly = years === 1;
                const labels = data.map(d => d.period);
                const values = data.map(d => +(d.yoy_pct).toFixed(2));
                const colors = values.map(v =>
                    v >= 10 ? '#EF5350' : v >= 5 ? '#FFA726' : v >= 0 ? '#66BB6A' : '#42A5F5'
                );

                let cfg;
                if (isMonthly) {
                    cfg = baseConfig('line', labels, [{
                        label: 'CPI YoY %/tháng (nguồn: GSO)',
                        data: values,
                        borderColor: '#FFA726',
                        backgroundColor: 'rgba(255,167,38,0.1)',
                        borderWidth: 2,
                        pointRadius: 3,
                        tension: 0.3,
                        fill: true,
                    }]);
                } else {
                    cfg = baseConfig('line', labels, [{
                        label: 'CPI trung bình %/năm (nguồn: GSO)',
                        data: values,
                        borderColor: '#FFA726',
                        backgroundColor: 'rgba(255,167,38,0.08)',
                        borderWidth: 2,
                        pointRadius: 4,
                        pointBackgroundColor: colors,
                        pointBorderColor: colors,
                        tension: 0.3,
                        fill: true,
                    }]);
                }
                cfg.options.scales.y.title = { display: true, text: '%', color: '#87867f', font: { size: 10 } };
                _cpiChart = new Chart(canvas.getContext('2d'), cfg);
            }

            // ── GDP bar chart
            function renderGdp(raw, years) {
                const data = sliceYears(raw, years);
                const labels = data.map(d => d.date);
                const values = data.map(d => +d.value.toFixed(2));

                const canvas = document.getElementById('macroGdpChart');
                if (!canvas) return;
                if (_gdpChart) _gdpChart.destroy();
                const cfg = baseConfig('line', labels, [{
                    label: 'GDP tăng trưởng %/năm',
                    data: values,
                    borderColor: TEAL,
                    backgroundColor: 'rgba(38, 166, 154, 0.08)',
                    borderWidth: 2,
                    pointRadius: 4,
                    pointBackgroundColor: values.map(v => v >= 0 ? TEAL : RED),
                    pointBorderColor: values.map(v => v >= 0 ? TEAL : RED),
                    tension: 0.3,
                    fill: true,
                }]);
                cfg.options.scales.y.title = { display: true, text: '%', color: '#87867f', font: { size: 10 } };
                _gdpChart = new Chart(canvas.getContext('2d'), cfg);
            }

            // ── Trade line chart (exports + imports in billion USD)
            function renderTrade(expRaw, impRaw, years) {
                const expData = sliceYears(expRaw, years);
                const impData = sliceYears(impRaw, years);
                // Align by year
                const years_set = new Set([...expData.map(d => d.date), ...impData.map(d => d.date)]);
                const labels = [...years_set].sort();
                const expMap = Object.fromEntries(expData.map(d => [d.date, d.value / 1e9]));
                const impMap = Object.fromEntries(impData.map(d => [d.date, d.value / 1e9]));
                const exports_ = labels.map(y => expMap[y] != null ? +expMap[y].toFixed(1) : null);
                const imports_ = labels.map(y => impMap[y] != null ? +impMap[y].toFixed(1) : null);
                const balance = labels.map((y, i) =>
                    expMap[y] != null && impMap[y] != null
                        ? +((expMap[y] - impMap[y]) / 1e9).toFixed(1) : null
                );

                const canvas = document.getElementById('macroTradeChart');
                if (!canvas) return;
                if (_tradeChart) _tradeChart.destroy();
                const cfg = baseConfig('line', labels, [
                    { label: 'Xuất khẩu (tỷ USD)', data: exports_, borderColor: GOLD, backgroundColor: 'transparent', tension: 0.3, pointRadius: 3 },
                    { label: 'Nhập khẩu (tỷ USD)', data: imports_, borderColor: BLUE, backgroundColor: 'transparent', tension: 0.3, pointRadius: 3 },
                    { label: 'Cán cân TM (tỷ USD)', data: balance, borderColor: TEAL, backgroundColor: 'transparent', tension: 0.3, borderDash: [4,3], pointRadius: 2 }
                ]);
                cfg.options.scales.y.title = { display: true, text: 'tỷ USD', color: '#87867f', font: { size: 10 } };
                _tradeChart = new Chart(canvas.getContext('2d'), cfg);
            }

            // ── Cached raw data
            // CPI: cached per view type (annual vs monthly)
            let _rawCpiAnnual = null, _rawCpiMonthly = null;
            let _rawGdp = null, _rawExp = null, _rawImp = null;

            // ── Main load function
            window.loadMacroCharts = async function (years = 20) {
                _macroPeriod = years;
                const isMonthly = years === 1;
                const cpiView = isMonthly ? 'monthly' : 'annual';
                const cpiYears = years === 0 ? 30 : years;  // 0 = "Tất cả" → fetch 30 years

                // CPI: always fetch fresh when view changes (monthly vs annual)
                const cpiCache = isMonthly ? _rawCpiMonthly : _rawCpiAnnual;

                // GDP/Trade: cache across period switches (WB data is annual, sliced client-side)
                if (cpiCache && _rawGdp && _rawExp && _rawImp) {
                    renderCpi(cpiCache, years);
                    renderGdp(_rawGdp, years);
                    renderTrade(_rawExp, _rawImp, years);
                    return;
                }

                // Show skeletons
                ['macroCpiLoading', 'macroGdpLoading', 'macroTradeLoading'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.style.display = 'flex';
                });

                try {
                    const cpiData = await cpiFetch(cpiView, cpiYears);
                    if (isMonthly) _rawCpiMonthly = cpiData;
                    else           _rawCpiAnnual  = cpiData;

                    if (!_rawGdp) {
                        [_rawGdp, _rawExp, _rawImp] = await Promise.all([
                            wbFetch('NY.GDP.MKTP.KD.ZG', 40),
                            wbFetch('NE.EXP.GNFS.CD', 40),
                            wbFetch('NE.IMP.GNFS.CD', 40)
                        ]);
                    }

                    renderCpi(cpiData, years);
                    renderGdp(_rawGdp, years);
                    renderTrade(_rawExp, _rawImp, years);
                } catch (e) {
                    console.error('[macro] fetch failed:', e);
                } finally {
                    ['macroCpiLoading', 'macroGdpLoading', 'macroTradeLoading'].forEach(id => {
                        const el = document.getElementById(id);
                        if (el) el.style.display = 'none';
                    });
                }
            };

            // ── Download macro data as CSV
            window.downloadMacroCSV = function (type) {
                const configs = {
                    cpi:   { header: 'Year,CPI Inflation (%/year)',    file: 'vietdataverse_vn_cpi_annual' },
                    gdp:   { header: 'Year,GDP Growth (%/year)',        file: 'vietdataverse_vn_gdp_growth' },
                    trade: { header: 'Year,Exports (billion USD),Imports (billion USD),Trade Balance (billion USD)', file: 'vietdataverse_vn_trade' }
                };
                const cfg = configs[type];
                if (!cfg) return;

                // Historical cutoff: only periods ending ≥ 2 months before today.
                const _cutoffDate = new Date();
                _cutoffDate.setMonth(_cutoffDate.getMonth() - 2);
                const _cutoff = _cutoffDate.toISOString().slice(0, 10);
                const _cutoffMonth = _cutoff.slice(0, 7);
                const _currentYear = new Date().getFullYear();
                const _passes = p => {
                    const s = String(p);
                    if (/^\d{4}$/.test(s)) return parseInt(s, 10) < _currentYear;
                    if (/^\d{4}-\d{2}$/.test(s)) return s < _cutoffMonth;
                    return s.slice(0, 10) <= _cutoff;
                };

                let csv;
                if (type === 'cpi') {
                    const cpiRaw = _rawCpiAnnual || _rawCpiMonthly;
                    if (!cpiRaw) { alert('Vui lòng mở tab Vĩ Mô để tải dữ liệu trước.'); return; }
                    csv = cfg.header + '\n' + cpiRaw.filter(d => _passes(d.period)).map(d => `${d.period},${(+d.yoy_pct).toFixed(2)}`).join('\n');
                } else if (type === 'gdp') {
                    if (!_rawGdp) { alert('Vui lòng mở tab Vĩ Mô để tải dữ liệu trước.'); return; }
                    csv = cfg.header + '\n' + _rawGdp.filter(d => _passes(d.date)).map(d => `${d.date},${d.value.toFixed(2)}`).join('\n');
                } else if (type === 'trade') {
                    if (!_rawExp || !_rawImp) { alert('Vui lòng mở tab Vĩ Mô để tải dữ liệu trước.'); return; }
                    const expMap = Object.fromEntries(_rawExp.map(d => [d.date, d.value / 1e9]));
                    const impMap = Object.fromEntries(_rawImp.map(d => [d.date, d.value / 1e9]));
                    const years = [...new Set([..._rawExp.map(d => d.date), ..._rawImp.map(d => d.date)])].filter(_passes).sort();
                    csv = cfg.header + '\n' + years.map(y => {
                        const exp = expMap[y] != null ? expMap[y].toFixed(1) : '';
                        const imp = impMap[y] != null ? impMap[y].toFixed(1) : '';
                        const bal = expMap[y] != null && impMap[y] != null ? (expMap[y] - impMap[y]).toFixed(1) : '';
                        return `${y},${exp},${imp},${bal}`;
                    }).join('\n');
                }

                const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = cfg.file + '.csv';
                a.click();
            };

            // ── Period filter buttons in macro tab
            document.addEventListener('click', e => {
                const btn = e.target.closest('[data-macro-period]');
                if (!btn) return;
                const years = +btn.dataset.macroPeriod;
                btn.closest('.chart-filters')
                    ?.querySelectorAll('[data-macro-period]')
                    .forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                loadMacroCharts(years);
            });

            // ── Knowledge Market — delegated to app.knowledge.js (window.KM) ──
            // Sprint-0 km* functions removed. KM namespace registers its own
            // tab-click listener inside app.knowledge.js IIFE.
            // Expose shim so auth.js checkAdminOverride callback still works.
            window.kmCheckAdmin = function () {
                if (window.KM && typeof window.KM._updateActionBarAsync === 'function') {
                    window.KM._updateActionBarAsync();
                }
            };

            // ── Topbar dropdowns (Docs + Settings) ──
            (function () {
                function toggleDropdown(btnId, ddId) {
                    const btn = document.getElementById(btnId);
                    const dd = document.getElementById(ddId);
                    if (!btn || !dd) return;
                    btn.addEventListener('click', function (e) {
                        e.stopPropagation();
                        const isOpen = dd.classList.contains('open');
                        document.querySelectorAll('.topbar-dropdown.open').forEach(el => el.classList.remove('open'));
                        if (!isOpen) dd.classList.add('open');
                    });
                }
                toggleDropdown('settings-topbar-btn', 'settings-dropdown');

                // Close on outside click
                document.addEventListener('click', function () {
                    document.querySelectorAll('.topbar-dropdown.open').forEach(el => el.classList.remove('open'));
                });

                // Update Settings dropdown: My Store vs + Become a Seller
                async function updateSettingsSellerLink() {
                    const token = localStorage.getItem('auth_token');
                    const sellerLink = document.getElementById('settings-dd-seller');
                    if (!sellerLink) return;
                    if (!token) {
                        sellerLink.textContent = '+ Become a Seller';
                        sellerLink.href = '/fe/#km/become-seller';
                        return;
                    }
                    try {
                        const base = window.APP_CONFIG?.API_BASE_URL || '/api/v1';
                        const res = await fetch(`${base}/seller/profile`, {
                            headers: { Authorization: `Bearer ${token}` }
                        });
                        if (res.ok) {
                            const data = await res.json();
                            if (data.success && data.seller) {
                                sellerLink.textContent = 'My Store';
                                sellerLink.href = '/fe/#km/seller-dashboard';
                            } else {
                                sellerLink.textContent = '+ Become a Seller';
                                sellerLink.href = '/fe/#km/become-seller';
                            }
                        } else {
                            sellerLink.textContent = '+ Become a Seller';
                            sellerLink.href = '/fe/#km/become-seller';
                        }
                    } catch (_) {
                        sellerLink.textContent = '+ Become a Seller';
                        sellerLink.href = '/fe/#km/become-seller';
                    }
                }
                document.addEventListener('DOMContentLoaded', updateSettingsSellerLink);
            })();
        })();
