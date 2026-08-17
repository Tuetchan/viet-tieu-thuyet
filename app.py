import streamlit as st
import re
import time

# ==========================================
# 1. CẤU HÌNH TRANG & CSS TÙY CHỈNH
# ==========================================
st.set_page_config(page_title="Web Đọc Truyện", page_icon="📖", layout="wide")

# CSS "Ma thuật" để ép các cột của Streamlit thành dạng vuốt ngang mượt mà
st.markdown("""
    <style>
    /* Ép cột nằm ngang và có thanh cuộn */
    [data-testid="stHorizontalBlock"] {
        overflow-x: auto;
        flex-wrap: nowrap;
        padding-bottom: 15px;
        gap: 15px;
    }
    /* Cố định kích thước mỗi khung truyện */
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
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. KHỞI TẠO CƠ SỞ DỮ LIỆU (SESSION STATE)
# ==========================================
if "page" not in st.session_state: st.session_state.page = "home"
if "current_novel_id" not in st.session_state: st.session_state.current_novel_id = ""
if "is_admin" not in st.session_state: st.session_state.is_admin = False
if "unlocked_novels" not in st.session_state: st.session_state.unlocked_novels = []

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
            "sao": 250, # Quy đổi: 1 lần đánh giá 5 sao = cộng 5 điểm
            "chuong": [
                {"title": "Chương 1: Bắt đầu", "content": "Nội dung chi tiết chương 1 nằm ở đây...", "views": 1500},
                {"title": "Chương 2: Hệ thống cảnh báo", "content": "Nội dung chi tiết chương 2...", "views": 1450}
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
            "chuong": [{"title": "Chương 1", "content": "Nội dung...", "views": 5000}]
        },
        "truyen_3": {
            "id": "truyen_3",
            "ten": "Đại Lão Trở Về",
            "bia": "https://via.placeholder.com/150x220/c0392b/ffffff?text=Dai+Lao",
            "van_an": "Ngày hắn trở về, bầu trời đổi màu...",
            "the_loai": ["Đô Thị", "Hệ Thống"],
            "tinh_trang": "Đang cập nhật",
            "luot_xem": 500,
            "de_xuat": 10,
            "sao": 15,
            "chuong": []
        }
    }

# ==========================================
# 3. THANH BÊN (SIDEBAR) & LỌC THỂ LOẠI
# ==========================================
danh_sach_the_loai_goc = ["Ngôn Tình", "Đam Mỹ", "Xuyên Không", "Hệ Thống", "Cao H", "Xuyên Sách", "Đô Thị", "Sủng"]

st.sidebar.title("📚 Danh Mục")
chon_the_loai = st.sidebar.radio("Chọn thể loại:", ["Tất cả Cả"] + danh_sach_the_loai_goc)

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
    """Hàm vẽ thẻ truyện (Bìa + Tên) dùng chung cho các khu vực"""
    st.image(novel["bia"], use_container_width=True)
    if st.button(f"{novel['ten']}", key=f"btn_{key_prefix}_{novel['id']}"):
        st.session_state.current_novel_id = novel['id']
        st.session_state.novels[novel['id']]["luot_xem"] += 1 # Tăng view khi click
        st.session_state.page = 'read'
        st.rerun()

if st.session_state.page == 'home':
    st.title("Trang Chủ Đọc Truyện")
    
    # Lọc truyện theo thể loại từ Sidebar
    tat_ca_truyen = list(st.session_state.novels.values())
    if chon_the_loai != "Tất cả Cả":
        truyen_hien_thi = [t for t in tat_ca_truyen if chon_the_loai in t.get("the_loai", [])]
    else:
        truyen_hien_thi = tat_ca_truyen

    if not truyen_hien_thi:
        st.info(f"Chưa có truyện nào thuộc thể loại '{chon_the_loai}'.")
    else:
        # THUẬT TOÁN PHÂN CHIA KHU VỰC
        # Khu 1: Truyện 5 Sao (Sắp xếp theo số sao giảm dần)
        top_sao = sorted(truyen_hien_thi, key=lambda x: x["sao"], reverse=True)
        # Khu 2: Truyện Đề Xuất (Sắp xếp theo lượt đề xuất giảm dần)
        top_dexuat = sorted(truyen_hien_thi, key=lambda x: x["de_xuat"], reverse=True)
        # Khu 3: Truyện Mới Đăng (Lấy thứ tự ngược lại của danh sách gốc)
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
        st.subheader("🔥 Truyện Được Đề Xuất Nhiều Nhất")
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
        
        # HIỂN THỊ THÔNG TIN TRUYỆN
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

        # CƠ CHẾ KHÓA / MỞ QUẢNG CÁO
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
            # HIỂN THỊ NỘI DUNG CHƯƠNG KHI ĐÃ MỞ KHÓA
            if not novel["chuong"]:
                st.info("Truyện này chưa có chương nào được đăng.")
            else:
                # Chọn chương để đọc
                danh_sach_ten_chuong = [c["title"] for c in novel["chuong"]]
                chuong_chon = st.selectbox("📚 Danh sách chương:", danh_sach_ten_chuong)
                
                chuong_data = next(c for c in novel["chuong"] if c["title"] == chuong_chon)
                
                st.markdown(f"### {chuong_data['title']}")
                st.write(chuong_data['content'])
                
                st.divider()
                
                # TƯƠNG TÁC CUỐI CHƯƠNG (Đồng bộ trực tiếp với Thuật toán Trang chủ)
                st.write("**Bạn thấy chương này thế nào? Hãy ủng hộ tác giả nhé!**")
                c_dexuat, c_sao = st.columns(2)
                with c_dexuat:
                    if st.button("👍 Đề xuất truyện này (+1 Đề xuất)", use_container_width=True):
                        st.session_state.novels[novel_id]["de_xuat"] += 1
                        st.success("Cảm ơn bạn đã đề xuất! Truyện sẽ được thăng hạng.")
                with c_sao:
                    if st.button("⭐ Đánh giá 5 Sao (+5 Điểm Sao)", use_container_width=True):
                        st.session_state.novels[novel_id]["sao"] += 5
                        st.success("Tuyệt vời! Truyện đã được cộng điểm sao.")

# ==========================================
# 6. GIAO DIỆN QUẢN LÝ (TRANG ẨN CHỦ SỞ HỮU)
# ==========================================
elif st.session_state.page == 'admin':
    # HỆ THỐNG KHÓA TRANG
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

        # CHỌN TRUYỆN ĐỂ QUẢN LÝ
        st.write("---")
        danh_sach_quan_ly = {k: v["ten"] for k, v in st.session_state.novels.items()}
        danh_sach_quan_ly["new_novel"] = "➕ THÊM TRUYỆN MỚI TỪ ĐẦU..."
        
        selected_mng_id = st.selectbox("Chọn Truyện Để Thao Tác:", options=list(danh_sach_quan_ly.keys()), format_func=lambda x: danh_sach_quan_ly[x])
        
        st.write("---")
        
        # 3 TAB QUẢN LÝ CHÍNH
        tab_sua, tab_chuong, tab_thongke = st.tabs(["📝 Sửa Truyện", "📋 Danh Sách Chương", "📊 Thống Kê"])

        # -------- TAB 1: SỬA TRUYỆN --------
        with tab_sua:
            if selected_mng_id == "new_novel":
                st.subheader("Tạo Truyện Mới")
                n_id = f"truyen_{int(time.time())}"
                n_ten = st.text_input("Tên Truyện Mới:")
                n_vanan = st.text_area("Văn Án:")
                n_theloai = st.multiselect("Thể Loại:", danh_sach_the_loai_goc)
                if st.button("Tạo Truyện Mới", type="primary"):
                    if n_ten:
                        st.session_state.novels[n_id] = {
                            "id": n_id, "ten": n_ten, "van_an": n_vanan, "the_loai": n_theloai,
                            "bia": "https://via.placeholder.com/150x220?text=Bia+Moi",
                            "tinh_trang": "Đang cập nhật", "luot_xem": 0, "de_xuat": 0, "sao": 0, "chuong": []
                        }
                        st.success("Tạo thành công! Trang chủ đã được cập nhật.")
                        time.sleep(1); st.rerun()
            else:
                edit_novel = st.session_state.novels[selected_mng_id]
                st.subheader("Thông Tin Truyện")
                
                c_img, c_form = st.columns([1, 3])
                with c_img:
                    st.image(edit_novel["bia"])
                    st.text_input("Link Ảnh Bìa Mới:", value=edit_novel["bia"], key="edit_bia")
                
                with c_form:
                    edit_novel["ten"] = st.text_input("Tên truyện:", value=edit_novel["ten"])
                    edit_novel["tinh_trang"] = st.selectbox("Tình trạng:", ["Đang cập nhật", "Hoàn thành", "Tạm ngưng"], index=["Đang cập nhật", "Hoàn thành", "Tạm ngưng"].index(edit_novel["tinh_trang"]))
                    edit_novel["the_loai"] = st.multiselect("Thể loại (Tag):", danh_sach_the_loai_goc, default=edit_novel["the_loai"])
                    
                    # Dữ liệu tĩnh tinh gọn như yêu cầu
                    cc1, cc2, cc3 = st.columns(3)
                    cc1.text_input("Lượt xem", value=edit_novel["luot_xem"], disabled=True)
                    cc2.text_input("Số đề xuất", value=edit_novel["de_xuat"], disabled=True)
                    cc3.text_input("Điểm Sao", value=edit_novel["sao"], disabled=True)
                
                edit_novel["van_an"] = st.text_area("Văn án:", value=edit_novel["van_an"], height=150)
                if st.button("💾 Lưu Thay Đổi Cấu Hình", type="primary"):
                    edit_novel["bia"] = st.session_state["edit_bia"]
                    st.success("Đã lưu!")

        # -------- TAB 2: DANH SÁCH CHƯƠNG & TỰ ĐỘNG TÁCH --------
        with tab_chuong:
            if selected_mng_id == "new_novel":
                st.warning("Vui lòng tạo truyện ở Tab 'Sửa Truyện' trước khi thêm chương.")
            else:
                mng_novel = st.session_state.novels[selected_mng_id]
                st.subheader("Tự Động Tách Chương Hàng Loạt")
                st.info("Dán toàn bộ nội dung text truyện vào ô bên dưới. Thuật toán sẽ tự động dò tìm các từ khóa (Chương 1, Chương 2,...) để cắt thành từng chương riêng biệt.")
                
                raw_text = st.text_area("Dán Text Truyện Gốc Vào Đây:", height=200)
                if st.button("✂️ Bắt Đầu Tách Chương", type="primary"):
                    if raw_text:
                        # Dùng Regex để tách dựa trên "Chương X" hoặc "Chương XX"
                        parts = re.split(r'(Chương\s*\d+.*?\n)', raw_text, flags=re.IGNORECASE)
                        
                        new_chapters = []
                        # Xử lý mảng sau khi tách
                        if len(parts) > 1:
                            for i in range(1, len(parts), 2):
                                title = parts[i].strip()
                                content = parts[i+1].strip() if i+1 < len(parts) else ""
                                new_chapters.append({"title": title, "content": content, "views": 0})
                                
                            mng_novel["chuong"].extend(new_chapters)
                            st.success(f"🎉 Đã tách thành công {len(new_chapters)} chương và thêm vào bộ truyện!")
                        else:
                            st.error("Không tìm thấy cấu trúc 'Chương 1', 'Chương 2'... trong đoạn text. Hãy kiểm tra lại.")
                    
                st.divider()
                st.subheader(f"📋 Các chương hiện có ({len(mng_novel['chuong'])} chương)")
                for idx, c in enumerate(mng_novel['chuong']):
                    with st.expander(f"{c['title']} (Click để xem lại/sửa)"):
                        st.text_area("Nội dung", value=c['content'], height=150, key=f"content_{selected_mng_id}_{idx}")

        # -------- TAB 3: THỐNG KÊ CHI TIẾT --------
        with tab_thongke:
            if selected_mng_id == "new_novel":
                st.warning("Vui lòng chọn một bộ truyện cụ thể.")
            else:
                st_novel = st.session_state.novels[selected_mng_id]
                st.subheader(f"📊 Báo cáo cho: {st_novel['ten']}")
                
                c_sum1, c_sum2, c_sum3 = st.columns(3)
                c_sum1.metric("Tổng Người Đọc (Views)", st_novel["luot_xem"])
                c_sum2.metric("Số Đề Xuất Được Thêm", st_novel["de_xuat"])
                c_sum3.metric("Tổng Điểm Sao (5-1)", st_novel["sao"])
                
                st.divider()
                st.markdown("**Lưu lượng đọc chi tiết từng chương:**")
                if not st_novel["chuong"]:
                    st.write("Chưa có dữ liệu chương.")
                else:
                    for c in st_novel["chuong"]:
                        st.markdown(f"- **{c['title']}**: {c.get('views', 0)} lượt đọc")
