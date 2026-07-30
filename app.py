import streamlit as st
import requests
import re
import time
import threading
import queue
import io
import zipfile
import json
from bs4 import BeautifulSoup
from supabase import create_client, Client

# ==========================================
# 1. CẤU HÌNH TRANG VÀ KẾT NỐI SUPABASE
# ==========================================
st.set_page_config(page_title="Máy Dịch Truyện Zhihu", page_icon="⚡", layout="wide")

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
        "web_cookie": "",
        "raw_full_text": "",
        "split_chapters_raw": {},
        "trans_prompt": "Bạn là một dịch giả tiểu thuyết chuyên nghiệp. Dịch mượt mà, thuần Việt, giữ nguyên đoạn văn và không tự ý thêm bớt tình tiết."
    }

workspace = st.session_state.novel_data
if "split_chapters_raw" not in workspace: workspace["split_chapters_raw"] = {}
if "raw_full_text" not in workspace: workspace["raw_full_text"] = ""
if "web_cookie" not in workspace: workspace["web_cookie"] = ""

def save_data(data_dict=None):
    if data_dict is None: data_dict = st.session_state.novel_data
    if supabase and st.session_state.authenticated and st.session_state.user_email:
        try:
            supabase.table("workspaces").upsert({"email": st.session_state.user_email, "workspace_data": data_dict}).execute()
            st.toast("💾 Đã lưu dữ liệu tự động!", icon="☁️")
        except Exception as e: st.error(f"Lỗi lưu Supabase: {e}")

# ==========================================
# 2. HÀM CÀO DỮ LIỆU & TÁCH PHẦN ZHIHU
# ==========================================
def parse_zhihu_content(soup):
    """Quét bóc tách toàn bộ nội dung trong trang Zhihu"""
    texts = []
    
    # 1. Quét qua dữ liệu ngầm js-initialData của Zhihu
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

    # 2. Quét DOM trực tiếp nếu cách 1 không ra
    if not texts:
        content_nodes = soup.find_all(['div', 'section', 'article'], class_=re.compile(r'(Post-RichText|BodyModule|css-1y8291e|PaidColumn)', re.IGNORECASE))
        for node in content_nodes:
            txt = node.get_text(separator="\n", strip=True)
            if len(txt) > 100:
                texts.append(txt)

    # 3. Quét thẻ <p> tổng quát nếu là dạng bài viết cơ bản
    if not texts:
        ps = soup.find_all('p')
        if len(ps) > 5:
            texts = [p.get_text().strip() for p in ps if p.get_text().strip()]

    return "\n\n".join(texts) if texts else ""

def scrape_zhihu_url(url, custom_cookie=""):
    """Hàm cào 1 URL Zhihu"""
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
        return text if len(text) >= 50 else None
    except Exception as e:
        return None

def auto_split_zhihu_sections(full_text):
    """Tách truyện Zhihu theo các dòng số đơn lẻ (1, 2, 3...) hoặc Chương"""
    # Pattern bắt dòng chỉ chứa 1 con số (VD: \n1\n hoặc \n2\n) hoặc từ "Chương/第"
    pattern = r"(?m)(^(?:[0-9]{1,3}|第.*?章|Chương\s+\d+)\s*$)"
    
    parts = re.split(pattern, full_text)
    
    res = {}
    
    # Nếu không tìm thấy dấu phân cách nào -> Lưu nguyên cả bài làm Phần 1
    if len(parts) <= 1:
        res["Toàn bộ truyện"] = full_text
        return res

    current_title = "Phần mở đầu"
    for i in range(len(parts)):
        segment = parts[i].strip()
        if not segment: continue
        
        # Nếu đoạn text trùng với pattern (ví dụ là con số "1", "2")
        if re.match(r'^(?:[0-9]{1,3}|第.*?章|Chương\s+\d+)$', segment):
            current_title = f"Phần {segment}" if segment.isdigit() else segment
        else:
            # Đây là nội dung chữ của phần đó
            if current_title in res:
                res[current_title] += "\n\n" + segment
            else:
                res[current_title] = segment

    return res

# ==========================================
# 3. GIAO DIỆN CHÍNH
# ==========================================
if not st.session_state.authenticated:
    st.title("⚡ Máy Dịch Truyện Zhihu")
    email = st.text_input("Email:")
    password = st.text_input("Mật khẩu:", type="password")
    if st.button("🚀 Đăng nhập", use_container_width=True):
        st.session_state.authenticated = True; st.session_state.user_email = email; st.rerun()
    st.stop()

st.sidebar.title("⚡ Menu")
menu = st.sidebar.radio("Chọn chức năng:", ["1. Cấu hình API & Cookie", "Lấy raw Zhihu", "3. Kho Raw & Dịch"])

if menu == "1. Cấu hình API & Cookie":
    st.header("🔑 Cấu hình System")
    workspace["api_keys"]["gemini"] = st.text_area("Gemini API Keys:", value=workspace["api_keys"].get("gemini", ""), height=100)
    workspace["web_cookie"] = st.text_area(
        "🍪 Cookie Zhihu (Bắt buộc nếu là bài VIP):", 
        value=workspace.get("web_cookie", ""),
        height=120,
        help="Dán chuỗi JSON hoặc Raw Cookie lấy từ F12/Extension vào đây."
    )
    if st.button("💾 Lưu Cấu Hình"): save_data(workspace)

elif menu == "Lấy raw Zhihu":
    st.header("🕷️ Cào & Tách Phần Truyện Zhihu")
    
    tab_link, tab_manual = st.tabs(["🌐 Cào trực tiếp từ 1 Link Zhihu", "📝 Dán Text Thủ Công"])
    
    with tab_link:
        url_zhihu = st.text_input("Dán Link bài Zhihu vào đây:", value="")
        auto_split = st.checkbox("Tự động cắt thành từng Phần (1, 2, 3...) sau khi cào", value=True)
        
        if st.button("🚀 Cào Ngay", type="primary", use_container_width=True):
            if url_zhihu:
                with st.spinner("Đang lấy nội dung từ Zhihu..."):
                    raw_content = scrape_zhihu_url(url_zhihu, workspace.get("web_cookie", ""))
                    if raw_content:
                        workspace["raw_full_text"] = raw_content
                        if auto_split:
                            split_res = auto_split_zhihu_sections(raw_content)
                            workspace["split_chapters_raw"].update(split_res)
                            st.success(f"🎉 Cào thành công & Đã tự tách thành {len(split_res)} phần!")
                        else:
                            workspace["split_chapters_raw"]["Truyện Zhihu"] = raw_content
                            st.success("🎉 Cào thành công toàn bộ văn bản!")
                        save_data(workspace)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Không lấy được nội dung. Hãy kiểm tra lại Cookie Zhihu ở Tab 1!")
            else: st.warning("Vui lòng nhập Link!")

    with tab_manual:
        raw_full = st.text_area("Nếu cào bị lỗi, bạn copy toàn bộ chữ trên web dán vào đây:", value=workspace.get("raw_full_text", ""), height=250)
        if st.button("🔪 Tách Thành Các Phần (1, 2, 3...)", use_container_width=True):
            if raw_full.strip():
                workspace["raw_full_text"] = raw_full
                split_res = auto_split_zhihu_sections(raw_full)
                workspace["split_chapters_raw"].update(split_res)
                save_data(workspace)
                st.success(f"🎉 Đã nhận diện và tách thành {len(split_res)} phần!")
                time.sleep(1)
                st.rerun()

    if workspace.get("split_chapters_raw"):
        st.markdown("---")
        st.subheader(f"📦 Các Phần Đã Tách ({len(workspace['split_chapters_raw'])} phần)")
        if st.button("🗑️ Xóa hết làm lại"):
            workspace["split_chapters_raw"] = {}
            workspace["raw_full_text"] = ""
            save_data(workspace)
            st.rerun()
            
        for ch_title, ch_content in list(workspace["split_chapters_raw"].items()):
            with st.expander(f"📖 {ch_title}"):
                st.text_area("Nội dung:", value=ch_content, height=150, key=f"p_{ch_title}")

elif menu == "3. Kho Raw & Dịch":
    st.header("📂 Danh Sách Các Phần Để Dịch")
    raw_dict = workspace.get("split_chapters_raw", {})
    if not raw_dict:
        st.info("Chưa có dữ liệu. Vui lòng qua Tab 'Lấy raw Zhihu' trước!")
    else:
        for k in raw_dict.keys():
            st.write(f"- **{k}** ({len(raw_dict[k])} ký tự)")
