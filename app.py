import streamlit as st
from supabase import create_client, Client
import requests
import json
import re
import random 
import time
import threading
import io
import zipfile
from bs4 import BeautifulSoup
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

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "trans_status" not in st.session_state: st.session_state.trans_status = {}
if "novel_data" not in st.session_state:
    st.session_state.novel_data = {
        "api_keys": {"gemini": ""},
        "selected_model": "Gemini 1.5 Flash (Nhanh, ít giới hạn)",
        "raw_chapters": {},
        "trans_prompt": "Bạn là một dịch giả tiểu thuyết. Dịch mượt mà, thuần Việt, giữ nguyên đoạn văn và không tự ý thêm bớt tình tiết."
    }

# ==========================================
# HÀM HỖ TRỢ
# ==========================================
def load_user_data_from_supabase(email):
    if supabase:
        try:
            res = supabase.table("workspaces").select("workspace_data").eq("email", email).execute()
            if res.data and len(res.data) > 0:
                saved_data = res.data[0].get("workspace_data")
                st.session_state.novel_data.update(saved_data)
                st.toast("🎉 Đã tải dữ liệu cũ!", icon="✅")
        except Exception as e: st.error(f"Lỗi tải dữ liệu: {e}")

def save_user_data_to_supabase():
    if supabase and st.session_state.authenticated and st.session_state.user_email:
        try:
            supabase.table("workspaces").upsert({"email": st.session_state.user_email, "workspace_data": st.session_state.novel_data}).execute()
            st.toast("💾 Đã lưu dữ liệu!", icon="☁️")
        except Exception as e: st.error(f"Lỗi lưu Supabase: {e}")

# --- CƠ CHẾ AUTO-RETRY ĐƯỢC TÍCH HỢP TẠI ĐÂY ---
def bg_translate_task(chap_key, raw_text, api_keys, model_choice, novel_data, trans_status):
    max_retries = 3
    retry_count = 0
    
    # Xác định Model dựa trên cấu hình người dùng
    model_name = "gemini-1.5-pro" if "Pro" in model_choice else "gemini-1.5-flash"
    
    base_prompt = novel_data.get("trans_prompt", "Bạn là dịch giả.")
    system_prompt = base_prompt + "\n\n[LỆNH BẮT BUỘC]: Nếu có lỗi hoặc vi phạm chính sách, KHÔNG được dừng đột ngột. PHẢI trả về dòng '⚠️ CẢNH BÁO AI TỪ CHỐI DỊCH:' kèm lý do."
    
    while retry_count < max_retries:
        try:
            translated_text = call_llm_gemini(system_prompt, f"RAW CẦN DỊCH:\n\n{raw_text}", api_keys, model_name)
            
            # Kiểm tra xem text trả về có báo lỗi Rate Limit từ phía hàm LLM không
            if "❌ LỖI RATE LIMIT" in translated_text or "429" in translated_text or "404" in translated_text or "Resource has been exhausted" in translated_text:
                retry_count += 1
                trans_status[chap_key] = f"⚠️ Quá tải API (Đang chờ 60s để thử lại lần {retry_count}/{max_retries}...)"
                time.sleep(60) # Tạm dừng 60 giây trước khi lặp lại
                continue
                
            # Nếu thành công hoặc AI nhả cảnh báo nội dung
            novel_data["raw_chapters"][chap_key]["translated"] = translated_text
            if "❌" in translated_text or "⚠️ LỖI" in translated_text or "⚠️ CẢNH BÁO" in translated_text:
                trans_status[chap_key] = "❌ Cảnh báo AI (Đã dịch lỗi)"
            else:
                trans_status[chap_key] = "✅ Hoàn thành"
            break # Phá vòng lặp while vì đã thành công
            
        except Exception as e:
            retry_count += 1
            err_str = str(e)
            if "429" in err_str or "404" in err_str or "quota" in err_str.lower() or "exhausted" in err_str.lower():
                trans_status[chap_key] = f"⚠️ Lỗi mạng (Đang chờ 60s thử lại lần {retry_count}/{max_retries}...)"
                time.sleep(60)
            else:
                novel_data["raw_chapters"][chap_key]["translated"] = f"❌ Lỗi Hệ Thống nghiêm trọng: {err_str}"
                trans_status[chap_key] = "❌ Lỗi Hệ Thống"
                break
                
    if retry_count >= max_retries:
        trans_status[chap_key] = "❌ Thất bại hoàn toàn (Hết số lần thử lại)"

def call_llm_gemini(system_prompt, prompt_text, api_keys, model_name):
    gemini_keys = [k.strip() for k in re.split(r'[\n,;\s]+', api_keys.get("gemini", "")) if k.strip()]
    if not gemini_keys: return "⚠️ LỖI: Chưa nhập Gemini API Key."
    
    random.shuffle(gemini_keys)
    last_error = ""
    for key in gemini_keys:
        try: 
            client = genai.Client(api_key=key)
            config = types.GenerateContentConfig(system_instruction=system_prompt) if system_prompt else None
            res = client.models.generate_content(model=model_name, contents=prompt_text, config=config)
            if res and res.text: return res.text
        except Exception as e:
            last_error = str(e)
            # Nếu bắt gặp lỗi 429/404, trả ngay về chuỗi này để hàm bg_translate_task bắt được và tự động ngủ 60s
            if "429" in last_error or "404" in last_error or "exhausted" in last_error.lower():
                return f"❌ LỖI RATE LIMIT: {last_error}"
            continue 
    return f"❌ LỖI API KEYS. Chi tiết: {last_error}"

def scrape_text_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        paragraphs = soup.find_all('p')
        if paragraphs and len(paragraphs) > 5:
            text = "\n".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
        else:
            text = soup.get_text(separator="\n", strip=True)
            
        return text if len(text) > 50 else "Không tìm thấy nội dung truyện ở link này."
    except Exception as e:
        return f"❌ Lỗi cào web: {str(e)}"

# ==========================================
# ĐĂNG NHẬP
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
# GIAO DIỆN CHÍNH
# ==========================================
st.sidebar.title("⚡ Menu")
menu = st.sidebar.radio("Chọn chức năng:", ["1. Cấu hình API", "2. Cào Web & Nhập Raw", "3. Quản lý & Dịch"])
if st.sidebar.button("💾 Lưu Dữ Liệu Lên Cloud"): save_user_data_to_supabase()
if st.sidebar.button("🚪 Đăng xuất"): st.session_state.authenticated = False; st.rerun()

if menu == "1. Cấu hình API":
    st.header("🔑 Cấu hình API")
    st.session_state.novel_data["api_keys"]["gemini"] = st.text_area("Gemini API Keys (Mỗi dòng 1 key):", value=st.session_state.novel_data["api_keys"].get("gemini", ""), height=150)
    
    st.session_state.novel_data["selected_model"] = st.selectbox(
        "Lựa chọn Model Dịch:", 
        [
            "Gemini 1.5 Flash (Nhanh, ít giới hạn - Dùng cho truyện dễ)", 
            "Gemini 1.5 Pro (Dịch chuẩn, suy luận cao, chờ lâu - Dùng cho truyện khó)"
        ],
        index=0 if "Flash" in st.session_state.novel_data.get("selected_model", "Flash") else 1
    )
    
    st.session_state.novel_data["trans_prompt"] = st.text_area("Luật Dịch (Tùy chỉnh):", value=st.session_state.novel_data.get("trans_prompt", ""), height=150)
    
    if st.button("💾 Lưu Cấu Hình"): save_user_data_to_supabase()
    
    st.info("💡 **Ghi chú Model:**\n- **Flash:** Model sẽ nghỉ 3 giây giữa mỗi chương, rất khó bị lỗi 429.\n- **Pro:** Do giới hạn Google khắt khe hơn, Model sẽ nghỉ 15 giây giữa mỗi chương. \n- **Auto-Retry:** Nếu chẳng may báo lỗi quá tải, hệ thống tự động ngừng 60 giây và thử lại.")

elif menu == "2. Cào Web & Nhập Raw":
    st.header("📥 Lấy Raw Cần Dịch")
    
    tab_web, tab_text = st.tabs(["🌐 Cào từ Link Web", "✍️ Nhập Text / Tách thủ công"])
    
    with tab_web:
        url_input = st.text_input("Nhập link (URL) chương truyện (VD: https://uukanshu.com/...):")
        chap_name_web = st.text_input("Tên chương muốn lưu (VD: Chương 1):", value="Chương Web")
        if st.button("🕷️ Cào & Lưu vào danh sách"):
            with st.spinner("Đang tải dữ liệu từ web..."):
                scraped_text = scrape_text_from_url(url_input)
                if "❌" not in scraped_text:
                    st.session_state.novel_data["raw_chapters"][chap_name_web] = {"raw": scraped_text, "translated": ""}
                    save_user_data_to_supabase()
                    st.success("Đã cào và lưu thành công!")
                else:
                    st.error(scraped_text)
                    
    with tab_text:
        chap_name_text = st.text_input("Tên chương:", value="Chương Mới")
        raw_text_input = st.text_area("Dán nội dung Raw vào đây:", height=300)
        if st.button("💾 Lưu Chương Này"):
            st.session_state.novel_data["raw_chapters"][chap_name_text] = {"raw": raw_text_input, "translated": ""}
            save_user_data_to_supabase()
            st.success("Đã lưu thành công!")

elif menu == "3. Quản lý & Dịch":
    st.header("✂️ Quản lý & Dịch")
    if not st.session_state.novel_data.get("raw_chapters"):
        st.warning("Vui lòng qua Menu 2 để cào web hoặc nhập raw trước.")
    else:
        chap_keys = list(st.session_state.novel_data["raw_chapters"].keys())
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for c_key, data in st.session_state.novel_data["raw_chapters"].items():
                content = data["translated"] if data["translated"] else data["raw"]
                safe_name = re.sub(r'[\\/*?:"<>|]', "", c_key) + ".txt"
                zip_file.writestr(safe_name, content)
        st.download_button("📥 Tải tất cả chương (.ZIP)", data=zip_buffer.getvalue(), file_name="Truyen_Da_Dich.zip", mime="application/zip")
        
        st.divider()
        
        selected_batch = st.multiselect("Chọn các chương cần dịch ngầm:", chap_keys)
        col_run, col_ref = st.columns([1, 1])
        with col_run:
            if st.button("▶️ Dịch ngầm các chương đã chọn"):
                # Thời gian trễ linh hoạt theo Model
                delay_time = 15 if "Pro" in st.session_state.novel_data["selected_model"] else 3
                
                for c_key in selected_batch:
                    if st.session_state.trans_status.get(c_key) == "🔄 Đang dịch...": continue
                    st.session_state.trans_status[c_key] = "🔄 Đang dịch..."
                    raw_txt = st.session_state.novel_data["raw_chapters"][c_key]["raw"]
                    t = threading.Thread(target=bg_translate_task, args=(
                        c_key, raw_txt, st.session_state.novel_data["api_keys"], 
                        st.session_state.novel_data["selected_model"], st.session_state.novel_data, st.session_state.trans_status
                    ))
                    t.start()
                    time.sleep(delay_time) # NGỦ TÙY THEO MODEL ĐỂ CHỐNG QUÁ TẢI API 
                st.toast(f"Đã bắt đầu luồng dịch! (Delay {delay_time}s giữa mỗi Request)")
                time.sleep(1); st.rerun()
        with col_ref:
            if st.button("🔄 Cập nhật màn hình"): st.rerun()
            
        active_tasks = {k: v for k, v in st.session_state.trans_status.items() if "🔄" in v or "⚠️" in v}
        if active_tasks: 
            st.info(f"⏳ Luồng ngầm đang chạy:\n" + "\n".join([f"- **{k}**: {v}" for k, v in active_tasks.items()]))
        
        st.divider()
        
        selected_chap = st.selectbox("👉 Chọn chương để xem:", chap_keys)
        chap_data = st.session_state.novel_data["raw_chapters"][selected_chap]
        
        # Hiển thị trạng thái với màu sắc tương ứng
        status_text = st.session_state.trans_status.get(selected_chap, 'Chưa dịch')
        if "⚠️" in status_text:
            st.warning(f"Trạng thái: `{status_text}`")
        elif "❌" in status_text:
            st.error(f"Trạng thái: `{status_text}`")
        else:
            st.caption(f"Trạng thái: `{status_text}`")
        
        if st.button("🗑️ Xóa chương này (Xóa vĩnh viễn)"):
            del st.session_state.novel_data["raw_chapters"][selected_chap]
            if selected_chap in st.session_state.trans_status: del st.session_state.trans_status[selected_chap]
            save_user_data_to_supabase()
            st.rerun()
            
        c1, c2 = st.columns(2)
        with c1: raw_t = st.text_area("Bản Raw:", value=chap_data["raw"], height=500)
        with c2: trans_t = st.text_area("Bản Dịch:", value=chap_data["translated"], height=500)
        
        if st.button("💾 Lưu chỉnh sửa chương này", use_container_width=True):
            st.session_state.novel_data["raw_chapters"][selected_chap]["raw"] = raw_t
            st.session_state.novel_data["raw_chapters"][selected_chap]["translated"] = trans_t
            save_user_data_to_supabase()
            st.success("Đã lưu!")
