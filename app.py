import streamlit as st
from supabase import create_client, Client
import os

# ==========================================
# 1. CẤU HÌNH TRANG VÀ KẾT NỐI SUPABASE
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
    col1, col2 = st.columns(2)
    with col1:
        openai_key = st.text_input("OpenAI API Key:", value=st.session_state.novel_data["api_keys"].get("openai", ""), type="password")
        gemini_key = st.text_input("Gemini API Key:", value=st.session_state.novel_data["api_keys"].get("gemini", ""), type="password")
    with col2:
        groq_key = st.text_input("Groq API Key:", value=st.session_state.novel_data["api_keys"].get("groq", ""), type="password")
        selected_model = st.selectbox("Mô hình AI ưu tiên:", ["OpenAI GPT-4o", "Google Gemini 1.5 Pro", "Groq Llama-3"])

    if st.button("💾 Lưu Cấu Hình API"):
        st.session_state.novel_data["api_keys"] = {"openai": openai_key, "gemini": gemini_key, "groq": groq_key, "selected_model": selected_model}
        st.success("Đã lưu cấu hình API thành công!")

# ==========================================
# PHẦN 2: TẢI LÊN RAW REFERENCE
# ==========================================
elif menu == "2. Tải lên RAW Reference":
    st.header("📚 Tải lên bộ Raw Tham Khảo")
    uploaded_files = st.file_uploader("Chọn các tệp Raw tham khảo (.txt, .md):", type=["txt", "md"], accept_multiple_files=True)

    if uploaded_files:
        for file in uploaded_files:
            # Kiểm tra xem file đã tồn tại trong list chưa để tránh trùng lặp
            if not any(d.get("filename") == file.name for d in st.session_state.novel_data["raw_docs"]):
                content = file.read().decode("utf-8", errors="ignore")
                st.session_state.novel_data["raw_docs"].append({"filename": file.name, "content": content[:5000]})
        st.success("Đã tải lên tệp Raw thành công!")

    if st.session_state.novel_data["raw_docs"]:
        st.subheader("📋 Danh sách Raw đã tải lên:")
        for idx, doc in enumerate(st.session_state.novel_data["raw_docs"]):
            col_name, col_btn = st.columns([4, 1])
            with col_name:
                st.write(f"- **{doc['filename']}** ({len(doc['content'])} ký tự)")
            with col_btn:
                # NÚT XÓA TỪNG FILE RAW
                if st.button("🗑️ Xóa file", key=f"del_raw_{idx}"):
                    st.session_state.novel_data["raw_docs"].pop(idx)
                    st.rerun()

# ==========================================
# PHẦN 3: AI PHỎNG VẤN VÀ XÂY DỰNG NHÂN VẬT
# ==========================================
elif menu == "3. AI Phỏng vấn (Bối cảnh & Nhân vật)":
    col_title, col_clear = st.columns([3, 1])
    with col_title:
        st.header("🤖 AI Phỏng vấn Trợ lý Biên tập")
    with col_clear:
        # NÚT XÓA LỊCH SỬ PHỎNG VẤN
        if st.button("🗑️ Xóa lịch sử chat"):
            st.session_state.novel_data["interview_history"] = []
            st.rerun()

    for msg in st.session_state.novel_data["interview_history"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if not st.session_state.novel_data["interview_history"]:
        initial_prompt = "Xin chào! Để bắt đầu xây dựng bộ tiểu thuyết, hãy cho tôi biết: Bạn muốn viết thể loại gì và ý tưởng sơ khởi ban đầu của bạn là gì?"
        st.session_state.novel_data["interview_history"].append({"role": "assistant", "content": initial_prompt})
        st.rerun()

    user_input = st.chat_input("Trả lời câu hỏi của AI hoặc đưa ra yêu cầu...")
    if user_input:
        st.session_state.novel_data["interview_history"].append({"role": "user", "content": user_input})
        ai_reply = f"[AI Editor]: Cảm ơn bạn. Dựa trên ý tưởng '{user_input}', hãy cho tôi biết thêm: Hoàn cảnh sống thực tế của nhân vật chính hiện tại ra sao?"
        st.session_state.novel_data["interview_history"].append({"role": "assistant", "content": ai_reply})
        st.rerun()

# ==========================================
# PHẦN 4: LẬP DÀN Ý & BỐ CỤC
# ==========================================
elif menu == "4. Lập Dàn ý & Bố cục":
    st.header("📌 Dàn ý Chi tiết & Cốt truyện Từng Chương")
    
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🪄 AI Tạo Dàn Ý Tự Động"):
            st.session_state.novel_data["outline"] = "Chương 1: Bữa cơm tối đắt đỏ.\nChương 2: Căn phòng trọ thuê lại.\nChương 3: Cuộc sống tự do đầy áp lực."
            st.rerun()
    with col2:
        # NÚT XÓA DÀN Ý
        if st.button("🗑️ Xóa Dàn Ý"):
            st.session_state.novel_data["outline"] = ""
            st.rerun()

    outline_text = st.text_area("Chỉnh sửa Dàn ý:", value=st.session_state.novel_data["outline"], height=300)
    st.session_state.novel_data["outline"] = outline_text

# ==========================================
# PHẦN 5: AI VIẾT NHÁP & CHỈNH SỬA TỪNG CHƯƠNG
# ==========================================
elif menu == "5. AI Viết nháp & Chỉnh sửa":
    st.header("✍️ AI Viết Nháp & Sửa Đổi Từng Chương")
    
    with st.expander("🛡️ Quy chuẩn văn phong bắt buộc (Bật mặc định)", expanded=False):
        st.code(STYLE_PROMPT, language="markdown")

    chapter_num = st.number_input("Chọn chương cần viết / sửa / xóa:", min_value=1, value=1, step=1)
    chapter_key = f"Chương {chapter_num}"

    current_draft = st.session_state.novel_data["chapters"].get(chapter_key, "")

    col_action1, col_action2 = st.columns(2)
    with col_action1:
        st.text_area("Yêu cầu cụ thể cho chương này:", key=f"prompt_{chapter_key}", placeholder="Ví dụ: Nhân vật A đi tính tiền phòng trọ...")
        if st.button("🚀 AI Viết Nháp Chương Này"):
            sample_generated = f"[{chapter_key}]\n\nTrời chạng vạng tối. Nam bấm đồng hồ điện ở hành lang phòng trọ. Con số nhảy thêm 15 số..."
            st.session_state.novel_data["chapters"][chapter_key] = sample_generated
            st.rerun()

    with col_action2:
        st.subheader(f"Nội dung bản nháp: {chapter_key}")
        edited_content = st.text_area("Nội dung chương:", value=current_draft, height=350)
        
        col_save, col_del = st.columns(2)
        with col_save:
            if st.button("💾 Lưu Chương Này"):
                st.session_state.novel_data["chapters"][chapter_key] = edited_content
                st.success("Đã lưu chương!")
        with col_del:
            # NÚT XÓA RIÊNG CHƯƠNG ĐANG CHỌN
            if st.button("🗑️ Xóa Chương Này"):
                if chapter_key in st.session_state.novel_data["chapters"]:
                    del st.session_state.novel_data["chapters"][chapter_key]
                    st.success(f"Đã xóa toàn bộ nội dung {chapter_key}!")
                    st.rerun()

# ==========================================
# PHẦN 6: HOÀN THIỆN & XUẤT BỘ TRUYỆN
# ==========================================
elif menu == "6. Hoàn thiện & Xuất bộ truyện":
    st.header("🏆 Hoàn Thiện & Xuất Toàn Bộ Tiểu Thuyết")
    
    full_novel_text = ""
    # Sắp xếp chương theo thứ tự
    sorted_chapters = sorted(st.session_state.novel_data["chapters"].keys(), key=lambda x: int(x.split(" ")[1]))
    
    for ch_name in sorted_chapters:
        full_novel_text += f"\n\n=== {ch_name} ===\n\n" + st.session_state.novel_data["chapters"][ch_name]

    st.text_area("Xem trước bản thảo đầy đủ:", value=full_novel_text, height=400)

    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        st.download_button(label="📥 Tải xuống Toàn bộ (.txt)", data=full_novel_text, file_name="Toan_Bo_Tieu_Thuyet.txt", mime="text/plain")
    with col_exp2:
        if st.button("☁️ Đăng lưu toàn bộ lên Supabase"):
            if supabase:
                try:
                    data_to_save = {"email": st.session_state.user_email, "workspace_data": st.session_state.novel_data}
                    supabase.table("workspaces").upsert(data_to_save).execute()
                    st.success("Đã đồng bộ lên Supabase thành công!")
                except Exception as e:
                    st.error(f"Lỗi khi lưu lên Supabase: {e}")
            else:
                st.error("Chưa kết nối Supabase.")