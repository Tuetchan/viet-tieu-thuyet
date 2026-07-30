import streamlit as st
import requests
import re
import time
import queue
import io
import zipfile
import json
from bs4 import BeautifulSoup
from supabase import create_client, Client
from google import genai
from google.genai import types

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
if "translated_data" not in st.session_state: st.session_state.translated_data = {}
if "novel_data" not in st.session_state:
    st.session_state.novel_data = {
        "api_keys": {"gemini": ""},
        "selected_model": "gemini-2.5-flash",
        "web_cookie": "",
        "raw_full_text": "",
        "split_chapters_raw": {},
        "trans_prompt": "Bạn là một dịch giả tiểu thuyết chuyên nghiệp. Hãy dịch đoạn văn bản sau sang tiếng Việt mượt mà, thuần Việt, đúng văn phong truyện. Giữ nguyên định dạng dòng và không tự ý bổ sung tình tiết."
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
        return text if len(text) >= 50 else None
    except Exception: return None

def auto_split_zhihu_sections(full_text):
    pattern = r"(?m)(^(?:[0-9]{1,3}|第.*?章|Chương\s+\d+)\s*$)"
    parts = re.split(pattern, full_text)
    res = {}
    if len(parts) <= 1:
        res["Toàn bộ truyện"] = full_text
        return res

    current_title = "Phần mở đầu"
    for i in range(len(parts)):
        segment = parts[i].strip()
        if not segment: continue
        if re.match(r'^(?:[0-9]{1,3}|第.*?章|Chương\s+\d+)$', segment):
            current_title = f"Phần {segment}" if segment.isdigit() else segment
        else:
            if current_title in res: res[current_title] += "\n\n" + segment
            else: res[current_title] = segment
    return res

# ==========================================
# 3. HÀM DỊCH TRUYỆN BẰNG GEMINI API
# ==========================================
def translate_text_with_gemini(raw_text, api_keys_list, system_prompt, model_name="gemini-2.5-flash"):
    if not api_keys_list:
        return None, "Chưa nhập API Key Gemini!"
    
    # Xoay vòng lấy key đầu tiên hoạt động
    last_error = ""
    for api_key in api_keys_list:
        api_key = api_key.strip()
        if not api_key: continue
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=f"{system_prompt}\n\nVăn bản cần dịch:\n{raw_text}",
            )
            if response and response.text:
                return response.text, None
        except Exception as e:
            last_error = str(e)
            continue
            
    return None, f"Tất cả API Key đều lỗi hoặc hết dung lượng. Chi tiết: {last_error}"

# ==========================================
# 4. GIAO DIỆN CỦA ỨNG DỤNG
# ==========================================
if not st.session_state.authenticated:
    st.title("⚡ Máy Dịch Truyện Zhihu")
    email = st.text_input("Email:")
    password = st.text_input("Mật khẩu:", type="password")
    if st.button("🚀 Đăng nhập", use_container_width=True):
        st.session_state.authenticated = True; st.session_state.user_email = email; st.rerun()
    st.stop()

st.sidebar.title("⚡ Menu")
menu = st.sidebar.radio("Chọn chức năng:", ["1. Cấu hình API & Cookie", "2. Lấy raw Zhihu", "3. Tiến Hành Dịch Truyện"])

if menu == "1. Cấu hình API & Cookie":
    st.header("🔑 Cấu hình System")
    workspace["api_keys"]["gemini"] = st.text_area("Gemini API Keys (Mỗi dòng 1 key):", value=workspace["api_keys"].get("gemini", ""), height=100)
    
    workspace["selected_model"] = st.selectbox(
        "Lựa chọn Model Gemini:", 
        ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"],
        index=0
    )
    
    workspace["web_cookie"] = st.text_area(
        "🍪 Cookie Zhihu (Bắt buộc nếu là bài VIP):", 
        value=workspace.get("web_cookie", ""),
        height=100
    )
    workspace["trans_prompt"] = st.text_area("Prompt / Luật dịch:", value=workspace.get("trans_prompt", ""), height=120)
    if st.button("💾 Lưu Cấu Hình"): save_data(workspace)

elif menu == "2. Lấy raw Zhihu":
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
                    else: st.error("❌ Không lấy được nội dung. Hãy kiểm tra lại Cookie Zhihu ở Tab 1!")

    with tab_manual:
        raw_full = st.text_area("Dán toàn bộ text thủ công vào đây:", value=workspace.get("raw_full_text", ""), height=200)
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
        if st.button("🗑️ Xóa hết Kho Raw"):
            workspace["split_chapters_raw"] = {}
            workspace["raw_full_text"] = ""
            save_data(workspace)
            st.rerun()
        for ch_title, ch_content in list(workspace["split_chapters_raw"].items()):
            with st.expander(f"📖 {ch_title}"):
                st.text_area("Nội dung Raw:", value=ch_content, height=120, key=f"p_{ch_title}")

elif menu == "3. Tiến Hành Dịch Truyện":
    st.header("🤖 Tiến Hành Dịch Thuật & Xuất Kết Quả")
    
    raw_dict = workspace.get("split_chapters_raw", {})
    if not raw_dict:
        st.info("💡 Chưa có dữ liệu Raw nào. Vui lòng qua menu '2. Lấy raw Zhihu' để lấy dữ liệu trước!")
    else:
        keys_list = list(raw_dict.keys())
        selected_parts = st.multiselect("Chọn các phần cần dịch:", options=keys_list, default=keys_list)
        
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button("🚀 Bắt Đầu Dịch Tự Động", type="primary", use_container_width=True):
                api_keys = [k.strip() for k in workspace["api_keys"].get("gemini", "").split("\n") if k.strip()]
                if not api_keys:
                    st.error("❌ Bạn chưa cấu hình Gemini API Key tại Tab 1!")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    total = len(selected_parts)
                    for idx, part_title in enumerate(selected_parts):
                        status_text.text(f"⏳ Đang dịch: {part_title} ({idx+1}/{total})...")
                        raw_text = raw_dict[part_title]
                        
                        translated_text, err = translate_text_with_gemini(
                            raw_text=raw_text,
                            api_keys_list=api_keys,
                            system_prompt=workspace.get("trans_prompt", ""),
                            model_name=workspace.get("selected_model", "gemini-2.5-flash")
                        )
                        
                        if translated_text:
                            st.session_state.translated_data[part_title] = translated_text
                        else:
                            st.error(f"❌ Dịch thất bại ở [{part_title}]: {err}")
                            break
                        
                        progress_bar.progress((idx + 1) / total)
                        time.sleep(0.5)
                        
                    status_text.success("🎉 Đã dịch xong toàn bộ các phần đã chọn!")

        with col_act2:
            if st.session_state.translated_data:
                # Tạo file ZIP kết quả
                zip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for p_title, p_trans in st.session_state.translated_data.items():
                        zip_file.writestr(f"{p_title}_dich.txt", p_trans.encode("utf-8"))
                        
                st.download_button(
                    "📥 Tải File ZIP Kết Quả Dịch",
                    data=zip_buf.getvalue(),
                    file_name="Truyen_Zhihu_Da_Dich.zip",
                    mime="application/zip",
                    use_container_width=True
                )

        # Hiển thị khu vực xem trước bản dịch
        if st.session_state.translated_data:
            st.divider()
            st.subheader("📖 Xem Bản Dịch Chi Tiết")
            selected_view = st.selectbox("Chọn phần muốn xem:", list(st.session_state.translated_data.keys()))
            
            c_raw, c_trans = st.columns(2)
            with c_raw:
                st.caption("🔴 Văn bản Tiếng Trung (Raw)")
                st.text_area("Raw", value=raw_dict.get(selected_view, ""), height=400, key="view_raw")
            with c_trans:
                st.caption("🟢 Văn bản Đã Dịch (Tiếng Việt)")
                st.text_area("Dịch", value=st.session_state.translated_data.get(selected_view, ""), height=400, key="view_trans")
