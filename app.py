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
    .stButton>button {
        height: 120px;
        font-weight: bold;
        border-radius: 10px;
        transition: 0.3s;
    }
    .stButton>button:hover {
        border-color: #ff4b4b;
        color: #ff4b4b;
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
if "current_novel" not in st.session_state: st.session_state.current_novel = ""
if "trans_status" not in st.session_state: st.session_state.trans_status = {}

if "novel_data" not in st.session_state:
    st.session_state.novel_data = {
        "api_keys": {"gemini": ""},
        "selected_model": "Gemini 3.5 Flash",
        "raw_docs": [],
        "raw_chapters": {},
        "trans_prompt": "Bạn là một dịch giả chuyên nghiệp..."
    }

# BẢO VỆ & NÂNG CẤP DỮ LIỆU CŨ (Tích hợp thêm Thể Loại)
if "danh_sach_truyen" not in st.session_state.novel_data:
    st.session_state.novel_data["danh_sach_truyen"] = [
        {"ten": "Xuyên Không Thành Hệ Thống", "khu_vuc": "5 Sao", "the_loai": ["Xuyên Không", "Hệ Thống"]},
        {"ten": "Lạc Sủng", "khu_vuc": "5 Sao", "the_loai": ["Ngôn Tình", "Đam Mỹ"]},
        {"ten": "Truyện Đề Xuất A", "khu_vuc": "Đề Xuất", "the_loai": ["Đô Thị"]}
    ]
else:
    # Nâng cấp các truyện cũ nếu chưa có trường 'the_loai'
    for t in st.session_state.novel_data["danh_sach_truyen"]:
        if "the_loai" not in t:
            t["the_loai"] = ["Ngôn Tình"] # Gắn tạm mặc định để không bị lỗi

if "worker_running" not in st.session_state: st.session_state.worker_running = False

# ==========================================
# 2. CÁC HÀM XỬ LÝ API VÀ CÀO WEB (GIỮ NGUYÊN)
# ==========================================
def parse_zhihu_content(soup):
    texts = []
    script_tag = soup.find('script', id='js-initialData')
    if script_tag and script_tag.string:
        try:
            data = json.loads(script_tag.string)
            texts.append(BeautifulSoup(data.get('initialState', {}).get('entities', {}).get('articles', {}).get(list(data['initialState']['entities']['articles'].keys())[0], {}).get('content', ''), 'html.parser').get_text(separator="\n", strip=True))
        except: pass
    if not texts: texts = [p.get_text().strip() for p in soup.find_all('p') if p.get_text().strip()]
    return "\n\n".join(texts) if texts else ""

def scrape_web_chapter(url):
    try:
        res = requests.get(url.strip(), headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.find('h1').get_text().strip() if soup.find('h1') else "Chương Web Mới"
        content_div = soup.select_one('#chapter-c, .chapter-content')
        text = "\n".join([p.get_text().strip() for p in content_div.find_all('p')]) if content_div else soup.get_text(separator="\n", strip=True)
        return title, text if len(text) > 50 else "Không tìm thấy nội dung."
    except Exception as e: return "Lỗi", f"❌ Lỗi: {str(e)}"

# ==========================================
# 3. THANH BÊN (SIDEBAR) 
# ==========================================
danh_sach_the_loai_goc = ["Ngôn Tình", "Đam Mỹ", "Xuyên Không", "Hệ Thống", "Cao H", "Xuyên Sách", "Đô Thị"]

st.sidebar.title("📚 Danh Mục")
chon_the_loai = st.sidebar.radio("Chọn thể loại:", ["Tất cả"] + danh_sach_the_loai_goc)

st.sidebar.divider()
if st.sidebar.button("🏠 Trang Chủ Đọc Truyện"):
    st.session_state.page = 'home'
    st.rerun()

if st.sidebar.button("⚙️ Khu Vực Quản Lý (Tác Giả)"):
    st.session_state.page = 'admin'
    st.rerun()

# ==========================================
# 4. GIAO DIỆN TRANG CHỦ ĐỌC TRUYỆN
# ==========================================
if st.session_state.page == 'home':
    st.title("Trang Chủ Đọc Truyện")
    
    # KỸ THUẬT LỌC TRUYỆN THEO DANH MỤC
    kho_truyen_goc = st.session_state.novel_data["danh_sach_truyen"]
    
    if chon_the_loai == "Tất cả":
        kho_truyen_hien_thi = kho_truyen_goc
    else:
        # Chỉ lấy những truyện mà "the_loai" chứa danh mục độc giả đang chọn
        kho_truyen_hien_thi = [t for t in kho_truyen_goc if chon_the_loai in t.get("the_loai", [])]
        st.info(f"🔍 Đang lọc các truyện thuộc thể loại: **{chon_the_loai}**")
        
    if not kho_truyen_hien_thi:
        st.warning(f"Hiện tại chưa có truyện nào thuộc thể loại '{chon_the_loai}'.")
    
    # --- KHU VỰC 1: TRUYỆN 5 SAO ---
    truyen_5sao = [t for t in kho_truyen_hien_thi if t["khu_vuc"] == "5 Sao"]
    if truyen_5sao:
        st.subheader("⭐ Truyện 5 Sao Đáng Đọc")
        for i in range(0, len(truyen_5sao), 4):
            cols = st.columns(4)
            for j in range(4):
                if i + j < len(truyen_5sao):
                    truyen = truyen_5sao[i+j]
                    with cols[j]:
                        if st.button(f"📖 {truyen['ten']}\n\n⭐⭐⭐⭐⭐", use_container_width=True, key=f"btn_5sao_{truyen['ten']}"):
                            st.session_state.current_novel = truyen['ten']
                            st.session_state.page = 'read'
                            st.rerun()
        st.write("---")
    
    # --- KHU VỰC 2: TRUYỆN ĐỀ XUẤT ---
    truyen_dexuat = [t for t in kho_truyen_hien_thi if t["khu_vuc"] == "Đề Xuất"]
    if truyen_dexuat:
        st.subheader("🔥 Truyện Đề Xuất")
        for i in range(0, len(truyen_dexuat), 4):
            cols = st.columns(4)
            for j in range(4):
                if i + j < len(truyen_dexuat):
                    truyen = truyen_dexuat[i+j]
                    with cols[j]:
                        if st.button(f"📖 {truyen['ten']}\n\n🔥 Hot", use_container_width=True, key=f"btn_dx_{truyen['ten']}"):
                            st.session_state.current_novel = truyen['ten']
                            st.session_state.page = 'read'
                            st.rerun()

# ==========================================
# 5. GIAO DIỆN ĐỌC TRUYỆN CHI TIẾT
# ==========================================
elif st.session_state.page == 'read':
    st.button("⬅️ Quay lại Trang Chủ", on_click=lambda: st.session_state.update(page='home'))
    
    novel_name = st.session_state.get("current_novel", "Truyện Không Tên")
    st.title(f"📖 {novel_name}")
    st.write(f"**Văn án:** Đây là đoạn giới thiệu của bộ truyện **{novel_name}**...")
    
    with st.expander("⚠️ MỞ KHÓA CHƯƠNG (Bấm vào đây)"):
        st.warning("Vui lòng xem quảng cáo để đọc tiếp!")
        st.markdown("[Nhấn vào đây để xem quảng cáo (Link Shopee)](https://shopee.vn)")
        if st.button("Tôi đã xem xong"):
            st.success("Đã mở khóa toàn bộ truyện!")
    
    st.divider()
    st.subheader("Chương 1: Bắt đầu")
    st.write(f"Nội dung chương 1 của truyện **{novel_name}** hiện ra ở đây...")
    
    st.write("---")
    col1, col2 = st.columns(2)
    with col1: 
        if st.button("👍 Đề xuất truyện này"): st.success("Cảm ơn bạn đã đề xuất!")
    with col2: 
        if st.button("⭐ Đánh giá 5 Sao"): st.success("Đã gửi đánh giá 5 sao!")

# ==========================================
# 6. GIAO DIỆN QUẢN LÝ
# ==========================================
elif st.session_state.page == 'admin':
    if not st.session_state.authenticated:
        st.title("🔒 Khu vực dành riêng cho Tác Giả")
        pwd = st.text_input("Nhập mật khẩu (Mặc định: 971856):", type="password")
        if st.button("Mở Khóa"):
            if pwd == "971856":
                st.session_state.authenticated = True
                st.rerun()
            else: st.error("Sai mật khẩu!")
    else:
        col_title, col_logout = st.columns([8, 2])
        with col_title: st.title("⚙️ Bảng Điều Khiển Chủ Sở Hữu")
        with col_logout: 
            if st.button("🚪 Đăng xuất", use_container_width=True): 
                st.session_state.authenticated = False
                st.rerun()
        
        tab_sua, tab_cao, tab_dich, tab_thong_ke = st.tabs([
            "📝 Quản Lý Truyện", 
            "🌐 Nguồn Raw", 
            "✂️ Dịch AI", 
            "📊 Thống Kê"
        ])
        
        # --- TAB: QUẢN LÝ VÀ ĐĂNG TRUYỆN MỚI ---
        with tab_sua:
            st.subheader("➕ Đăng Truyện Mới Lên Trang Chủ")
            
            c_ten, c_khu = st.columns([2, 1])
            with c_ten: ten_truyen_moi = st.text_input("Tên truyện muốn đăng:")
            with c_khu: khu_vuc_dang = st.selectbox("Hiển thị ở khu vực:", ["5 Sao", "Đề Xuất"])
            
            # Thêm ô chọn Thể loại (có thể chọn nhiều thẻ cùng lúc)
            the_loai_dang = st.multiselect("Gắn Thẻ Thể Loại:", danh_sach_the_loai_goc)
            
            if st.button("Phát Hành Truyện Này", type="primary"):
                if ten_truyen_moi.strip() != "" and len(the_loai_dang) > 0:
                    st.session_state.novel_data["danh_sach_truyen"].append({
                        "ten": ten_truyen_moi.strip(),
                        "khu_vuc": khu_vuc_dang,
                        "the_loai": the_loai_dang
                    })
                    st.success(f"🎉 Đã đẩy truyện '{ten_truyen_moi}' ra Trang Chủ!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Vui lòng nhập tên truyện và chọn ít nhất 1 thể loại!")
            
            st.divider()
            
            st.subheader("📋 Danh sách các truyện đang hiển thị")
            for idx, truyen in enumerate(st.session_state.novel_data["danh_sach_truyen"]):
                tag_str = ", ".join(truyen.get("the_loai", []))
                st.write(f"- **{truyen['ten']}** | Khu: {truyen['khu_vuc']} | Thể loại: [{tag_str}]")

        with tab_cao:
            st.write("Giao diện cào truyện...")
        with tab_dich:
            st.write("Giao diện dịch AI...")
        with tab_thong_ke:
            st.write("Giao diện thống kê...")
