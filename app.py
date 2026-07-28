import streamlit as st
from supabase import create_client, Client
import requests
import json
import re

# ==========================================
# 1. CẤU HÌNH TRANG VÀ KẾT NỐI SUPABASE
# ==========================================
st.set_page_config(
    page_title="Novel Studio - AI Assistant",
    page_icon="📖",
    layout="wide"
)

# Lấy Secrets an toàn
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

# Khởi tạo Session State
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "novel_data" not in st.session_state:
    st.session_state.novel_data = {
        "api_keys": {"openai": "", "gemini": "", "groq": ""},
        "selected_model": "Google Gemini (Miễn phí)",
        "genre": "",
        "setting": "",
        "characters": "",
        "outline": "",
        "raw_docs": [],
        "raw_chapters": {}, # THÊM MỚI: Nơi lưu các chương Raw đã tách và dịch
        "interview_history": [],
        "chapters": {}
    }

# SYSTEM PROMPT BẮT BUỘC VỀ VĂN PHONG
STYLE_PROMPT = """
[YÊU CẦU BẮT BUỘC VỀ VĂN PHONG VÀ HÀNH VĂN]
- Tuyệt đối KHÔNG sử dụng từ ngữ hoa mỹ, phô trương, cường điệu hay lãng mạn hóa quá mức (tránh xa các từ ngữ kiểu ngôn tình sến sẩm).
- Giữ giọng văn mộc mạc, gần gũi, mang đậm chất đời thường và hơi thở thực tế của bối cảnh.
- Giữ nhịp điệu kể chuyện tỉnh táo: Kể sự việc theo lối "thấy sao nói vậy", để nhân vật quan sát sự việc bằng con mắt thực tế.
- Nhịp câu ngắn gọn, gãy gọn, tập trung vào hành động thực tế và tâm lý nhân vật.
- Lời thoại và độc thoại nội tâm phải tự nhiên, đứng ở vị thế ngôi kể thứ ba.
"""

# ==========================================
# CÁC HÀM XỬ LÝ DỮ LIỆU VỚI SUPABASE (LOAD & SAVE)
# ==========================================
def load_user_data_from_supabase(email):
    """Tự động tải dữ liệu cũ của User từ Supabase về ứng dụng"""
    if supabase:
        try:
            res = supabase.table("workspaces").select("workspace_data").eq("email", email).execute()
            if res.data and len(res.data) > 0:
                saved_data = res.data[0].get("workspace_data")
                if saved_data and isinstance(saved_data, dict):
                    st.session_state.novel_data.update(saved_data)
                    # Cập nhật thêm key mới nếu dữ liệu cũ chưa có
                    if "raw_chapters" not in st.session_state.novel_data:
                        st.session_state.novel_data["raw_chapters"] = {}
                    st.toast("🎉 Đã tải thành công dữ liệu truyện cũ của bạn!", icon="✅")
        except Exception as e:
            st.error(f"Lỗi khi tải dữ liệu từ Supabase: {e}")

def save_user_data_to_supabase():
    """Tự động đồng bộ và lưu dữ liệu hiện tại lên Supabase"""
    if supabase and st.session_state.authenticated and st.session_state.user_email:
        try:
            data_to_save = {
                "email": st.session_state.user_email,
                "workspace_data": st.session_state.novel_data
            }
            supabase.table("workspaces").upsert(data_to_save).execute()
            st.toast("💾 Đã lưu toàn bộ tiến trình lên Cloud!", icon="☁️")
        except Exception as e:
            st.error(f"Lỗi khi lưu lên Supabase: {e}")

# ==========================================
# CÁC HÀM GỌI API AI TRỰC TIẾP
# ==========================================
def call_llm(system_prompt, messages_or_prompt, api_keys, model_choice):
    openai_key = api_keys.get("openai", "").strip()
    gemini_key = api_keys.get("gemini", "").strip()
    groq_key = api_keys.get("groq", "").strip()

    if openai_key.startswith("sb_") or "supabase" in openai_key.lower():
        return "⚠️ LỖI CẤU HÌNH: Bạn đang dán nhầm Supabase Key vào ô OpenAI Key! Key OpenAI chuẩn có dạng 'sk-'."

    provider = None
    if "Gemini" in model_choice and gemini_key:
        provider = "gemini"
    elif "OpenAI" in model_choice and openai_key:
        provider = "openai"
    elif "Groq" in model_choice and groq_key:
        provider = "groq"
    else:
        if gemini_key:
            provider = "gemini"
        elif openai_key:
            provider = "openai"
        elif groq_key:
            provider = "groq"

    if not provider:
        return "⚠️ BẠN CHƯA CẤU HÌNH API KEY! Vui lòng vào mục '1. Cấu hình API Keys' nhập API Key để AI hoạt động."

    try:
        if provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            headers = {"Content-Type": "application/json"}
            
            contents = []
            if system_prompt:
                contents.append({"role": "user", "parts": [{"text": f"[YÊU CẦU HỆ THỐNG]: {system_prompt}"}]})
                contents.append({"role": "model", "parts": [{"text": "Đã hiểu yêu cầu hệ thống."}]})

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
                url_fb = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={gemini_key}"
                res_fb = requests.post(url_fb, headers=headers, json={"contents": contents}, timeout=60)
                if res_fb.status_code == 200:
                    return res_fb.json()["candidates"][0]["content"]["parts"][0]["text"]
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
# 2. XÁC THỰC TÀI KHOẢN & TỰ ĐỘNG NẠP DỮ LIỆU
# ==========================================
if not st.session_state.authenticated:
    st.title("☁️ Đăng nhập Novel Studio")
    st.caption("Dữ liệu dàn ý, cuộc trò chuyện và chương truyện của bạn sẽ tự động đồng bộ.")
    
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
                    load_user_data_from_supabase(email)
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
                st.error("Chưa cấu hình Supabase URL/Key trong secrets.")

    st.stop()

# ==========================================
# 3. GIAO DIỆN CHÍNH & ĐIỀU HƯỚNG
# ==========================================
st.sidebar.title("📖 Novel Studio")
st.sidebar.write(f"👤 **{st.session_state.user_email}**")

col_sb1, col_sb2 = st.columns(2)
with st.sidebar:
    if st.button("💾 Lưu dữ liệu ngay", use_container_width=True):
        save_user_data_to_supabase()

    if st.button("🚪 Đăng xuất", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_email = ""
        st.rerun()

st.sidebar.divider()

menu = st.sidebar.radio(
    "Điều hướng quy trình:",
    [
        "1. Cấu hình API Keys",
        "2. Tải lên RAW Reference",
        "3. Tách & Dịch Raw", # MENU MỚI
        "4. AI Phỏng vấn (Bối cảnh & Nhân vật)",
        "5. Lập Dàn ý & Bố cục",
        "6. AI Viết nháp & Chỉnh sửa",
        "7. Hoàn thiện & Xuất bộ truyện"
    ]
)

# Đảm bảo có key raw_chapters để tránh lỗi khi người dùng load từ phiên bản cũ
if "raw_chapters" not in st.session_state.novel_data:
    st.session_state.novel_data["raw_chapters"] = {}

# ==========================================
# PHẦN 1: CẤU HÌNH API KEYS
# ==========================================
if menu == "1. Cấu hình API Keys":
    st.header("🔑 Cấu hình các kết nối API AI")
    st.info("API Key sau khi lưu sẽ được giữ nguyên cho các lần đăng nhập sau.")

    col1, col2 = st.columns(2)
    with col1:
        gemini_key = st.text_input("Google Gemini API Key (Miễn phí):", value=st.session_state.novel_data["api_keys"].get("gemini", ""), type="password")
        openai_key = st.text_input("OpenAI API Key (Dạng sk-...):", value=st.session_state.novel_data["api_keys"].get("openai", ""), type="password")
    with col2:
        groq_key = st.text_input("Groq API Key:", value=st.session_state.novel_data["api_keys"].get("groq", ""), type="password")
        selected_model = st.selectbox("Mô hình AI ưu tiên:", ["Google Gemini (Miễn phí)", "OpenAI GPT-4o", "Groq Llama-3"])

    if st.button("💾 Lưu Cấu Hình API"):
        st.session_state.novel_data["api_keys"] = {"openai": openai_key, "gemini": gemini_key, "groq": groq_key}
        st.session_state.novel_data["selected_model"] = selected_model
        save_user_data_to_supabase()
        st.success("Đã lưu và đồng bộ API Key thành công!")

# ==========================================
# PHẦN 2: TẢI LÊN RAW REFERENCE
# ==========================================
elif menu == "2. Tải lên RAW Reference":
    st.header("📚 Tải lên bộ Raw Tham Khảo")
    uploaded_files = st.file_uploader("Chọn các tệp Raw (.txt, .md) chứa truyện gốc:", type=["txt", "md"], accept_multiple_files=True)

    if uploaded_files:
        for file in uploaded_files:
            if not any(d.get("filename") == file.name for d in st.session_state.novel_data["raw_docs"]):
                content = file.read().decode("utf-8", errors="ignore")
                # Xóa bỏ giới hạn 8000 ký tự để lưu giữ toàn bộ nội dung file
                st.session_state.novel_data["raw_docs"].append({"filename": file.name, "content": content})
        save_user_data_to_supabase()
        st.success("Đã tải lên và lưu tệp Raw!")

    if st.session_state.novel_data["raw_docs"]:
        st.subheader("📋 Danh sách Raw đã lưu:")
        for idx, doc in enumerate(st.session_state.novel_data["raw_docs"]):
            col_name, col_btn = st.columns([4, 1])
            with col_name:
                st.write(f"- **{doc['filename']}** ({len(doc['content'])} ký tự)")
            with col_btn:
                if st.button("🗑️ Xóa file", key=f"del_raw_{idx}"):
                    st.session_state.novel_data["raw_docs"].pop(idx)
                    save_user_data_to_supabase()
                    st.rerun()

# ==========================================
# PHẦN 3: TÁCH CHƯƠNG VÀ DỊCH RAW
# ==========================================
elif menu == "3. Tách & Dịch Raw":
    st.header("✂️ Tách chương & Dịch Raw")
    
    if not st.session_state.novel_data.get("raw_docs"):
        st.warning("⚠️ Vui lòng tải lên ít nhất một file Raw ở bước 2 trước khi sử dụng chức năng này.")
    else:
        # 1. Chọn file để tách
        doc_names = [d["filename"] for d in st.session_state.novel_data["raw_docs"]]
        selected_doc = st.selectbox("1. Chọn file Raw cần tách thành từng chương:", doc_names)
        doc_content = next((d["content"] for d in st.session_state.novel_data["raw_docs"] if d["filename"] == selected_doc), "")
        
        # 2. Thiết lập quy tắc tách
        st.subheader("2. Thiết lập Tách Chương")
        col_split1, col_split2 = st.columns([3, 1])
        with col_split1:
            split_pattern = st.text_input("Từ khóa hoặc Regex bắt đầu mỗi chương (VD: 'Chương ', 'Chapter ', '第'):", value="Chương ")
        with col_split2:
            st.write("")
            st.write("")
            if st.button("✂️ Bắt đầu Tách", use_container_width=True):
                try:
                    # Thử tách bằng regex (giữ nguyên từ khóa ở đầu chương)
                    pattern = f"(?={split_pattern})"
                    chunks = re.split(pattern, doc_content)
                except re.error:
                    # Fallback nếu Regex lỗi: Dùng split string thông thường
                    chunks_raw = doc_content.split(split_pattern)
                    chunks = [c if i == 0 else (split_pattern + c) for i, c in enumerate(chunks_raw)]
                
                new_chapters = {}
                chap_idx = 1
                for chunk in chunks:
                    if len(chunk.strip()) < 10:  # Bỏ qua các đoạn quá ngắn
                        continue
                    
                    # Lấy dòng đầu tiên làm tiêu đề nháp
                    first_line = chunk.strip().split('\n')[0][:30]
                    chap_key = f"Raw_Chương_{chap_idx} ({first_line}...)"
                    
                    new_chapters[chap_key] = {
                        "raw": chunk.strip(),
                        "translated": ""
                    }
                    chap_idx += 1
                    
                st.session_state.novel_data["raw_chapters"] = new_chapters
                save_user_data_to_supabase()
                st.success(f"Đã tách thành {len(new_chapters)} chương!")
                st.rerun()
        
        # 3. Dịch từng chương
        if st.session_state.novel_data.get("raw_chapters"):
            st.divider()
            st.subheader("3. Dịch Thuật Từng Chương")
            chap_keys = list(st.session_state.novel_data["raw_chapters"].keys())
            selected_chap = st.selectbox("Chọn chương để xem và dịch:", chap_keys)
            
            chap_data = st.session_state.novel_data["raw_chapters"][selected_chap]
            
            col_raw, col_trans = st.columns(2)
            with col_raw:
                st.markdown("**Bản Raw (Gốc)**")
                raw_text = st.text_area("Nội dung Raw:", value=chap_data["raw"], height=500, key=f"raw_{selected_chap}")
            with col_trans:
                st.markdown("**Bản Dịch (Tiếng Việt)**")
                if st.button("🌐 AI Dịch Chương Này", use_container_width=True):
                    trans_system_prompt = """Bạn là một dịch giả tiểu thuyết chuyên nghiệp.
Nhiệm vụ: Dịch đoạn văn bản truyện RAW sau sang tiếng Việt.
Yêu cầu:
- Dịch mượt mà, thuần Việt, không lậm văn phong máy móc.
- Giữ nguyên nghĩa gốc, cảm xúc, văn phong và tính cách nhân vật.
- Tuyệt đối KHÔNG tự ý thêm bớt tình tiết hay tóm tắt truyện.
- Giữ nguyên cách phân chia đoạn văn."""
                    
                    with st.spinner("AI đang tiến hành dịch thuật... Quá trình này có thể mất vài chục giây."):
                        translated_text = call_llm(
                            system_prompt=trans_system_prompt,
                            messages_or_prompt=f"NỘI DUNG RAW CẦN DỊCH:\n\n{raw_text}",
                            api_keys=st.session_state.novel_data["api_keys"],
                            model_choice=st.session_state.novel_data["selected_model"]
                        )
                        st.session_state.novel_data["raw_chapters"][selected_chap]["translated"] = translated_text
                        st.session_state.novel_data["raw_chapters"][selected_chap]["raw"] = raw_text
                        save_user_data_to_supabase()
                        st.rerun()
                
                trans_text = st.text_area("Nội dung Dịch:", value=chap_data["translated"], height=500, key=f"trans_{selected_chap}")
                
            col_save_btn, _ = st.columns([1, 3])
            with col_save_btn:
                if st.button("💾 Lưu bản Dịch / Chỉnh sửa", use_container_width=True):
                    st.session_state.novel_data["raw_chapters"][selected_chap]["raw"] = raw_text
                    st.session_state.novel_data["raw_chapters"][selected_chap]["translated"] = trans_text
                    save_user_data_to_supabase()
                    st.success("Đã lưu bản cập nhật!")

# ==========================================
# PHẦN 4: AI PHỎNG VẤN VÀ XÂY DỰNG NHÂN VẬT
# ==========================================
elif menu == "4. AI Phỏng vấn (Bối cảnh & Nhân vật)":
    col_title, col_clear = st.columns([3, 1])
    with col_title:
        st.header("🤖 AI Phỏng vấn Trợ lý Biên tập")
    with col_clear:
        if st.button("🗑️ Xóa lịch sử chat"):
            st.session_state.novel_data["interview_history"] = []
            save_user_data_to_supabase()
            st.rerun()

    for msg in st.session_state.novel_data["interview_history"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if not st.session_state.novel_data["interview_history"]:
        initial_prompt = "Chào bạn! Tôi là Trợ lý Biên tập viên AI. Để bắt đầu xây dựng sườn khung cho bộ truyện, bạn có thể chia sẻ: Ý tưởng ban đầu hoặc thể loại truyện mà bạn đang muốn viết là gì?"
        st.session_state.novel_data["interview_history"].append({"role": "assistant", "content": initial_prompt})
        save_user_data_to_supabase()
        st.rerun()

    user_input = st.chat_input("Nhập câu trả lời hoặc suy nghĩ của bạn...")
    if user_input:
        st.session_state.novel_data["interview_history"].append({"role": "user", "content": user_input})

        editor_system_prompt = """
        Bạn là một Trợ lý Biên tập viên Tiểu thuyết Chuyên nghiệp.
        Nhiệm vụ: Phỏng vấn tác giả để xây dựng nên Sườn khung câu chuyện (Thể loại, Bối cảnh, Tuyến nhân vật, Mâu thuẫn trung tâm).
        Quy tắc: Đọc kỹ câu trả lời cũ, không lặp lại câu hỏi, đặt câu hỏi tiếp theo dựa trên câu trả lời của tác giả.
        """

        with st.spinner("AI Biên tập đang phân tích..."):
            ai_response = call_llm(
                system_prompt=editor_system_prompt,
                messages_or_prompt=st.session_state.novel_data["interview_history"],
                api_keys=st.session_state.novel_data["api_keys"],
                model_choice=st.session_state.novel_data["selected_model"]
            )

        st.session_state.novel_data["interview_history"].append({"role": "assistant", "content": ai_response})
        save_user_data_to_supabase()
        st.rerun()

# ==========================================
# PHẦN 5: LẬP DÀN Ý & BỐ CỤC TỔNG THỂ
# ==========================================
elif menu == "5. Lập Dàn ý & Bố cục":
    st.header("📌 Dàn ý Chi tiết & Cốt truyện Cả Bộ Truyện")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🪄 AI Tổng Hợp & Tạo Dàn Ý Tự Động"):
            interview_context = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.novel_data["interview_history"]])
            
            raw_context = ""
            # Nối một ít raw tham khảo để AI nắm bắt văn phong (Giới hạn khoảng 2000 ký tự đầu của mỗi file để không bị tràn token)
            for doc in st.session_state.novel_data["raw_docs"]:
                raw_context += f"\n--- Tệp mẫu {doc['filename']} ---\n" + doc['content'][:2000]

            outline_system_prompt = f"""
            Bạn là Chuyên gia Cấu trúc Cốt truyện Tiểu thuyết.
            Nhiệm vụ: Phân tích toàn bộ thông tin phỏng vấn tác giả và tài liệu Raw tham khảo để tạo DÀN Ý CHI TIẾT TỔNG THỂ CẢ BỘ TRUYỆN.

            {STYLE_PROMPT}

            Yêu cầu Bố cục Dàn ý:
            I. TỔNG QUAN BỘ TRUYỆN (Tên truyện, Bối cảnh, Mâu thuẫn chính, Tuyến nhân vật)
            II. DÀN Ý CHI TIẾT TỪNG CHƯƠNG (Chương 1, Chương 2, Chương 3...)
            """

            combined_prompt = f"=== DỮ LIỆU PHỎNG VẤN ===\n{interview_context}\n\n=== DỮ LIỆU RAW THAM KHẢO ===\n{raw_context}"

            with st.spinner("AI đang đúc kết thông tin và tạo Dàn ý..."):
                generated_outline = call_llm(
                    system_prompt=outline_system_prompt,
                    messages_or_prompt=combined_prompt,
                    api_keys=st.session_state.novel_data["api_keys"],
                    model_choice=st.session_state.novel_data["selected_model"]
                )
                st.session_state.novel_data["outline"] = generated_outline
                save_user_data_to_supabase()
                st.success("Đã tạo và lưu Dàn ý tổng thể thành công!")
                st.rerun()

    with col2:
        if st.button("🗑️ Xóa Dàn Ý"):
            st.session_state.novel_data["outline"] = ""
            save_user_data_to_supabase()
            st.rerun()

    outline_text = st.text_area("Bảng chỉnh sửa Dàn ý tổng thể:", value=st.session_state.novel_data["outline"], height=400)
    if outline_text != st.session_state.novel_data["outline"]:
        st.session_state.novel_data["outline"] = outline_text

    if st.button("💾 Lưu Dàn Ý"):
        save_user_data_to_supabase()

# ==========================================
# PHẦN 6: AI VIẾT NHÁP & CHỈNH SỬA TỪNG CHƯƠNG
# ==========================================
elif menu == "6. AI Viết nháp & Chỉnh sửa":
    st.header("✍️ AI Viết Nháp & Sửa Đổi Từng Chương")

    chapter_num = st.number_input("Chọn số chương cần viết / sửa:", min_value=1, value=1, step=1)
    chapter_key = f"Chương {chapter_num}"

    current_draft = st.session_state.novel_data["chapters"].get(chapter_key, "")

    col_action1, col_action2 = st.columns(2)
    with col_action1:
        extra_note = st.text_area("Yêu cầu/Ghi chú riêng cho chương này (nếu có):", key=f"prompt_{chapter_key}")
        
        if st.button("🚀 AI Viết Nháp Chương Này"):
            interview_context = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.novel_data["interview_history"]])

            draft_system_prompt = f"""
            Bạn là tác giả viết tiểu thuyết thực lực.
            Nhiệm vụ: Hãy viết bản nháp hoàn chỉnh cho {chapter_key}.

            {STYLE_PROMPT}
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
                save_user_data_to_supabase()
                st.success(f"Đã tạo và lưu xong {chapter_key}!")
                st.rerun()

    with col_action2:
        st.subheader(f"Nội dung bản nháp: {chapter_key}")
        edited_content = st.text_area("Nội dung chương:", value=current_draft, height=350)
        
        col_save, col_del = st.columns(2)
        with col_save:
            if st.button("💾 Lưu Chương Này"):
                st.session_state.novel_data["chapters"][chapter_key] = edited_content
                save_user_data_to_supabase()
                st.success("Đã lưu chương lên Cloud!")
        with col_del:
            if st.button("🗑️ Xóa Chương Này"):
                if chapter_key in st.session_state.novel_data["chapters"]:
                    del st.session_state.novel_data["chapters"][chapter_key]
                    save_user_data_to_supabase()
                    st.success(f"Đã xóa {chapter_key}!")
                    st.rerun()

# ==========================================
# PHẦN 7: HOÀN THIỆN & XUẤT BỘ TRUYỆN
# ==========================================
elif menu == "7. Hoàn thiện & Xuất bộ truyện":
    st.header("🏆 Hoàn Thiện & Xuất Toàn Bộ Tiểu Thuyết")
    
    full_novel_text = ""
    # Nếu là truyện viết thủ công từ Outline
    if st.session_state.novel_data["chapters"]:
        sorted_chapters = sorted(st.session_state.novel_data["chapters"].keys(), key=lambda x: int(x.split(" ")[1]) if len(x.split(" "))>1 and x.split(" ")[1].isdigit() else 0)
        for ch_name in sorted_chapters:
            full_novel_text += f"\n\n=== {ch_name} ===\n\n" + st.session_state.novel_data["chapters"][ch_name]

    # Nếu chỉ có các bản truyện Dịch từ Raw
    elif st.session_state.novel_data["raw_chapters"]:
        for ch_name, data in st.session_state.novel_data["raw_chapters"].items():
            if data["translated"]:
                full_novel_text += f"\n\n=== {ch_name} ===\n\n" + data["translated"]
            else:
                full_novel_text += f"\n\n=== {ch_name} (Chưa dịch) ===\n\n" + data["raw"]
    
    st.text_area("Xem trước bản thảo đầy đủ:", value=full_novel_text, height=400)

    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        st.download_button(label="📥 Tải xuống Toàn bộ (.txt)", data=full_novel_text, file_name="Toan_Bo_Tieu_Thuyet.txt", mime="text/plain")
    with col_exp2:
        if st.button("☁️ Đồng bộ lưu thủ công lên Supabase"):
            save_user_data_to_supabase()
