import streamlit as st
import requests
import re
import time
import threading
import queue
import io
import zipfile
import json
import concurrent.futures
from datetime import datetime
from bs4 import BeautifulSoup
from supabase import create_client, Client, ClientOptions
from google import genai
from google.genai import types

# ==========================================
# 1. CẤU HÌNH TRANG VÀ KẾT NỐI SUPABASE
# ==========================================
st.set_page_config(page_title="Web Truyện & Máy Dịch", page_icon="⚡", layout="wide")

# CSS tùy chỉnh để tạo hiệu ứng vuốt ngang các truyện (Giao diện hiển thị)
st.markdown("""
    <style>
    .scroll-container {
        display: flex;
        overflow-x: auto;
        gap: 15px;
        padding-bottom: 15px;
    }
    .truyen-card {
        min-width: 160px;
        height: 220px;
        background-color: #2c3e50;
        color: white;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        box-shadow: 2px 2px 8px rgba(0,0,0,0.2);
        font-weight: bold;
        cursor: pointer;
    }
    </style>
""", unsafe_allow_html=True)

SUPABASE_URL = ""
SUPABASE_KEY = ""
try:
    if "SUPABASE_URL" in st.secrets: SUPABASE_URL = st.secrets["SUPABASE_URL"]
    if "SUPABASE_KEY" in st.secrets: SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception: pass

@st.cache_resource
def init_supabase():
    if SUPABASE_URL and SUPABASE_KEY:
        try: 
            opts = ClientOptions(postgrest_client_timeout=60, storage_client_timeout=60)
            return create_client(SUPABASE_URL, SUPABASE_KEY, options=opts)
        except Exception: return None
    return None

supabase = init_supabase()

# Khởi tạo Session State
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "page" not in st.session_state: st.session_state.page = "home"
if "trans_status" not in st.session_state: st.session_state.trans_status = {}
if "novel_data" not in st.session_state:
    st.session_state.novel_data = {
        "api_keys": {"gemini": ""},
        "selected_model": "Gemini 3.5 Flash (Thông minh, Ổn định)",
        "raw_docs": [],
        "raw_chapters": {},
        "trans_prompt": "Bạn là một dịch giả tiểu thuyết chuyên nghiệp. Dịch mượt mà, thuần Việt, giữ nguyên đoạn văn và không tự ý thêm bớt tình tiết."
    }

if "worker_running" not in st.session_state: st.session_state.worker_running = False

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

# --- CÁC HÀM XỬ LÝ CÀO WEB VÀ ZHIHU ---
def parse_zhihu_content(soup):
    texts = []
    script_tag = soup.find('script', id='js-initialData')
    if script_tag and script_tag.string:
        try:
            data = json.loads(script_tag.string)
            initial_state = data.get('initialState', {})
            entities = initial_state.get('entities', {})
            articles = entities.get('articles', {})
            for item_id, item_data in articles.items():
                if 'content' in item_data:
                    c_soup = BeautifulSoup(item_data['content'], 'html.parser')
                    texts.append(c_soup.get_text(separator="\n", strip=True))
                    
            if not texts:
                str_data = json.dumps(initial_state, ensure_ascii=False)
                found_contents = re.findall(r'"content"\s*:\s*"([^"]+)"', str_data)
                for fc in found_contents:
                    if len(fc) > 200:
                        c_soup = BeautifulSoup(fc.encode().decode('unicode-escape', errors='ignore'), 'html.parser')
                        texts.append(c_soup.get_text(separator="\n", strip=True))
        except Exception: pass

    if not texts:
        content_nodes = soup.find_all(['div', 'section', 'article'], class_=re.compile(r'(Post-RichText|BodyModule|css-1y8291e|PaidColumn)', re.IGNORECASE))
        for node in content_nodes:
            txt = node.get_text(separator="\n", strip=True)
            if len(txt) > 100: texts.append(txt)

    if not texts:
        ps = soup.find_all('p')
        if len(ps) > 5: texts = [p.get_text().strip() for p in ps if p.get_text().strip()]

    return "\n\n".join(texts) if texts else ""

def scrape_zhihu_url(url, custom_cookie=""):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.7',
        }
        cookie_val = custom_cookie.strip()
        if cookie_val:
            if cookie_val.startswith('[') and cookie_val.endswith(']'):
                try:
                    cookie_list = json.loads(cookie_val)
                    cookie_val = "; ".join([f"{c['name']}={c['value']}" for c in cookie_list if 'name' in c and 'value' in c])
                except Exception: pass
            headers['Cookie'] = cookie_val

        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = res.apparent_encoding
        res.raise_for_status() 
        
        soup = BeautifulSoup(res.text, 'html.parser')
        text = parse_zhihu_content(soup)
        return text if len(text) >= 50 else None, None
    except Exception as e: 
        return None, str(e)

def scrape_web_chapter(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(url.strip(), headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        title_tag = soup.find('h1')
        title = title_tag.get_text().strip() if title_tag else ""
        if not title and soup.title: title = soup.title.string.strip()
        if not title: title = "Chương Web Mới"

        content_div = soup.select_one('#chapter-c, .chapter-content, #chapter-content, .box-chap, .story-detail-content')
        if content_div:
            paragraphs = content_div.find_all('p')
            if paragraphs: text = "\n".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
            else: text = content_div.get_text(separator="\n", strip=True)
        else:
            paragraphs = soup.find_all('p')
            if paragraphs and len(paragraphs) > 5: text = "\n".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
            else: text = soup.get_text(separator="\n", strip=True)
                
        return title, text if len(text) > 50 else "Không tìm thấy nội dung truyện ở link này."
    except Exception as e:
        return "Lỗi", f"❌ Lỗi cào web: {str(e)}"

# --- HÀM GỌI LLM & WORKER DỊCH ---
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
        current_key = gemini_keys[i]
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
                return True, res.text
            else:
                last_error = "AI trả về kết quả rỗng (Có thể bị Google block ngầm)."
                
        except Exception as e:
            last_error = str(e)
            continue 
            
    return False, f"Lỗi API: {last_error}"

def process_single_chapter(chap_key, raw_text, api_keys, model_choice, novel_data_dict, trans_status_dict, custom_prompt=None):
    max_retries = 3
    retry_count = 0
    base_prompt = custom_prompt if custom_prompt else novel_data_dict.get("trans_prompt", "Bạn là dịch giả.")
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

def batch_worker(chap_keys_list, api_keys, model_choice, novel_data_dict, trans_status_dict, delay_time, user_email):
    st.session_state.worker_running = True
    batch_size = 3 
    keys_to_translate = [
        k for k in chap_keys_list 
        if not novel_data_dict["raw_chapters"][k].get("translated") or "❌" in novel_data_dict["raw_chapters"][k].get("translated", "")
    ]

    for i in range(0, len(keys_to_translate), batch_size):
        batch = keys_to_translate[i : i + batch_size]
        for k in batch: trans_status_dict[k] = "🔄 Đang dịch..."
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
            futures = [
                executor.submit(process_single_chapter, k, novel_data_dict["raw_chapters"][k]["raw"], api_keys, model_choice, novel_data_dict, trans_status_dict) for k in batch
            ]
            concurrent.futures.wait(futures)
            
        if supabase and user_email:
            try: supabase.table("workspaces").upsert({"email": user_email, "workspace_data": novel_data_dict}).execute()
            except Exception: pass
        time.sleep(delay_time)
    st.session_state.worker_running = False

# ==========================================
# 3. GIAO DIỆN ĐĂNG NHẬP
# ==========================================
if not st.session_state.authenticated:
    st.title("⚡ Đăng Nhập Hệ Thống")
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
# 4. GIAO DIỆN CHÍNH & SIDEBAR
# ==========================================
st.sidebar.title("📚 Danh Mục")
the_loai = ["Tất cả", "Ngôn Tình", "Đam Mỹ", "Xuyên Không", "Hệ Thống"]
chon_the_loai = st.sidebar.radio("Chọn thể loại:", the_loai)

st.sidebar.divider()
if st.sidebar.button("🏠 Trang Chủ"):
    st.session_state.page = 'home'
    st.rerun()

if st.sidebar.button("⚙️ Trang Chủ Sở Hữu (Ẩn)"):
    st.session_state.page = 'admin'
    st.rerun()

st.sidebar.divider()
if st.sidebar.button("💾 Lưu Dữ Liệu Lên Mây"): save_user_data_to_supabase()
if st.sidebar.button("🚪 Đăng xuất"): st.session_state.authenticated = False; st.rerun()


# ==========================================
# GIAO DIỆN TRANG CHỦ ĐỌC TRUYỆN
# ==========================================
if st.session_state.page == 'home':
    st.title("Trang Chủ Đọc Truyện")
    
    st.subheader("⭐ Truyện 5 Sao (Vuốt ngang)")
    st.markdown("""
        <div class="scroll-container">
            <div class="truyen-card">Lạc Sủng<br>(Bìa 1)</div>
            <div class="truyen-card">Xuyên Không...<br>(Bìa 2)</div>
            <div class="truyen-card">Truyện 3<br>(Bìa 3)</div>
            <div class="truyen-card">Truyện 4<br>(Bìa 4)</div>
            <div class="truyen-card">Truyện 5<br>(Bìa 5)</div>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("📖 Đọc thử truyện: Xuyên Không Thành Hệ Thống"):
        st.session_state.page = 'read'
        st.rerun()

    st.subheader("🔥 Truyện Đề Xuất")
    st.markdown("""
        <div class="scroll-container">
            <div class="truyen-card">Truyện A</div>
            <div class="truyen-card">Truyện B</div>
            <div class="truyen-card">Truyện C</div>
        </div>
    """, unsafe_allow_html=True)

    st.subheader("🆕 Truyện Mới Đăng")
    st.markdown("""
        <div class="scroll-container">
            <div class="truyen-card">Truyện X</div>
            <div class="truyen-card">Truyện Y</div>
            <div class="truyen-card">Truyện Z</div>
        </div>
    """, unsafe_allow_html=True)

# ==========================================
# GIAO DIỆN ĐỌC TRUYỆN CHI TIẾT
# ==========================================
elif st.session_state.page == 'read':
    st.button("⬅️ Quay lại Trang Chủ", on_click=lambda: st.session_state.update(page='home'))
    st.title("📖 Xuyên Không Thành Hệ Thống")
    st.write("**Văn án:** Lâm Duyệt hoảng hốt khi thấy cơ thể thạch của mình đang phát sáng...")
    
    with st.expander("⚠️ MỞ KHÓA CHƯƠNG (Bấm vào đây)"):
        st.warning("Vui lòng xem quảng cáo để đọc tiếp!")
        st.markdown("[Nhấn vào đây để xem quảng cáo (Link Shopee)](https://shopee.vn)")
        if st.button("Tôi đã xem xong"):
            st.success("Đã mở khóa toàn bộ truyện!")
    
    st.divider()
    st.subheader("Chương 1: Xuyên không")
    st.write("Nội dung chương 1 hiện ra ở đây... độc giả có thể đọc bình thường.")
    
    st.write("---")
    col1, col2 = st.columns(2)
    with col1: st.button("👍 Đề xuất truyện này")
    with col2: st.button("⭐ Đánh giá 5 Sao")

# ==========================================
# GIAO DIỆN QUẢN LÝ (TRANG ẨN KẾT HỢP TOOL DỊCH)
# ==========================================
elif st.session_state.page == 'admin':
    st.title("⚙️ Bảng Điều Khiển Chủ Sở Hữu")
    
    tab_sua, tab_cao, tab_dich, tab_thong_ke = st.tabs([
        "📝 Cấu Hình & Sửa Truyện", 
        "🌐 Nguồn Truyện (Cào/Tải Raw)", 
        "✂️ Dịch & Quản Lý Chương", 
        "📊 Thống Kê"
    ])
    
    # ------------------ TAB 1: SỬA TRUYỆN & CẤU HÌNH API ------------------
    with tab_sua:
        st.subheader("1. Chỉnh sửa thông tin truyện (Giao diện gốc)")
        st.text_input("Tên truyện", value="Xuyên Không Thành Hệ Thống")
        col_tinh_trang, col_luot_xem = st.columns(2)
        col_tinh_trang.selectbox("Tình trạng", ["Đang viết", "Hoàn thành", "Tạm ngưng"])
        col_luot_xem.text_input("Lượt xem (Chỉ đọc)", value="15,200", disabled=True)
        st.multiselect("Thể loại (Gắn tag)", ["Chủ Thụ", "Đam Mỹ", "Hệ Thống", "Xuyên Không"], default=["Đam Mỹ", "Xuyên Không"])
        
        st.divider()
        st.subheader("2. Cấu hình Máy Dịch API & Model")
        st.session_state.novel_data["api_keys"]["gemini"] = st.text_area("Gemini API Keys (Mỗi dòng 1 key, tự động xoay vòng):", value=st.session_state.novel_data["api_keys"].get("gemini", ""), height=100)
        st.session_state.novel_data["selected_model"] = st.selectbox("Lựa chọn Model Dịch:", [
            "Gemini 3.5 Flash (Thông minh, Ổn định)", 
            "Gemini 3.1 Flash-Lite (Cực nhanh)", 
            "Gemini 2.5 Pro (Cao cấp)", 
            "Gemini 2.5 Flash"
        ], index=0)
        st.session_state.novel_data["trans_prompt"] = st.text_area("Prompt Dịch:", value=st.session_state.novel_data.get("trans_prompt", ""), height=100)
        if st.button("💾 Lưu Cấu Hình Hệ Thống", use_container_width=True): 
            save_user_data_to_supabase()
            st.success("✅ Đã lưu cấu hình!")

    # ------------------ TAB 2: CÀO TRUYỆN & QUẢN LÝ RAW ------------------
    with tab_cao:
        c_tab1, c_tab2 = st.tabs(["🌐 Cào Raw từ Web", "📂 Quản Lý File Raw & Tách Chương"])
        with c_tab1:
            urls_input = st.text_area("Nhập danh sách Link (mỗi link 1 dòng):", height=100)
            custom_cookie = st.text_input("Cookie Zhihu (Tùy chọn):")
            if st.button("🕷️ Bắt đầu cào", use_container_width=True):
                if urls_input.strip():
                    urls = [u.strip() for u in urls_input.split('\n') if u.strip()]
                    success_count = 0
                    with st.spinner(f"Đang cào {len(urls)} link..."):
                        for url in urls:
                            if "zhihu.com" in url:
                                raw_text, err_msg = scrape_zhihu_url(url, custom_cookie)
                                if raw_text:
                                    file_name = f"Zhihu_{datetime.now().strftime('%H%M%S')}.txt"
                                    st.session_state.novel_data["raw_docs"].append({"filename": file_name, "content": raw_text})
                                    success_count += 1
                            else:
                                title, scraped_text = scrape_web_chapter(url)
                                if "❌" not in scraped_text:
                                    file_name = f"Web_{datetime.now().strftime('%H%M%S')}.txt"
                                    st.session_state.novel_data["raw_docs"].append({"filename": file_name, "content": scraped_text})
                                    success_count += 1
                    if success_count > 0: save_user_data_to_supabase(); st.success(f"🎉 Cào thành công {success_count} link!")
                else: st.warning("Nhập ít nhất 1 link.")

        with c_tab2:
            uploaded_file = st.file_uploader("Tải lên file tiểu thuyết (.txt)", type=["txt"])
            if uploaded_file is not None:
                existing_names = [d["filename"] for d in st.session_state.novel_data.get("raw_docs", [])]
                if uploaded_file.name not in existing_names:
                    content = uploaded_file.read().decode('utf-8', errors='ignore')
                    st.session_state.novel_data["raw_docs"].append({"filename": uploaded_file.name, "content": content})
                    save_user_data_to_supabase(); st.success("✅ Tải lên thành công!"); time.sleep(1); st.rerun()

            if st.session_state.novel_data.get("raw_docs"):
                doc_names = [d["filename"] for d in st.session_state.novel_data["raw_docs"]]
                selected_doc_name = st.selectbox("Chọn File để Tách chương:", doc_names)
                selected_doc = next(d for d in st.session_state.novel_data["raw_docs"] if d["filename"] == selected_doc_name)
                
                col1, col2 = st.columns(2)
                with col1: regex_split = st.text_input("Regex Tách Chương:", value=r"(第\s*[0-9一二三四五六七八九十百千万零]+\s*[章回节集卷部])")
                with col2: str_split = st.text_input("Hoặc Tách theo Từ Khóa:")
                
                if st.button("✂️ Bắt đầu Tách Chương"):
                    raw_text = selected_doc["content"]
                    if str_split: 
                        parts = raw_text.split(str_split)
                        titles = [f"{str_split} {i}" for i in range(1, len(parts))]
                        contents = parts[1:]
                    else: 
                        parts = re.split(regex_split, raw_text)
                        if len(parts) > 1: titles, contents = parts[1::2], parts[2::2]
                        else: titles, contents = [], []
                    
                    if titles:
                        for t, c in zip(titles, contents):
                            chap_name = f"[{selected_doc_name[:10]}] {t.strip()}"
                            st.session_state.novel_data["raw_chapters"][chap_name] = {"raw": f"{chap_name}\n{c.strip()}", "translated": ""}
                            st.session_state.trans_status[chap_name] = "⏳ Đợi Dịch"
                        save_user_data_to_supabase()
                        st.success(f"✅ Đã tách {len(titles)} chương!")
                    else: st.warning("Không tìm thấy chương nào!")
                
                if st.button("🗑️ Xóa File này"):
                    st.session_state.novel_data["raw_docs"] = [d for d in st.session_state.novel_data["raw_docs"] if d["filename"] != selected_doc_name]
                    save_user_data_to_supabase(); st.rerun()

    # ------------------ TAB 3: DỊCH & QUẢN LÝ CHƯƠNG ------------------
    with tab_dich:
        chapters = st.session_state.novel_data.get("raw_chapters", {})
        if not chapters: st.info("Chưa có chương nào trong hàng chờ.")
        else:
            chap_keys = list(chapters.keys())
            st.write(f"**Tổng số chương hiện có:** {len(chap_keys)}")
            
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1: delay = st.number_input("Delay dịch (giây):", value=2.0, min_value=0.5)
            with col_b2:
                if st.button("🚀 Dịch Tự Động (Batch)", use_container_width=True):
                    if not st.session_state.worker_running:
                        threading.Thread(target=batch_worker, args=(chap_keys, st.session_state.novel_data["api_keys"], st.session_state.novel_data["selected_model"], st.session_state.novel_data, st.session_state.trans_status, delay, st.session_state.user_email), daemon=True).start()
                        st.toast("✅ Đã bắt đầu dịch!", icon="🚀")
            with col_b3: 
                if st.button("🗑️ Reset Dữ Liệu", use_container_width=True):
                    st.session_state.novel_data["raw_chapters"] = {}; st.session_state.trans_status = {}; save_user_data_to_supabase(); st.rerun()

            for k in chap_keys:
                if k not in st.session_state.trans_status: 
                    st.session_state.trans_status[k] = "✅ Hoàn thành" if chapters[k].get("translated") else "⏳ Đợi Dịch"
            
            st.divider()
            options = [f"{k}  ---  ({st.session_state.trans_status[k]})" for k in chap_keys]
            selected_option = st.selectbox("Chọn chương muốn xem:", options)
            
            if selected_option:
                selected_key = selected_option.split("  ---  ")[0]
                if st.button(f"✨ Bấm để Dịch chương này"):
                    st.session_state.trans_status[selected_key] = "🔄 Đang dịch..."
                    process_single_chapter(selected_key, chapters[selected_key]["raw"], st.session_state.novel_data["api_keys"], st.session_state.novel_data["selected_model"], st.session_state.novel_data, st.session_state.trans_status)
                    save_user_data_to_supabase(); st.rerun()
                
                col_raw, col_trans = st.columns(2)
                with col_raw:
                    st.markdown("🇨🇳 **Bản Raw**")
                    st.text_area("raw", chapters[selected_key]["raw"], height=400, label_visibility="collapsed")
                with col_trans:
                    st.markdown("🇻🇳 **Bản Dịch**")
                    st.text_area("trans", chapters[selected_key].get("translated", ""), height=400, label_visibility="collapsed")

            st.divider()
            export_text = ""
            for k in chap_keys:
                trans_text = chapters[k].get("translated", "").strip()
                if not trans_text or "❌" in trans_text or "⚠️" in trans_text: trans_text = "(Chương này lỗi/chưa dịch)"
                export_text += f"{k}\n\n{trans_text}\n\n{'-'*50}\n\n"
            
            if export_text:
                st.download_button(label="⬇️ Tải toàn bộ bản dịch (.txt)", data=export_text, file_name=f"Truyen_Dich.txt", mime="text/plain")

    # ------------------ TAB 4: THỐNG KÊ ------------------
    with tab_thong_ke:
        st.subheader("Thống kê chi tiết Hệ thống")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric(label="Tổng số người đọc", value="15,200", delta="+120")
        col_b.metric(label="Số đề xuất", value="1,400", delta="+15")
        col_c.metric(label="Đánh giá 5 Sao", value="850", delta="0")
