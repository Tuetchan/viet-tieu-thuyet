import streamlit as st
from supabase import create_client, Client
import requests
import json
import re
import random # Thư viện để chọn ngẫu nhiên API key xoay vòng

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
        "api_keys": {"openai": "", "gemini": ""},
        "selected_model": "Google Gemini (Miễn phí)",
        "genre": "",
        "setting": "",
        "characters": "",
        "outline": "",
        "raw_docs": [],
        "raw_chapters": {},
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
    if supabase:
        try:
            res = supabase.table("workspaces").select("workspace_data").eq("email", email).execute()
            if res.data and len(res.data) > 0:
                saved_data = res.data[0].get("workspace_data")
                if saved_data and isinstance(saved_data, dict):
                    st.session_state.novel_data.update(saved_data)
                    if "raw_chapters" not in st.session_state.novel_data:
                        st.session_state.novel_data["raw_chapters"] = {}
                    st.toast("🎉 Đã tải thành công dữ liệu truyện cũ của bạn!", icon="✅")
        except Exception as e:
            st.error(f"Lỗi khi tải dữ liệu: {e}")

def save_user_data_to_supabase():
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
    # Hàm con: Tách các key từ ô nhập (nhiều dòng) và chọn ngẫu nhiên 1 key (Xoay vòng)
    def get_random_key(key_string):
        if not key_string: return ""
        keys = [k.strip() for k in key_string.split('\n') if k.strip()]
        return random.choice(keys) if keys else ""

    gemini_key = get_random_key(api_keys.get("gemini", ""))
    openai_key = get_random_key(api_keys.get("openai", ""))

    if openai_key.startswith("sb_"):
        return "⚠️ LỖI: Bạn đang dán nhầm Supabase Key vào ô OpenAI Key!"

    provider = None
    if "Gemini" in model_choice and gemini_key:
        provider = "gemini"
    elif "OpenAI" in model_choice and openai_key:
        provider = "openai"
    else:
        if gemini_key: provider = "gemini"
        elif openai_key: provider = "openai"

    if not provider:
        return "⚠️ BẠN CHƯA CẤU HÌNH API KEY! Vui lòng vào mục '1. Cấu hình API Keys' để nhập."

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
        "3. Tách & Dịch Raw", 
        "4. AI Phỏng vấn (Bối cảnh & Nhân vật)",
        "5. Lập Dàn ý & Bố cục",
        "6. AI Viết nháp & Chỉnh sửa",
        "7. Hoàn thiện & Xuất bộ truyện"
    ]
)

if "raw_chapters" not in st.session_state.novel_data:
    st.session_state.novel_data["raw_chapters"] = {}

# ==========================================
# PHẦN 1: CẤU HÌNH API KEYS (HỖ TRỢ NHIỀU TÀI KHOẢN / XOAY VÒNG KEY)
# ==========================================
if menu == "1. Cấu hình API Keys":
    st.header("🔑 Cấu hình API (Hỗ trợ chống Rate Limit)")
    st.info("💡 **Mẹo:** Bạn có thể dán nhiều API Key vào cùng 1 ô (Mỗi key nằm trên 1 dòng). Hệ thống sẽ tự động chọn ngẫu nhiên để xoay vòng, giúp bạn dịch hàng trăm chương mà không bị chặn hạn mức tài khoản!")

    col1, col2 = st.columns(2)
    with col1:
        gemini_keys_input = st.text_area(
            "Google Gemini API Keys (Mỗi key 1 dòng):", 
            value=st.session_state.novel_data["api_keys"].get("gemini", ""), 
            height=150,
            placeholder="AIzaSy...\nAIzaSy...\nAIzaSy..."
        )
    with col2:
        openai_keys_input = st.text_area(
            "OpenAI API Keys (Mỗi key 1 dòng - Tùy chọn):", 
            value=st.session_state.novel_data["api_keys"].get("openai", ""), 
            height=150,
            placeholder="sk-...\nsk-..."
        )
        selected_model = st.selectbox("Mô hình AI ưu tiên xử lý:", ["Google Gemini (Miễn phí)", "OpenAI GPT-4o"])

    if st.button("💾 Lưu Cấu Hình API"):
        st.session_state.novel_data["api_keys"] = {"openai": openai_keys_input, "gemini": gemini_keys_input}
        st.session_state.novel_data["selected_model"] = selected_model
        save_user_data_to_supabase()
        st.success("Đã lưu API Keys! Hệ thống sẽ tự động xoay vòng các key này.")

# ==========================================
# PHẦN 2: TẢI LÊN RAW REFERENCE
# ==========================================
elif menu == "2. Tải lên RAW Reference":
    st.header("📚 Tải lên bộ Raw Tham Khảo")
    uploaded_files = st.file_uploader("Chọn các tệp Raw (.txt, .md):", type=["txt", "md"], accept_multiple_files=True)

    if uploaded_files:
        for file in uploaded_files:
            if not any(d.get("filename") == file.name for d in st.session_state.novel_data["raw_docs"]):
                content = file.read().decode("utf-8", errors="ignore")
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
        doc_names = [d["filename"] for d in st.session_state.novel_data["raw_docs"]]
        selected_doc = st.selectbox("1. Chọn file Raw cần tách thành từng chương:", doc_names)
        doc_content = next((d["content"] for d in st.session_state.novel_data["raw_docs"] if d["filename"] == selected_doc), "")
        
        st.subheader("2. Thiết lập Tách Chương")
        col_split1, col_split2 = st.columns([3, 1])
        with col_split1:
            split_pattern = st.text_input("Từ khóa hoặc Regex bắt đầu mỗi chương (VD: 'Chương ', 'Chapter ', '第'):", value="Chương ")
        with col_split2:
            st.write("")
            st.write("")
            if st.button("✂️ Bắt đầu Tách", use_container_width=True):
                try:
                    pattern = f"(?={split_pattern})"
                    chunks = re.split(pattern, doc_content)
                except re.error:
                    chunks_raw = doc_content.split(split_pattern)
                    chunks = [c if i == 0 else (split_pattern + c) for i, c in enumerate(chunks_raw)]
                
                new_chapters = {}
                chap_idx = 1
                for chunk in chunks:
                    if len(chunk.strip()) < 10: continue
                    first_line = chunk.strip().split('\n')[0][:30]
                    chap_key = f"Raw_Chương_{chap_idx} ({first_line}...)"
                    
                    new_chapters[chap_key] = {"raw": chunk.strip(), "translated": ""}
                    chap_idx += 1
                    
                st.session_state.novel_data["raw_chapters"] = new_chapters
                save_user_data_to_supabase()
                st.success(f"Đã tách thành {len(new_chapters)} chương!")
                st.rerun()
        
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
Yêu cầu: Dịch mượt mà, thuần Việt. Giữ nguyên nghĩa gốc, không lậm văn phong máy móc. Giữ nguyên cách phân đoạn."""
                    
                    with st.spinner("AI đang tiến hành dịch thuật..."):
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
                if st.button("💾 Lưu bản Dịch", use_container_width=True):
                    st.session_state.novel_data["raw_chapters"][selected_chap]["raw"] = raw_text
                    st.session_state.novel_data["raw_chapters"][selected_chap]["translated"] = trans_text
                    save_user_data_to_supabase()
                    st.success("Đã lưu bản cập nhật!")

# ==========================================
# PHẦN 4, 5, 6, 7 (Phỏng vấn, Dàn ý, Viết nháp, Xuất truyện giữ nguyên)
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
        initial_prompt = "Chào bạn! Tôi là Trợ lý Biên tập viên AI. Bạn có thể chia sẻ ý tưởng ban đầu hoặc thể loại truyện mà bạn đang muốn viết là gì không?"
        st.session_state.novel_data["interview_history"].append({"role": "assistant", "content": initial_prompt})
        save_user_data_to_supabase()
        st.rerun()

    user_input = st.chat_input("Nhập câu trả lời hoặc suy nghĩ của bạn...")
    if user_input:
        st.session_state.novel_data["interview_history"].append({"role": "user", "content": user_input})
        editor_system_prompt = "Bạn là Trợ lý Biên tập viên. Hãy phỏng vấn tác giả để xây dựng Sườn khung câu chuyện."
        with st.spinner("AI Biên tập đang phân tích..."):
            ai_response = call_llm(editor_system_prompt, st.session_state.novel_data["interview_history"], st.session_state.novel_data["api_keys"], st.session_state.novel_data["selected_model"])
        st.session_state.novel_data["interview_history"].append({"role": "assistant", "content": ai_response})
        save_user_data_to_supabase()
        st.rerun()

elif menu == "5. Lập Dàn ý & Bố cục":
    st.header("📌 Dàn ý Chi tiết & Cốt truyện")
    if st.button("🪄 AI Tổng Hợp Dàn Ý Tự Động"):
        interview_context = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.novel_data["interview_history"]])
        raw_context = "".join([f"\n--- {doc['filename']} ---\n" + doc['content'][:2000] for doc in st.session_state.novel_data["raw_docs"]])
        outline_system_prompt = f"Tạo DÀN Ý CHI TIẾT. {STYLE_PROMPT}"
        combined_prompt = f"=== PHỎNG VẤN ===\n{interview_context}\n\n=== RAW THAM KHẢO ===\n{raw_context}"
        with st.spinner("AI đang tạo Dàn ý..."):
            generated_outline = call_llm(outline_system_prompt, combined_prompt, st.session_state.novel_data["api_keys"], st.session_state.novel_data["selected_model"])
            st.session_state.novel_data["outline"] = generated_outline
            save_user_data_to_supabase()
            st.rerun()

    outline_text = st.text_area("Bảng chỉnh sửa Dàn ý:", value=st.session_state.novel_data["outline"], height=400)
    if outline_text != st.session_state.novel_data["outline"]:
        st.session_state.novel_data["outline"] = outline_text
    if st.button("💾 Lưu Dàn Ý"): save_user_data_to_supabase()

elif menu == "6. AI Viết nháp & Chỉnh sửa":
    st.header("✍️ AI Viết Nháp & Sửa Đổi Từng Chương")
    chapter_num = st.number_input("Chọn số chương cần viết / sửa:", min_value=1, value=1, step=1)
    chapter_key = f"Chương {chapter_num}"
    current_draft = st.session_state.novel_data["chapters"].get(chapter_key, "")

    col_action1, col_action2 = st.columns(2)
    with col_action1:
        extra_note = st.text_area("Yêu cầu riêng cho chương này:", key=f"prompt_{chapter_key}")
        if st.button("🚀 AI Viết Nháp Chương Này"):
            interview_context = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.novel_data["interview_history"]])
            combined_prompt = f"=== DÀN Ý ===\n{st.session_state.novel_data['outline']}\n\n=== YÊU CẦU CHO {chapter_key} ===\n{extra_note}"
            with st.spinner(f"AI đang viết nháp {chapter_key}..."):
                generated_chapter = call_llm(f"Viết bản nháp cho {chapter_key}. {STYLE_PROMPT}", combined_prompt, st.session_state.novel_data["api_keys"], st.session_state.novel_data["selected_model"])
                st.session_state.novel_data["chapters"][chapter_key] = generated_chapter
                save_user_data_to_supabase()
                st.rerun()

    with col_action2:
        edited_content = st.text_area("Nội dung chương:", value=current_draft, height=350)
        if st.button("💾 Lưu Chương Này"):
            st.session_state.novel_data["chapters"][chapter_key] = edited_content
            save_user_data_to_supabase()

elif menu == "7. Hoàn thiện & Xuất bộ truyện":
    st.header("🏆 Hoàn Thiện & Xuất Toàn Bộ Tiểu Thuyết")
    full_novel_text = ""
    if st.session_state.novel_data["chapters"]:
        for ch_name in sorted(st.session_state.novel_data["chapters"].keys(), key=lambda x: int(x.split(" ")[1]) if len(x.split(" "))>1 and x.split(" ")[1].isdigit() else 0):
            full_novel_text += f"\n\n=== {ch_name} ===\n\n" + st.session_state.novel_data["chapters"][ch_name]
    elif st.session_state.novel_data["raw_chapters"]:
        for ch_name, data in st.session_state.novel_data["raw_chapters"].items():
            full_novel_text += f"\n\n=== {ch_name} ===\n\n" + (data["translated"] if data["translated"] else data["raw"])
    
    st.text_area("Xem trước bản thảo:", value=full_novel_text, height=400)
    st.download_button(label="📥 Tải xuống Toàn bộ (.txt)", data=full_novel_text, file_name="Truyen.txt", mime="text/plain")
