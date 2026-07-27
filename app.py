import streamlit as st
from supabase import create_client, Client
import os
import json

# ==========================================
# 1. CẤU HÌNH TRANG VÀ KẾT NỐI SUPABASE (AN TOÀN LOCAL & CLOUD)
# ==========================================
st.set_page_config(
    page_title="Novel Studio - AI Assistant",
    page_icon="📖",
    layout="wide"
)

# Lấy Secrets an toàn (không bị crash nếu chạy local/Codespaces chưa tạo secrets)
SUPABASE_URL = ""
SUPABASE_KEY = ""

try:
    if "SUPABASE_URL" in st.secrets:
        SUPABASE_URL = st.secrets["SUPABASE_URL"]
    if "SUPABASE_KEY" in st.secrets:
        SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    pass

@st.cache_resource
def init_supabase():
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception:
            return None
    return None

supabase = init_supabase()

# Khởi tạo Session State cho ứng dụng
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "novel_data" not in st.session_state:
    st.session_state.novel_data = {
        "api_keys": {"openai": "", "gemini": "", "groq": ""},
        "genre": "",
        "setting": "",
        "characters": "",
        "outline": "",
        "raw_docs": [],
        "interview_history": [],
        "chapters": {}
    }

# SYSTEM PROMPT BẮT BUỘC VỀ VĂN PHONG
STYLE_PROMPT = """
[YÊU CẦU VỀ VĂN PHONG VÀ CÁCH HÀNH VĂN] 
- Tuyệt đối KHÔNG sử dụng từ ngữ hoa mỹ, phô trương, cường điệu hay lãng mạn hóa quá mức (tránh xa các từ ngữ kiểu ngôn tình sến sẩm, ví dụ: đau xé tâm can, tuyệt mỹ, kinh thiên động địa, ánh mắt sắc bén như dao cau...). 
- Giữ giọng văn mộc mạc, gần gũi, mang đậm chất đời thường và hơi thở thực tế của bối cảnh. 
- Giữ nhịp điệu kể chuyện tỉnh táo: Kể sự việc theo lối "thấy sao nói vậy", để nhân vật quan sát sự việc bằng con mắt thực tế, không lý tưởng hóa hoàn cảnh hay nhân vật. 
- Nhịp câu ngắn gọn, gãy gọn, tập trung vào hành động thực tế, sinh hoạt phí hằng ngày và tâm lý nhân vật một cách tỉnh táo, thực dụng. 
- Lời thoại và độc thoại nội tâm phải tự nhiên, đứng ở vị thế là ngôi kể thứ ba. 
- Nhân vật phản ứng theo logic thông thường của con người trong hoàn cảnh đó. 
"""

# ==========================================
# 2. XÁC THỰC TÀI KHOẢN (AUTH)
# ==========================================
if not st.session_state.authenticated:
    st.title("☁️ Đăng nhập Novel Studio")
    st.caption("Ứng dụng tự động đồng bộ tiểu thuyết và dữ liệu của bạn.")
    
    tab_login, tab_signup = st.tabs(["🔑 Đăng nhập", "📝 Đăng ký mới"])
    
    with tab_login:
        email = st.text_input("Email đăng nhập:", key="login_email")
        password = st.text_input("Mật khẩu:", type="password", key="login_pass")
        if st.button("🚀 Đăng nhập"):
            if supabase:
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.authenticated = True
                    st.session_state.user_email = email
                    st.success("Đăng nhập thành công!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi đăng nhập: {e}")
            else:
                # Nếu chưa cấu hình Supabase vẫn cho phép đăng nhập thử nghiệm
                st.session_state.authenticated = True
                st.session_state.user_email = email
                st.warning("Đã vào chế độ dùng thử Local (Chưa kết nối Supabase).")
                st.rerun()

    with tab_signup:
        s_email = st.text_input("Email đăng ký:", key="signup_email")
        s_password = st.text_input("Mật khẩu (ít nhất 6 ký tự):", type="password", key="signup_pass")
        if st.button("Tạo tài khoản"):
            if supabase:
                try:
                    res = supabase.auth.sign_up({"email": s_email, "password": s_password})
                    st.success("Tạo tài khoản thành công! Bạn có thể đăng nhập ngay.")
                except Exception as e:
                    st.error(f"Lỗi đăng ký: {e}")
            else:
                st.error("Chưa cấu hình Supabase URL/Key trong secrets nên không thể đăng ký mới.")

    st.stop()

# ==========================================
# 3. GIAO DIỆN CHÍNH - NOVEL STUDIO WORKSPACE
# ==========================================
st.sidebar.title("📖 Novel Studio")
st.sidebar.write(f"👤 **{st.session_state.user_email}**")

if st.sidebar.button("🚪 Đăng xuất"):
    st.session_state.authenticated = False
    st.session_state.user_email = ""
    st.rerun()

st.sidebar.divider()

# Menu chức năng
menu = st.sidebar.radio(
    "Điều hướng quy trình:",
    [
        "1. Cấu hình API Keys",
        "2. Tải lên RAW Reference",
        "3. AI Phỏng vấn (Bối cảnh & Nhân vật)",
        "4. Lập Dàn ý & Bố cục",
        "5. AI Viết nháp & Chỉnh sửa",
        "6. Hoàn thiện & Xuất bộ truyện"
    ]
)

# ==========================================
# PHẦN 1: CẤU HÌNH API KEYS
# ==========================================
if menu == "1. Cấu hình API Keys":
    st.header("🔑 Cấu hình các kết nối API AI")
    st.info("Nhập các API Key của bạn để ứng dụng kết nối trực tiếp với các mô hình AI.")

    col1, col2 = st.columns(2)
    with col1:
        openai_key = st.text_input(
            "OpenAI API Key (GPT-4o/GPT-4o-mini):", 
            value=st.session_state.novel_data["api_keys"].get("openai", ""),
            type="password"
        )
        gemini_key = st.text_input(
            "Google Gemini API Key:", 
            value=st.session_state.novel_data["api_keys"].get("gemini", ""),
            type="password"
        )
    with col2:
        groq_key = st.text_input(
            "Groq API Key (Llama 3 / DeepSeek):", 
            value=st.session_state.novel_data["api_keys"].get("groq", ""),
            type="password"
        )
        selected_model = st.selectbox(
            "Mô hình AI ưu tiên xử lý:",
            ["OpenAI GPT-4o", "Google Gemini 1.5 Pro", "Groq Llama-3"]
        )

    if st.button("💾 Lưu Cấu Hình API"):
        st.session_state.novel_data["api_keys"] = {
            "openai": openai_key,
            "gemini": gemini_key,
            "groq": groq_key,
            "selected_model": selected_model
        }
        st.success("Đã lưu cấu hình API thành công!")

# ==========================================
# PHẦN 2: TẢI LÊN RAW REFERENCE
# ==========================================
elif menu == "2. Tải lên RAW Reference":
    st.header("📚 Tải lên bộ Raw Tham Khảo & Văn Phong")
    st.write("Tải lên 2-3 bộ RAW (hoặc nhiều hơn) dạng `.txt` để AI phân tích cốt truyện, văn phong mẫu và gợi ý ý tưởng.")

    uploaded_files = st.file_uploader(
        "Chọn các tệp Raw tham khảo (.txt, .md):", 
        type=["txt", "md"], 
        accept_multiple_files=True
    )

    if uploaded_files:
        for file in uploaded_files:
            content = file.read().decode("utf-8", errors="ignore")
            st.session_state.novel_data["raw_docs"].append({
                "filename": file.name,
                "content": content[:5000] # Giới hạn lưu ký tự xem trước
            })
        st.success(f"Đã tải lên {len(uploaded_files)} tệp Raw tham khảo!")

    if st.session_state.novel_data["raw_docs"]:
        st.subheader("📋 Danh sách Raw đã tải lên:")
        for idx, doc in enumerate(st.session_state.novel_data["raw_docs"]):
            st.write(f"- **{doc['filename']}** ({len(doc['content'])} ký tự mẫu)")

# ==========================================
# PHẦN 3: AI PHỎNG VẤN VÀ XÂY DỰNG NHÂN VẬT
# ==========================================
elif menu == "3. AI Phỏng vấn (Bối cảnh & Nhân vật)":
    st.header("🤖 AI Phỏng vấn Trợ lý Biên tập")
    st.write("AI sẽ đóng vai trò Biên tập viên, chủ động đặt các câu hỏi để giúp bạn định hình: *Thể loại, Bối cảnh, Nhân vật, Cốt truyện*.")

    # Hiển thị lịch sử hội thoại phỏng vấn
    for msg in st.session_state.novel_data["interview_history"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if not st.session_state.novel_data["interview_history"]:
        initial_prompt = "Xin chào! Tôi là Trợ lý Biên tập AI. Để bắt đầu xây dựng bộ tiểu thuyết, hãy cho tôi biết: Bạn muốn viết thể loại gì (ví dụ: Đô thị thực tế, Mạt thế, Trinh thám...) và ý tưởng sơ khởi ban đầu của bạn là gì?"
        st.session_state.novel_data["interview_history"].append({"role": "assistant", "content": initial_prompt})
        st.rerun()

    user_input = st.chat_input("Trả lời câu hỏi của AI hoặc đưa ra yêu cầu...")
    if user_input:
        st.session_state.novel_data["interview_history"].append({"role": "user", "content": user_input})
        
        # Mô phỏng AI phỏng vấn liên tục theo ngữ cảnh
        ai_reply = f"[AI Editor]: Cảm ơn thông tin của bạn. Dựa trên ý tưởng '{user_input}', hãy cho tôi biết thêm:\n1. Mức thu nhập, công việc và hoàn cảnh sống thực tế của nhân vật chính là gì?\n2. Mâu thuẫn đời sống lớn nhất mà nhân vật phải đối mặt trong 3 chương đầu là gì?"
        st.session_state.novel_data["interview_history"].append({"role": "assistant", "content": ai_reply})
        st.rerun()

# ==========================================
# PHẦN 4: LẬP DÀN Ý & BỐ CỤC
# ==========================================
elif menu == "4. Lập Dàn ý & Bố cục":
    st.header("📌 Dàn ý Chi tiết & Cốt truyện Từng Chương")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("🪄 AI Tạo Dàn Ý Tự Động"):
            st.session_state.novel_data["outline"] = """Chương 1: Bữa cơm tối đắt đỏ và quyết định nghỉ việc.
Chương 2: Căn phòng trọ thuê lại và vết nứt trong mối quan hệ.
Chương 3: Lần đầu tiên đối mặt với cuộc sống tự do đầy áp lực.
Chương 4: Lựa chọn thực dụng trước món tiền bất ngờ."""
            st.success("Đã khởi tạo dàn ý!")

    with col2:
        outline_text = st.text_area(
            "Chỉnh sửa Dàn ý / Cấu trúc chương:", 
            value=st.session_state.novel_data["outline"], 
            height=300
        )
        st.session_state.novel_data["outline"] = outline_text

# ==========================================
# PHẦN 5: AI VIẾT NHÁP & CHỈNH SỬA TỪNG CHƯƠNG
# ==========================================
elif menu == "5. AI Viết nháp & Chỉnh sửa":
    st.header("✍️ AI Viết Nháp & Sửa Đổi Từng Chương")
    st.caption("Mọi văn bản viết nháp đều bắt buộc tuân thủ Prompt Văn phong chuẩn.")

    # Hiển thị Prompt Văn phong bắt buộc
    with st.expander("🛡️ Quy chuẩn văn phong bắt buộc (Bật mặc định)", expanded=False):
        st.code(STYLE_PROMPT, language="markdown")

    chapter_num = st.number_input("Chọn chương cần viết / sửa:", min_value=1, value=1, step=1)
    chapter_key = f"Chương {chapter_num}"

    current_draft = st.session_state.novel_data["chapters"].get(chapter_key, "")

    col_action1, col_action2 = st.columns(2)
    with col_action1:
        chapter_prompt = st.text_area("Yêu cầu cụ thể cho chương này (Ý tưởng bổ sung):", placeholder="Ví dụ: Nhân vật A đi tính tiền phòng trọ, phát hiện bị tính nhầm 200k...")
        if st.button("🚀 AI Viết Nháp Chương Này"):
            # Mô phỏng AI sinh văn bản tuân thủ STYLE_PROMPT
            sample_generated = f"[{chapter_key}]\n\nTrời chạng vạng tối. Nam bấm đồng hồ điện ở hành lang phòng trọ. Con số nhảy thêm 15 số so với tuần trước. Anh rút bao thuốc lá giá rẻ, châm một điếu rồi thở dài. Số tiền còn lại trong ví chỉ đủ ăn cơm bình dân đến cuối tháng."
            st.session_state.novel_data["chapters"][chapter_key] = sample_generated
            st.success(f"Đã tạo xong bản nháp cho {chapter_key}!")
            st.rerun()

    with col_action2:
        st.subheader(f"Nội dung bản nháp: {chapter_key}")
        edited_content = st.text_area("Nội dung chương (Có thể chỉnh sửa trực tiếp):", value=current_draft, height=350)
        if st.button("💾 Lưu Chương Này"):
            st.session_state.novel_data["chapters"][chapter_key] = edited_content
            st.success("Đã lưu chương vào hệ thống!")

# ==========================================
# PHẦN 6: HOÀN THIỆN & XUẤT BỘ TRUYỆN
# ==========================================
elif menu == "6. Hoàn thiện & Xuất bộ truyện":
    st.header("🏆 Hoàn Thiện & Xuất Toàn Bộ Tiểu Thuyết")
    
    st.subheader("📄 Tổng quan tác phẩm:")
    st.write(f"- **Số lượng chương đã hoàn thành:** {len(st.session_state.novel_data['chapters'])} chương")
    st.write(f"- **Số tài liệu Raw tham khảo:** {len(st.session_state.novel_data['raw_docs'])} tệp")

    full_novel_text = ""
    for ch_name, ch_content in st.session_state.novel_data["chapters"].items():
        full_novel_text += f"\n\n=== {ch_name} ===\n\n" + ch_content

    st.text_area("Xem trước bản thảo đầy đủ:", value=full_novel_text, height=400)

    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        st.download_button(
            label="📥 Tải xuống Toàn bộ Bảng thảo (.txt)",
            data=full_novel_text,
            file_name="Toan_Bo_Tieu_Thuyet.txt",
            mime="text/plain"
        )
    with col_exp2:
        if st.button("☁️ Đăng lưu toàn bộ lên Supabase"):
            if supabase:
                try:
                    data_to_save = {
                        "email": st.session_state.user_email,
                        "workspace_data": st.session_state.novel_data
                    }
                    supabase.table("workspaces").upsert(data_to_save).execute()
                    st.success("Đã đồng bộ toàn bộ tác phẩm lên Supabase thành công!")
                except Exception as e:
                    st.error(f"Lỗi khi lưu lên Supabase: {e}")
            else:
                st.error("Chưa kết nối Supabase.")