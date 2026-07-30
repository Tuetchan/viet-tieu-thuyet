import streamlit as st
import requests
import re
import time
import threading
import queue
import io
import zipfile
from bs4 import BeautifulSoup
from supabase import create_client, Client
from google import genai
from google.genai import types

# ==========================================
# 1. CẤU HÌNH TRANG VÀ KẾT NỐI SUPABASE
# ==========================================
st.set_page_config(page_title="Máy Dịch Truyện - Tối Giản", page_icon="⚡", layout="wide")

SUPABASE_URL = ""
SUPABASE_KEY = ""
try:
    if "SUPABASE_URL" in st.secrets: SUPABASE_URL = st.secrets["SUPABASE_URL"]
    if "SUPABASE_KEY" in st.secrets: SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception: pass

@st.cache_resource
def init_supabase():
    if SUPABASE_URL and SUPABASE_KEY:
        try: return create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception: return None
    return None

supabase = init_supabase()

# Khởi tạo Session State
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "trans_status" not in st.session_state: st.session_state.trans_status = {}
if "novel_data" not in st.session_state:
    st.session_state.novel_data = {
        "api_keys": {"gemini": ""},
        "selected_model": "Gemini 3.5 Flash (Thông minh, Ổn định)",
        "raw_docs": [],
        "raw_chapters": {},
        "trans_prompt": "Bạn là một dịch giả tiểu thuyết chuyên nghiệp. Dịch mượt mà, thuần Việt, giữ nguyên đoạn văn và không tự ý thêm bớt tình tiết."
    }

if "translation_queue" not in st.session_state:
    st.session_state.translation_queue = queue.Queue()
if "worker_running" not in st.session_state:
    st.session_state.worker_running = False
if "key_rotation_index" not in st.session_state:
    st.session_state.key_rotation_index = 0

# ==========================================
# 2. HÀM HỖ TRỢ & CALL API
# ==========================================
def load_user_data_from_supabase(email):
    if supabase:
        try:
            res = supabase.table("workspaces").select("workspace_data").eq("email", email).execute()
            if res.data and len(res.data) > 0:
                saved_data = res.data[0].get("workspace_data")
                st.session_state.novel_data.update(saved_data)
                st.toast("🎉 Đã tải dữ liệu trên mây!", icon="✅")
        except Exception as e: 
            st.error(f"Lỗi tải dữ liệu: {e}")

def save_user_data_to_supabase():
    if supabase and st.session_state.authenticated and st.session_state.user_email:
        try:
            supabase.table("workspaces").upsert({"email": st.session_state.user_email, "workspace_data": st.session_state.novel_data}).execute()
            st.toast("💾 Đã lưu dữ liệu tự động!", icon="☁️")
        except Exception as e: 
            st.error(f"Lỗi lưu Supabase: {e}")

def scrape_web_chapter(url):
    """Cào nội dung và cố gắng lấy tiêu đề từ link truyện"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(url.strip(), headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Thử lấy tiêu đề (Title hoặc H1)
        title_tag = soup.find('h1')
        title = title_tag.get_text().strip() if title_tag else ""
        if not title and soup.title:
            title = soup.title.string.strip()
        if not title:
            title = "Chương Web Mới"

        # Thử tìm các div chứa nội dung truyện phổ biến
        content_div = soup.select_one('#chapter-c, .chapter-content, #chapter-content, .box-chap, .story-detail-content')
        
        if content_div:
            paragraphs = content_div.find_all('p')
            if paragraphs:
                text = "\n".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
            else:
                text = content_div.get_text(separator="\n", strip=True)
        else:
            # Fallback lấy toàn bộ thẻ p
            paragraphs = soup.find_all('p')
            if paragraphs and len(paragraphs) > 5:
                text = "\n".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
            else:
                text = soup.get_text(separator="\n", strip=True)
                
        return title, text if len(text) > 50 else "Không tìm thấy nội dung truyện ở link này."
    except Exception as e:
        return "Lỗi", f"❌ Lỗi cào web: {str(e)}"

def call_llm(system_prompt, prompt_text, api_keys, model_choice) -> tuple[bool, str]:
    gemini_keys = [k.strip() for k in re.split(r'[\n,;\s]+', api_keys.get("gemini", "")) if k.strip()]
    if not gemini_keys: 
        return False, "Chưa nhập Gemini API Key."
    
    if "3.5 Flash" in str(model_choice): model_name = "gemini-3.5-flash"
    elif "3.1 Flash-Lite" in str(model_choice): model_name = "gemini-3.1-flash-lite"
    elif "2.5 Pro" in str(model_choice): model_name = "gemini-2.5-pro"
    elif "2.5 Flash" in str(model_choice): model_name = "gemini-2.5-flash"
    else: model_name = "gemini-3.5-flash" 

    num_keys = len(gemini_keys)
    last_error = ""
    
    for i in range(num_keys):
        current_idx = (st.session_state.key_rotation_index + i) % num_keys
        current_key = gemini_keys[current_idx]
        try: 
            client = genai.Client(api_key=current_key)
            safety_settings = [
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            ]
            
            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                safety_settings=safety_settings,
                temperature=0.3
            )
            
            res = client.models.generate_content(model=model_name, contents=prompt_text, config=config)
            
            if res and res.text:
                st.session_state.key_rotation_index = (current_idx + 1) % num_keys
                return True, res.text
            else:
                last_error = "AI trả về kết quả rỗng (Có thể bị Google block ngầm)."
                
        except Exception as e:
            last_error = str(e)
            continue 
            
    return False, f"Lỗi API (Đã thử tất cả keys): {last_error}"

def process_single_chapter(chap_key, raw_text, api_keys, model_choice, novel_data_dict, trans_status_dict):
    max_retries = 3
    retry_count = 0
    
    base_prompt = novel_data_dict.get("trans_prompt", "Bạn là dịch giả.")
    system_prompt = base_prompt + "\n\n[LỆNH BẮT BUỘC]: Trả về trực tiếp bản dịch. Không giải thích."
    
    while retry_count < max_retries:
        success, result = call_llm(system_prompt, f"RAW CẦN DỊCH:\n\n{raw_text}", api_keys, model_choice)
        
        if success:
            novel_data_dict["raw_chapters"][chap_key]["translated"] = result
            trans_status_dict[chap_key] = "✅ Hoàn thành"
            break
        else:
            retry_count += 1
            if "429" in result or "quota" in result.lower() or "exhausted" in result.lower():
                trans_status_dict[chap_key] = f"⚠️ Quá tải API (Chờ 30s thử lại lần {retry_count}/{max_retries})"
                time.sleep(30)
            else:
                novel_data_dict["raw_chapters"][chap_key]["translated"] = f"❌ Lỗi: {result}"
                trans_status_dict[chap_key] = "❌ Lỗi Hệ Thống"
                break
                
    if retry_count >= max_retries:
        trans_status_dict[chap_key] = "❌ Thất bại (Hết Quota, đã thử 3 lần)"

def sequential_worker(q, api_keys, model_choice, novel_data_dict, trans_status_dict, delay_time):
    st.session_state.worker_running = True
    while not q.empty():
        chap_key = q.get()
        if chap_key in novel_data_dict.get("raw_chapters", {}):
            trans_status_dict[chap_key] = "🔄 Đang dịch..."
            raw_txt = novel_data_dict["raw_chapters"][chap_key]["raw"]
            process_single_chapter(chap_key, raw_txt, api_keys, model_choice, novel_data_dict, trans_status_dict)
            time.sleep(delay_time) 
        q.task_done()
    st.session_state.worker_running = False

# ==========================================
# 3. GIAO DIỆN ĐĂNG NHẬP
# ==========================================
if not st.session_state.authenticated:
    st.title("⚡ Máy Dịch Truyện - Tối Giản")
    email = st.text_input("Email:")
    password = st.text_input("Mật khẩu:", type="password")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 Đăng nhập", use_container_width=True):
            if supabase:
                try:
                    supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.authenticated = True; st.session_state.user_email = email
                    load_user_data_from_supabase(email)
                    st.rerun()
                except Exception as e: st.error(f"Lỗi: {e}")
            else:
                st.session_state.authenticated = True; st.session_state.user_email = email
                st.rerun()
    with col2:
        if st.button("📝 Đăng ký", use_container_width=True):
            if supabase:
                try: supabase.auth.sign_up({"email": email, "password": password}); st.success("Đăng ký thành công!")
                except Exception as e: st.error(f"Lỗi: {e}")
    st.stop()

# ==========================================
# 4. GIAO DIỆN CHÍNH & CHỨC NĂNG
# ==========================================
st.sidebar.title("⚡ Menu")
menu = st.sidebar.radio("Chọn chức năng:", ["1. Cấu hình API", "2. Nguồn Truyện (Cào/Tải Raw)", "3. Dịch & Quản Lý"])
if st.sidebar.button("💾 Lưu Dữ Liệu"): save_user_data_to_supabase()
if st.sidebar.button("🚪 Đăng xuất"): st.session_state.authenticated = False; st.rerun()

# --- MENU 1: CẤU HÌNH API ---
if menu == "1. Cấu hình API":
    st.header("🔑 Cấu hình API & Model")
    st.session_state.novel_data["api_keys"]["gemini"] = st.text_area("Gemini API Keys (Mỗi dòng 1 key, tự động xoay vòng):", value=st.session_state.novel_data["api_keys"].get("gemini", ""), height=150)
    
    st.session_state.novel_data["selected_model"] = st.selectbox(
        "Lựa chọn Model Dịch:", 
        [
            "Gemini 3.5 Flash (Thông minh, Ổn định)", 
            "Gemini 3.1 Flash-Lite (Nhanh, Tiết kiệm chi phí)", 
            "Gemini 2.5 Pro (Suy luận sâu sắc cho truyện khó)",
            "Gemini 2.5 Flash (Tối ưu khối lượng lớn, Độ trễ thấp)"
        ],
        index=0
    )
    st.session_state.novel_data["trans_prompt"] = st.text_area("Luật Dịch (Prompt):", value=st.session_state.novel_data.get("trans_prompt", ""), height=150)
    if st.button("💾 Lưu Cấu Hình"): save_user_data_to_supabase()

# --- MENU 2: NGUỒN TRUYỆN (CÀO WEB / TẢI FILE) ---
elif menu == "2. Nguồn Truyện (Cào/Tải Raw)":
    st.header("📥 Thêm Nội Dung Cần Dịch")
    
    tab1, tab2 = st.tabs(["🌐 Cào Raw từ Web", "📂 Tải File .TXT"])
    
    with tab1:
        st.subheader("Cào nhiều chương cùng lúc")
        urls_input = st.text_area("Nhập danh sách Link (Mỗi dòng 1 URL):", placeholder="https://truyen.../chuong-1\nhttps://truyen.../chuong-2")
        
        if st.button("🕷️ Bắt đầu cào & Thêm vào hàng đợi dịch", use_container_width=True):
            if urls_input.strip():
                urls = [u for u in urls_input.split('\n') if u.strip()]
                if "raw_chapters" not in st.session_state.novel_data: st.session_state.novel_data["raw_chapters"] = {}
                
                success_count = 0
                with st.spinner(f"Đang cào {len(urls)} link..."):
                    for i, url in enumerate(urls):
                        title, scraped_text = scrape_web_chapter(url)
                        if "❌" not in scraped_text:
                            # Đảm bảo tên không bị trùng
                            chap_key = f"{title}" if title not in st.session_state.novel_data["raw_chapters"] else f"{title} ({i+1})"
                            st.session_state.novel_data["raw_chapters"][chap_key] = {"raw": scraped_text, "translated": ""}
                            success_count += 1
                        else:
                            st.error(f"Lỗi ở link {url}: {scraped_text}")
                            
                if success_count > 0:
                    save_user_data_to_supabase()
                    st.success(f"Đã cào thành công {success_count} chương và đưa thẳng vào phần Dịch & Quản Lý!")
                    time.sleep(1.5)
            else: 
                st.warning("Vui lòng nhập ít nhất 1 link.")

    with tab2:
        st.subheader("Tải File Gốc (Dành cho raw gộp chung)")
        uploaded_file = st.file_uploader("Chọn file TXT từ máy tính:", type=["txt"])
        if uploaded_file is not None:
            content = uploaded_file.read().decode("utf-8", errors="ignore")
            if "raw_docs" not in st.session_state.novel_data: st.session_state.novel_data["raw_docs"] = []
            
            existing_names = [d["filename"] for d in st.session_state.novel_data["raw_docs"]]
            if uploaded_file.name not in existing_names:
                st.session_state.novel_data["raw_docs"].append({"filename": uploaded_file.name, "content": content})
                save_user_data_to_supabase()
                st.success(f"Đã lưu file: {uploaded_file.name}")
            else: st.info("File này đã tồn tại.")
        
        if st.session_state.novel_data.get("raw_docs"):
            st.divider()
            doc_names = [d["filename"] for d in st.session_state.novel_data["raw_docs"]]
            selected_doc = st.selectbox("Chọn file Raw cần tách thành từng chương:", doc_names)
            doc_content = next((d["content"] for d in st.session_state.novel_data["raw_docs"] if d["filename"] == selected_doc), "")
            
            split_method = st.radio("Phương pháp tách:", ["🤖 Tự động thông minh", "✍️ Tùy chỉnh (Regex/Từ khóa)"])
            if "Tự động" in split_method: split_pattern = r"(?im)(?=^(?:第.*?章|Chương\s+|Chap\s+|Chapter\s+))"
            else: split_pattern = st.text_input("Từ khóa:", value="Chương ")

            if st.button("✂️ Tách File & Đưa vào hàng đợi", use_container_width=True):
                if "Tự động" in split_method:
                    chunks = re.split(split_pattern, doc_content)
                else:
                    try: chunks = re.split(f"(?={split_pattern})", doc_content)
                    except re.error:
                        chunks_raw = doc_content.split(split_pattern)
                        chunks = [c if i == 0 else (split_pattern + c) for i, c in enumerate(chunks_raw)]
                        
                chunks = [c.strip() for c in chunks if len(c.strip()) > 10]
                if "raw_chapters" not in st.session_state.novel_data: st.session_state.novel_data["raw_chapters"] = {}
                
                chap_idx = len(st.session_state.novel_data["raw_chapters"]) + 1
                for chunk in chunks:
                    first_line = chunk.split('\n')[0][:40].strip() + "..."
                    chap_key = f"Chương_Tách_{chap_idx} ({first_line})"
                    st.session_state.novel_data["raw_chapters"][chap_key] = {"raw": chunk, "translated": ""}
                    chap_idx += 1
                    
                save_user_data_to_supabase()
                st.success(f"Đã tách {len(chunks)} chương thành công!")

# --- MENU 3: DỊCH & QUẢN LÝ ---
elif menu == "3. Dịch & Quản Lý":
    st.header("⚡ Dịch Thuật & Quản Lý Chương")

    if not st.session_state.novel_data.get("raw_chapters"):
        st.info("💡 Danh sách trống. Hãy qua mục '2. Nguồn Truyện' để cào Web hoặc tải file lên nhé.")
    else:
        chap_keys = list(st.session_state.novel_data["raw_chapters"].keys())
        
        # --- NÚT XUẤT FILE ---
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for chap_key, data in st.session_state.novel_data["raw_chapters"].items():
                content_to_save = data["translated"] if data["translated"] else data["raw"]
                safe_filename = re.sub(r'[\\/*?:"<>|]', "", chap_key) + ".txt"
                zip_file.writestr(safe_filename, content_to_save.encode("utf-8"))
        
        st.download_button("📥 Tải tất cả chương (.ZIP)", data=zip_buffer.getvalue(), file_name="Truyen_Da_Dich.zip", mime="application/zip", use_container_width=True)
        st.divider()

        # --- BẢNG ĐIỀU KHIỂN DỊCH HÀNG LOẠT ---
        st.subheader("🚀 Chạy dịch ngầm hàng loạt")
        selected_batch = st.multiselect("Chọn các chương cần dịch:", chap_keys)
        col_b1, col_b2 = st.columns([1, 1])
        with col_b1:
            if st.button("▶️ Đưa vào hàng chờ dịch ngầm", use_container_width=True):
                model_choice = st.session_state.novel_data.get("selected_model", "3.5 Flash")
                delay_time = 15 if "Pro" in model_choice else 5 
                
                count = 0
                for c_key in selected_batch:
                    if st.session_state.trans_status.get(c_key) != "🔄 Đang dịch...":
                        st.session_state.trans_status[c_key] = "⏳ Đang chờ..."
                        st.session_state.translation_queue.put(c_key)
                        count += 1
                
                if count > 0 and not st.session_state.worker_running:
                    t = threading.Thread(
                        target=sequential_worker, 
                        args=(
                            st.session_state.translation_queue,
                            st.session_state.novel_data["api_keys"],
                            model_choice,
                            st.session_state.novel_data,
                            st.session_state.trans_status,
                            delay_time
                        )
                    )
                    t.start()
                    st.success(f"Đã thêm {count} chương vào hàng đợi dịch!")
                    time.sleep(1)
                    st.rerun()
        with col_b2:
            if st.button("🔄 Cập nhật tiến độ UI", use_container_width=True): st.rerun()

        active = {k: v for k, v in st.session_state.trans_status.items() if "🔄" in v or "⏳" in v or "⚠️" in v}
        if active:
            st.info("⏳ Đang chạy ngầm:\n" + "\n".join([f"- **{k}**: {v}" for k, v in active.items()]))
        
        st.divider()
        
        # --- CHI TIẾT TỪNG CHƯƠNG ---
        st.subheader("📖 Xem & Chỉnh sửa chi tiết")
        selected_chap = st.selectbox("👉 Chọn chương:", chap_keys)
        chap_data = st.session_state.novel_data["raw_chapters"][selected_chap]
        status = st.session_state.trans_status.get(selected_chap, "Chưa dịch")
        
        if "❌" in status or "⚠️" in status: st.error(f"**Trạng thái:** `{status}`")
        else: st.caption(f"**Trạng thái:** `{status}`")
            
        if st.button("🗑️ Xóa chương này"):
            del st.session_state.novel_data["raw_chapters"][selected_chap]
            save_user_data_to_supabase()
            st.rerun()
        
        col_raw, col_trans = st.columns(2)
        with col_raw:
            st.markdown("**Bản Raw (Gốc)**")
            raw_text = st.text_area("Nội dung Raw:", value=chap_data["raw"], height=500, key=f"raw_{selected_chap}")
        with col_trans:
            st.markdown("**Bản Dịch**")
            if st.button("🌐 Ép dịch TRỰC TIẾP chương này", use_container_width=True):
                with st.spinner("Đang dịch..."):
                    process_single_chapter(
                        selected_chap, raw_text, 
                        st.session_state.novel_data["api_keys"], 
                        st.session_state.novel_data.get("selected_model", "3.5 Flash"), 
                        st.session_state.novel_data, st.session_state.trans_status
                    )
                    save_user_data_to_supabase()
                    st.rerun()
            
            trans_text = st.text_area("Nội dung Dịch:", value=chap_data["translated"], height=500, key=f"trans_{selected_chap}")
            
        if st.button("💾 LƯU CHỈNH SỬA TAY", use_container_width=True):
            st.session_state.novel_data["raw_chapters"][selected_chap]["raw"] = raw_text
            st.session_state.novel_data["raw_chapters"][selected_chap]["translated"] = trans_text
            save_user_data_to_supabase()
            st.success("Đã lưu chỉnh sửa!")
