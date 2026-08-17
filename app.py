import streamlit as st
import re
import time
import base64

# ==========================================
# 1. CẤU HÌNH TRANG & CSS TÙY CHỈNH
# ==========================================
st.set_page_config(page_title="Web Đọc Truyện", page_icon="📖", layout="wide")

st.markdown("""
    <style>
    /* Ép cột nằm ngang và có thanh cuộn */
    [data-testid="stHorizontalBlock"] {
        overflow-x: auto;
        flex-wrap: nowrap;
        padding-bottom: 15px;
        gap: 15px;
    }
    /* Cố định kích thước mỗi khung truyện ngoài trang chủ */
    [data-testid="column"] {
        min-width: 160px;
        max-width: 160px;
        flex: 0 0 auto;
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        text-align: center;
    }
    /* Làm đẹp nút bấm tên truyện */
    .stButton > button {
        width: 100%;
        border: none;
        background: transparent;
        color: #1f77b4;
        font-weight: bold;
        padding: 5px 0;
    }
    .stButton > button:hover {
        color: #ff4b4b;
        background: transparent;
    }
    /* CSS Riêng Cho Bảng Quản Lý (Ghi đè lại cột để không bị bóp nghẹt) */
    .admin-mode [data-testid="column"] {
        min-width: unset;
        max-width: unset;
        flex: 1 1 auto;
        text-align: left;
        background-color: transparent;
        box-shadow: none;
        padding: 0;
    }
    .admin-mode .stButton > button {
        border: 1px solid #ddd;
        background: #f1f3f4;
        color: #333;
        font-weight: normal;
    }
    .admin-mode .stButton > button[kind="primary"] {
        background: #1f77b4;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. KHỞI TẠO CƠ SỞ DỮ LIỆU ĐỘNG (SESSION STATE)
# ==========================================
if "page" not in st.session_state: st.session_state.page = "home"
if "current_novel_id" not in st.session_state: st.session_state.current_novel_id = ""
if "is_admin" not in st.session_state: st.session_state.is_admin = False
if "unlocked_novels" not in st.session_state: st.session_state.unlocked_novels = []
if "editing_chap_idx" not in st.session_state: st.session_state.editing_chap_idx = None

# Dữ liệu gốc mô phỏng Database
if "novels" not in st.session_state:
    st.session_state.novels = {
        "truyen_1": {
            "id": "truyen_1",
            "ten": "Xuyên Không Thành Hệ Thống",
            "bia": "https://via.placeholder.com/150x220/2c3e50/ffffff?text=Xuyen+Khong",
            "van_an": "Lâm Duyệt hoảng hốt khi thấy cơ thể thạch của mình đang phát sáng rực rỡ...",
            "the_loai": ["Xuyên Không", "Hệ Thống", "Đam Mỹ"],
            "tinh_trang": "Đang cập nhật",
            "luot_xem": 15200,
            "de_xuat": 1400,
            "sao": 250, 
            "chuong": [
                {"title": "Chương 1: Bắt đầu", "content": "Nội dung chi tiết chương 1 nằm ở đây...", "views": 1500},
                {"title": "Chương 2: Cảnh báo", "content": "Nội dung chi tiết chương 2...", "views": 1450}
            ]
        },
        "truyen_2": {
            "id": "truyen_2",
            "ten": "Lạc Sủng",
            "bia": "https://via.placeholder.com/150x220/8e44ad/ffffff?text=Lac+Sung",
            "van_an": "Một câu chuyện ngôn tình đầy trắc trở...",
            "the_loai": ["Ngôn Tình", "Sủng"],
            "tinh_trang": "Hoàn thành",
            "luot_xem": 32000,
            "de_xuat": 5600,
            "sao": 850,
            "chuong": [{"title": "Chương 1: Gặp gỡ", "content": "Nội dung chương 1...", "views": 5000}]
        }
    }

# ==========================================
# 3. THANH BÊN (SIDEBAR) & LỌC THỂ LOẠI
# ==========================================
danh_sach_the_loai_goc = ["Ngôn Tình", "Đam Mỹ", "Xuyên Không", "Hệ Thống", "Cao H", "Xuyên Sách", "Đô Thị", "Sủng"]

st.sidebar.title("📚 Danh Mục")
chon_the_loai = st.sidebar.radio("Chọn thể loại:", ["Tất cả"] + danh_sach_the_loai_goc)

st.sidebar.divider()
if st.sidebar.button("🏠 Trang Chủ", use_container_width=True):
    st.session_state.page = 'home'
    st.rerun()

if st.sidebar.button("⚙️ Chủ Sở Hữu (Ẩn)", use_container_width=True):
    st.session_state.page = 'admin'
    st.rerun()

# ==========================================
# 4. GIAO DIỆN TRANG CHỦ (3 KHU VỰC VUỐT NGANG)
# ==========================================
def draw_novel_card(novel, key_prefix):
    st.image(novel["bia"], use_container_width=True)
    if st.button(f"{novel['ten']}", key=f"btn_{key_prefix}_{novel['id']}"):
        st.session_state.current_novel_id = novel['id']
        st.session_state.novels[novel['id']]["luot_xem"] += 1 
        st.session_state.page = 'read'
        st.rerun()

if st.session_state.page == 'home':
    st.title("Trang Chủ Đọc Truyện")
    
    tat_ca_truyen = list(st.session_state.novels.values())
    if chon_the_loai != "Tất cả":
        truyen_hien_thi = [t for t in tat_ca_truyen if chon_the_loai in t.get("the_loai", [])]
    else:
        truyen_hien_thi = tat_ca_truyen

    if not truyen_hien_thi:
        st.info(f"Chưa có truyện nào thuộc thể loại '{chon_the_loai}'.")
    else:
        top_sao = sorted(truyen_hien_thi, key=lambda x: x["sao"], reverse=True)
        top_dexuat = sorted(truyen_hien_thi, key=lambda x: x["de_xuat"], reverse=True)
        moi_dang = list(reversed(truyen_hien_thi))

        # --- KHU 1 ---
        st.subheader("⭐ Bảng Xếp Hạng 5 Sao")
        cols1 = st.columns(max(len(top_sao), 1))
        for idx, novel in enumerate(top_sao):
            with cols1[idx]:
                draw_novel_card(novel, "k1")
                st.caption(f"⭐ {novel['sao']} điểm")

        st.write("---")

        # --- KHU 2 ---
        st.subheader("🔥 Truyện Được Đề Xuất")
        cols2 = st.columns(max(len(top_dexuat), 1))
        for idx, novel in enumerate(top_dexuat):
            with cols2[idx]:
                draw_novel_card(novel, "k2")
                st.caption(f"👍 {novel['de_xuat']} đề xuất")

        st.write("---")

        # --- KHU 3 ---
        st.subheader("🆕 Truyện Mới Đăng")
        cols3 = st.columns(max(len(moi_dang), 1))
        for idx, novel in enumerate(moi_dang):
            with cols3[idx]:
                draw_novel_card(novel, "k3")
                st.caption("Mới cập nhật")

# ==========================================
# 5. GIAO DIỆN CHI TIẾT & ĐỌC TRUYỆN
# ==========================================
elif st.session_state.page == 'read':
    novel_id = st.session_state.current_novel_id
    if novel_id not in st.session_state.novels:
        st.error("Truyện không tồn tại.")
        st.button("Về Trang Chủ", on_click=lambda: st.session_state.update(page='home'))
    else:
        novel = st.session_state.novels[novel_id]
        
        st.button("⬅️ Quay lại Trang Chủ", on_click=lambda: st.session_state.update(page='home'))
        
        col_img, col_info = st.columns([1, 3])
        with col_img:
            st.image(novel["bia"], use_container_width=True)
        with col_info:
            st.title(novel["ten"])
            st.markdown(f"**Tình trạng:** {novel['tinh_trang']} | **Lượt xem:** {novel['luot_xem']}")
            st.markdown(f"**Thể loại:** {', '.join(novel['the_loai'])}")
            st.write("---")
            st.markdown(f"**Văn án:**\n\n{novel['van_an']}")
            
        st.divider()

        is_unlocked = novel_id in st.session_state.unlocked_novels
        
        if not is_unlocked:
            st.warning("🔒 Nội dung truyện đang bị khóa. Bạn cần xem quảng cáo để mở khóa toàn bộ chương.")
            with st.expander("👉 BẤM VÀO ĐÂY ĐỂ ĐỌC TRUYỆN", expanded=True):
                st.info("Bằng cách bấm vào link Shopee bên dưới, hệ thống sẽ mở khóa truyện cho bạn.")
                st.markdown("[🛒 Xem Quảng Cáo Shopee (Mở tab mới)](https://shopee.vn)")
                if st.button("✅ Tôi đã xem xong, Mở Khóa Truyện!", type="primary"):
                    st.session_state.unlocked_novels.append(novel_id)
                    st.success("Mở khóa thành công! Đang tải chương...")
                    time.sleep(1)
                    st.rerun()
        else:
            if not novel["chuong"]:
                st.info("Truyện này chưa có chương nào được đăng.")
            else:
                danh_sach_ten_chuong = [c["title"] for c in novel["chuong"]]
                chuong_chon = st.selectbox("📚 Chọn chương để đọc:", danh_sach_ten_chuong)
                chuong_data = next(c for c in novel["chuong"] if c["title"] == chuong_chon)
                
                st.markdown(f"### {chuong_data['title']}")
                st.write(chuong_data['content'])
                
                st.divider()
                
                st.write("**Bạn thấy chương này thế nào? Hãy ủng hộ tác giả nhé!**")
                c_dexuat, c_sao = st.columns(2)
                with c_dexuat:
                    if st.button("👍 Đề xuất truyện này (+1 Đề xuất)", use_container_width=True):
                        st.session_state.novels[novel_id]["de_xuat"] += 1
                        st.success("Đã cộng 1 Đề xuất! Số liệu Thống kê đã được cập nhật.")
                        time.sleep(1); st.rerun()
                with c_sao:
                    if st.button("⭐ Đánh giá 5 Sao (+5 Điểm)", use_container_width=True):
                        st.session_state.novels[novel_id]["sao"] += 5
                        st.success("Đã đánh giá 5 sao! Số liệu Thống kê đã được cập nhật.")
                        time.sleep(1); st.rerun()

# ==========================================
# 6. GIAO DIỆN QUẢN LÝ (TRANG ẨN CHỦ SỞ HỮU)
# ==========================================
elif st.session_state.page == 'admin':
    # Kích hoạt CSS riêng cho Admin
    st.markdown('<div class="admin-mode"></div>', unsafe_allow_html=True)
    
    if not st.session_state.is_admin:
        st.title("🔒 Khu Vực Đăng Truyện")
        pwd = st.text_input("Nhập mật khẩu (Pass: 971856):", type="password")
        if st.button("Mở Khóa"):
            if pwd == "971856":
                st.session_state.is_admin = True
                st.rerun()
            else: st.error("Mật khẩu không chính xác.")
    else:
        col_t, col_out = st.columns([8, 2])
        with col_t: st.title("⚙️ Bảng Điều Khiển Quản Trị")
        with col_out:
            if st.button("🚪 Đăng xuất", use_container_width=True):
                st.session_state.is_admin = False; st.rerun()

        st.write("---")
        danh_sach_quan_ly = {k: v["ten"] for k, v in st.session_state.novels.items()}
        danh_sach_quan_ly["new_novel"] = "➕ THÊM TRUYỆN MỚI TỪ ĐẦU..."
        
        selected_mng_id = st.selectbox("Chọn Truyện Để Thao Tác:", options=list(danh_sach_quan_ly.keys()), format_func=lambda x: danh_sach_quan_ly[x])
        
        st.write("---")
        tab_sua, tab_chuong, tab_thongke = st.tabs(["📝 Sửa Truyện", "📋 Danh Sách Chương", "📊 Thống Kê"])

        # -------- TAB 1: SỬA TRUYỆN --------
        with tab_sua:
            st.markdown('<div class="admin-mode">', unsafe_allow_html=True)
            if selected_mng_id == "new_novel":
                st.subheader("Tạo Truyện Mới")
                n_id = f"truyen_{int(time.time())}"
                n_ten = st.text_input("Tên Truyện Mới:")
                n_vanan = st.text_area("Văn Án:")
                n_theloai = st.multiselect("Thể Loại:", danh_sach_the_loai_goc)
                
                upload_bia_moi = st.file_uploader("Tải ảnh bìa lên (PNG/JPG):", type=['png', 'jpg', 'jpeg'], key="upload_new")
                b64_img = "https://via.placeholder.com/150x220?text=Bia+Moi"
                if upload_bia_moi:
                    b64 = base64.b64encode(upload_bia_moi.read()).decode()
                    b64_img = f"data:image/jpeg;base64,{b64}"
                    st.success("Tải ảnh thành công!")

                if st.button("Tạo Truyện Mới", type="primary"):
                    if n_ten:
                        st.session_state.novels[n_id] = {
                            "id": n_id, "ten": n_ten, "van_an": n_vanan, "the_loai": n_theloai,
                            "bia": b64_img,
                            "tinh_trang": "Đang cập nhật", "luot_xem": 0, "de_xuat": 0, "sao": 0, "chuong": []
                        }
                        st.success("Tạo thành công! Trang chủ đã tự động hiển thị truyện này.")
                        time.sleep(1); st.rerun()
            else:
                edit_novel = st.session_state.novels[selected_mng_id]
                st.subheader("Thông Tin Truyện")
                
                c_img, c_form = st.columns([1, 3])
                with c_img:
                    st.image(edit_novel["bia"], use_container_width=True)
                    upload_bia = st.file_uploader("Đổi ảnh bìa mới:", type=['png', 'jpg', 'jpeg'])
                    if upload_bia:
                        b64 = base64.b64encode(upload_bia.read()).decode()
                        st.session_state["temp_img"] = f"data:image/jpeg;base64,{b64}"
                        st.success("Ảnh đã sẵn sàng. Bấm Lưu bên phải để thay đổi!")

                with c_form:
                    edit_novel["ten"] = st.text_input("Tên truyện:", value=edit_novel["ten"])
                    edit_novel["tinh_trang"] = st.selectbox("Tình trạng:", ["Đang cập nhật", "Hoàn thành", "Tạm ngưng"], index=["Đang cập nhật", "Hoàn thành", "Tạm ngưng"].index(edit_novel["tinh_trang"]))
                    edit_novel["the_loai"] = st.multiselect("Thể loại (Tag):", danh_sach_the_loai_goc, default=edit_novel["the_loai"])
                    
                    cc1, cc2, cc3 = st.columns(3)
                    cc1.text_input("Lượt xem (Tự nhảy)", value=edit_novel["luot_xem"], disabled=True)
                    cc2.text_input("Số đề xuất (Tự nhảy)", value=edit_novel["de_xuat"], disabled=True)
                    cc3.text_input("Điểm Sao (Tự nhảy)", value=edit_novel["sao"], disabled=True)
                
                edit_novel["van_an"] = st.text_area("Văn án:", value=edit_novel["van_an"], height=150)
                if st.button("💾 Lưu Thay Đổi Cấu Hình", type="primary"):
                    if "temp_img" in st.session_state:
                        edit_novel["bia"] = st.session_state.pop("temp_img")
                    st.success("Đã cập nhật toàn bộ thông tin!")
                    time.sleep(1); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # -------- TAB 2: QUẢN LÝ DANH SÁCH CHƯƠNG --------
        with tab_chuong:
            st.markdown('<div class="admin-mode">', unsafe_allow_html=True)
            if selected_mng_id == "new_novel":
                st.warning("Vui lòng tạo truyện ở Tab 'Sửa Truyện' trước khi thêm chương.")
            else:
                mng_novel = st.session_state.novels[selected_mng_id]
                
                # NÚT THÊM CHƯƠNG NHƯ YÊU CẦU
                if st.button("➕ Thêm Chương Mới", type="primary"):
                    new_idx = len(mng_novel['chuong'])
                    mng_novel['chuong'].append({"title": f"Chương {new_idx + 1}", "content": "", "views": 0})
                    st.session_state.editing_chap_idx = f"{selected_mng_id}_{new_idx}"
                    st.rerun()

                with st.expander("✂️ Tự Động Tách Chương Hàng Loạt"):
                    st.info("Dán toàn bộ nội dung text vào ô. Thuật toán sẽ dò chữ 'Chương 1', 'Chương 2'... để tách.")
                    raw_text = st.text_area("Dán Text Truyện Gốc Vào Đây:", height=150)
                    if st.button("Bắt Đầu Tách", type="primary"):
                        if raw_text:
                            parts = re.split(r'(Chương\s*\d+.*?\n)', raw_text, flags=re.IGNORECASE)
                            new_chapters = []
                            if len(parts) > 1:
                                for i in range(1, len(parts), 2):
                                    title = parts[i].strip()
                                    content = parts[i+1].strip() if i+1 < len(parts) else ""
                                    new_chapters.append({"title": title, "content": content, "views": 0})
                                mng_novel["chuong"].extend(new_chapters)
                                st.success(f"🎉 Đã tách thành công {len(new_chapters)} chương!")
                                time.sleep(1); st.rerun()
                            else:
                                st.error("Không tìm thấy cấu trúc 'Chương X' trong đoạn text.")
                    
                st.divider()
                st.subheader(f"📋 Các chương hiện có ({len(mng_novel['chuong'])} chương)")
                
                # GIAO DIỆN HIỂN THỊ DẠNG DANH SÁCH CÓ NÚT EDIT/DELETE
                for idx, c in enumerate(mng_novel['chuong']):
                    # NẾU ĐANG BẤM SỬA CHƯƠNG NÀY -> HIỆN FORM NHẬP LIỆU
                    if st.session_state.get("editing_chap_idx") == f"{selected_mng_id}_{idx}":
                        with st.container(border=True):
                            new_title = st.text_input("Tên chương", value=c['title'], key=f"edit_title_{idx}")
                            new_content = st.text_area("Nội dung", value=c['content'], height=200, key=f"edit_content_{idx}")
                            
                            col_save, col_cancel = st.columns(2)
                            with col_save:
                                if st.button("💾 Lưu Chương", type="primary", use_container_width=True, key=f"save_{idx}"):
                                    mng_novel['chuong'][idx]['title'] = new_title
                                    mng_novel['chuong'][idx]['content'] = new_content
                                    st.session_state.editing_chap_idx = None
                                    st.success("Đã lưu chương thành công!")
                                    time.sleep(0.5); st.rerun()
                            with col_cancel:
                                if st.button("❌ Hủy", use_container_width=True, key=f"cancel_{idx}"):
                                    st.session_state.editing_chap_idx = None
                                    st.rerun()
                    
                    # NẾU KHÔNG SỬA -> HIỆN DẠNG DANH SÁCH LIST
                    else:
                        with st.container(border=True):
                            col_title, col_edit, col_del = st.columns([6, 2, 2])
                            with col_title:
                                st.markdown(f"**{c['title']}**")
                            with col_edit:
                                if st.button("📝 Sửa", use_container_width=True, key=f"btn_edit_{idx}"):
                                    st.session_state.editing_chap_idx = f"{selected_mng_id}_{idx}"
                                    st.rerun()
                            with col_del:
                                if st.button("🗑️ Xóa", use_container_width=True, key=f"btn_del_{idx}"):
                                    mng_novel['chuong'].pop(idx)
                                    st.success("Đã xóa chương!")
                                    time.sleep(0.5); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # -------- TAB 3: THỐNG KÊ CHI TIẾT --------
        with tab_thongke:
            if selected_mng_id == "new_novel":
                st.warning("Vui lòng chọn một bộ truyện cụ thể.")
            else:
                st_novel = st.session_state.novels[selected_mng_id]
                st.subheader(f"📊 Báo cáo Thống Kê Động: {st_novel['ten']}")
                
                c_sum1, c_sum2, c_sum3 = st.columns(3)
                c_sum1.metric("Tổng Người Đọc (Lượt xem)", st_novel["luot_xem"])
                c_sum2.metric("Số Đề Xuất", st_novel["de_xuat"])
                c_sum3.metric("Tổng Điểm Sao", st_novel["sao"])
