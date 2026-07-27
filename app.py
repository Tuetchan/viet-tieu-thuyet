import streamlit as st
import json
from google import genai
from supabase import create_client

st.set_page_config(page_title="Novel Studio Cloud", page_icon="☁️", layout="wide")

# ==========================================
# 1. KẾT NỐI ĐÁM MÂY & KHỞI TẠO DỮ LIỆU
# ==========================================
@st.cache_resource
def init_supabase():
    # Lấy thông tin từ cấu hình bảo mật của Streamlit
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

try:
    supabase = init_supabase()
except Exception:
    st.error("⚠️ Chưa cấu hình kết nối Đám mây (Supabase).")
    st.stop()

def get_default_workspace():
    return {
        "the_loai": "", "boi_canh": "", "raw_tham_khao": "",
        "nhan_vat": [], "dan_y_chuong": [], "ban_nhap": {}
    }

if 'user' not in st.session_state: st.session_state.user = None
if 'workspace' not in st.session_state: st.session_state.workspace = get_default_workspace()
if 'api_key' not in st.session_state: st.session_state.api_key = ""

# ==========================================
# 2. HỆ THỐNG ĐĂNG NHẬP / ĐĂNG KÝ
# ==========================================
if not st.session_state.user:
    st.title("☁️ Đăng nhập Novel Studio")
    st.write("Đăng nhập để tự động đồng bộ tiểu thuyết của bạn trên mọi thiết bị.")
    
    tab1, tab2 = st.tabs(["🔑 Đăng nhập", "📝 Đăng ký mới"])
    
    with tab1:
        email_login = st.text_input("Email:")
        pass_login = st.text_input("Mật khẩu:", type="password")
        if st.button("🚀 Đăng nhập", type="primary"):
            try:
                # Đăng nhập qua Supabase Auth
                res = supabase.auth.sign_in_with_password({"email": email_login, "password": pass_login})
                st.session_state.user = res.user
                
                # Kéo dữ liệu tiểu thuyết từ Cloud về
                db_res = supabase.table("workspaces").select("workspace_data").eq("email", email_login).execute()
                if db_res.data:
                    st.session_state.workspace = db_res.data[0]["workspace_data"]
                st.rerun()
            except Exception as e:
                st.error("Sai Email hoặc Mật khẩu!")

    with tab2:
        email_reg = st.text_input("Email đăng ký:")
        pass_reg = st.text_input("Mật khẩu mới (ít nhất 6 ký tự):", type="password")
        if st.button("Tạo tài khoản"):
            try:
                supabase.auth.sign_up({"email": email_reg, "password": pass_reg})
                # Tạo không gian làm việc trống cho tài khoản mới
                supabase.table("workspaces").insert({
                    "email": email_reg,
                    "workspace_data": get_default_workspace()
                }).execute()
                st.success("🎉 Đăng ký thành công! Hãy chuyển sang tab Đăng nhập.")
            except Exception as e:
                st.error(f"Lỗi: {e}")
                
    st.stop() # Dừng vẽ giao diện viết truyện nếu chưa đăng nhập

# ==========================================
# 3. GIAO DIỆN VIẾT TRUYỆN CHÍNH (Đã Đăng Nhập)
# ==========================================
st.sidebar.success(f"👤 Đang đăng nhập: {st.session_state.user.email}")

if st.sidebar.button("💾 LƯU ĐỒNG BỘ LÊN CLOUD", type="primary"):
    with st.spinner("Đang đẩy dữ liệu lên đám mây..."):
        supabase.table("workspaces").upsert({
            "email": st.session_state.user.email,
            "workspace_data": st.session_state.workspace
        }).execute()
        st.sidebar.success("✅ Đã lưu an toàn!")

st.sidebar.divider()
st.session_state.api_key = st.sidebar.text_input("🔑 Nhập Gemini API Key:", type="password", value=st.session_state.api_key)

menu = st.sidebar.radio("📌 Tính năng", [
    "1. Bối cảnh & Thể loại", 
    "2. Sổ tay Nhân vật", 
    "3. Dàn ý chi tiết", 
    "4. AI Viết nháp",
    "5. Xuất bản File"
])

ws = st.session_state.workspace

# CÁC TÍNH NĂNG NHƯ CŨ (KHÔNG ĐỔI)
if menu == "1. Bối cảnh & Thể loại":
    st.header("🌍 Xây dựng Thế giới & Nền tảng")
    ws["the_loai"] = st.text_input("🎭 Thể loại tiểu thuyết:", value=ws.get("the_loai", ""))
    ws["boi_canh"] = st.text_area("Mô tả hệ thống sức mạnh, bối cảnh...", value=ws.get("boi_canh", ""), height=150)
    ws["raw_tham_khao"] = st.text_area("Dán đoạn raw để AI học văn phong:", value=ws.get("raw_tham_khao", ""), height=150)
    st.info("Nhớ bấm nút 'LƯU ĐỒNG BỘ LÊN CLOUD' ở thanh bên để cất dữ liệu nhé!")

elif menu == "2. Sổ tay Nhân vật":
    st.header("👥 Hồ sơ Nhân vật")
    col1, col2, col3 = st.columns([2, 2, 4])
    with col1: nv_ten = st.text_input("Tên nhân vật:")
    with col2: nv_vai = st.selectbox("Vai trò:", ["Chính", "Phụ", "Phản diện", "Quần chúng"])
    with col3: nv_mota = st.text_input("Đặc điểm:")
    
    if st.button("➕ Thêm nhân vật"):
        if nv_ten:
            ws["nhan_vat"].append({"ten": nv_ten, "vai_tro": nv_vai, "mo_ta": nv_mota})
            st.rerun()
            
    for idx, nv in enumerate(ws["nhan_vat"]):
        with st.expander(f"👤 {nv['ten']} ({nv['vai_tro']})"):
            st.write(f"**Mô tả:** {nv['mo_ta']}")
            if st.button(f"❌ Xóa {nv['ten']}", key=f"del_nv_{idx}"):
                ws["nhan_vat"].pop(idx)
                st.rerun()

elif menu == "3. Dàn ý chi tiết":
    st.header("📋 Lên Dàn Ý Từng Chương")
    col_c1, col_c2 = st.columns([1, 4])
    with col_c1: chuong_so = st.number_input("Chương số:", min_value=1, value=len(ws["dan_y_chuong"])+1)
    with col_c2: tieu_de = st.text_input("Tiêu đề chương:")
    tom_tat = st.text_area("Tóm tắt diễn biến (Các sự kiện chính, cao trào):", height=100)
    
    if st.button("➕ Thêm vào Dàn ý"):
        ws["dan_y_chuong"].append({"chuong": chuong_so, "tieu_de": tieu_de, "tom_tat": tom_tat})
        st.success(f"Đã thêm Dàn ý Chương {chuong_so}!")
        
    for idx, dy in enumerate(ws["dan_y_chuong"]):
        with st.expander(f"Chương {dy['chuong']}: {dy['tieu_de']}"):
            st.write(dy['tom_tat'])
            if st.button("❌ Xóa", key=f"del_dy_{idx}"):
                ws["dan_y_chuong"].pop(idx)
                st.rerun()

elif menu == "4. AI Viết nháp":
    st.header("✍️ AI Chấp Bút Bản Nháp")
    if not ws["dan_y_chuong"]:
        st.warning("Hãy tạo Dàn ý chương trước khi yêu cầu AI viết!")
    else:
        chuong_chon = st.selectbox("Chọn chương muốn viết:", [f"Chương {c['chuong']}: {c['tieu_de']}" for c in ws["dan_y_chuong"]])
        chuong_idx = int(chuong_chon.split(" ")[1].replace(":", "")) - 1
        dy_hien_tai = ws["dan_y_chuong"][chuong_idx]
        
        if st.button("🚀 Bắt đầu viết nháp", type="primary"):
            if not st.session_state.api_key:
                st.error("⚠️ Vui lòng nhập API Key ở thanh bên!")
            else:
                with st.spinner("AI đang nhào nặn câu chữ..."):
                    client = genai.Client(api_key=st.session_state.api_key)
                    danh_sach_nv = "\n".join([f"- {n['ten']}: {n['mo_ta']}" for n in ws["nhan_vat"]])
                    prompt = f"""THỂ LOẠI: {ws['the_loai']}
BỐI CẢNH: {ws['boi_canh']}
NHÂN VẬT: {danh_sach_nv}
VĂN PHONG THAM KHẢO: {ws['raw_tham_khao'][:1000]}
YÊU CẦU: Viết bản nháp cho Tiêu đề: {dy_hien_tai['tieu_de']}. Diễn biến: {dy_hien_tai['tom_tat']}"""
                    
                    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                    ws["ban_nhap"][str(dy_hien_tai['chuong'])] = response.text
        
        ban_nhap_hien_tai = ws["ban_nhap"].get(str(dy_hien_tai['chuong']), "")
        van_ban = st.text_area("Bản thảo (Có thể tự chỉnh sửa):", value=ban_nhap_hien_tai, height=400)
        
        if st.button("💾 Lưu chỉnh sửa vào Workspace"):
            ws["ban_nhap"][str(dy_hien_tai['chuong'])] = van_ban
            st.success("Đã lưu tạm! Đừng quên bấm NÚT ĐỒNG BỘ MÀU ĐỎ ở thanh bên để đưa lên mây.")

elif menu == "5. Xuất bản File":
    st.header("📥 Tải bản thảo về máy")
    st.write("Nếu bạn muốn backup dự phòng, hãy tải file text này về.")
    
    full_text = ""
    for c in ws["dan_y_chuong"]:
        ch_num = str(c["chuong"])
        full_text += f"\n\n=== {c['tieu_de'].upper()} ===\n\n"
        full_text += ws["ban_nhap"].get(ch_num, "[Chưa có nội dung]")
        
    st.download_button("📥 Tải toàn bộ bản thảo (.txt)", data=full_text, file_name="TieuThuyet_BanThao.txt", mime="text/plain")
