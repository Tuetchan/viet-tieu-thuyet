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
        "raw_docs": [],
        "raw_chapters": {},
        "trans_prompt": "Bạn là một dịch giả tiểu thuyết chuyên nghiệp. Dịch mượt mà, thuần Việt, giữ nguyên đoạn văn và không tự ý thêm bớt tình tiết."
    }

# ==========================================
# 2. HÀM HỖ TRỢ XỬ LÝ DỮ LIỆU & CALL API
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

def call_llm(system_prompt, prompt_text, api_keys, model_choice):
    gemini_keys = [k.strip() for k in re.split(r'[\n,;\s]+', api_keys.get("gemini", "")) if k.strip()]
    if not gemini_keys: return "⚠️ LỖI: Chưa nhập Gemini API Key."
    
    model_name = "gemini-1.5-pro" if "Pro" in str(model_choice) else "gemini-1.5-flash"
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
            if "429" in last_error or "404" in last_error or "exhausted" in last_error.lower():
                return f"❌ LỖI RATE LIMIT (429/404): {last_error}"
            continue 
    return f"❌ LỖI API KEYS. Chi tiết: {last_error}"

def bg_translate_task(chap_key, raw_text, api_keys, model_choice, novel_data, trans_status):
    max_retries = 3
    retry_count = 0
    
    base_prompt = novel_data.get("trans_prompt", "Bạn là dịch giả.")
    system_prompt = base_prompt + "\n\n[LỆNH BẮT BUỘC]: Nếu có lỗi hoặc vi phạm chính sách, KHÔNG được dừng đột ngột. PHẢI trả về dòng '⚠️ CẢNH BÁO AI TỪ CHỐI DỊCH:' kèm lý do."
    
    while retry_count < max_retries:
        try:
            translated_text = call_llm(system_prompt, f"RAW CẦN DỊCH:\n\n{raw_text}", api_keys, model_choice)
            
            if "❌ LỖI RATE LIMIT" in translated_text or "429" in translated_text or "404" in translated_text or "exhausted" in translated_text.lower():
                retry_count += 1
                trans_status[chap_key] = f"⚠️ Quá tải API (Đang chờ 60s để thử lại lần {retry_count}/{max_retries}...)"
                time.sleep(60)
                continue
                
            novel_data["raw_chapters"][chap_key]["translated"] = translated_text
            if "❌" in translated_text or "⚠️ LỖI" in translated_text or "⚠️ CẢNH BÁO" in translated_text:
                trans_status[chap_key] = "❌ Cảnh báo AI (Đã dịch lỗi)"
            else:
                trans_status[chap_key] = "✅ Hoàn thành"
            break
            
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
menu = st.sidebar.radio("Chọn chức năng:", ["1. Cấu hình API", "2. Tải File Raw", "3. Tách & Dịch Raw"])
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

elif menu == "2. Tải File Raw":
    st.header("📂 Tải Lên File Raw (.txt)")
    uploaded_file = st.file_uploader("Chọn file TXT từ máy tính:", type=["txt"])
    if uploaded_file is not None:
        content = uploaded_file.read().decode("utf-8", errors="ignore")
        if "raw_docs" not in st.session_state.novel_data:
            st.session_state.novel_data["raw_docs"] = []
        
        existing_names = [d["filename"] for d in st.session_state.novel_data["raw_docs"]]
        if uploaded_file.name not in existing_names:
            st.session_state.novel_data["raw_docs"].append({"filename": uploaded_file.name, "content": content})
            save_user_data_to_supabase()
            st.success(f"Đã lưu file: {uploaded_file.name}")
        else:
            st.info("File này đã tồn tại trong danh sách.")
            
    if st.session_state.novel_data.get("raw_docs"):
        st.subheader("Danh sách file Raw đã tải:")
        for idx, doc in enumerate(st.session_state.novel_data["raw_docs"]):
            st.text(f"📄 {doc['filename']} ({len(doc['content'])} ký tự)")

elif menu == "3. Tách & Dịch Raw":
    st.header("✂️ Tách chương & Dịch Raw")
    
    # --- CÀO RAW TRỰC TIẾP TỪ WEB ---
    with st.expander("🌐 Tùy chọn: Cào nhanh 1 chương từ Link Web (Không cần file)"):
        st.markdown("💡 *Nếu bạn có link URL của chương truyện, hãy nhập vào đây để lấy nội dung ngay lập tức.*")
        col_url, col_name = st.columns([3, 1])
        with col_url:
            url_input = st.text_input("Nhập link (URL) chương truyện (VD: https://uukanshu.com/...):")
        with col_name:
            chap_name_web = st.text_input("Tên chương:", value="Chương Web Mới")
            
        if st.button("🕷️ Cào & Thêm vào danh sách", use_container_width=True):
            if url_input:
                with st.spinner("Đang tải dữ liệu từ web..."):
                    scraped_text = scrape_text_from_url(url_input) 
                    if "❌" not in scraped_text:
                        if "raw_chapters" not in st.session_state.novel_data:
                            st.session_state.novel_data["raw_chapters"] = {}
                        st.session_state.novel_data["raw_chapters"][chap_name_web] = {"raw": scraped_text, "translated": ""}
                        save_user_data_to_supabase()
                        st.success("🎉 Đã cào và lưu thành công! Cuộn xuống phần Quản lý để xem.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(scraped_text)
            else:
                st.warning("Vui lòng nhập link URL.")

    st.divider()

    # --- TÁCH CHƯƠNG TỪ FILE RAW ---
    if not st.session_state.novel_data.get("raw_docs"):
        st.info("💡 Bạn chưa tải lên file Raw nào ở bước 2. Bỏ qua phần tách file nếu bạn chỉ dùng tính năng Cào Web.")
    else:
        doc_names = [d["filename"] for d in st.session_state.novel_data["raw_docs"]]
        selected_doc = st.selectbox("1. Chọn file Raw cần tách thành từng chương:", doc_names)
        doc_content = next((d["content"] for d in st.session_state.novel_data["raw_docs"] if d["filename"] == selected_doc), "")
        
        st.subheader("2. Thiết lập Tách Chương")
        
        split_method = st.radio("Chọn phương pháp tách:", [
            "🤖 Tự động thông minh (Nhận diện 第...章, Chương, Chap, Chapter)",
            "✍️ Tùy chỉnh thủ công (Nhập từ khóa)"
        ])
        
        if "Tự động" in split_method:
            split_pattern = r"(?im)(?=^(?:第.*?章|Chương\s+|Chap\s+|Chapter\s+))"
            st.info("💡 Hệ thống sẽ tự động tìm kiếm các dòng chứa tiền tố chương (tiếng Việt, Anh, Trung) để tách.")
        else:
            split_pattern = st.text_input("Từ khóa hoặc Regex bắt đầu mỗi chương (VD: 'Chương ', 'Chapter '):", value="Chương ")

        if st.button("✂️ Bắt đầu Tách", use_container_width=True):
            if "Tự động" in split_method:
                chunks = re.split(split_pattern, doc_content)
                chunks = [c.strip() for c in chunks if len(c.strip()) > 10]
            else:
                try: 
                    chunks = re.split(f"(?={split_pattern})", doc_content)
                except re.error:
                    chunks_raw = doc_content.split(split_pattern)
                    chunks = [c if i == 0 else (split_pattern + c) for i, c in enumerate(chunks_raw)]
                chunks = [c.strip() for c in chunks if len(c.strip()) > 10]
            
            if "raw_chapters" not in st.session_state.novel_data:
                st.session_state.novel_data["raw_chapters"] = {}
                
            chap_idx = len(st.session_state.novel_data["raw_chapters"]) + 1
            for chunk in chunks:
                first_line = chunk.split('\n')[0][:50].strip()
                if len(first_line) > 40: first_line = first_line[:40] + "..."
                chap_key = f"Chương_Lưu_{chap_idx} ({first_line})"
                st.session_state.novel_data["raw_chapters"][chap_key] = {"raw": chunk, "translated": ""}
                chap_idx += 1
                
            save_user_data_to_supabase()
            st.success(f"Đã tách và nối thêm {len(chunks)} chương vào danh sách!")
            st.rerun()
    
    # --- QUẢN LÝ & DỊCH THUẬT (Có Auto-Retry) ---
    if st.session_state.novel_data.get("raw_chapters"):
        st.divider()
        
        col_title, col_download = st.columns([2, 1])
        with col_title:
            st.subheader("3. Dịch Thuật & Quản Lý")
        with col_download:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for chap_key, data in st.session_state.novel_data["raw_chapters"].items():
                    content_to_save = data["translated"] if data["translated"] else data["raw"]
                    safe_filename = re.sub(r'[\\/*?:"<>|]', "", chap_key) + ".txt"
                    zip_file.writestr(safe_filename, content_to_save)
            
            st.download_button(
                label="📥 Tải tất cả các chương (.ZIP)",
                data=zip_buffer.getvalue(),
                file_name="Cac_Chuong_Da_Tach_Dich.zip",
                mime="application/zip",
                use_container_width=True
            )

        with st.expander("📝 Cấu hình Luật Dịch/Prompt (Áp dụng cho mọi chương)", expanded=True):
            custom_prompt_input = st.text_area(
                "Nhập các yêu cầu riêng cho AI (Ví dụ: cách xưng hô, văn phong...):",
                value=st.session_state.novel_data.get("trans_prompt", "Bạn là một dịch giả tiểu thuyết chuyên nghiệp..."),
                height=120
            )
            if st.button("💾 Lưu Luật Dịch"):
                st.session_state.novel_data["trans_prompt"] = custom_prompt_input
                save_user_data_to_supabase()
                st.success("Đã lưu yêu cầu dịch thuật!")
        if st.button("💾 Lưu Luật Dịch"):
                st.session_state.novel_data["trans_prompt"] = custom_prompt_input
                save_user_data_to_supabase()
                st.success("Đã lưu yêu cầu dịch thuật!")

            # =========================================================================
            # 👇 DÁN ĐOẠN CODE TÌM & THAY THẾ VÀO ĐÂY (LÙI VÀO 12 KHOẢNG TRẮNG / 3 TAB)
            # =========================================================================
            with st.expander("🔍 Tìm kiếm & Thay thế hàng loạt (Giống Word)", expanded=False):
                st.markdown("💡 *Thay thế tên nhân vật, từ ngữ, xưng hô... trên tất cả các chương cùng lúc.*")
                
                col_find, col_replace = st.columns(2)
                with col_find:
                    find_text = st.text_input("Từ / Cụm từ cần tìm (Ví dụ: Ta, Lục Sĩ...):", key="find_inp")
                with col_replace:
                    replace_text = st.text_input("Từ / Cụm từ thay thế (Ví dụ: Tôi, Lục Sơ...):", key="replace_inp")

                col_opt1, col_opt2 = st.columns(2)
                with col_opt1:
                    target_scope = st.radio("Phạm vi áp dụng:", ["Chỉ Bản Dịch", "Chỉ Bản Raw", "Cả Bản Dịch & Raw"], horizontal=True)
                with col_opt2:
                    use_regex = st.checkbox("Sử dụng Regex (Tìm nâng cao)")

                if st.button("⚡ Thực Hiện Thay Thế Hàng Loạt", use_container_width=True):
                    if not find_text:
                        st.warning("⚠️ Vui lòng nhập từ cần tìm!")
                    else:
                        count_modified_chaps = 0
                        total_replacements = 0

                        for chap_key, data in st.session_state.novel_data["raw_chapters"].items():
                            chap_modified = False

                            # 1. Thay thế trong Bản Dịch
                            if target_scope in ["Chỉ Bản Dịch", "Cả Bản Dịch & Raw"] and data.get("translated"):
                                if use_regex:
                                    try:
                                        new_text, num_subs = re.subn(find_text, replace_text, data["translated"])
                                        if num_subs > 0:
                                            data["translated"] = new_text
                                            total_replacements += num_subs
                                            chap_modified = True
                                    except re.error as e:
                                        st.error(f"❌ Lỗi Regex: {e}")
                                        break
                                else:
                                    matches = data["translated"].count(find_text)
                                    if matches > 0:
                                        data["translated"] = data["translated"].replace(find_text, replace_text)
                                        total_replacements += matches
                                        chap_modified = True

                            # 2. Thay thế trong Bản Raw
                            if target_scope in ["Chỉ Bản Raw", "Cả Bản Dịch & Raw"] and data.get("raw"):
                                if use_regex:
                                    try:
                                        new_text, num_subs = re.subn(find_text, replace_text, data["raw"])
                                        if num_subs > 0:
                                            data["raw"] = new_text
                                            total_replacements += num_subs
                                            chap_modified = True
                                    except re.error as e:
                                        st.error(f"❌ Lỗi Regex: {e}")
                                        break
                                else:
                                    matches = data["raw"].count(find_text)
                                    if matches > 0:
                                        data["raw"] = data["raw"].replace(find_text, replace_text)
                                        total_replacements += matches
                                        chap_modified = True

                            if chap_modified:
                                count_modified_chaps += 1

                        if total_replacements > 0:
                            save_user_data_to_supabase()
                            st.success(f"🎉 Đã thay thế thành công {total_replacements} vị trí trên {count_modified_chaps} chương!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.info("Nội dung tìm kiếm không tồn tại trong các chương.")
            # =========================================================================

            chap_keys = list(st.session_state.novel_data["raw_chapters"].keys())
        chap_keys = list(st.session_state.novel_data["raw_chapters"].keys())
        
        with st.expander("🚀 Bảng điều khiển Dịch Hàng Loạt (Chạy Ngầm)", expanded=True):
            st.markdown("💡 *Tool sẽ tự động điều chỉnh thời gian nghỉ (3s cho Flash, 15s cho Pro) và tự retry 60s nếu quá tải API.*")
            
            selected_batch = st.multiselect("Chọn các chương cần dịch:", chap_keys)
            
            col_btn_run, col_btn_ref = st.columns([1, 1])
            with col_btn_run:
                if st.button("▶️ Bắt đầu dịch ngầm"):
                    started = 0
                    
                    selected_model = st.session_state.novel_data.get("selected_model", "Flash")
                    delay_time = 15 if "Pro" in selected_model else 3
                    
                    for c_key in selected_batch:
                        if st.session_state.trans_status.get(c_key) == "🔄 Đang dịch...": continue
                        
                        st.session_state.trans_status[c_key] = "🔄 Đang dịch..."
                        raw_txt = st.session_state.novel_data["raw_chapters"][c_key]["raw"]
                        
                        t = threading.Thread(target=bg_translate_task, args=(
                            c_key, raw_txt, 
                            st.session_state.novel_data["api_keys"],
                            selected_model,
                            st.session_state.novel_data,
                            st.session_state.trans_status
                        ))
                        t.start()
                        started += 1
                        time.sleep(delay_time)
                    
                    if started > 0:
                        st.toast(f"Đã đưa {started} chương vào tiến trình nền! (Tự động nghỉ {delay_time}s giữa các request)")
                        time.sleep(1)
                        st.rerun()
            
            with col_btn_ref:
                if st.button("🔄 Cập nhật tiến độ"):
                    st.rerun()

            active_tasks = {k: v for k, v in st.session_state.trans_status.items() if "🔄" in v or "⚠️" in v}
            if active_tasks:
                st.info(f"⏳ Đang xử lý dưới nền:\n" + "\n".join([f"- **{k}**: {v}" for k, v in active_tasks.items()]))
        
        st.divider()
        
        selected_chap = st.selectbox("👉 Chọn chương để xem/chỉnh sửa:", chap_keys)
        chap_data = st.session_state.novel_data["raw_chapters"][selected_chap]
        
        c_status = st.session_state.trans_status.get(selected_chap, "Chưa đưa vào luồng tự động")
        if "⚠️" in c_status:
            st.warning(f"**Trạng thái hệ thống ngầm:** `{c_status}`")
        elif "❌" in c_status:
            st.error(f"**Trạng thái hệ thống ngầm:** `{c_status}`")
        else:
            st.caption(f"**Trạng thái hệ thống ngầm:** `{c_status}`")
            
        if st.button("🗑️ Xóa bỏ chương này"):
            del st.session_state.novel_data["raw_chapters"][selected_chap]
            if selected_chap in st.session_state.trans_status: del st.session_state.trans_status[selected_chap]
            save_user_data_to_supabase()
            st.rerun()
        
        col_raw, col_trans = st.columns(2)
        with col_raw:
            st.markdown("**Bản Raw (Gốc)**")
            raw_text = st.text_area("Nội dung Raw:", value=chap_data["raw"], height=500, key=f"raw_{selected_chap}")
        with col_trans:
            st.markdown("**Bản Dịch (Tiếng Việt)**")
            
            if st.button("🌐 Ép dịch trực tiếp chương này ngay", use_container_width=True):
                base_prompt = st.session_state.novel_data.get("trans_prompt", "Bạn là một dịch giả...")
                trans_system_prompt = base_prompt + "\n[LỆNH BẮT BUỘC HỆ THỐNG]: Nếu bạn không thể dịch vì lý do vi phạm chính sách, không hiểu nội dung, bạn PHẢI trả về dòng chữ '⚠️ CẢNH BÁO AI TỪ CHỐI DỊCH:' kèm theo lý do giải thích chi tiết."
                
                max_retries = 3
                retry_count = 0
                success = False
                status_placeholder = st.empty()
                
                with st.spinner("Đang ép luồng dịch trực tiếp..."):
                    while retry_count < max_retries and not success:
                        try:
                            translated_text = call_llm(trans_system_prompt, f"NỘI DUNG RAW:\n\n{raw_text}", st.session_state.novel_data["api_keys"], st.session_state.novel_data.get("selected_model", "Flash"))
                            
                            if "429" in translated_text or "404" in translated_text or "RATE LIMIT" in translated_text or "exhausted" in translated_text.lower():
                                retry_count += 1
                                status_placeholder.warning(f"⚠️ Quá tải API. Tự động chờ 60s để thử lại lần {retry_count}/{max_retries}...")
                                time.sleep(60)
                                continue
                            
                            st.session_state.novel_data["raw_chapters"][selected_chap]["translated"] = translated_text
                            
                            if "❌" in translated_text or "⚠️" in translated_text:
                                st.session_state.trans_status[selected_chap] = "❌ Lỗi / Cảnh báo AI"
                            else:
                                st.session_state.trans_status[selected_chap] = "✅ Dịch trực tiếp xong"
                                
                            success = True
                            
                        except Exception as e:
                            retry_count += 1
                            err_str = str(e).lower()
                            if "429" in err_str or "404" in err_str or "quota" in err_str or "exhausted" in err_str:
                                status_placeholder.warning(f"⚠️ Lỗi mạng/Quá tải. Tự động chờ 60s để thử lại lần {retry_count}/{max_retries}...")
                                time.sleep(60)
                            else:
                                st.session_state.novel_data["raw_chapters"][selected_chap]["translated"] = f"❌ Lỗi Hệ Thống nghiêm trọng: {str(e)}"
                                st.session_state.trans_status[selected_chap] = "❌ Lỗi Hệ Thống"
                                break
                    
                    if not success and retry_count >= max_retries:
                        st.session_state.novel_data["raw_chapters"][selected_chap]["translated"] = "❌ Thất bại hoàn toàn (Hết số lần kiên nhẫn thử lại)"
                        st.session_state.trans_status[selected_chap] = "❌ Lỗi Hệ Thống"
                        
                    save_user_data_to_supabase()
                    st.rerun()
            
            trans_text = st.text_area("Nội dung Dịch:", value=chap_data["translated"], height=500, key=f"trans_{selected_chap}")
            
        col_save_btn, col_note = st.columns([1, 3])
        with col_save_btn:
            if st.button("💾 Lưu bản Dịch này", use_container_width=True):
                st.session_state.novel_data["raw_chapters"][selected_chap]["raw"] = raw_text
                st.session_state.novel_data["raw_chapters"][selected_chap]["translated"] = trans_text
                save_user_data_to_supabase()
                st.success("Đã lưu bản cập nhật!")
        with col_note:
            st.caption("Nhớ click **Lưu bản Dịch này** nếu bạn vừa sửa tay nhé. Nếu luồng ngầm đã báo dịch xong, hãy click **Cập nhật tiến độ** ở trên để tải text vào ô này.")
