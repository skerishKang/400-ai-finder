/*
 * citizen-i18n.js
 * Closed, synchronous locale registry for the five-language civic demo.
 *
 * Guarantees (per #1143):
 * - no fetch / XHR / dynamic import / external CDN;
 * - no provider, model, or translation API calls;
 * - closed locale set {ko, en, vi, th, id};
 * - invalid locale -> ko;
 * - missing translation key -> ko fallback;
 * - text-only values (no HTML injection);
 * - locale state stays in sync with the URL `lang` param and
 *   document.documentElement.lang.
 *
 * The left Bukgu-gu canvas stays Korean; only the AI shell, selector,
 * journey narration, and resident/foreign-language copy are localized.
 */

(function () {
  "use strict";

  var SUPPORTED = ["ko", "en", "vi", "th", "id"];

  // Display names shown in the language selector (never flags-only).
  var LOCALE_NAMES = Object.freeze({
    ko: "한국어",
    en: "English",
    vi: "Tiếng Việt",
    th: "ไทย",
    id: "Bahasa Indonesia",
  });

  // ── UI / shell string registry ──────────────────────────────────
  // Korean is the source of truth; every other locale falls back to ko for
  // any missing key.
  var UI = Object.freeze({
    ko: Object.freeze({
      "chat.title": "북구청 AI 민원 네비게이터",
      "chat.badge": "안내",
      "chat.attribution": "AI 행정 브라우저",
      "chat.welcome":
        "안녕하세요. 북구청 AI 민원 네비게이터입니다. 궁금한 민원을 물어보시면 관련 화면을 함께 열어 경로를 안내해 드립니다.",
      "chat.reset": "새로 시작",
      "chat.send": "보내기",
      "chat.placeholder": "여기에 물어보세요",
      "chat.inputAria": "메시지 입력",
      "chat.recommendationsAria": "추천 질문",
      "recommendations.show": "추천 질문 보기",
      "recommendations.hide": "추천 질문 숨기기",
      "chat.hint": "첫 질문 후 북구청 안내 화면과 함께 경로를 보여드립니다.",
      "chat.disclosure":
        "이 안내는 시연용이며 실제 민원 접수나 개인정보 전송은 하지 않습니다.",
      "chat.languageLabel": "언어",

      "chip.mayor": "구청장에게 제안하고 싶어요",
      "chip.illegalParking": "불법 주정차 신고",
      "chip.apartment": "공동주택 부서 문의",
      "chip.bulkyWaste": "대형폐기물 배출",
      "chip.passport": "여권 발급 안내",
      "chip.kiosk": "무인민원발급기 안내",
      "chip.streetlight": "가로등 고장 신고 (AI 도움)",
      "chip.litter": "쓰레기 무단투기 (AI 도움)",

      "action.yesGuide": "예, 안내해 주세요",
      "action.no": "아니요",
      "action.confirmSubmit": "검토했고, 제출하기",
      "action.edit": "수정할게요",
      "action.previous": "이전",
      "action.continue": "계속",
      "action.chooseAi": "AI 도움 받기",
      "action.writeMyself": "직접 작성",
      "action.restart": "다시 시작",

      "status.thinking": "잠시만 기다려 주세요...",
      "status.searching": "검색 중입니다...",
      "status.typingTitle": "제목을 정리하는 중입니다...",
      "status.typingBody": "본문을 작성하는 중입니다...",
      "status.openingPage": "화면을 여는 중입니다...",
      "status.preSubmit": "입력 내용을 확인하는 중입니다...",
      "status.officialChannel": "공식 채널에서 직접 확인해 주세요.",

      "safety.draftOnly":
        "현재 화면은 초안 작성 단계입니다. 실제 제출은 하지 않습니다.",
      "safety.noSubmission":
        "안내만 진행하며 실제 민원은 제출되지 않습니다.",
      "safety.preSubmit": "제출 전에 내용을 다시 확인해 주세요.",
      "safety.officialChannel":
        "공식 제출은 북구청 공식 채널에서 직접 진행해 주세요.",
      "safety.koreanDraft":
        "한국어 행정 초안은 검수된 동일 본문입니다.",

      "draft.originalResidentMessage": "주민 원문 메시지",
      "draft.koreanAdministrativeDraft": "한국어 행정 초안",
      "draft.translatedForDraft": "작성 보조를 위한 번역",
      "draft.reviewBeforeSubmission": "제출 전에 다시 확인해 주세요.",

      "confirm.mayor": "작성된 제안의 제목과 본문을 검토했습니다. 이 내용으로 구정 제안서를 최종 확인할까요?",
      "confirm.generic": "작성된 제목과 본문을 검토했습니다. 확인 전에는 제출되지 않습니다. 이 내용으로 진행할까요?",
      "choice.prompt":
        "직접 작성하시겠습니까, 아니면 AI가 초안 작성을 도와드릴까요?",

      "split.confirm": "에 대해 안내해 드릴까요?",
      "split.ready":
        "질문을 확인했습니다. 왼쪽에 북구청 안내 화면을 열었습니다.",
      "split.followUp":
        "북구청 안내 화면을 왼쪽에 열어두었습니다. 메뉴 이동과 세부 안내를 이어서 보여드리겠습니다. 새 질문을 시작하려면 '새 대화'를 선택해 주세요.",
      "unsupported":
        "현재 첫 화면에서는 불법 주정차 신고, 공동주택 문의, 대형폐기물 처리, 여권 발급 안내, 무인민원발급기 안내를 준비했습니다. 예시 질문으로 다시 입력해 주세요.",

      "apartment.final.prefix": "공동주택과 부서 대표전화는 ",
      "apartment.final.fax": ", FAX는 ",
      "apartment.final.suffix": "입니다. 왼쪽 조직 및 업무안내 표에서 전체 ",
      "apartment.final.tail": "명의 업무별 연락처를 확인할 수 있습니다.",
      "apartment.table.prefix": "공식 조직 및 업무안내의 전체 ",
      "apartment.table.tail": "명 표를 열고 대표 연락처 행을 확인했습니다.",
      "apartment.missing": "공동주택과 공식 스냅샷을 불러오지 못했습니다.",
    }),

    en: Object.freeze({
      "chat.title": "BUKGU AI CIVIC NAVIGATOR",
      "chat.badge": "Guide",
      "chat.attribution": "AI Administrative Browser",
      "chat.welcome":
        "Hello. I am BUKGU AI CIVIC NAVIGATOR. Ask about a public service and I will open the relevant screen and guide you through the steps.",
      "chat.reset": "Start over",
      "chat.send": "Send",
      "chat.placeholder": "Ask here",
      "chat.inputAria": "Type a message",
      "chat.recommendationsAria": "Suggested questions",
      "recommendations.show": "Show recommendations",
      "recommendations.hide": "Hide recommendations",
      "chat.hint":
        "After your first question, I will show the route together with the Bukgu-gu guide screen.",
      "chat.disclosure":
        "This guide is for demonstration only. It does not submit real complaints or send personal information.",
      "chat.languageLabel": "Language",

      "chip.mayor": "I want to propose to the mayor",
      "chip.illegalParking": "Illegal parking report",
      "chip.apartment": "Apartment housing department",
      "chip.bulkyWaste": "Bulky waste disposal",
      "chip.passport": "Passport issuance guide",
      "chip.kiosk": "Unmanned document kiosk",
      "chip.streetlight": "Broken streetlight report (AI help)",
      "chip.litter": "Illegal dumping (AI help)",

      "action.yesGuide": "Yes, please guide me",
      "action.no": "No",
      "action.confirmSubmit": "Reviewed, submit",
      "action.edit": "I will edit",
      "action.previous": "Previous",
      "action.continue": "Continue",
      "action.chooseAi": "Get AI help",
      "action.writeMyself": "Write myself",
      "action.restart": "Restart",

      "status.thinking": "Please wait a moment...",
      "status.searching": "Searching...",
      "status.typingTitle": "Organizing the title...",
      "status.typingBody": "Writing the body...",
      "status.openingPage": "Opening the screen...",
      "status.preSubmit": "Checking your input...",
      "status.officialChannel": "Please verify through the official channel directly.",

      "safety.draftOnly":
        "This screen is for drafting only. No real submission is made.",
      "safety.noSubmission":
        "Only guidance is provided; no real complaint is submitted.",
      "safety.preSubmit": "Please review the content before submitting.",
      "safety.officialChannel":
        "Please complete the official submission directly through Bukgu-gu's official channels.",
      "safety.koreanDraft":
        "The Korean administrative draft is a reviewed, consistent version.",

      "draft.originalResidentMessage": "Original resident message",
      "draft.koreanAdministrativeDraft": "Korean administrative draft",
      "draft.translatedForDraft": "Translation for drafting assistance",
      "draft.reviewBeforeSubmission": "Please review again before submitting.",

      "confirm.mayor": "I have reviewed the title and body of the proposal. Shall we finalize this district proposal?",
      "confirm.generic":
        "I have reviewed the title and body. Nothing is submitted before you confirm. Shall we proceed with this?",
      "choice.prompt":
        "Would you like to write it yourself, or shall I help draft it with AI?",

      "split.confirm": " — shall I guide you through this?",
      "split.ready":
        "I have your question. The Bukgu-gu guide screen is now open on the left.",
      "split.followUp":
        "The Bukgu-gu guide screen stays open on the left. I will continue with the menu and detailed guidance. To start a new question, choose 'Start over'.",
      "unsupported":
        "On this first screen I can help with illegal parking reports, apartment housing inquiries, bulky waste disposal, passport guidance, and unmanned kiosks. Please try one of the example questions.",

      "apartment.final.prefix": "The Apartment Housing Division main line is ",
      "apartment.final.fax": ", and the fax number is ",
      "apartment.final.suffix": ". You can see all ",
      "apartment.final.tail": " department contacts in the organization table on the left.",
      "apartment.table.prefix": "I've opened the full official organization table with ",
      "apartment.table.tail": " rows and highlighted the main contact row.",
      "apartment.missing": "Could not load the Apartment Housing Division official snapshot.",
    }),

    vi: Object.freeze({
      "chat.title": "BUKGU AI CIVIC NAVIGATOR",
      "chat.badge": "Hướng dẫn",
      "chat.attribution": "Trình duyệt hành chính AI",
      "chat.welcome":
        "Xin chào. Tôi là BUKGU AI CIVIC NAVIGATOR. Hãy đặt câu hỏi về dịch vụ công, tôi sẽ mở màn hình liên quan và hướng dẫn bạn từng bước.",
      "chat.reset": "Bắt đầu lại",
      "chat.send": "Gửi",
      "chat.placeholder": "Nhập câu hỏi tại đây",
      "chat.inputAria": "Nhập tin nhắn",
      "chat.recommendationsAria": "Câu hỏi gợi ý",
      "recommendations.show": "Hiện gợi ý",
      "recommendations.hide": "Ẩn gợi ý",
      "chat.hint":
        "Sau câu hỏi đầu tiên, tôi sẽ hiện đường dẫn cùng màn hình hướng dẫn của Bukgu-gu.",
      "chat.disclosure":
        "Hướng dẫn này chỉ dùng để trình diễn, không tiếp nhận khiếu nại thật hay gửi thông tin cá nhân.",
      "chat.languageLabel": "Ngôn ngữ",

      "chip.mayor": "Tôi muốn gửi đề xuất đến quận trưởng",
      "chip.illegalParking": "Báo cáo đỗ xe trái phép",
      "chip.apartment": "Hỏi đáp phòng quản lý nhà chung cư",
      "chip.bulkyWaste": "Vứt bỏ rác cồng kềnh",
      "chip.passport": "Hướng dẫn cấp hộ chiếu",
      "chip.kiosk": "Hướng dẫn máy cấp giấy tờ tự động",
      "chip.streetlight": "Báo cáo đèn đường hỏng (có AI hỗ trợ)",
      "chip.litter": "Vứt rác bừa bãi (có AI hỗ trợ)",

      "action.yesGuide": "Vâng, hãy hướng dẫn tôi",
      "action.no": "Không",
      "action.confirmSubmit": "Đã xem xét, gửi đi",
      "action.edit": "Tôi sẽ chỉnh sửa",
      "action.previous": "Trước",
      "action.continue": "Tiếp tục",
      "action.chooseAi": "Nhờ AI hỗ trợ",
      "action.writeMyself": "Tự tôi viết",
      "action.restart": "Bắt đầu lại",

      "status.thinking": "Xin vui lòng đợi một chút...",
      "status.searching": "Đang tìm kiếm...",
      "status.typingTitle": "Đang soạn tiêu đề...",
      "status.typingBody": "Đang soạn nội dung...",
      "status.openingPage": "Đang mở màn hình...",
      "status.preSubmit": "Đang kiểm tra nội dung nhập...",
      "status.officialChannel": "Vui lòng kiểm tra trực tiếp qua kênh chính thức.",

      "safety.draftOnly":
        "Màn hình này chỉ dùng để nháp. Không có việc nộp thật nào được thực hiện.",
      "safety.noSubmission":
        "Chỉ hướng dẫn, không gửi khiếu nại thật.",
      "safety.preSubmit": "Vui lòng xem lại nội dung trước khi gửi.",
      "safety.officialChannel":
        "Vui lòng hoàn tất việc nộp chính thức qua kênh chính thức của Bukgu-gu.",
      "safety.koreanDraft":
        "Bản nháp hành chính tiếng Hàn là văn bản nhất quán đã được kiểm duyệt.",

      "draft.originalResidentMessage": "Tin nhắn gốc của cư dân",
      "draft.koreanAdministrativeDraft": "Bản nháp hành chính tiếng Hàn",
      "draft.translatedForDraft": "Bản dịch hỗ trợ soạn thảo",
      "draft.reviewBeforeSubmission": "Vui lòng xem lại trước khi gửi.",

      "confirm.mayor": "Tôi đã xem xét tiêu đề và nội dung của đề xuất. Xin hãy xác nhận bản đề xuất này gửi đến quận trưởng?",
      "confirm.generic":
        "Tôi đã xem xét tiêu đề và nội dung. Chưa gửi trước khi bạn xác nhận. Tiếp tục với nội dung này?",
      "choice.prompt":
        "Bạn muốn tự viết, hay để AI hỗ trợ soạn thảo?",

      "split.confirm": " — tôi có nên hướng dẫn bạn việc này không?",
      "split.ready":
        "Tôi đã nhận câu hỏi. Màn hình hướng dẫn Bukgu-gu đã mở bên trái.",
      "split.followUp":
        "Màn hình hướng dẫn Bukgu-gu vẫn mở bên trái. Tôi sẽ tiếp tục với menu và hướng dẫn chi tiết. Để bắt đầu câu hỏi mới, hãy chọn 'Bắt đầu lại'.",
      "unsupported":
        "Ở màn hình đầu này, tôi hỗ trợ báo cáo đỗ xe trái phép, hỏi đáp nhà chung cư, vứt bỏ rác cồng kềnh, hướng dẫn hộ chiếu và máy tự động. Hãy thử một câu hỏi ví dụ.",

      "apartment.final.prefix": "Điện thoại chính của phòng Quản lý nhà chung cư là ",
      "apartment.final.fax": ", fax là ",
      "apartment.final.suffix": ". Bạn có thể xem tất cả ",
      "apartment.final.tail": " liên hệ theo nghiệp vụ trong bảng tổ chức bên trái.",
      "apartment.table.prefix": "Tôi đã mở bảng tổ chức và công việc chính thức với ",
      "apartment.table.tail": " dòng và làm nổi bật hàng liên hệ chính.",
      "apartment.missing": "Không thể tải ảnh chụp chính thức phòng Quản lý nhà chung cư.",
    }),

    th: Object.freeze({
      "chat.title": "BUKGU AI CIVIC NAVIGATOR",
      "chat.badge": "คู่มือ",
      "chat.attribution": "เบราว์เซอร์งานราชการ AI",
      "chat.welcome":
        "สวัสดีค่ะ/ครับ ฉันคือ BUKGU AI CIVIC NAVIGATOR หากมีคำถามเรื่องบริการสาธารณะ บอกได้เลย ฉันจะเปิดหน้าจอที่เกี่ยวข้องและนำทางให้ทีละขั้นตอน",
      "chat.reset": "เริ่มใหม่",
      "chat.send": "ส่ง",
      "chat.placeholder": "พิมพ์คำถามที่นี่",
      "chat.inputAria": "พิมพ์ข้อความ",
      "chat.recommendationsAria": "คำถามแนะนำ",
      "recommendations.show": "แสดงคำแนะนำ",
      "recommendations.hide": "ซ่อนคำแนะนำ",
      "chat.hint":
        "หลังคำถามแรก ฉันจะแสดงเส้นทางพร้อมหน้าจอแนะนำของเขต Bukgu-gu",
      "chat.disclosure":
        "คำแนะนำนี้เป็นเพียงการสาธิต ไม่มีการรับเรื่องราชการจริงหรือส่งข้อมูลส่วนบุคคล",
      "chat.languageLabel": "ภาษา",

      "chip.mayor": "ฉันอยากส่งข้อเสนอถึงนายกเทศมนตรีเขต",
      "chip.illegalParking": "แจ้งจอดรถผิดกฎหมาย",
      "chip.apartment": "สอบถามแผนกอาคารชุด",
      "chip.bulkyWaste": "ทิ้งขยะชิ้นใหญ่",
      "chip.passport": "คู่มือการทำหนังสือเดินทาง",
      "chip.kiosk": "คู่มือเครื่องออกเอกสารอัตโนมัติ",
      "chip.streetlight": "แจ้งโคมไฟถนนเสีย (มี AI ช่วย)",
      "chip.litter": "ทิ้งขยะมิชอบ (มี AI ช่วย)",

      "action.yesGuide": "ใช่ ค่อยแนะนำด้วย",
      "action.no": "ไม่",
      "action.confirmSubmit": "ตรวจสอบแล้ว ส่งเรื่อง",
      "action.edit": "ฉันจะแก้ไข",
      "action.previous": "ย้อนกลับ",
      "action.continue": "ดำเนินการต่อ",
      "action.chooseAi": "ขอความช่วยเหลือจาก AI",
      "action.writeMyself": "เขียนเอง",
      "action.restart": "เริ่มใหม่",

      "status.thinking": "โปรดรอสักครู่...",
      "status.searching": "กำลังค้นหา...",
      "status.typingTitle": "กำลังจัดเตรียมหัวข้อ...",
      "status.typingBody": "กำลังเขียนเนื้อหา...",
      "status.openingPage": "กำลังเปิดหน้าจอ...",
      "status.preSubmit": "กำลังตรวจสอบข้อมูลที่กรอก...",
      "status.officialChannel": "โปรดตรวจสอบด้วยตนเองผ่านช่องทางทางการ",

      "safety.draftOnly":
        "หน้าจอนี้ใช้ร่างเท่านั้น ไม่มีการส่งเรื่องจริง",
      "safety.noSubmission":
        "ให้คำแนะนำเท่านั้น ไม่มีการส่งเรื่องราชการจริง",
      "safety.preSubmit": "โปรดตรวจสอบเนื้อหาอีกครั้งก่อนส่ง",
      "safety.officialChannel":
        "โปรดดำเนินการส่งเรื่องทางการด้วยตนเองผ่านช่องทางทางการของเขต Bukgu-gu",
      "safety.koreanDraft":
        "ร่างเอกสารราชการภาษาเกาหลีเป็นฉบับที่ตรวจสอบแล้วและสม่ำเสมอ",

      "draft.originalResidentMessage": "ข้อความต้นฉบับของผู้พักอาศัย",
      "draft.koreanAdministrativeDraft": "ร่างเอกสารราชการภาษาเกาหลี",
      "draft.translatedForDraft": "คำแปลเพื่อช่วยร่างเอกสาร",
      "draft.reviewBeforeSubmission": "โปรดตรวจสอบอีกครั้งก่อนส่ง",

      "confirm.mayor": "ฉันได้ตรวจสอบหัวข้อและเนื้อหาของข้อเสนอแล้ว ยืนยันร่างข้อเสนอนี้ถึงนายกเทศมนตรีเขตหรือไม่?",
      "confirm.generic":
        "ฉันได้ตรวจสอบหัวข้อและเนื้อหาแล้ว ยังไม่ส่งก่อนคุณยืนยัน ดำเนินการต่อกับเนื้อหานี้หรือไม่?",
      "choice.prompt":
        "คุณต้องการเขียนเอง หรือให้ AI ช่วยร่างให้?",

      "split.confirm": " — ให้ฉันนำทางเรื่องนี้ไหม?",
      "split.ready":
        "ฉันได้รับคำถามแล้ว หน้าจอแนะนำของเขต Bukgu-gu เปิดอยู่ด้านซ้าย",
      "split.followUp":
        "หน้าจอแนะนำของเขต Bukgu-gu ยังคงเปิดด้านซ้าย ฉันจะดำเนินการต่อด้วยเมนูและคำแนะนำรายละเอียด หากต้องการเริ่มคำถามใหม่ ให้เลือก 'เริ่มใหม่'",
      "unsupported":
        "ในหน้าแรกนี้ ฉันช่วยเรื่องแจ้งจอดรถผิดกฎหมาย สอบถามอาคารชุด ทิ้งขยะชิ้นใหญ่ คู่มือหนังสือเดินทาง และเครื่องอัตโนมัติได้ โปรดลองคำถามตัวอย่าง",

      "apartment.final.prefix": "หมายเลขโทรศัพท์หลักของแผนกอาคารชุดคือ ",
      "apartment.final.fax": " และหมายเลขแฟกซ์คือ ",
      "apartment.final.suffix": " คุณสามารถดูข้อมูลติดต่อทั้งหมด ",
      "apartment.final.tail": " ตามสายงานในตารางองค์กรด้านซ้าย",
      "apartment.table.prefix": "ฉันเปิดตารางองค์กรและงานทางการทั้งหมด ",
      "apartment.table.tail": " แถว และเน้นแถวติดต่อหลักแล้ว",
      "apartment.missing": "ไม่สามารถโหลดสแนปช็อตทางการของแผนกอาคารชุดได้",
    }),

    id: Object.freeze({
      "chat.title": "BUKGU AI CIVIC NAVIGATOR",
      "chat.badge": "Panduan",
      "chat.attribution": "Peramban Administrasi AI",
      "chat.welcome":
        "Halo. Saya adalah BUKGU AI CIVIC NAVIGATOR. Tanyakan layanan publik apa pun, dan saya akan membuka layar terkait serta memandu Anda langkah demi langkah.",
      "chat.reset": "Mulai ulang",
      "chat.send": "Kirim",
      "chat.placeholder": "Tanyakan di sini",
      "chat.inputAria": "Ketik pesan",
      "chat.recommendationsAria": "Pertanyaan yang disarankan",
      "recommendations.show": "Tampilkan saran",
      "recommendations.hide": "Sembunyikan saran",
      "chat.hint":
        "Setelah pertanyaan pertama, saya akan menampilkan rute beserta layar panduan Bukgu-gu.",
      "chat.disclosure":
        "Panduan ini hanya untuk demonstrasi. Tidak mengirimkan pengaduan sungguhan atau data pribadi.",
      "chat.languageLabel": "Bahasa",

      "chip.mayor": "Saya ingin mengusulkan kepada bupati",
      "chip.illegalParking": "Laporan parkir liar",
      "chip.apartment": "Tanya departemen perumahan",
      "chip.bulkyWaste": "Pembuangan sampah besar",
      "chip.passport": "Panduan pembuatan paspor",
      "chip.kiosk": "Panduan mesin layanan mandiri",
      "chip.streetlight": "Laporan lampu jalan rusak (bantuan AI)",
      "chip.litter": "Membuang sampah sembarangan (bantuan AI)",

      "action.yesGuide": "Ya, bantu saya",
      "action.no": "Tidak",
      "action.confirmSubmit": "Sudah diperiksa, kirim",
      "action.edit": "Saya akan edit",
      "action.previous": "Sebelumnya",
      "action.continue": "Lanjut",
      "action.chooseAi": "Gunakan bantuan AI",
      "action.writeMyself": "Tulis sendiri",
      "action.restart": "Mulai ulang",

      "status.thinking": "Mohon tunggu sebentar...",
      "status.searching": "Sedang mencari...",
      "status.typingTitle": "Menyusun judul...",
      "status.typingBody": "Menulis isi...",
      "status.openingPage": "Membuka layar...",
      "status.preSubmit": "Memeriksa isian Anda...",
      "status.officialChannel": "Harap verifikasi langsung melalui saluran resmi.",

      "safety.draftOnly":
        "Layar ini hanya untuk membuat draf. Tidak ada pengiriman sungguhan.",
      "safety.noSubmission":
        "Hanya panduan; tidak ada pengaduan sungguhan yang dikirim.",
      "safety.preSubmit": "Harap periksa kembali isi sebelum mengirim.",
      "safety.officialChannel":
        "Harap selesaikan pengiriman resmi melalui saluran resmi Bukgu-gu.",
      "safety.koreanDraft":
        "Draf administratif bahasa Korea adalah teks yang telah ditinjau dan konsisten.",

      "draft.originalResidentMessage": "Pesan asli warga",
      "draft.koreanAdministrativeDraft": "Draf administratif bahasa Korea",
      "draft.translatedForDraft": "Terjemahan bantuan penyusunan",
      "draft.reviewBeforeSubmission": "Harap periksa kembali sebelum mengirim.",

      "confirm.mayor": "Saya telah meninjau judul dan isi usulan. Yakin menyelesaikan usulan kepada bupati ini?",
      "confirm.generic":
        "Saya telah meninjau judul dan isi. Belum dikirim sebelum Anda konfirmasi. Lanjutkan dengan ini?",
      "choice.prompt":
        "Apakah Anda ingin menulis sendiri, atau saya bantu buatkan drafnya dengan AI?",

      "split.confirm": " — ingin saya pandu hal ini?",
      "split.ready":
        "Pertanyaan sudah saya terima. Layar panduan Bukgu-gu kini terbuka di kiri.",
      "split.followUp":
        "Layar panduan Bukgu-gu tetap terbuka di kiri. Saya lanjutkan dengan menu dan panduan rincinya. Untuk pertanyaan baru, pilih 'Mulai ulang'.",
      "unsupported":
        "Di layar pertama ini saya membantu laporan parkir liar, tanya perumahan, pembuangan sampah besar, panduan paspor, dan mesin mandiri. Silakan coba salah satu pertanyaan contoh.",

      "apartment.final.prefix": "Nomor telepon utama Divisi Perumahan adalah ",
      "apartment.final.fax": ", dan nomor faks adalah ",
      "apartment.final.suffix": ". Anda dapat melihat semua ",
      "apartment.final.tail": " kontak per bidang di tabel organisasi di kiri.",
      "apartment.table.prefix": "Saya telah membuka tabel organisasi dan tugas resmi dengan ",
      "apartment.table.tail": " baris dan menyoroti baris kontak utama.",
      "apartment.missing": "Tidak dapat memuat snapshot resmi Divisi Perumahan.",
    }),
  });

  // ── Journey narration map ──────────────────────────────────────
  // Keyed by the frozen Korean source string used in the choreography.
  // translateMessage(koText) returns the localized equivalent (or the
  // original Korean when no translation exists). The left canvas, the
  // Korean administrative draft, and typed form content stay Korean.
  var JOURNEY = Object.freeze({
    en: Object.freeze({
      "구청장에게 전할 제안을 함께 작성하겠습니다.":
        "Let's write the proposal to the mayor together.",
      "주민의 문제 제기와 기대 효과가 잘 드러나도록 구정 제안 문장으로 정리합니다.":
        "I will shape your point and expected benefit into a clear district proposal.",
      "먼저 제안 제목을 입력합니다.": "First, I'll enter the proposal title.",
      "현장 상황과 기대 효과를 담아 본문을 작성합니다.":
        "Now I'll write the body with the on-site situation and expected benefit.",
      "제안 초안을 완성했습니다. 위치 정보를 보완한 뒤 [검토했고, 제출하기]를 선택해 주세요.":
        "The proposal draft is ready. Add the location, then choose [Reviewed, submit].",
      "한국어 초안 작성을 마쳤습니다. 공식 제출은 북구청 공식 채널에서 직접 확인하고 진행해 주세요.":
        "The Korean draft is complete. Please verify and submit through Bukgu-gu's official channels directly.",

      "가로등 고장 신고를 도와드립니다.":
        "I'll help you report a broken streetlight.",
      "민원게시판으로 이동합니다.": "Going to the civil complaint board.",
      "글쓰기 버튼을 눌러 새 신고 양식을 엽니다.":
        "Pressing the write button to open a new report form.",
      "민원 제목을 입력합니다.": "Entering the complaint title.",
      "말씀하실 내용을 민원 문장으로 정리해 본문에 입력합니다.":
        "Turning your words into a civil complaint and filling in the body.",
      "제목과 본문 초안을 입력했습니다. 대괄호 부분을 확인한 뒤 제출 여부를 선택해 주세요.":
        "I've entered the title and body draft. Check the bracketed parts, then decide whether to submit.",
      "민원 초안 작성을 마쳤습니다. 실제 제출은 북구청 공식 채널에서 직접 진행해 주세요.":
        "The complaint draft is complete. Please submit through Bukgu-gu's official channels directly.",

      "공동주택 부서 정보를 안내해 드립니다.":
        "Here is the apartment housing department information.",
      "먼저 북구소개 메뉴를 열겠습니다.": "First, opening the About Bukgu menu.",
      "구청안내에서 행정조직의 공동주택과를 찾습니다.":
        "Finding the Apartment Housing Division under Administrative Organization.",
      "검색창에 공동주택을 입력하겠습니다.":
        "Typing 'apartment housing' in the search box.",
      "입력한 검색어로 담당 부서를 조회합니다.":
        "Looking up the responsible division for your search term.",
      "공동주택과 부서 대표전화는 ":
        "The Apartment Housing Division main line is ",
      ", FAX는 ": ", and the fax number is ",
      "입니다. 왼쪽 조직 및 업무안내 표에서 전체 ":
        ". You can see all ",
      "명의 업무별 연락처를 확인할 수 있습니다.":
        " department contacts in the organization table on the left.",
      "공식 조직 및 업무안내의 전체 ":
        "I've opened the full official organization table with ",
      "명 표를 열고 대표 연락처 행을 확인했습니다.":
        " rows and highlighted the main contact row.",
      "공동주택과 공식 스냅샷을 불러오지 못했습니다.":
        "Could not load the Apartment Housing Division official snapshot.",

      "불법 주정차 신고 경로를 안내해 드립니다.":
        "Here is the illegal parking report path.",
      "지도단속 안내 화면으로 이동합니다.":
        "Moving to the map-based enforcement screen.",
      "안전신문고 등 공식 신고 채널을 안내합니다.":
        "The official reporting channel is Safety Report (safetyreport.go.kr).",
      "안내를 마쳤습니다. 실제 신고는 안전신문고(safetyreport.go.kr)에서 가능합니다.":
        "That's the end of the guide. Real reports are made via Safety Report (safetyreport.go.kr).",
      "대형폐기물 배출방법 경로를 안내해 드립니다.":
        "Here is the bulky waste disposal path.",
      "대형폐기물 배출방법 페이지로 이동합니다.":
        "Going to the bulky waste disposal page.",
      "전화 신고와 여기로 신청 경로를 안내합니다.":
        "I'll show the phone-report and online application paths.",
      "안내를 마쳤습니다. 실제 신청은 여기로 앱 또는 북구청 홈페이지에서 가능합니다.":
        "That's the end of the guide. Real applications are via the app or the Bukgu-gu website.",
      "여권 발급 경로를 안내해 드립니다.": "Here is the passport issuance path.",
      "종합민원 메뉴를 확인합니다.": "Opening the Integrated Civil Service menu.",
      "종합민원 페이지로 이동합니다.": "Going to the Integrated Civil Service page.",
      "여권민원 안내 화면으로 이동합니다.": "Going to the passport guide screen.",
      "여권민원 안내를 확인합니다. 여권 수수료표, 구비서류, 신청안내를 보실 수 있습니다. 실제 여권 신청은 북구청 민원실 방문 후 직접 진행해야 합니다.":
        "This is the passport guide: fee table, required documents, and application info. Real passport applications require an in-person visit to the Bukgu-gu civil office.",
      "안내를 마쳤습니다. 실제 여권 신청은 북구청 민원실 또는 정부24에서 가능합니다.":
        "That's the end of the guide. Real passport applications are at the Bukgu-gu civil office or Government24.",
      "무인민원발급기 이용 경로를 안내해 드립니다.":
        "Here is the unmanned kiosk path.",
      "무인민원발급기 안내 화면으로 이동합니다.":
        "Going to the unmanned kiosk guide screen.",
      "무인민원발급기 안내를 확인합니다. 설치장소, 발급종류, 이용방법을 보실 수 있습니다. 실제 서류 발급은 현장에서 본인인증 후 직접 진행해야 합니다.":
        "This is the unmanned kiosk guide: locations, document types, and usage. Real document issuance requires on-site identity verification.",
      "안내를 마쳤습니다. 실제 이용은 북구청 및 각 행정복지센터에 설치된 무인민원발급기에서 가능합니다.":
        "That's the end of the guide. Real use is at the kiosks in Bukgu-gu offices and welfare centers.",
      "쓰레기 무단투기 신고 작성을 도와드립니다.":
        "I'll help you draft an illegal dumping report.",
      "민원게시판의 글쓰기 양식으로 이동합니다.":
        "Moving to the complaint board writing form.",
      "직접 작성하시겠습니까, 아니면 AI가 초안 작성을 도와드릴까요?":
        "Would you like to write it yourself, or shall I help draft it with AI?",
      "AI 도움을 선택하셨습니다. 글쓰기 버튼을 누르고 양식을 열겠습니다. 어떤 불편사항인지 편하게 말씀해 주세요.":
        "You chose AI help. I'll press write and open the form. Please tell me what the problem is.",
      "집 앞 공원에 쓰레기가 너무 많고 냄새가 나요. 빨리 치워주세요.":
        "There is too much trash in the park near my home and it smells. Please clean it up soon.",
      "말씀하신 내용을 바탕으로 민원 접수 양식에 맞게 초안을 작성합니다...":
        "Drafting a complaint that fits the form, based on what you said...",
      "먼저 민원 제목을 입력합니다.": "First, entering the complaint title.",
      "이어서 주민의 표현을 정중하고 구체적인 민원 문장으로 다듬어 본문에 입력합니다.":
        "Now polishing your words into a polite, specific complaint for the body.",
      "작성된 초안을 확인한 뒤 오른쪽의 [검토했고, 제출하기]를 선택해 주세요. 확인 전에는 제출되지 않습니다.":
        "Review the draft, then choose [Reviewed, submit] on the right. Nothing is sent before you confirm.",

      "잠시만 기다려 주세요...": "Please wait a moment...",
      "게시판으로 이동 중입니다...": "Moving to the board...",
      "양식을 준비 중입니다...": "Preparing the form...",
      "제목을 다듬는 중입니다...": "Polishing the title...",
      "민원 문장을 작성하는 중입니다...": "Writing the complaint...",
      "북구청 사이트에 접속 중입니다...": "Connecting to the Bukgu-gu site...",
      "신고 채널 정보를 확인 중입니다...": "Checking the reporting channel...",
      "안전신문고 사이트를 검색 중입니다...": "Searching Safety Report...",
      "북구청 메뉴를 살펴보는 중입니다...": "Browsing the Bukgu-gu menu...",
      "담당 부서 경로를 찾는 중입니다...": "Finding the responsible division...",
      "부서 검색을 준비하는 중입니다...": "Preparing the department search...",
      "공동주택 관련 부서를 검색 중입니다...":
        "Searching for the apartment housing division...",
      "공식 결과를 확인하는 중입니다...": "Checking the official result...",
      "대형폐기물 페이지를 불러오는 중입니다...": "Loading the bulky waste page...",
      "배출 방법 정보를 확인 중입니다...": "Checking disposal information...",
      "메뉴를 탐색 중입니다...": "Exploring the menu...",
      "여권민원 안내 화면을 찾는 중입니다...": "Finding the passport guide...",
      "여권 발급 관련 정보를 검색 중입니다...": "Searching passport information...",
      "여권 발급 정보를 확인 중입니다...": "Checking passport information...",
      "무인민원발급기 정보 페이지를 불러오는 중입니다...":
        "Loading the kiosk information page...",
      "무인민원발급기 정보를 확인 중입니다...": "Checking kiosk information...",
      "제안 작성 화면을 준비 중입니다...": "Preparing the proposal screen...",
      "열린구청장실 경로를 찾는 중입니다...": "Finding the path to the Open Mayor's Office...",
      "제안 작성 양식을 여는 중입니다...": "Opening the proposal writing form...",
      "제안의 핵심과 기대 효과를 분석하는 중입니다...":
        "Analyzing the core idea and expected benefit...",
      "제목을 구체화하는 중입니다...": "Making the title more specific...",
      "설득력 있는 제안 문장을 작성하는 중입니다...":
        "Writing a persuasive proposal sentence...",
      "내용을 분석하고 윤문하는 중입니다...": "Analyzing and polishing the text...",
      "핵심 내용을 제목으로 정리하는 중입니다...": "Summarizing the key point as a title...",
    }),

    vi: Object.freeze({
      "구청장에게 전할 제안을 함께 작성하겠습니다.":
        "Chúng ta sẽ soạn đề xuất gửi quận trưởng cùng nhau.",
      "주민의 문제 제기와 기대 효과가 잘 드러나도록 구정 제안 문장으로 정리합니다.":
        "Tôi sẽ trình bày ý kiến và lợi ích kỳ vọng thành câu đề xuất quận rõ ràng.",
      "먼저 제안 제목을 입력합니다.": "Đầu tiên, tôi nhập tiêu đề đề xuất.",
      "현장 상황과 기대 효과를 담아 본문을 작성합니다.":
        "Giờ tôi soạn nội dung với tình hình thực tế và lợi ích kỳ vọng.",
      "제안 초안을 완성했습니다. 위치 정보를 보완한 뒤 [검토했고, 제출하기]를 선택해 주세요.":
        "Bản nháp đề xuất đã xong. Bổ sung vị trí, rồi chọn [Đã xem xét, gửi đi].",
      "한국어 초안 작성을 마쳤습니다. 공식 제출은 북구청 공식 채널에서 직접 확인하고 진행해 주세요.":
        "Bản nháp tiếng Hàn đã hoàn tất. Vui lòng xác nhận và nộp qua kênh chính thức của Bukgu-gu.",

      "가로등 고장 신고를 도와드립니다.":
        "Tôi sẽ giúp bạn báo cáo đèn đường hỏng.",
      "민원게시판으로 이동합니다.": "Chuyển đến bảng tiếp nhận khiếu nại.",
      "글쓰기 버튼을 눌러 새 신고 양식을 엽니다.":
        "Nhấn nút viết để mở form báo cáo mới.",
      "민원 제목을 입력합니다.": "Nhập tiêu đề khiếu nại.",
      "말씀하실 내용을 민원 문장으로 정리해 본문에 입력합니다.":
        "Chuyển lời bạn thành văn bản khiếu nại và điền vào nội dung.",
      "제목과 본문 초안을 입력했습니다. 대괄호 부분을 확인한 뒤 제출 여부를 선택해 주세요.":
        "Tôi đã nhập tiêu đề và bản nháp nội dung. Kiểm tra phần trong ngoặc, rồi chọn có gửi hay không.",
      "민원 초안 작성을 마쳤습니다. 실제 제출은 북구청 공식 채널에서 직접 진행해 주세요.":
        "Bản nháp khiếu nại đã hoàn tất. Vui lòng nộp qua kênh chính thức của Bukgu-gu.",

      "공동주택 부서 정보를 안내해 드립니다.":
        "Đây là thông tin phòng quản lý nhà chung cư.",
      "먼저 북구소개 메뉴를 열겠습니다.": "Đầu tiên, mở menu Giới thiệu Bukgu.",
      "구청안내에서 행정조직의 공동주택과를 찾습니다.":
        "Tìm phòng Quản lý nhà chung cư trong cơ cấu hành chính.",
      "검색창에 공동주택을 입력하겠습니다.":
        "Nhập 'nhà chung cư' vào ô tìm kiếm.",
      "입력한 검색어로 담당 부서를 조회합니다.":
        "Tra cứu phòng phụ trách theo từ khóa bạn nhập.",
      "공동주택과 부서 대표전화는 ":
        "Điện thoại chính của phòng Quản lý nhà chung cư là ",
      ", FAX는 ": ", fax là ",
      "입니다. 왼쪽 조직 및 업무안내 표에서 전체 ":
        ". Bạn có thể xem tất cả ",
      "명의 업무별 연락처를 확인할 수 있습니다.":
        " liên hệ theo nghiệp vụ trong bảng tổ chức bên trái.",
      "공식 조직 및 업무안내의 전체 ":
        "Tôi đã mở bảng tổ chức và công việc chính thức với ",
      "명 표를 열고 대표 연락처 행을 확인했습니다.":
        " dòng và làm nổi bật hàng liên hệ chính.",
      "공동주택과 공식 스냅샷을 불러오지 못했습니다.":
        "Không thể tải ảnh chụp chính thức phòng Quản lý nhà chung cư.",

      "불법 주정차 신고 경로를 안내해 드립니다.":
        "Đây là đường dẫn báo cáo đỗ xe trái phép.",
      "지도단속 안내 화면으로 이동합니다.":
        "Chuyển đến màn hình kiểm tra qua bản đồ.",
      "안전신문고 등 공식 신고 채널을 안내합니다.":
        "Kênh báo cáo chính thức là Safety Report (safetyreport.go.kr).",
      "안내를 마쳤습니다. 실제 신고는 안전신문고(safetyreport.go.kr)에서 가능합니다.":
        "Kết thúc hướng dẫn. Báo cáo thật thực hiện qua Safety Report (safetyreport.go.kr).",
      "대형폐기물 배출방법 경로를 안내해 드립니다.":
        "Đây là đường dẫn xử lý rác cồng kềnh.",
      "대형폐기물 배출방법 페이지로 이동합니다.":
        "Chuyển đến trang xử lý rác cồng kềnh.",
      "전화 신고와 여기로 신청 경로를 안내합니다.":
        "Tôi sẽ hướng dẫn đường dây báo cáo qua điện thoại và nộp trực tuyến.",
      "안내를 마쳤습니다. 실제 신청은 여기로 앱 또는 북구청 홈페이지에서 가능합니다.":
        "Kết thúc hướng dẫn. Nộp thật qua ứng dụng hoặc trang chủ Bukgu-gu.",
      "여권 발급 경로를 안내해 드립니다.": "Đây là đường dẫn cấp hộ chiếu.",
      "종합민원 메뉴를 확인합니다.": "Mở menu Dịch vụ công tổng hợp.",
      "종합민원 페이지로 이동합니다.": "Chuyển đến trang Dịch vụ công tổng hợp.",
      "여권민원 안내 화면으로 이동합니다.": "Chuyển đến màn hình hướng dẫn hộ chiếu.",
      "여권민원 안내를 확인합니다. 여권 수수료표, 구비서류, 신청안내를 보실 수 있습니다. 실제 여권 신청은 북구청 민원실 방문 후 직접 진행해야 합니다.":
        "Đây là hướng dẫn hộ chiếu: biểu phí, giấy tờ cần thiết và thông tin nộp. Nộp hộ chiếu thật cần đến trực tiếp bộ phận một cửa Bukgu-gu.",
      "안내를 마쳤습니다. 실제 여권 신청은 북구청 민원실 또는 정부24에서 가능합니다.":
        "Kết thúc hướng dẫn. Nộp hộ chiếu thật tại bộ phận một cửa Bukgu-gu hoặc Chính phủ24.",
      "무인민원발급기 이용 경로를 안내해 드립니다.":
        "Đây là đường dẫn máy cấp giấy tờ tự động.",
      "무인민원발급기 안내 화면으로 이동합니다.":
        "Chuyển đến màn hình hướng dẫn máy tự động.",
      "무인민원발급기 안내를 확인합니다. 설치장소, 발급종류, 이용방법을 보실 수 있습니다. 실제 서류 발급은 현장에서 본인인증 후 직접 진행해야 합니다.":
        "Đây là hướng dẫn máy tự động: vị trí, loại giấy tờ, cách dùng. Cấp giấy tờ thật cần xác thực tại chỗ.",
      "안내를 마쳤습니다. 실제 이용은 북구청 및 각 행정복지센터에 설치된 무인민원발급기에서 가능합니다.":
        "Kết thúc hướng dẫn. Dùng thật tại máy tự động ở cơ quan Bukgu-gu và trung tâm phúc lợi.",
      "쓰레기 무단투기 신고 작성을 도와드립니다.":
        "Tôi sẽ giúp bạn soạn báo cáo vứt rác bừa bãi.",
      "민원게시판의 글쓰기 양식으로 이동합니다.":
        "Chuyển đến form viết của bảng tiếp nhận khiếu nại.",
      "직접 작성하시겠습니까, 아니면 AI가 초안 작성을 도와드릴까요?":
        "Bạn muốn tự viết, hay để AI hỗ trợ soạn thảo?",
      "AI 도움을 선택하셨습니다. 글쓰기 버튼을 누르고 양식을 열겠습니다. 어떤 불편사항인지 편하게 말씀해 주세요.":
        "Bạn chọn nhờ AI. Tôi sẽ nhấn viết và mở form. Hãy thoải mái nói tình trạng khó chịu.",
      "집 앞 공원에 쓰레기가 너무 많고 냄새가 나요. 빨리 치워주세요.":
        "Công viên trước nhà tôi có quá nhiều rác và bốc mùi. Xin hãy dọn sớm.",
      "말씀하신 내용을 바탕으로 민원 접수 양식에 맞게 초안을 작성합니다...":
        "Soạn bản nháp phù hợp form tiếp nhận, dựa trên lời bạn...",
      "먼저 민원 제목을 입력합니다.": "Đầu tiên, nhập tiêu đề khiếu nại.",
      "이어서 주민의 표현을 정중하고 구체적인 민원 문장으로 다듬어 본문에 입력합니다.":
        "Tiếp theo, trau chuốt lời bạn thành câu khiếu nại lịch sự, cụ thể cho nội dung.",
      "작성된 초안을 확인한 뒤 오른쪽의 [검토했고, 제출하기]를 선택해 주세요. 확인 전에는 제출되지 않습니다.":
        "Xem lại bản nháp, rồi chọn [Đã xem xét, gửi đi] bên phải. Chưa xác nhận thì chưa gửi.",

      "잠시만 기다려 주세요...": "Xin vui lòng đợi một chút...",
      "게시판으로 이동 중입니다...": "Đang chuyển đến bảng...",
      "양식을 준비 중입니다...": "Đang chuẩn bị form...",
      "제목을 다듬는 중입니다...": "Đang trau chuốt tiêu đề...",
      "민원 문장을 작성하는 중입니다...": "Đang soạn văn bản khiếu nại...",
      "북구청 사이트에 접속 중입니다...": "Đang kết nối trang Bukgu-gu...",
      "신고 채널 정보를 확인 중입니다...": "Đang kiểm tra kênh báo cáo...",
      "안전신문고 사이트를 검색 중입니다...": "Đang tìm kiếm Safety Report...",
      "북구청 메뉴를 살펴보는 중입니다...": "Đang xem menu Bukgu-gu...",
      "담당 부서 경로를 찾는 중입니다...": "Đang tìm phòng phụ trách...",
      "부서 검색을 준비하는 중입니다...": "Đang chuẩn bị tìm kiếm phòng ban...",
      "공동주택 관련 부서를 검색 중입니다...":
        "Đang tìm phòng liên quan nhà chung cư...",
      "공식 결과를 확인하는 중입니다...": "Đang kiểm tra kết quả chính thức...",
      "대형폐기물 페이지를 불러오는 중입니다...": "Đang tải trang rác cồng kềnh...",
      "배출 방법 정보를 확인 중입니다...": "Đang kiểm tra thông tin xử lý...",
      "메뉴를 탐색 중입니다...": "Đang khám phá menu...",
      "여권민원 안내 화면을 찾는 중입니다...": "Đang tìm màn hình hướng dẫn hộ chiếu...",
      "여권 발급 관련 정보를 검색 중입니다...": "Đang tìm thông tin hộ chiếu...",
      "여권 발급 정보를 확인 중입니다...": "Đang kiểm tra thông tin hộ chiếu...",
      "무인민원발급기 정보 페이지를 불러오는 중입니다...":
        "Đang tải trang thông tin máy tự động...",
      "무인민원발급기 정보를 확인 중입니다...": "Đang kiểm tra thông tin máy tự động...",
      "제안 작성 화면을 준비 중입니다...": "Đang chuẩn bị màn hình soạn đề xuất...",
      "열린구청장실 경로를 찾는 중입니다...": "Đang tìm đường đến Cổng ý kiến quận trưởng...",
      "제안 작성 양식을 여는 중입니다...": "Đang mở form soạn đề xuất...",
      "제안의 핵심과 기대 효과를 분석하는 중입니다...":
        "Đang phân tích ý chính và lợi ích kỳ vọng...",
      "제목을 구체화하는 중입니다...": "Đang cụ thể hóa tiêu đề...",
      "설득력 있는 제안 문장을 작성하는 중입니다...":
        "Đang viết câu đề xuất thuyết phục...",
      "내용을 분석하고 윤문하는 중입니다...": "Đang phân tích và trau chuốt văn bản...",
      "핵심 내용을 제목으로 정리하는 중입니다...": "Đang tóm tắt ý chính thành tiêu đề...",
    }),

    th: Object.freeze({
      "구청장에게 전할 제안을 함께 작성하겠습니다.":
        "เรามาเขียนข้อเสนอถึงนายกเทศมนตรีเขตด้วยกัน",
      "주민의 문제 제기와 기대 효과가 잘 드러나도록 구정 제안 문장으로 정리합니다.":
        "ฉันจะเรียบเรียงประเด็นและผลลัพธ์ที่คาดหวังให้เป็นข้อความเสนอโครงการเขต",
      "먼저 제안 제목을 입력합니다.": "ก่อนอื่น ฉันจะกรอกหัวข้อข้อเสนอ",
      "현장 상황과 기대 효과를 담아 본문을 작성합니다.":
        "ตอนนี้ฉันจะเขียนเนื้อหาพร้อมสถานการณ์หน้างานและผลลัพธ์ที่คาดหวัง",
      "제안 초안을 완성했습니다. 위치 정보를 보완한 뒤 [검토했고, 제출하기]를 선택해 주세요.":
        "ร่างข้อเสนอเสร็จแล้ว เพิ่มตำแหน่งแล้วเลือก [ตรวจสอบแล้ว ส่งเรื่อง]",
      "한국어 초안 작성을 마쳤습니다. 공식 제출은 북구청 공식 채널에서 직접 확인하고 진행해 주세요.":
        "ร่างภาษาเกาหลีเสร็จเรียบร้อย โปรดตรวจสอบและส่งเรื่องผ่านช่องทางทางการของเขต Bukgu-gu โดยตรง",

      "가로등 고장 신고를 도와드립니다.":
        "ฉันจะช่วยคุณแจ้งโคมไฟถนนเสีย",
      "민원게시판으로 이동합니다.": "กำลังไปที่กระดานรับเรื่องราชการ",
      "글쓰기 버튼을 눌러 새 신고 양식을 엽니다.":
        "กดปุ่มเขียนเพื่อเปิดแบบฟอร์มแจ้งใหม่",
      "민원 제목을 입력합니다.": "กำลังกรอกหัวข้อเรื่องราชการ",
      "말씀하실 내용을 민원 문장으로 정리해 본문에 입력합니다.":
        "นำคำของคุณมาเขียนเป็นเรื่องราชการและเติมในเนื้อหา",
      "제목과 본문 초안을 입력했습니다. 대괄호 부분을 확인한 뒤 제출 여부를 선택해 주세요.":
        "ฉันกรอกหัวข้อและร่างเนื้อหาแล้ว ตรวจสอบส่วนในวงเล็บ แล้วเลือกว่าจะส่งเรื่องหรือไม่",
      "민원 초안 작성을 마쳤습니다. 실제 제출은 북구청 공식 채널에서 직접 진행해 주세요.":
        "ร่างเรื่องราชการเสร็จแล้ว โปรดส่งเรื่องผ่านช่องทางทางการของเขต Bukgu-gu โดยตรง",

      "공동주택 부서 정보를 안내해 드립니다.":
        "นี่คือข้อมูลแผนกอาคารชุด",
      "먼저 북구소개 메뉴를 열겠습니다.": "ก่อนอื่น เปิดเมนูแนะนำ Bukgu-gu",
      "구청안내에서 행정조직의 공동주택과를 찾습니다.":
        "กำลังหาแผนกอาคารชุดในโครงสร้างองค์กรปกครอง",
      "검색창에 공동주택을 입력하겠습니다.":
        "พิมพ์ 'อาคารชุด' ในช่องค้นหา",
      "입력한 검색어로 담당 부서를 조회합니다.":
        "ค้นหาแผนกที่รับผิดชอบตามคำที่คุณพิมพ์",
      "공동주택과 부서 대표전화는 ":
        "หมายเลขโทรศัพท์หลักของแผนกอาคารชุดคือ ",
      ", FAX는 ": " และหมายเลขแฟกซ์คือ ",
      "입니다. 왼쪽 조직 및 업무안내 표에서 전체 ":
        " คุณสามารถดูข้อมูลติดต่อทั้งหมด ",
      "명의 업무별 연락처를 확인할 수 있습니다.":
        " ตามสายงานในตารางองค์กรด้านซ้าย",
      "공식 조직 및 업무안내의 전체 ":
        "ฉันเปิดตารางองค์กรและงานทางการทั้งหมด ",
      "명 표를 열고 대표 연락처 행을 확인했습니다.":
        " แถว และเน้นแถวติดต่อหลักแล้ว",
      "공동주택과 공식 스냅샷을 불러오지 못했습니다.":
        "ไม่สามารถโหลดสแนปช็อตทางการของแผนกอาคารชุดได้",

      "불법 주정차 신고 경로를 안내해 드립니다.":
        "นี่คือเส้นทางแจ้งจอดรถผิดกฎหมาย",
      "지도단속 안내 화면으로 이동합니다.":
        "กำลังไปที่หน้าจัดการผ่านแผนที่",
      "안전신문고 등 공식 신고 채널을 안내합니다.":
        "ช่องทางแจ้งอย่างเป็นทางการคือ Safety Report (safetyreport.go.kr)",
      "안내를 마쳤습니다. 실제 신고는 안전신문고(safetyreport.go.kr)에서 가능합니다.":
        "จบคำแนะนำแล้ว การแจ้งจริงทำได้ผ่าน Safety Report (safetyreport.go.kr)",
      "대형폐기물 배출방법 경로를 안내해 드립니다.":
        "นี่คือเส้นทางทิ้งขยะชิ้นใหญ่",
      "대형폐기물 배출방법 페이지로 이동합니다.":
        "กำลังไปที่หน้าทิ้งขยะชิ้นใหญ่",
      "전화 신고와 여기로 신청 경로를 안내합니다.":
        "ฉันจะแสดงเส้นทางแจ้งทางโทรศัพท์และสมัครออนไลน์",
      "안내를 마쳤습니다. 실제 신청은 여기로 앱 또는 북구청 홈페이지에서 가능합니다.":
        "จบคำแนะนำแล้ว การสมัครจริงทำได้ผ่านแอปหรือเว็บไซต์เขต Bukgu-gu",
      "여권 발급 경로를 안내해 드립니다.": "นี่คือเส้นทางทำหนังสือเดินทาง",
      "종합민원 메뉴를 확인합니다.": "กำลังเปิดเมนูงานบริการประชาชนรวม",
      "종합민원 페이지로 이동합니다.": "กำลังไปที่หน้าบริการประชาชนรวม",
      "여권민원 안내 화면으로 이동합니다.": "กำลังไปที่หน้าคู่มือหนังสือเดินทาง",
      "여권민원 안내를 확인합니다. 여권 수수료표, 구비서류, 신청안내를 보실 수 있습니다. 실제 여권 신청은 북구청 민원실 방문 후 직접 진행해야 합니다.":
        "นี่คือคู่มือหนังสือเดินทาง: ตารางค่าธรรมเนียม เอกสารที่ต้องใช้ และข้อมูลการสมัคร การทำหนังสือเดินทางจริงต้องไปที่ศูนย์บริการเขต Bukgu-gu",
      "안내를 마쳤습니다. 실제 여권 신청은 북구청 민원실 또는 정부24에서 가능합니다.":
        "จบคำแนะนำแล้ว การทำหนังสือเดินทางจริงทำได้ที่ศูนย์บริการเขต Bukgu-gu หรือ Government24",
      "무인민원발급기 이용 경로를 안내해 드립니다.":
        "นี่คือเส้นทางเครื่องออกเอกสารอัตโนมัติ",
      "무인민원발급기 안내 화면으로 이동합니다.":
        "กำลังไปที่หน้าคู่มือเครื่องอัตโนมัติ",
      "무인민원발급기 안내를 확인합니다. 설치장소, 발급종류, 이용방법을 보실 수 있습니다. 실제 서류 발급은 현장에서 본인인증 후 직접 진행해야 합니다.":
        "นี่คือคู่มือเครื่องอัตโนมัติ: สถานที่ ประเภทเอกสาร และวิธีใช้ การออกเอกสารจริงต้องยืนยันตัวตนที่เครื่อง",
      "안내를 마쳤습니다. 실제 이용은 북구청 및 각 행정복지센터에 설치된 무인민원발급기에서 가능합니다.":
        "จบคำแนะนำแล้ว การใช้งานจริงอยู่ที่เครื่องอัตโนมัติในสำนักเขต Bukgu-gu และศูนย์บริการ",
      "쓰레기 무단투기 신고 작성을 도와드립니다.":
        "ฉันจะช่วยคุณเขียนแจ้งทิ้งขยะมิชอบ",
      "민원게시판의 글쓰기 양식으로 이동합니다.":
        "กำลังไปที่แบบฟอร์มเขียนของกระดานรับเรื่อง",
      "직접 작성하시겠습니까, 아니면 AI가 초안 작성을 도와드릴까요?":
        "คุณต้องการเขียนเอง หรือให้ AI ช่วยร่างให้?",
      "AI 도움을 선택하셨습니다. 글쓰기 버튼을 누르고 양식을 열겠습니다. 어떤 불편사항인지 편하게 말씀해 주세요.":
        "คุณเลือกให้ AI ช่วย ฉันจะกดเขียนและเปิดแบบฟอร์ม บอกอาการไม่สะดวกสบายได้เลย",
      "집 앞 공원에 쓰레기가 너무 많고 냄샨가 나요. 빨리 치워주세요.":
        "มีขยะมากเกินไปและเหม็นหน้าสวนใกล้บ้าน กรุณาเก็บกวาดโดยเร็ว",
      "말씀하신 내용을 바탕으로 민원 접수 양식에 맞게 초안을 작성합니다...":
        "กำลังร่างตามแบบฟอร์มรับเรื่องจากคำที่คุณพูด...",
      "먼저 민원 제목을 입력합니다.": "ก่อนอื่น กรอกหัวข้อเรื่องราชการ",
      "이어서 주민의 표현을 정중하고 구체적인 민원 문장으로 다듬어 본문에 입력합니다.":
        "ต่อมา ปรับคำของคุณให้เป็นประโยคเรื่องราชการสุภาพและชัดเจนสำหรับเนื้อหา",
      "작성된 초안을 확인한 뒤 오른쪽의 [검토했고, 제출하기]를 선택해 주세요. 확인 전에는 제출되지 않습니다.":
        "ตรวจสอบร่างแล้วเลือก [ตรวจสอบแล้ว ส่งเรื่อง] ด้านขวา ยังไม่ส่งก่อนคุณยืนยัน",

      "잠시만 기다려 주세요...": "โปรดรอสักครู่...",
      "게시판으로 이동 중입니다...": "กำลังไปที่กระดาน...",
      "양식을 준비 중입니다...": "กำลังเตรียมแบบฟอร์ม...",
      "제목을 다듬는 중입니다...": "กำลังปรับหัวข้อ...",
      "민원 문장을 작성하는 중입니다...": "กำลังเขียนประโยคเรื่องราชการ...",
      "북구청 사이트에 접속 중입니다...": "กำลังเชื่อมต่อเว็บไซต์เขต Bukgu-gu...",
      "신고 채널 정보를 확인 중입니다...": "กำลังตรวจสอบช่องทางแจ้ง...",
      "안전신문고 사이트를 검색 중입니다...": "กำลังค้นหา Safety Report...",
      "북구청 메뉴를 살펴보는 중입니다...": "กำลังดูเมนูเขต Bukgu-gu...",
      "담당 부서 경로를 찾는 중입니다...": "กำลังหาแผนกที่รับผิดชอบ...",
      "부서 검색을 준비하는 중입니다...": "กำลังเตรียมค้นหาแผนก...",
      "공동주택 관련 부서를 검색 중입니다...": "กำลังค้นหาแผนกอาคารชุด...",
      "공식 결과를 확인하는 중입니다...": "กำลังตรวจสอบผลทางการ...",
      "대형폐기물 페이지를 불러오는 중입니다...": "กำลังโหลดหน้าขยะชิ้นใหญ่...",
      "배출 방법 정보를 확인 중입니다...": "กำลังตรวจสอบข้อมูลการทิ้ง...",
      "메뉴를 탐색 중입니다...": "กำลังสำรวจเมนู...",
      "여권민원 안내 화면을 찾는 중입니다...": "กำลังหาหน้าคู่มือหนังสือเดินทาง...",
      "여권 발급 관련 정보를 검색 중입니다...": "กำลังค้นหาข้อมูลหนังสือเดินทาง...",
      "여권 발급 정보를 확인 중입니다...": "กำลังตรวจสอบข้อมูลหนังสือเดินทาง...",
      "무인민원발급기 정보 페이지를 불러오는 중입니다...":
        "กำลังโหลดหน้าข้อมูลเครื่องอัตโนมัติ...",
      "무인민원발급기 정보를 확인 중입니다...": "กำลังตรวจสอบข้อมูลเครื่องอัตโนมัติ...",
      "제안 작성 화면을 준비 중입니다...": "กำลังเตรียมหน้าจอเขียนข้อเสนอ...",
      "열린구청장실 경로를 찾는 중입니다...": "กำลังหาเส้นทางไปยังประตูรับฟังความคิดเห็นนายกเทศมนตรีเขต...",
      "제안 작성 양식을 여는 중입니다...": "กำลังเปิดแบบฟอร์มเขียนข้อเสนอ...",
      "제안의 핵심과 기대 효과를 분석하는 중입니다...":
        "กำลังวิเคราะห์ใจความสำคัญและผลลัพธ์ที่คาดหวัง...",
      "제목을 구체화하는 중입니다...": "กำลังทำให้หัวข้อเฉพาะเจาะจง...",
      "설득력 있는 제안 문장을 작성하는 중입니다...":
        "กำลังเขียนประโยคข้อเสนอที่น่ากล่อมใจ...",
      "내용을 분석하고 윤문하는 중입니다...": "กำลังวิเคราะห์และปรับแก้ข้อความ...",
      "핵심 내용을 제목으로 정리하는 중입니다...": "กำลังสรุปใจความสำคัญเป็นหัวข้อ...",
    }),

    id: Object.freeze({
      "구청장에게 전할 제안을 함께 작성하겠습니다.":
        "Mari kita susun usulan kepada bupati bersama-sama.",
      "주민의 문제 제기와 기대 효과가 잘 드러나도록 구정 제안 문장으로 정리합니다.":
        "Saya akan menyusun pokok masalah dan manfaat yang diharapkan menjadi kalimat usulan kabupaten yang jelas.",
      "먼저 제안 제목을 입력합니다.": "Pertama, saya isi judul usulan.",
      "현장 상황과 기대 효과를 담아 본문을 작성합니다.":
        "Sekarang saya tulis isi dengan situasi lapangan dan manfaat yang diharapkan.",
      "제안 초안을 완성했습니다. 위치 정보를 보완한 뒤 [검토했고, 제출하기]를 선택해 주세요.":
        "Draf usulan sudah siap. Lengkapi lokasi, lalu pilih [Sudah diperiksa, kirim].",
      "한국어 초안 작성을 마쳤습니다. 공식 제출은 북구청 공식 채널에서 직접 확인하고 진행해 주세요.":
        "Draf bahasa Korea sudah selesai. Harap verifikasi dan kirim melalui saluran resmi Bukgu-gu secara langsung.",

      "가로등 고장 신고를 도와드립니다.":
        "Saya akan bantu Anda melaporkan lampu jalan rusak.",
      "민원게시판으로 이동합니다.": "Pindah ke papan pengaduan warga.",
      "글쓰기 버튼을 눌러 새 신고 양식을 엽니다.":
        "Tekan tombol tulis untuk membuka formulir laporan baru.",
      "민원 제목을 입력합니다.": "Mengisi judul pengaduan.",
      "말씀하실 내용을 민원 문장으로 정리해 본문에 입력합니다.":
        "Mengubah kata Anda menjadi kalimat pengaduan dan mengisinya ke isi.",
      "제목과 본문 초안을 입력했습니다. 대괄호 부분을 확인한 뒤 제출 여부를 선택해 주세요.":
        "Saya telah isi judul dan draf isi. Periksa bagian dalam kurung siku, lalu pilih kirim atau tidak.",
      "민원 초안 작성을 마쳤습니다. 실제 제출은 북구청 공식 채널에서 직접 진행해 주세요.":
        "Draf pengaduan sudah selesai. Harap kirim melalui saluran resmi Bukgu-gu secara langsung.",

      "공동주택 부서 정보를 안내해 드립니다.":
        "Berikut informasi departemen perumahan.",
      "먼저 북구소개 메뉴를 열겠습니다.": "Pertama, buka menu Perkenalan Bukgu.",
      "구청안내에서 행정조직의 공동주택과를 찾습니다.":
        "Mencari Divisi Perumahan dalam struktur organisasi administrasi.",
      "검색창에 공동주택을 입력하겠습니다.":
        "Mengetik 'perumahan' di kotak pencarian.",
      "입력한 검색어로 담당 부서를 조회합니다.":
        "Mencari departemen terkait berdasarkan kata kunci yang Anda ketik.",
      "공동주택과 부서 대표전화는 ":
        "Nomor telepon utama Divisi Perumahan adalah ",
      ", FAX는 ": ", dan nomor faks adalah ",
      "입니다. 왼쪽 조직 및 업무안내 표에서 전체 ":
        ". Anda dapat melihat semua ",
      "명의 업무별 연락처를 확인할 수 있습니다.":
        " kontak per bidang di tabel organisasi di kiri.",
      "공식 조직 및 업무안내의 전체 ":
        "Saya telah membuka tabel organisasi dan tugas resmi dengan ",
      "명 표를 열고 대표 연락처 행을 확인했습니다.":
        " baris dan menyoroti baris kontak utama.",
      "공동주택과 공식 스냅샷을 불러오지 못했습니다.":
        "Tidak dapat memuat snapshot resmi Divisi Perumahan.",

      "불법 주정차 신고 경로를 안내해 드립니다.":
        "Berikut jalur laporan parkir liar.",
      "지도단속 안내 화면으로 이동합니다.":
        "Pindah ke layar penertiban lewat peta.",
      "안전신문고 등 공식 신고 채널을 안내합니다.":
        "Saluran pelaporan resmi adalah Safety Report (safetyreport.go.kr).",
      "안내를 마쳤습니다. 실제 신고는 안전신문고(safetyreport.go.kr)에서 가능합니다.":
        "Panduan selesai. Laporan nyata dilakukan melalui Safety Report (safetyreport.go.kr).",
      "대형폐기물 배출방법 경로를 안내해 드립니다.":
        "Berikut jalur pembuangan sampah besar.",
      "대형폐기물 배출방법 페이지로 이동합니다.":
        "Pindah ke halaman pembuangan sampah besar.",
      "전화 신고와 여기로 신청 경로를 안내합니다.":
        "Saya akan tunjukkan jalur lapor via telepon dan pendaftaran daring.",
      "안내를 마쳤습니다. 실제 신청은 여기로 앱 또는 북구청 홈페이지에서 가능합니다.":
        "Panduan selesai. Pendaftaran nyata melalui aplikasi atau situs web Bukgu-gu.",
      "여권 발급 경로를 안내해 드립니다.": "Berikut jalur pembuatan paspor.",
      "종합민원 메뉴를 확인합니다.": "Membuka menu Layanan Publik Terpadu.",
      "종합민원 페이지로 이동합니다.": "Pindah ke halaman Layanan Publik Terpadu.",
      "여권민원 안내 화면으로 이동합니다.": "Pindah ke layar panduan paspor.",
      "여권민원 안내를 확인합니다. 여권 수수료표, 구비서류, 신청안내를 보실 수 있습니다. 실제 여권 신청은 북구청 민원실 방문 후 직접 진행해야 합니다.":
        "Berikut panduan paspor: tabel biaya, dokumen, dan info pendaftaran. Pembuatan paspor nyata harus datang langsung ke loket Bukgu-gu.",
      "안내를 마쳤습니다. 실제 여권 신권은 북구청 민원실 또는 정부24에서 가능합니다.":
        "Panduan selesai. Pembuatan paspor nyata di loket Bukgu-gu atau Government24.",
      "무인민원발급기 이용 경로를 안내해 드립니다.":
        "Berikut jalur mesin layanan mandiri.",
      "무인민원발급기 안내 화면으로 이동합니다.":
        "Pindah ke layar panduan mesin mandiri.",
      "무인민원발급기 안내를 확인합니다. 설치장소, 발급종류, 이용방법을 보실 수 있습니다. 실제 서류 발급은 현장에서 본인인증 후 직접 진행해야 합니다.":
        "Berikut panduan mesin mandiri: lokasi, jenis dokumen, cara pakai. Penerbitan dokumen nyata butuh verifikasi di tempat.",
      "안내를 마쳤습니다. 실제 이용은 북구청 및 각 행정복지센터에 설치된 무인민원발급기에서 가능합니다.":
        "Panduan selesai. Pemakaian nyata di mesin mandiri di kantor Bukgu-gu dan pusat layanan.",
      "쓰레기 무단투기 신고 작성을 도와드립니다.":
        "Saya akan bantu menyusun laporan membuang sampah sembarangan.",
      "민원게시판의 글쓰기 양식으로 이동합니다.":
        "Pindah ke formulir tulis papan pengaduan.",
      "직접 작성하시겠습니까, 아니면 AI가 초안 작성을 도와드릴까요?":
        "Apakah Anda ingin menulis sendiri, atau saya bantu buatkan drafnya dengan AI?",
      "AI 도움을 선택하셨습니다. 글쓰기 버튼을 누르고 양식을 열겠습니다. 어떤 불편사항인지 편하게 말씀해 주세요.":
        "Anda memilih bantuan AI. Saya tekan tulis dan buka formulir. Ceritakan saja keluhan Anda.",
      "집 앞 공원에 쓰레기가 너무 많고 냄새가 나요. 빨리 치워주세요.":
        "Sampah di taman dekat rumah saya terlalu banyak dan berbau. Tolong segera bersihkan.",
      "말씀하신 내용을 바탕으로 민원 접수 양식에 맞게 초안을 작성합니다...":
        "Menyusun draf sesuai formulir penerimaan dari kata Anda...",
      "먼저 민원 제목을 입력합니다.": "Pertama, isi judul pengaduan.",
      "이어서 주민의 표현을 정중하고 구체적인 민원 문장으로 다듬어 본문에 입력합니다.":
        "Lalu rapikan kata Anda menjadi kalimat pengaduan yang sopan dan rinci untuk isi.",
      "작성된 초안을 확인한 뒤 오른쪽의 [검토했고, 제출하기]를 선택해 주세요. 확인 전에는 제출되지 않습니다.":
        "Periksa draf, lalu pilih [Sudah diperiksa, kirim] di kanan. Belum dikirim sebelum Anda konfirmasi.",

      "잠시만 기다려 주세요...": "Mohon tunggu sebentar...",
      "게시판으로 이동 중입니다...": "Pindah ke papan...",
      "양식을 준비 중입니다...": "Menyiapkan formulir...",
      "제목을 다듬는 중입니다...": "Merapikan judul...",
      "민원 문장을 작성하는 중입니다...": "Menulis kalimat pengaduan...",
      "북구청 사이트에 접속 중입니다...": "Menghubungkan ke situs Bukgu-gu...",
      "신고 채널 정보를 확인 중입니다...": "Memeriksa saluran pelaporan...",
      "안전신문고 사이트를 검색 중입니다...": "Mencari Safety Report...",
      "북구청 메뉴를 살펴보는 중입니다...": "Menelusuri menu Bukgu-gu...",
      "담당 부서 경로를 찾는 중입니다...": "Mencari departemen terkait...",
      "부서 검색을 준비하는 중입니다...": "Menyiapkan pencarian departemen...",
      "공동주택 관련 부서를 검색 중입니다...": "Mencari departemen perumahan...",
      "공식 결과를 확인하는 중입니다...": "Memeriksa hasil resmi...",
      "대형폐기물 페이지를 불러오는 중입니다...": "Memuat halaman sampah besar...",
      "배출 방법 정보를 확인 중입니다...": "Memeriksa info pembuangan...",
      "메뉴를 탐색 중입니다...": "Menjelajahi menu...",
      "여권민원 안내 화면을 찾는 중입니다...": "Mencari layar panduan paspor...",
      "여권 발급 관련 정보를 검색 중입니다...": "Mencari info paspor...",
      "여권 발급 정보를 확인 중입니다...": "Memeriksa info paspor...",
      "무인민원발급기 정보 페이지를 불러오는 중입니다...":
        "Memuat halaman info mesin mandiri...",
      "무인민원발급기 정보를 확인 중입니다...": "Memeriksa info mesin mandiri...",
      "제안 작성 화면을 준비 중입니다...": "Menyiapkan layar penyusunan usulan...",
      "열린구청장실 경로를 찾는 중입니다...": "Mencari jalur ke Ruang Aspirasi Bupati...",
      "제안 작성 양식을 여는 중입니다...": "Membuka formulir penyusunan usulan...",
      "제안의 핵심과 기대 효과를 분석하는 중입니다...":
        "Menganalisis inti dan manfaat yang diharapkan...",
      "제목을 구체화하는 중입니다...": "Memperjelas judul...",
      "설득력 있는 제안 문장을 작성하는 중입니다...":
        "Menulis kalimat usulan yang meyakinkan...",
      "내용을 분석하고 윤문하는 중입니다...": "Menganalisis dan merapikan teks...",
      "핵심 내용을 제목으로 정리하는 중입니다...": "Merangkum inti menjadi judul...",
    }),
  });

  // ── Foreign-language resident utterances (per #1143 §11) ────────
  // The resident speaks in their own language; the Korean administrative
  // draft is generated separately and stays Korean.
  var RESIDENT = Object.freeze({
    ko: "학교 앞 횡단보도가 밤에 너무 어둡습니다.\n아이들이 안전하게 건널 수 있도록 조명을 개선해 주세요.",
    en: "The crosswalk in front of the school is too dark at night.\nPlease improve the lighting so children can cross safely.",
    vi: "Lối qua đường trước trường quá tối vào ban đêm.\nXin hãy cải thiện hệ thống chiếu sáng để trẻ em có thể qua đường an toàn.",
    th: "ทางม้าลายหน้าโรงเรียนมืดเกินไปในเวลากลางคืน\nกรุณาปรับปรุงแสงสว่างเพื่อให้เด็ก ๆ ข้ามถนนได้อย่างปลอดภัย",
    id: "Penyeberangan di depan sekolah terlalu gelap pada malam hari.\nMohon tingkatkan penerangannya agar anak-anak dapat menyeberang dengan aman.",
  });

  var state = { locale: "ko" };
  var subscribers = [];

  function isSupported(value) {
    return SUPPORTED.indexOf(value) !== -1;
  }

  function normalizeLocale(value) {
    if (!value || typeof value !== "string") return "ko";
    var v = value.trim().toLowerCase();
    return isSupported(v) ? v : "ko";
  }

  function supportedLocales() {
    return SUPPORTED.slice();
  }

  function localeName(value) {
    var loc = normalizeLocale(value);
    return LOCALE_NAMES[loc] || LOCALE_NAMES.ko;
  }

  function getLocale() {
    return state.locale;
  }

  function setLocale(locale) {
    var next = normalizeLocale(locale);
    if (next === state.locale) return next;
    state.locale = next;
    return next;
  }

  function _uiTable(locale) {
    return UI[locale] || UI.ko;
  }

  function t(key) {
    if (typeof key !== "string") return "";
    var loc = state.locale;
    var table = _uiTable(loc);
    if (Object.prototype.hasOwnProperty.call(table, key) && table[key] != null) {
      return table[key];
    }
    var koTable = UI.ko;
    if (Object.prototype.hasOwnProperty.call(koTable, key) && koTable[key] != null) {
      return koTable[key];
    }
    return key;
  }

  // Translate a frozen Korean journey narration string into the active
  // locale; returns the original Korean when no translation exists.
  function translateMessage(koText) {
    if (typeof koText !== "string") return koText;
    var loc = state.locale;
    if (loc === "ko") return koText;
    var map = JOURNEY[loc];
    if (map && Object.prototype.hasOwnProperty.call(map, koText)) {
      return map[koText];
    }
    return koText;
  }

  // The resident's own-language utterance for the active locale.
  function getResidentMessage() {
    var loc = state.locale;
    return RESIDENT[loc] || RESIDENT.ko;
  }

  function setDocumentLang() {
    if (typeof document === "undefined" || !document.documentElement) return;
    document.documentElement.lang = state.locale;
  }

  function readLangFromUrl() {
    try {
      var params = new URLSearchParams(window.location.search || "");
      return normalizeLocale(params.get("lang"));
    } catch (_) {
      return "ko";
    }
  }

  // Update the URL `lang` param, preserving all other params (mvp, journey,
  // dept-state, replay, etc.). Uses replaceState so language switches do not
  // flood browser history.
  function syncUrlLang(locale, opts) {
    opts = opts || {};
    try {
      var url = new URL(window.location.href);
      url.searchParams.set("lang", locale);
      if (opts.replace === false && window.history && history.pushState) {
        history.pushState({}, "", url.toString());
      } else if (window.history && history.replaceState) {
        history.replaceState({}, "", url.toString());
      }
    } catch (_) {
      /* URL sync is an enhancement; locale state still applies. */
    }
  }

  function initFromUrl() {
    setLocale(readLangFromUrl());
    setDocumentLang();
  }

  function onLocaleChange(cb) {
    if (typeof cb === "function") subscribers.push(cb);
  }

  function _notify() {
    for (var i = 0; i < subscribers.length; i++) {
      try {
        subscribers[i](state.locale);
      } catch (_) {
        /* ignore subscriber errors */
      }
    }
  }

  // Apply a locale change: update state, document lang, URL, and notify
  // subscribers (the shell resets its journey on change).
  function applyLocale(locale, opts) {
    opts = opts || {};
    var next = setLocale(locale);
    setDocumentLang();
    if (opts.syncUrl !== false) syncUrlLang(next, opts);
    _notify();
    return next;
  }

  function getJourneyCopy() {
    return Object.freeze({
      locale: state.locale,
      translate: translateMessage,
      resident: getResidentMessage,
      t: t,
    });
  }

  window.CitizenI18n = Object.freeze({
    supportedLocales: supportedLocales,
    normalizeLocale: normalizeLocale,
    getLocale: getLocale,
    setLocale: setLocale,
    t: t,
    getJourneyCopy: getJourneyCopy,
    // ── extended API (URL + resident copy) ──
    localeName: localeName,
    translateMessage: translateMessage,
    getResidentMessage: getResidentMessage,
    setDocumentLang: setDocumentLang,
    readLangFromUrl: readLangFromUrl,
    syncUrlLang: syncUrlLang,
    initFromUrl: initFromUrl,
    onLocaleChange: onLocaleChange,
    applyLocale: applyLocale,
  });
})();
