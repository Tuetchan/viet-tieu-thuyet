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
st.set_page_config(page_title="Trang Đọc Truyện", page_icon="📖", layout="wide")

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
# 2. CÁC HÀM XỬ LÝ (GIỮ NGUYÊN)
# ==========================================
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
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = res.apparent_encoding
        res.raise_for_status() 
        soup = BeautifulSoup(res.text, 'html.parser')
        text = parse_zhihu_content(soup)
        return text if len(text) >= 50 else None, None
    except Exception as e: return None, str(e)

def scrape_web_chapter(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url.strip(), headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        title_tag = soup.find('h1')
        title = title_tag.get_text().strip() if title_tag else "Chương Web Mới"
        content_div = soup.select_one('#chapter-c, .chapter-content, #chapter-content, .box-chap, .story-detail-content')
        if content_div:
            paragraphs = content_div.find_all('p')
            text = "\n".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()]) if paragraphs else content_div.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)
        return title, text if len(text) > 50 else "Không tìm thấy nội dung."
    except Exception as e: return "Lỗi", f"❌ Lỗi cào web: {str(e)}"

def call_llm(system_prompt, prompt_text, api_keys, model_choice) -> tuple[bool, str]:
    gemini_keys = [k.strip() for k in re.split(r'[\n,;\s]+', api_keys.get("gemini", "")) if k.strip()]
    if not gemini_keys: return False, "Chưa nhập Gemini API Key."
    model_name = "gemini-3.5-flash"
    for current_key in gemini_keys:
        try: 
            client = genai.Client(api_key=current_key)
            config = types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.3)
            res = client.models.generate_content(model=model_name, contents=prompt_text, config=config)
            if res and res.text: return True, res.text
        except Exception as e: continue 
    return False, "Lỗi API."

def process_single_chapter(chap_key, raw_text, api_keys, model_choice, novel_data_dict, trans_status_dict, custom_prompt=None):
    system_prompt = novel_data_dict.get("trans_prompt", "") + "\n\n[LỆNH BẮT BUỘC]: Trả về trực tiếp bản dịch."
    success, result = call_llm(system_prompt, f"RAW CẦN DỊCH:\n\n{raw_text}", api_keys, model_choice)
    if success:
        novel_data_dict["raw_chapters"][chap_key]["translated"] = result
        trans_status_dict[chap_key] = "✅ Hoàn thành"
    else:
        novel_data_dict["raw_chapters"][chap_key]["translated"] = f"❌ Lỗi: {result}"
        trans_status_dict[chap_key] = "❌ Lỗi Hệ Thống"

def batch_worker(chap_keys_list, api_keys, model_choice, novel_data_dict, trans_status_dict, delay_time):
    st.session_state.worker_running = True
    batch_size = 3 
    keys_to_translate = [k for k in chap_keys_list if not novel_data_dict["raw_chapters"][k].get("translated")]
    for i in range(0, len(keys_to_translate), batch_size):
        batch = keys_to_translate[i : i + batch_size]
        for k in batch: trans_status_dict[k] = "🔄 Đang dịch..."
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
            futures = [executor.submit(process_single_chapter, k, novel_data_dict["raw_chapters"][k]["raw"], api_keys, model_choice, novel_data_dict, trans_status_dict) for k in batch]
            concurrent.futures.wait(futures)
        time.sleep(delay_time)
    st.session_state.worker_running = False

# ==========================================
# 3. THANH BÊN (SIDEBAR) - HIỂN THỊ CÔNG KHAI
# ==========================================
st.sidebar.title("📚 Danh Mục")
the_loai = ["Tất cả", "Ngôn Tình", "Đam Mỹ", "Xuyên Không", "Hệ Thống","Cao H","Xuyên Sách","Đô Thị"]
chon_the_loai = st.sidebar.radio("Chọn thể loại:", the_loai)

st.sidebar.divider()
if st.sidebar.button("🏠 Trang Chủ Đọc Truyện"):
    st.session_state.page = 'home'
    st.rerun()

# Nút này ai cũng thấy, nhưng bấm vào sẽ đòi mật khẩu
if st.sidebar.button("⚙️ Khu Vực Quản Lý (Tác Giả)"):
    st.session_state.page = 'admin'
    st.rerun()

# ==========================================
# 4. GIAO DIỆN TRANG CHỦ ĐỌC TRUYỆN (CÔNG KHAI)
# ==========================================
if st.session_state.page == 'home':
    st.title("Trang Chủ Đọc Truyện")
    
    st.subheader("⭐ Truyện 5 Sao Đáng Đọc")
    st.markdown("""
        <div class="scroll-container">
            <div class="truyen-card">Xuyên Không Thành Hệ Thống<br>(Nhấn 'Đọc thử' bên dưới)</div>
            <div class="truyen-card">Lạc Sủng<br>(Bìa 2)</div>
            <div class="truyen-card">Truyện 3<br>(Bìa 3)</div>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("📖 Đọc thử: Xuyên Không Thành Hệ Thống", type="primary"):
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

# ==========================================
# 5. GIAO DIỆN ĐỌC TRUYỆN CHI TIẾT (CÔNG KHAI)
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
    with col1: 
        if st.button("👍 Đề xuất truyện này"): st.success("Cảm ơn bạn đã đề xuất!")
    with col2: 
        if st.button("⭐ Đánh giá 5 Sao"): st.success("Đã gửi đánh giá 5 sao!")

# ==========================================
# 6. GIAO DIỆN QUẢN LÝ (KHÓA MẬT KHẨU)
# ==========================================
elif st.session_state.page == 'admin':
    # KIỂM TRA ĐĂNG NHẬP
    if not st.session_state.authenticated:
        st.title("🔒 Khu vực dành riêng cho Tác Giả")
        st.info("Vui lòng nhập mật khẩu để vào trang quản lý)")
        pwd = st.text_input("Nhập mật khẩu:", type="password")
        if st.button("Mở Khóa"):
            if pwd == "971856":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Sai mật khẩu!")
    
    # NẾU ĐÃ ĐĂNG NHẬP ĐÚNG MẬT KHẨU -> HIỆN CÔNG CỤ DỊCH VÀ QUẢN LÝ
    else:
        col_title, col_logout = st.columns([8, 2])
        with col_title: st.title("⚙️ Bảng Điều Khiển Chủ Sở Hữu")
        with col_logout: 
            if st.button("🚪 Đăng xuất", use_container_width=True): 
                st.session_state.authenticated = False
                st.rerun()
        
        tab_sua, tab_cao, tab_dich, tab_thong_ke = st.tabs([
            "📝 Cấu Hình & Sửa Truyện", 
            "🌐 Nguồn Truyện (Cào/Tải Raw)", 
            "✂️ Dịch & Quản Lý Chương", 
            "📊 Thống Kê"
        ])
        
        with tab_sua:
            st.subheader("1. Chỉnh sửa thông tin truyện")
            st.text_input("Tên truyện", value="Xuyên Không Thành Hệ Thống")
            col_tinh_trang, col_luot_xem = st.columns(2)
            col_tinh_trang.selectbox("Tình trạng", ["Đang viết", "Hoàn thành", "Tạm ngưng"])
            col_luot_xem.text_input("Lượt xem (Chỉ đọc)", value="15,200", disabled=True)
            
            st.divider()
            st.subheader("2. Cấu hình Máy Dịch API")
            st.session_state.novel_data["api_keys"]["gemini"] = st.text_area("Gemini API Keys:", value=st.session_state.novel_data["api_keys"].get("gemini", ""), height=100)
            if st.button("💾 Lưu Cấu Hình Hệ Thống", use_container_width=True): st.success("✅ Đã lưu!")

        with tab_cao:
            urls_input = st.text_area("Nhập danh sách Link cào raw (mỗi link 1 dòng):")
            if st.button("🕷️ Bắt đầu cào", use_container_width=True):
                if urls_input.strip():
                    urls = [u.strip() for u in urls_input.split('\n') if u.strip()]
                    with st.spinner("Đang cào..."):
                        for url in urls:
                            title, scraped_text = scrape_web_chapter(url)
                            if "❌" not in scraped_text:
                                file_name = f"Web_{datetime.now().strftime('%H%M%S')}.txt"
                                st.session_state.novel_data["raw_docs"].append({"filename": file_name, "content": scraped_text})
                    st.success("Cào thành công! Chuyển sang Tab Dịch để xử lý.")
            
            st.divider()
            uploaded_file = st.file_uploader("Hoặc Tải lên file txt từ máy tính", type=["txt"])
            if uploaded_file:
                content = uploaded_file.read().decode('utf-8', errors='ignore')
                st.session_state.novel_data["raw_docs"].append({"filename": uploaded_file.name, "content": content})
                st.success("Tải lên thành công!")
                
            if st.session_state.novel_data.get("raw_docs"):
                doc_names = [d["filename"] for d in st.session_state.novel_data["raw_docs"]]
                selected_doc_name = st.selectbox("Chọn File để Tách chương:", doc_names)
                if st.button("✂️ Bắt đầu Tách Chương"):
                    selected_doc = next(d for d in st.session_state.novel_data["raw_docs"] if d["filename"] == selected_doc_name)
                    parts = re.split(r"(第\s*[0-9一二三四五六七八九十百千万零]+\s*[章回节集卷部])", selected_doc["content"])
                    if len(parts) > 1:
                        titles, contents = parts[1::2], parts[2::2]
                        for t, c in zip(titles, contents):
                            chap_name = f"[{selected_doc_name[:10]}] {t.strip()}"
                            st.session_state.novel_data["raw_chapters"][chap_name] = {"raw": f"{chap_name}\n{c.strip()}", "translated": ""}
                            st.session_state.trans_status[chap_name] = "⏳ Đợi Dịch"
                        st.success(f"✅ Đã tách {len(titles)} chương!")

        with tab_dich:
            chapters = st.session_state.novel_data.get("raw_chapters", {})
            if not chapters: st.info("Chưa có chương nào.")
            else:
                chap_keys = list(chapters.keys())
                if st.button("🚀 Dịch Tự Động Toàn Bộ", type="primary"):
                    threading.Thread(target=batch_worker, args=(chap_keys, st.session_state.novel_data["api_keys"], "Gemini 3.5 Flash", st.session_state.novel_data, st.session_state.trans_status, 2), daemon=True).start()
                    st.toast("✅ Đã bắt đầu dịch!")
                
                for k in chap_keys:
                    if k not in st.session_state.trans_status: st.session_state.trans_status[k] = "⏳ Đợi Dịch"
                
                selected_option = st.selectbox("Chọn chương muốn xem:", [f"{k}  ---  ({st.session_state.trans_status[k]})" for k in chap_keys])
                if selected_option:
                    selected_key = selected_option.split("  ---  ")[0]
                    if st.button(f"✨ Dịch thủ công chương này"):
                        process_single_chapter(selected_key, chapters[selected_key]["raw"], st.session_state.novel_data["api_keys"], "Gemini 3.5 Flash", st.session_state.novel_data, st.session_state.trans_status)
                        st.rerun()
                    
                    col_raw, col_trans = st.columns(2)
                    with col_raw: st.text_area("Bản Raw", chapters[selected_key]["raw"], height=300)
                    with col_trans: st.text_area("Bản Dịch", chapters[selected_key].get("translated", ""), height=300)

        with tab_thong_ke:
            st.subheader("Thống kê")
            c1, c2, c3 = st.columns(3)
            c1.metric("Người đọc", "15,200", "+120")
            c2.metric("Đề xuất", "1,400", "+15")
            c3.metric("5 Sao", "850", "+5")
