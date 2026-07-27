import streamlit as st
from supabase import create_client, Client
import requests
import json

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
        "selected_model": "Google Gemini 1.5 Pro",
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
[YÊU CẦU BẮT BUỘC VỀ VĂN PHONG VÀ HÀNH VĂN]
- Tuyệt đối KHÔNG sử dụng từ ngữ hoa mỹ, phô trương, cường điệu hay lãng mạn hóa quá mức (tránh xa các từ ngữ kiểu ngôn tình sến sẩm, ví dụ: đau xé tâm can, tuyệt mỹ, kinh thiên động địa, ánh mắt sắc bén như dao cau...).
- Giữ giọng văn mộc mạc, gần gũi, mang đậm chất đời thường và hơi thở thực tế của bối cảnh.
- Giữ nhịp điệu kể chuyện tỉnh táo: Kể sự việc theo lối "thấy sao nói vậy", để nhân vật quan sát sự việc bằng con mắt thực tế, không lý tưởng hóa hoàn cảnh hay nhân vật.
- Nhịp câu ngắn gọn, gãy gọn, tập trung vào hành động thực tế, sinh hoạt phí hằng ngày và tâm lý nhân vật một cách tỉnh táo, thực dụng.
- Lời thoại và độc thoại nội tâm phải tự nhiên, đứng ở vị thế là ngôi kể thứ ba.
- Nhân vật phản ứng theo logic thông thường của con người trong hoàn cảnh đó.
"""

# ==========================================
# CÁC HÀM GỌI API AI TRỰC TIẾP
# ==========================================
def call_llm(system_prompt, messages_or_prompt, api_keys, model_choice):
    openai_key = api_keys.get("openai", "").strip()
    gemini_key = api_keys.get("gemini", "").strip()
    groq_key = api_keys.get("groq", "").strip()

    provider = None
    if "OpenAI" in model_choice and openai_key:
        provider = "openai"
    elif "Gemini" in model_choice and gemini_key:
        provider = "gemini"
    elif "Groq" in model_choice and groq_key:
        provider = "groq"
    else:
        if openai_key:
            provider = "openai"
        elif gemini_key:
            provider = "gemini"
        elif groq_key:
            provider = "groq"

    if not provider:
        return "⚠️ BẠN CHƯA CẤU HÌNH API KEY! Vui lòng vào mục '1. Cấu hình API Keys' nhập API Key (Gemini, OpenAI hoặc Groq) để AI hoạt động."

    try:
        if provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            headers = {"Content-Type": "application/json"}
            contents = []
            if system_prompt:
                contents.append({"role": "user", "parts": [{"text": f"[YÊU CẦU HỆ THỐNG]: {system_prompt}"}]})
                contents.append({"role": "model", "parts": [{"text": "Đã hiểu yêu cầu hệ thống. Tôi sẵn sàng."}]})

            if isinstance(messages_or_prompt, list):
                for m in messages_or_prompt:
                    role = "user" if m["role"] == "user" else "model"
                    contents.append({"role": role, "parts": [{"text": m["content"]}]})
            else:
                contents.append({"role": "user", "parts": [{"text": str(messages_or_prompt)}]})

            res = requests.post(url, headers=headers, json={"contents": contents}, timeout=60)
            if res.status_code == 200:
                return res.json()["candidates"][0]["content"]["parts"][0]["text"]
            else:
                return f"❌ Lỗi Gemini ({res.status_code}): {res.text}"

        elif provider == "openai":
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            msgs = [{"role": "system", "content": system_prompt}]
            if isinstance(messages_or_prompt, list):
                msgs.extend(messages_or_prompt)
            else:
                msgs.append({"role": "user", "content": str(messages_or_prompt)})
            res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json={"model": "gpt-4o-mini", "messages": msgs, "temperature": 0.7}, timeout=60)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
            else:
                return f"❌ Lỗi OpenAI ({res.status_code}): {res.text}"

        elif provider == "groq":
            headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
            msgs = [{"role": "system", "content": system_prompt}]
            if isinstance(messages_or_prompt, list):
                msgs.extend(messages_or_prompt)
            else:
                msgs.append({"role": "user", "content": str(messages_or_prompt)})
            res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json={"model": "llama-3.3-70b-versatile", "messages": msgs, "temperature": 0.7}, timeout=60)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
            else:
                return f"❌ Lỗi Groq ({res.status_code}): {res.text}"

    except Exception as e:
        return f"❌ Lỗi kết nối AI: {str(e)}"

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
    st.info("Nhập API Key để AI bắt đầu hoạt động và tư duy thực tế.")

    col1, col2 = st.columns(2)
    with col1:
        openai_key = st.text_input("OpenAI API Key:", value=st.session_state.novel_data["api_keys"].get("openai", ""), type="password")
        gemini_key = st.text_input("Gemini API Key (Khuyên dùng):", value=st.session_state.novel_data["api_keys"].get("gemini", ""), type="password")
    with col2:
        groq_key = st.text_input("Groq API Key:", value=st.session_state.novel_data["api_keys"].get("groq", ""), type="password")
        selected_model = st.selectbox("Mô hình AI ưu tiên:", ["Google Gemini 1.5 Pro", "OpenAI GPT-4o", "Groq Llama-3"])

    if st.button("💾 Lưu Cấu Hình API"):
        st.session_state.novel_data["api_keys"] = {"openai": openai_key, "gemini": gemini_key, "groq": groq_key}
        st.session_state.novel_data["selected_model"] = selected_model
        st.success("Đã lưu cấu hình API thành công!")

# ==========================================
# PHẦN 2: TẢI LÊN RAW REFERENCE
# ==========================================
elif menu == "2. Tải lên RAW Reference":
    st.header("📚 Tải lên bộ Raw Tham Khảo")
    st.write("Tải lên các file `.txt` tham khảo. AI sẽ đọc các file này để học bối cảnh và phối hợp tạo Dàn ý/Chương nháp.")

    uploaded_files = st.file_uploader("Chọn các tệp Raw tham khảo (.txt, .md):", type=["txt", "md"], accept_multiple_files=True)

    if uploaded_files:
        for file in uploaded_files:
            if not any(d.get("filename") == file.name for d in st.session_state.novel_data["raw_docs"]):
                content = file.read().decode("utf-8", errors="ignore")
                st.session_state.novel_data["raw_docs"].append({"filename": file.name, "content": content[:8000]})
        st.success("Đã tải lên tệp Raw thành công!")

    if st.session_state.novel_data["raw_docs"]:
        st.subheader("📋 Danh sách Raw đã tải lên:")
        for idx, doc in enumerate(st.session_state.novel_data["raw_docs"]):
            col_name, col_btn = st.columns([4, 1])
            with col_name:
                st.write(f"- **{doc['filename']}** ({len(doc['content'])} ký tự)")
            with col_btn:
                if st.button("🗑️ Xóa file", key=f"del_raw_{idx}"):
                    st.session_state.novel_data["raw_docs"].pop(idx)
                    st.rerun()

# ==========================================
# PHẦN 3: AI PHỎNG VẤN VÀ XÂY DỰNG NHÂN VẬT (THẬT 100%)
# ==========================================
elif menu == "3. AI Phỏng vấn (Bối cảnh & Nhân vật)":
    col_title, col_clear = st.columns([3, 1])
    with col_title:
        st.header("🤖 AI Phỏng vấn Trợ lý Biên tập")
    with col_clear:
        if st.button("🗑️ Xóa lịch sử chat"):
            st.session_state.novel_data["interview_history"] = []
            st.rerun()

    st.caption("AI sẽ đóng vai Trợ lý Biên tập viên. Từng câu trả lời của bạn sẽ được AI tổng hợp để dựng nên Sườn khung (Bối cảnh, Nhân vật, Mâu thuẫn) của câu chuyện.")

    # Hiển thị lịch sử chat
    for msg in st.session_state.novel_data["interview_history"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Nếu chưa có câu đầu tiên
    if not st.session_state.novel_data["interview_history"]:
        initial_prompt = "Chào bạn! Tôi là Trợ lý Biên tập viên AI. Để bắt đầu xây dựng sườn khung cho bộ truyện, bạn có thể chia sẻ: Ý tưởng ban đầu hoặc thể loại truyện mà bạn đang muốn viết là gì?"
        st.session_state.novel_data["interview_history"].append({"role": "assistant", "content": initial_prompt})
        st.rerun()

    user_input = st.chat_input("Nhập câu trả lời hoặc suy nghĩ của bạn...")
    if user_input:
        # Lưu tin nhắn người dùng
        st.session_state.novel_data["interview_history"].append({"role": "user", "content": user_input})

        # Gọi AI suy luận câu tiếp theo
        editor_system_prompt = """
        Bạn là một Trợ lý Biên tập viên Tiểu thuyết Chuyên nghiệp.
        Nhiệm vụ: Phỏng vấn tác giả để xây dựng nên Sườn khung câu chuyện (Thể loại, Bối cảnh, Tuyến nhân vật, Mâu thuẫn trung tâm).
        
        Quy tắc đối thoại:
        1. Đọc và phân tích kỹ câu trả lời mới nhất của tác giả cùng toàn bộ lịch sử chat.
        2. Tóm tắt ngắn gọn 1-2 điểm cốt lõi bạn đã ghi nhận được về bộ truyện.
        3. Đặt tiếp 1-2 câu hỏi sắc bén, thực tế để phát triển chiều sâu (ví dụ: hoàn cảnh thực tế, mâu thuẫn chính, tâm lý nhân vật, logic thế giới).
        4. Tuyệt đối KHÔNG lặp lại câu hỏi cũ. Giữ giọng văn thân thiện, chuyên nghiệp, khơi gợi sáng tạo.
        """

        with st.spinner("AI Biên tập đang suy nghĩ và phân tích câu trả lời..."):
            ai_response = call_llm(
                system_prompt=editor_system_prompt,
                messages_or_prompt=st.session_state.novel_data["interview_history"],
                api_keys=st.session_state.novel_data["api_keys"],
                model_choice=st.session_state.novel_data["selected_model"]
            )

        st.session_state.novel_data["interview_history"].append({"role": "assistant", "content": ai_response})
        st.rerun()

# ==========================================
# PHẦN 4: LẬP DÀN Ý & BỐ CỤC TỔNG THỂ (LIÊN KẾT TOÀN BỘ DỮ LIỆU)
# ==========================================
elif menu == "4. Lập Dàn ý & Bố cục":
    st.header("📌 Dàn ý Chi tiết & Cốt truyện Cả Bộ Truyện")
    st.caption("Dàn ý sẽ được AI tự động đúc kết từ: Lịch sử phỏng vấn AI + Các tệp Raw tham khảo đã tải lên.")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🪄 AI Tổng Hợp & Tạo Dàn Ý Tự Động"):
            # Tổng hợp dữ liệu từ phỏng vấn và raw
            interview_context = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.novel_data["interview_history"]])
            
            raw_context = ""
            for doc in st.session_state.novel_data["raw_docs"]:
                raw_context += f"\n--- Tệp mẫu {doc['filename']} ---\n" + doc['content'][:2000]

            outline_system_prompt = f"""
            Bạn là Chuyên gia Cấu trúc Cốt truyện Tiểu thuyết.
            Nhiệm vụ: Hãy phân tích toàn bộ thông tin phỏng vấn tác giả và các tài liệu Raw tham khảo dưới đây để tổng hợp và lập ra DÀN Ý CHI TIẾT TỔNG THỂ CẢ BỘ TRUYỆN.

            {STYLE_PROMPT}

            Yêu cầu Bố cục Dàn ý đầu ra:
            I. TỔNG QUAN BỘ TRUYỆN
            - Tên truyện dự kiến:
            - Thể loại & Bối cảnh chính:
            - Mâu thuẫn trung tâm & Chủ đề chính:
            - Thiết lập Nhân vật chính & Nhân vật phụ (Tính cách, động cơ, hoàn cảnh):

            II. DÀN Ý CHI TIẾT TỪNG CHƯƠNG (Tạo ít nhất 5-10 chương ban đầu)
            - Chương 1: [Tên chương] -> Tóm tắt sự việc, xung đột chính, diễn biến tâm lý nhân vật.
            - Chương 2: [Tên chương] -> Tóm tắt sự việc, xung đột chính, diễn biến tâm lý nhân vật.
            ...
            """

            combined_prompt = f"=== DỮ LIỆU PHỎNG VẤN VỚI TÁC GIẢ ===\n{interview_context}\n\n=== DỮ LIỆU RAW THAM KHẢO ===\n{raw_context}"

            with st.spinner("AI đang đúc kết thông tin và tạo Dàn ý tổng thể..."):
                generated_outline = call_llm(
                    system_prompt=outline_system_prompt,
                    messages_or_prompt=combined_prompt,
                    api_keys=st.session_state.novel_data["api_keys"],
                    model_choice=st.session_state.novel_data["selected_model"]
                )
                st.session_state.novel_data["outline"] = generated_outline
                st.success("Đã tạo Dàn ý tổng thể thành công!")
                st.rerun()

    with col2:
        if st.button("🗑️ Xóa Dàn Ý"):
            st.session_state.novel_data["outline"] = ""
            st.rerun()

    outline_text = st.text_area("Bảng chỉnh sửa Dàn ý tổng thể (Bạn có thể sửa trực tiếp):", value=st.session_state.novel_data["outline"], height=400)
    st.session_state.novel_data["outline"] = outline_text

# ==========================================
# PHẦN 5: AI VIẾT NHÁP & CHỈNH SỬA TỪNG CHƯƠNG (LIÊN KẾT DÀN Ý)
# ==========================================
elif menu == "5. AI Viết nháp & Chỉnh sửa":
    st.header("✍️ AI Viết Nháp & Sửa Đổi Từng Chương")
    st.caption("AI sẽ viết nháp dựa trên: Dàn ý tổng thể + Bối cảnh phỏng vấn + Quy chuẩn văn phong đời thường.")

    with st.expander("🛡️ Quy chuẩn văn phong bắt buộc (Bật mặc định)", expanded=False):
        st.code(STYLE_PROMPT, language="markdown")

    chapter_num = st.number_input("Chọn số chương cần viết / sửa:", min_value=1, value=1, step=1)
    chapter_key = f"Chương {chapter_num}"

    current_draft = st.session_state.novel_data["chapters"].get(chapter_key, "")

    col_action1, col_action2 = st.columns(2)
    with col_action1:
        extra_note = st.text_area("Yêu cầu/Ghi chú riêng cho chương này (nếu có):", key=f"prompt_{chapter_key}", placeholder="Ví dụ: Tập trung tả sâu tâm lý nhân vật khi phát hiện bị mất tiền...")
        
        if st.button("🚀 AI Viết Nháp Chương Này"):
            if not st.session_state.novel_data["outline"]:
                st.warning("⚠️ Bạn chưa có Dàn ý! Nên vào mục '4. Lập Dàn ý' để tạo dàn ý trước giúp AI viết chuẩn xác nhất.")

            interview_context = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.novel_data["interview_history"]])

            draft_system_prompt = f"""
            Bạn là tác giả viết tiểu thuyết thực lực.
            Nhiệm vụ: Hãy viết bản nháp hoàn chỉnh cho {chapter_key}.

            {STYLE_PROMPT}

            Yêu cầu kết nối dữ liệu:
            1. Bám sát Dàn ý tổng thể của bộ truyện (đặc biệt là yêu cầu của {chapter_key}).
            2. Thể hiện đúng tính cách nhân vật và bối cảnh đã thống nhất trong phần phỏng vấn.
            3. Viết chi tiết, có lời thoại tự nhiên, hành động thực tế, độ dài vừa đủ.
            """

            combined_prompt = f"""
            === DÀN Ý TỔNG THỂ CẢ BỘ TRUYỆN ===
            {st.session_state.novel_data['outline']}

            === THÔNG TIN BỐI CẢNH & NHÂN VẬT ===
            {interview_context}

            === YÊU CẦU CỤ THỂ CHO {chapter_key.upper()} ===
            {extra_note if extra_note else 'Viết đúng diễn biến chương theo dàn ý.'}
            """

            with st.spinner(f"AI đang viết nháp nội dung cho {chapter_key}..."):
                generated_chapter = call_llm(
                    system_prompt=draft_system_prompt,
                    messages_or_prompt=combined_prompt,
                    api_keys=st.session_state.novel_data["api_keys"],
                    model_choice=st.session_state.novel_data["selected_model"]
                )
                st.session_state.novel_data["chapters"][chapter_key] = generated_chapter
                st.success(f"Đã tạo xong bản nháp cho {chapter_key}!")
                st.rerun()

    with col_action2:
        st.subheader(f"Nội dung bản nháp: {chapter_key}")
        edited_content = st.text_area("Nội dung chương (chỉnh sửa trực tiếp):", value=current_draft, height=350)
        
        col_save, col_del = st.columns(2)
        with col_save:
            if st.button("💾 Lưu Chương Này"):
                st.session_state.novel_data["chapters"][chapter_key] = edited_content
                st.success("Đã lưu chương!")
        with col_del:
            if st.button("🗑️ Xóa Chương Này"):
                if chapter_key in st.session_state.novel_data["chapters"]:
                    del st.session_state.novel_data["chapters"][chapter_key]
                    st.success(f"Đã xóa {chapter_key}!")
                    st.rerun()

# ==========================================
# PHẦN 6: HOÀN THIỆN & XUẤT BỘ TRUYỆN
# ==========================================
elif menu == "6. Hoàn thiện & Xuất bộ truyện":
    st.header("🏆 Hoàn Thiện & Xuất Toàn Bộ Tiểu Thuyết")
    
    full_novel_text = ""
    # Sắp xếp chương theo thứ tự số
    sorted_chapters = sorted(st.session_state.novel_data["chapters"].keys(), key=lambda x: int(x.split(" ")[1]) if x.split(" ")[1].isdigit() else 0)
    
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
                    st.success("Đã đồng bộ toàn bộ tác phẩm lên Supabase thành công!")
                except Exception as e:
                    st.error(f"Lỗi khi lưu lên Supabase: {e}")
            else:
                st.error("Chưa kết nối Supabase.")
