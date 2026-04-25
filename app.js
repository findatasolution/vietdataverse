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
                nav1sFutureOutlook: '1s Dự đoán thị trường',
                nav1sfuturesub: 'Dự báo & phân tích tài sản',
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
                navVN30Score: 'VN30 Score',
                navVN30ScoreSub: 'Xác suất tăng giá cổ phiếu',
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
                nav1sFutureOutlook: '1s Future Outlook',
                nav1sfuturesub: 'Asset forecasts & analysis',
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
                navVN30Score: 'VN30 Score',
                navVN30ScoreSub: 'Stock gain probability',
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
            document.querySelector('.brand-subtitle').textContent = t.subtitle;

            // Update navigation
            const navLinks = document.querySelectorAll('.nav-link');
            navLinks.forEach(link => {
                if (link.getAttribute('data-tab') === 'data-portal') {
                    link.querySelector('h4').textContent = t.navDataPortal;
                } else if (link.getAttribute('data-tab') === '1smarket-portal') {
                    link.querySelector('h4').textContent = t.nav1sMarketPortal;
                    const meta = link.querySelector('.nav-meta');
                    if (meta) meta.textContent = t.nav1smarketsub;
                } else if (link.getAttribute('data-tab') === '1s-future-outlook') {
                    link.querySelector('h4').textContent = t.nav1sFutureOutlook;
                    const meta = link.querySelector('.nav-meta');
                    if (meta) meta.textContent = t.nav1sFutureOutlook;
                } else if (link.getAttribute('data-tab') === 'vn30-score') {
                    const h4 = link.querySelector('h4');
                    const badge = h4 ? h4.querySelector('.beta-badge') : null;
                    if (h4) {
                        h4.childNodes[0].textContent = t.navVN30Score + ' ';
                        if (!badge) { const b = document.createElement('span'); b.className = 'beta-badge'; b.textContent = 'NEW'; h4.appendChild(b); }
                    }
                    const meta = link.querySelector('.nav-meta');
                    if (meta) meta.textContent = t.navVN30ScoreSub;
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
                    ? '/api/v1'
                    : 'https://api.vietdataverse.online/api/v1';

            // Prefetch gold & silver data immediately (before DOMContentLoaded)
            // These promises are consumed by loadChartData() when it runs later
            const base = window.APP_CONFIG.API_BASE_URL;
            window._prefetchPromises = {};
            window._prefetchPromises['gold-1m-DOJI HN'] = fetch(`${base}/gold?period=1m&type=${encodeURIComponent('DOJI HN')}`)
                .then(r => r.ok ? r.json() : Promise.reject(r.status))
                .catch(e => { console.warn('[prefetch] gold failed:', e); return null; });
            window._prefetchPromises['silver-1m'] = fetch(`${base}/silver?period=1m`)
                .then(r => r.ok ? r.json() : Promise.reject(r.status))
                .catch(e => { console.warn('[prefetch] silver failed:', e); return null; });
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
            initChartTabs();
            initFilterButtons();
            initNotifications();

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
            const langBtn = document.getElementById('lang-toggle');
            const sidebarLangBtn = document.getElementById('sidebar-lang-toggle');

            /* ---------- LANGUAGE (ENG / VIE) ---------- */
            const savedLang = localStorage.getItem('lang') || 'vi';
            updateLanguage(savedLang);

            if (langBtn) {
                langBtn.addEventListener('click', () => {
                    const current = document.documentElement.lang || 'vi';
                    const next = current === 'vi' ? 'en' : 'vi';
                    updateLanguage(next);
                });
            }
            if (sidebarLangBtn) {
                sidebarLangBtn.addEventListener('click', () => {
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

            // Update header lang button
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
            '1s-future-outlook': '1s Future Outlook',
            'vn30-score': 'VN30 Score',
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

            // If switching to data-portal, restore the inner chart tab
            if (tabId === 'data-portal') {
                const activeChartTab = document.querySelector('.chart-tab-btn.active');
                if (activeChartTab) {
                    const innerTabId = activeChartTab.dataset.tab;
                    const innerTarget = document.getElementById(innerTabId);
                    if (innerTarget) innerTarget.classList.add('active');
                }
            }

            // Lazy-load VN30 Score on first visit
            if (tabId === 'vn30-score' && !window._vn30Loaded) {
                window._vn30Loaded = true;
                loadVN30Scores();
            }

            // Close mobile sidebar
            const sidebar = document.querySelector('.sidebar');
            const mobileOverlay = document.getElementById('mobile-overlay');
            if (sidebar) sidebar.classList.remove('active');
            if (mobileOverlay) mobileOverlay.classList.remove('active');
        }

        function initSidebarTabs() {
            // Nav-link tab clicks
            document.querySelectorAll('.nav-link[data-tab]').forEach(link => {
                link.addEventListener('click', () => activateTab(link.dataset.tab));
            });

            // Sidebar bottom links (About & Terms, Privacy Policy, Contact)
            document.querySelectorAll('.sidebar-bottom-link[data-tab]').forEach(link => {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    activateTab(link.dataset.tab);
                });
            });

            // Handle URL hash on page load (e.g. index.html#about-terms)
            const hash = window.location.hash.replace('#', '');
            if (hash && document.getElementById(hash)) {
                activateTab(hash);
            }
        }

        /* =========================================================
           CHART SUB-TABS (Vang & Bac / Tien te VN / Quoc te)
           WITH LAZY LOADING
        ========================================================= */
        function initChartTabs() {
            document.querySelectorAll('.chart-tab-btn[data-tab]').forEach(btn => {
                btn.addEventListener('click', () => {
                    const tabId = btn.dataset.tab;

                    // Toggle button active states
                    document.querySelectorAll('.chart-tab-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');

                    // Toggle inner tab-contents within charts-section
                    const chartsSection = btn.closest('.charts-section');
                    if (chartsSection) {
                        chartsSection.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                    }
                    const target = document.getElementById(tabId);
                    if (target) target.classList.add('active');

                    // Lazy load charts when tab is clicked for the first time
                    loadChartsForTab(tabId);
                });
            });

            // Load the first tab (gold & silver) immediately on page load
            loadChartsForTab('tab-gold-silver');
        }

        /* =========================================================
           LAZY LOAD CHARTS FOR A SPECIFIC TAB
        ========================================================= */
        function loadChartsForTab(tabId) {
            // Skip if already loaded
            if (loadedTabs[tabId]) {
                return;
            }

            loadedTabs[tabId] = true;

            // Load charts in parallel for each tab
            if (tabId === 'tab-gold-silver') {
                const goldType = document.getElementById('goldTypeSelect')?.value || 'DOJI HN';
                Promise.all([
                    loadChartData('gold', '1m', goldType),
                    loadChartData('silver', '1m')
                ]);
            } else if (tabId === 'tab-currency') {
                const bankCode = document.getElementById('bankTypeSelect')?.value || 'ACB';
                Promise.all([
                    loadChartData('td', '1y', null, bankCode),
                    loadChartData('sbv', '1m'),
                    loadChartData('fxrate', '1m')
                ]);
            } else if (tabId === 'tab-global') {
                loadChartData('global', '1m');
            } else if (tabId === 'tab-macro') {
                loadMacroCharts(20);
            }
            // tab-download: no charts to load, content is static
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

                // Fetch data from API
                const response = await fetch(`${base}/${endpoint}`);
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

        async function downloadDataset(datasetId) {
            const base = window.APP_CONFIG.API_BASE_URL;
            const btn = event.currentTarget;
            const origHtml = btn.innerHTML;
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

                const res = await fetch(url);
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
        const loadedTabs = {
            'tab-gold-silver': false,
            'tab-currency': false,
            'tab-global': false,
            'tab-macro': false,
            'tab-download': false
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
                    const res = await fetchWithTimeout(apiUrl, {}, 20000);
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
           MARKET PULSE - LOAD & RENDER ARTICLES
        ========================================================= */
        const LABEL_COLORS = {
            VNINDEX: '#4CAF50',
            GOLD: '#c96442',
            REAL_ESTATE: '#FF7043',
            BANKING: '#42A5F5',
            FX: '#AB47BC'
        };

        const LABEL_NAMES_VI = {
            VNINDEX: 'VN-Index',
            GOLD: 'Vang',
            REAL_ESTATE: 'BDS',
            BANKING: 'Ngan hang',
            FX: 'Ngoai hoi'
        };

        function formatPulseDate(isoStr) {
            if (!isoStr) return '';
            try {
                const d = new Date(isoStr);
                return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
            } catch { return isoStr; }
        }

        function renderMriBadge(mri) {
            if (mri == null) return '';
            const color = mri > 0 ? '#4CAF50' : mri < 0 ? '#EF5350' : '#888';
            const arrow = mri > 0 ? '&#9650;' : mri < 0 ? '&#9660;' : '&#9654;';
            return `<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:4px;font-size:0.8rem;font-weight:600;color:${color};background:${color}1a;">${arrow} MRI ${mri > 0 ? '+' : ''}${mri}</span>`;
        }

        function renderPulseArticle(item) {
            const labelColor = LABEL_COLORS[item.label] || '#888';
            return `
    <article class="article-featured" style="margin-bottom:1.5rem;">
        <div class="article-header" style="padding:1.5rem 2rem 1rem;">
            <div style="display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;margin-bottom:0.75rem;">
                <span class="article-tag" style="border-color:${labelColor}40;color:${labelColor};background:${labelColor}15;margin-bottom:0;">${item.label || 'NEWS'}</span>
                ${renderMriBadge(item.mri)}
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

        async function loadMarketPulse() {
            const base = window.APP_CONFIG.API_BASE_URL;
            const container = document.getElementById('market-pulse-articles');
            if (!container) return;

            const lang = localStorage.getItem('lang') || 'vi';
            let data = null;

            try {
                if (base) {
                    const token = await getToken().catch(() => null);
                    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
                    const res = await fetch(`${base}/market-pulse?lang=${lang}&limit=20`, { headers });
                    if (res.ok) {
                        const json = await res.json();
                        data = json.data || [];
                        pulseGatedPreview = json.free_preview_count ?? null; // null = no gate
                    }
                }

                if (!data || data.length === 0) {
                    container.innerHTML = '<p style="text-align:center;color:var(--text-tertiary);padding:3rem;">Chưa có bài viết nào.</p>';
                    return;
                }

                pulseDataCache = data;
                renderFilteredPulse();
            } catch (e) {
                console.error('Market Pulse fetch failed:', e);
                container.innerHTML = '<p style="text-align:center;color:var(--text-tertiary);padding:3rem;">Không thể tải dữ liệu.</p>';
            }
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
        ? `Còn <strong style="color:var(--text-primary,#141413)">${hiddenCount} bài phân tích</strong> mới nhất được phân tích bởi AI — đăng nhập miễn phí để xem đầy đủ.`
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
      <a href="/pages/pricing.html"
         style="background:none;border:1px solid var(--border-cream,#e8e6dc);color:var(--text-secondary,#87867f);
                border-radius:8px;padding:10px 20px;font-size:13px;font-weight:500;
                cursor:pointer;font-family:inherit;text-decoration:none;display:inline-flex;align-items:center;">
        ${isVi ? 'Xem gói Pro' : 'View Pro plan'}
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

            let filtered = pulseDataCache;
            if (sourceFilter) filtered = filtered.filter(i => i.source_name?.includes(sourceFilter));
            if (labelFilter)  filtered = filtered.filter(i => i.label === labelFilter);
            if (mriFilter === 'positive') filtered = filtered.filter(i => i.mri > 0);
            else if (mriFilter === 'negative') filtered = filtered.filter(i => i.mri < 0);

            if (filtered.length === 0) {
                container.innerHTML = '<p style="text-align:center;color:var(--text-tertiary);padding:3rem;">Không có kết quả phù hợp.</p>';
                return;
            }

            const displayMax = 10;
            const items = filtered.slice(0, displayMax);

            // No gate → render all normally
            if (pulseGatedPreview === null || pulseGatedPreview >= items.length) {
                container.innerHTML = items.map(renderPulseArticle).join('');
                return;
            }

            // Gate: first N articles clearly, then gate card, then blurred teasers
            const clearItems  = items.slice(0, pulseGatedPreview);
            const gatedItems  = items.slice(pulseGatedPreview);
            const hiddenCount = gatedItems.length;

            const clearHtml  = clearItems.map(renderPulseArticle).join('');
            const gateHtml   = _renderPulseGate(hiddenCount);
            const gatedHtml  = `
<div style="position:relative;pointer-events:none;user-select:none;">
  <div style="filter:blur(4px);opacity:.55;">
    ${gatedItems.map(renderPulseArticle).join('')}
  </div>
  <div style="position:absolute;inset:0;background:linear-gradient(to bottom,transparent 0%,var(--bg-primary,#f5f4ed) 85%);"></div>
</div>`;

            container.innerHTML = clearHtml + gateHtml + gatedHtml;
        }

        // Initialize Market Pulse with filter listeners
        document.addEventListener('DOMContentLoaded', () => {
            loadMarketPulse();
            ['filter-source', 'filter-label', 'filter-mri'].forEach(id => {
                document.getElementById(id)?.addEventListener('change', renderFilteredPulse);
            });
            document.getElementById('filter-reset')?.addEventListener('click', () => {
                document.getElementById('filter-source').value = '';
                document.getElementById('filter-label').value = '';
                document.getElementById('filter-mri').value = '';
                renderFilteredPulse();
            });
        });

        // ============================================================
        // VN30 SCORE
        // ============================================================
        const _vn30SignalClass = { 'MUA': 'buy', 'TRUNG TÍNH': 'neu', 'BÁN': 'sell' };
        const _vn30BarColor = { 'MUA': '#22c55e', 'TRUNG TÍNH': '#eab308', 'BÁN': '#ef4444' };
        let _vn30SparklineCharts = {};

        function _vn30RenderRow(item, rank, isLocked) {
            const signal = item.signal || 'TRUNG TÍNH';
            const cls = _vn30SignalClass[signal] || 'neu';
            const barColor = _vn30BarColor[signal] || '#eab308';
            const score = item.score != null ? item.score.toFixed(1) : '--.-';
            const histBtn = !isLocked
                ? `<button class="vn30-history-btn" onclick="loadVN30TickerHistory('${item.ticker}')" title="Xem lịch sử">↗</button>`
                : '<span></span>';
            return `<div class="vn30-row${isLocked ? ' locked' : ''}" id="vn30-row-${rank}">
                <span class="vn30-rank">#${rank}</span>
                <span class="vn30-ticker">${item.ticker}</span>
                <span class="vn30-signal ${cls}">${signal}</span>
                <div class="vn30-bar-wrap"><div class="vn30-bar" style="width:${score}%;background:${barColor};"></div></div>
                <span class="vn30-score">${score}%</span>
                ${histBtn}
            </div>
            <div class="vn30-sparkline-panel" id="spark-${item.ticker}" style="display:none;grid-column:1/-1;"></div>`;
        }

        function _vn30RenderLockedRow(rank) {
            const fakePct = 45 + Math.floor(Math.random() * 30);
            return `<div class="vn30-row locked">
                <span class="vn30-rank">#${rank}</span>
                <span class="vn30-ticker">---</span>
                <span class="vn30-signal neu">---</span>
                <div class="vn30-bar-wrap"><div class="vn30-bar" style="width:${fakePct}%;background:rgba(201, 100, 66, 0.20);"></div></div>
                <span class="vn30-score">--.-%</span>
                <span></span>
            </div>`;
        }

        async function loadVN30Scores() {
            const base = window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL;
            const wrapper = document.getElementById('vn30-table-wrapper');
            const skeleton = document.getElementById('vn30-skeleton');
            const cta = document.getElementById('vn30-gate-cta');
            const metaEl = document.getElementById('vn30-meta-info');
            if (!wrapper) return;

            if (skeleton) skeleton.style.display = 'block';
            wrapper.innerHTML = '';
            if (cta) cta.style.display = 'none';

            let authHeaders = {};
            try {
                const token = await getToken();
                if (token) authHeaders['Authorization'] = 'Bearer ' + token;
            } catch(e) { /* anonymous */ }

            try {
                const res = await fetch(`${base}/vn30-scores`, { headers: authHeaders });
                if (!res.ok) throw new Error(res.status);
                const json = await res.json();

                if (skeleton) skeleton.style.display = 'none';

                if (!json.data || json.data.length === 0) {
                    wrapper.innerHTML = '<p style="text-align:center;color:var(--text-tertiary,#555);padding:3rem;">Chưa có dữ liệu điểm số VN30.</p>';
                    return;
                }

                // Render visible rows
                wrapper.innerHTML = json.data.map((item, i) => _vn30RenderRow(item, i + 1, false)).join('');

                // Meta info
                if (metaEl && json.updated_at) {
                    const d = new Date(json.updated_at);
                    const label = (currentLang === 'en') ? 'Updated' : 'Cập nhật';
                    const locale = (currentLang === 'en') ? 'en-US' : 'vi-VN';
                    metaEl.textContent = `${label}: Q${json.quarter}/${json.year} — ${d.toLocaleDateString(locale)}`;
                }

                // Gated: add blurred placeholder rows + CTA
                if (json.is_gated) {
                    const total = 30;
                    const shown = json.data.length;
                    const locked = Array.from({length: total - shown}, (_, i) => _vn30RenderLockedRow(shown + i + 1)).join('');
                    wrapper.innerHTML += locked;
                    if (cta) cta.style.display = 'block';
                }
            } catch(e) {
                if (skeleton) skeleton.style.display = 'none';
                wrapper.innerHTML = '<p style="text-align:center;color:var(--text-tertiary,#555);padding:3rem;">Không thể tải dữ liệu VN30 Score.</p>';
            }
        }

        async function loadVN30TickerHistory(ticker) {
            const panel = document.getElementById('spark-' + ticker);
            if (!panel) return;

            // Toggle: close if already open
            if (panel.style.display !== 'none') {
                panel.style.display = 'none';
                if (_vn30SparklineCharts[ticker]) { _vn30SparklineCharts[ticker].destroy(); delete _vn30SparklineCharts[ticker]; }
                return;
            }

            panel.style.display = 'block';
            panel.innerHTML = '<p style="color:var(--text-tertiary,#555);font-size:0.8rem;padding:0.5rem;">Đang tải...</p>';

            const base = window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL;
            let authHeaders = {};
            try { const t = await getToken(); if (t) authHeaders['Authorization'] = 'Bearer ' + t; } catch(e) {}

            try {
                const res = await fetch(`${base}/vn30-scores/ticker/${ticker}?limit=8`, { headers: authHeaders });
                if (res.status === 403) {
                    panel.innerHTML = '<p style="color:var(--text-tertiary,#555);font-size:0.8rem;padding:0.5rem;">Cần tài khoản Premium để xem lịch sử.</p>';
                    return;
                }
                const json = await res.json();
                const hist = (json.data || []).reverse();
                if (!hist.length) { panel.innerHTML = '<p style="color:var(--text-tertiary,#555);font-size:0.8rem;padding:0.5rem;">Không có dữ liệu lịch sử.</p>'; return; }

                const canvasId = 'spark-canvas-' + ticker;
                panel.innerHTML = `<div style="font-size:0.75rem;color:var(--gold-primary);font-weight:600;margin-bottom:0.5rem;">${ticker} — Lịch sử điểm (${hist.length} tuần)</div><canvas id="${canvasId}" height="80"></canvas>`;

                const ctx = document.getElementById(canvasId).getContext('2d');
                if (_vn30SparklineCharts[ticker]) _vn30SparklineCharts[ticker].destroy();
                _vn30SparklineCharts[ticker] = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: hist.map(h => h.report_date || ''),
                        datasets: [{
                            data: hist.map(h => h.score),
                            borderColor: '#c96442',
                            backgroundColor: 'rgba(201, 100, 66,0.08)',
                            tension: 0.3,
                            pointRadius: 4,
                            pointBackgroundColor: '#c96442',
                            fill: true,
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: { min: 0, max: 100, ticks: { color: '#87867f', font: { size: 10 } }, grid: { display: false } },
                            x: { ticks: { color: '#87867f', font: { size: 10 } }, grid: { display: false } }
                        }
                    }
                });
            } catch(e) {
                panel.innerHTML = '<p style="color:var(--text-tertiary,#555);font-size:0.8rem;padding:0.5rem;">Lỗi tải lịch sử.</p>';
            }
        }

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

            // ── Fetch CPI from internal GSO API (relative URL — same origin as FE)
            async function cpiFetch(view, years) {
                const r = await fetch(`/api/v1/macro/cpi?view=${view}&years=${years}`);
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
        })();
