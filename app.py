import streamlit as st
import re
import time
import base64

# ==========================================
# 1. CẤU HÌNH TRANG & CSS LINH HOẠT THEO THEME MÁY TÍNH
# ==========================================
st.set_page_config(page_title="Web Đọc Truyện", page_icon="📖", layout="wide")

st.markdown("""
    <style>
    /* Bỏ ép màu cứng, cho phép web tự đổi Trắng/Đen theo cài đặt máy tính của độc giả */
    
    /* Làm đẹp nút bấm tên truyện và Tự động cắt chữ bằng dấu ... */
    .stButton > button {
        width: 100%;
        border-radius: 6px;
    }
    .stButton > button p {
        white-space: nowrap !important; 
        overflow: hidden !important; 
        text-overflow: ellipsis !important;
        width: 100% !important;
        margin: 0 !important;
        font-weight: bold !important;
        font-size: 14px !important;
    }
    
    /* Thiết kế cho thẻ truyện ngoài Trang Chủ */
    [data-testid="column"] img {
        border-radius: 6px;
        object-fit: cover;
        width: 100%;
        height: 220px; /* Chiều cao cố định cho ảnh bìa (Chuẩn 2x3) */
        margin-bottom: 5px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    
    /* Text số sao/đề xuất nhỏ */
    .small-stats { 
        font-size: 13px !important; 
        opacity: 0.7; /* Làm mờ đi một chút để phân biệt với tên truyện */
        margin-top: 4px !important; 
        text-align: center;
    }
    
    /* Khung danh sách Admin và Tab Xem Thêm */
    .list-thumb img { 
        border-radius: 4px; 
        height: 80px !important; 
        object-fit: cover; 
        width: 55px !important; 
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }
    </style>
""", unsafe_allow_html=True)

# Ảnh bìa mặc định an toàn tuyệt đối
DEFAULT_COVER = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAQAAAAnOwc2AAAAEUlEQVR42mO88Z8BAzAOZUEAhy8S9yVvD1sAAAAASUVORK5CYII="

# ==========================================
# 2. KHỞI TẠO CƠ SỞ DỮ LIỆU ĐỘNG (SESSION STATE)
# ==========================================
if "page" not in st.session_state: st.session_state.page = "home"
if "current_novel_id" not in st.session_state: st.session_state.current_novel_id = ""
if "view_more_category" not in st.session_state: st.session_state.view_more_category = None
if "is_admin" not in st.session_state: st.session_state.is_admin = False
if "admin_selected_novel_id" not in st.session_state: st.session_state.admin_selected_novel_id = None
if "unlocked_novels" not in st.session_state: st.session_state.unlocked_novels = []
if "editing_chap_idx" not in st.session_state: st.session_state.editing_chap_idx = None

if "novels" not in st.session_state:
    st.session_state.novels = {
        "truyen_1": {
            "id": "truyen_1", "ten": "Xuyên Không Thành Hệ Thống Chống Lại Thế Giới",
            "bia": DEFAULT_COVER,
            "van_an": "Lâm Duyệt hoảng hốt khi thấy cơ thể thạch của mình đang phát sáng rực rỡ...",
            "the_loai": ["Xuyên Không", "Hệ Thống", "Đam Mỹ"],
            "tinh_trang": "Đang cập nhật", "luot_xem": 15200, "de_xuat": 1400, "sao": 250, "hien_thi_trang_chu": True,
            "chuong": [{"title": "Chương 1: Bắt đầu", "content": "Nội dung chi tiết chương 1...", "views": 1500}]
        },
        "truyen_2": {
            "id": "truyen_2", "ten": "Lạc Sủng Của Bạo Quân Chốn Hậu Cung",
            "bia": DEFAULT_COVER,
            "van_an": "Một câu chuyện ngôn tình đầy trắc trở...",
            "the_loai": ["Ngôn Tình", "Sủng"],
            "tinh_trang": "Hoàn thành", "luot_xem": 32000, "de_xuat": 5600, "sao": 850, "hien_thi_trang_chu": True,
            "chuong": [{"title": "Chương 1: Gặp gỡ", "content": "Nội dung chương 1...", "views": 5000}]
        }
    }

for k, v in st.session_state.novels.items():
    if "hien_thi_trang_chu" not in v: v["hien_thi_trang_chu"] = True
    if "via.placeholder.com" in v["bia"]: v["bia"] = DEFAULT_COVER

# ==========================================
# 3. THANH BÊN (SIDEBAR) & LỌC THỂ LOẠI
# ==========================================
danh_sach_the_loai_goc = ["Ngôn Tình", "Đam Mỹ", "Xuyên Không", "Hệ Thống", "Cao H", "Xuyên Sách", "Đô Thị", "Sủng"]

st.sidebar.title("📚 Danh Mục")
chon_the_loai = st.sidebar.radio("Chọn thể loại:", ["Tất cả"] + danh_sach_the_loai_goc)

st.sidebar.divider()
if st.sidebar.button("🏠 Trang Chủ", use_container_width=True):
    st.session_state.page = 'home'
    st.session_state.view_more_category = None
    st.rerun()

if st.sidebar.button("⚙️ Chủ Sở Hữu (Ẩn)", use_container_width=True):
    st.session_state.page = 'admin'
    st.rerun()

# ==========================================
# 4. GIAO DIỆN TRANG CHỦ & DANH SÁCH (XEM THÊM)
# ==========================================
def click_novel(novel_id):
    st.session_state.current_novel_id = novel_id
    st.session_state.novels[novel_id]["luot_xem"] += 1 
    st.session_state.page = 'read'
    st.rerun()

if st.session_state.page == 'home':
    tat_ca_truyen = [t for t in st.session_state.novels.values() if t.get("hien_thi_trang_chu") == True]
    if chon_the_loai != "Tất cả": truyen_hien_thi = [t for t in tat_ca_truyen if chon_the_loai in t.get("the_loai", [])]
    else: truyen_hien_thi = tat_ca_truyen

    top_sao = sorted(truyen_hien_thi, key=lambda x: x["sao"], reverse=True)
    top_dexuat = sorted(truyen_hien_thi, key=lambda x: x["de_xuat"], reverse=True)
    moi_dang = list(reversed(truyen_hien_thi))

    # ---- GIAO DIỆN XEM THÊM (CÓ ẢNH THUMBNAIL) ----
    if st.session_state.view_more_category:
        st.button("⬅️ Quay lại Trang Chủ", on_click=lambda: st.session_state.update(view_more_category=None))
        cat_name = st.session_state.view_more_category
        st.title(f"📖 Danh sách: {cat_name}")
        list_to_show = top_sao if cat_name == "Top 5 Sao" else (top_dexuat if cat_name == "Top Đề Xuất" else moi_dang)
        
        c1, c2, c3, c4 = st.columns([1, 4, 3, 2])
        c1.markdown("**Bìa**")
        c2.markdown("**Tên Truyện**")
        c3.markdown("**Thể Loại & Lượt Xem**")
        c4.markdown("**Đánh Giá**")
        st.divider()
        for n in list_to_show:
            c1, c2, c3, c4 = st.columns([1, 4, 3, 2])
            with c1:
                st.markdown(f'<div class="list-thumb"><img src="{n["bia"]}"></div>', unsafe_allow_html=True)
            with c2:
                if st.button(n['ten'], key=f"list_{n['id']}", use_container_width=True): click_novel(n['id'])
            with c3:
                st.write(", ".join(n['the_loai']))
                st.caption(f"👁️ {n['luot_xem']} lượt xem")
            with c4:
                st.write(f"⭐ {n['sao']} điểm")
                st.caption(f"👍 {n['de_xuat']} đề xuất")
            st.write("---")
            
    # ---- GIAO DIỆN TRANG CHỦ (LƯỚI 3 CỘT x 2 HÀNG) ----
    else:
        st.title("Trang Chủ Đọc Truyện")
        if not truyen_hien_thi:
            st.info(f"Chưa có truyện nào thuộc danh mục '{chon_the_loai}'.")
        else:
            def render_grid_section(title, novels_list, cat_name, icon_stat):
                col_title, col_space, col_btn = st.columns([7, 1, 2])
                with col_title: st.subheader(title)
                with col_btn:
                    if st.button("Xem thêm >", use_container_width=True, key=f"more_{cat_name}"):
                        st.session_state.view_more_category = cat_name; st.rerun()
                
                # Lấy tối đa 6 truyện (Để vẽ 2 hàng, mỗi hàng 3 cột)
                novels_6 = novels_list[:6]
                
                # Vòng lặp vẽ lưới 3 cột
                for i in range(0, len(novels_6), 3):
                    cols = st.columns(3)
                    for j in range(3):
                        if i + j < len(novels_6):
                            n = novels_6[i+j]
                            with cols[j]:
                                st.image(n["bia"])
                                if st.button(n['ten'], key=f"card_{cat_name}_{n['id']}"): click_novel(n['id'])
                                if icon_stat == "sao": st.markdown(f"<div class='small-stats'>⭐ {n['sao']} điểm</div>", unsafe_allow_html=True)
                                elif icon_stat == "dexuat": st.markdown(f"<div class='small-stats'>👍 {n['de_xuat']} đề xuất</div>", unsafe_allow_html=True)
                                else: st.markdown(f"<div class='small-stats'>🆕 Mới cập nhật</div>", unsafe_allow_html=True)
                    st.write("") # Khoảng cách giữa các hàng

            render_grid_section("⭐ Truyện 5 Sao", top_sao, "Top 5 Sao", "sao")
            st.write("---")
            render_grid_section("🔥 Truyện Đề Xuất", top_dexuat, "Top Đề Xuất", "dexuat")
            st.write("---")
            render_grid_section("🆕 Truyện Mới Đăng", moi_dang, "Truyện Mới", "moi")

# ==========================================
# 5. GIAO DIỆN CHI TIẾT & ĐỌC TRUYỆN
# ==========================================
elif st.session_state.page == 'read':
    novel_id = st.session_state.current_novel_id
    if novel_id not in st.session_state.novels:
        st.error("Truyện không tồn tại."); st.button("Về Trang Chủ", on_click=lambda: st.session_state.update(page='home'))
    else:
        novel = st.session_state.novels[novel_id]
        st.button("⬅️ Quay lại Trang Chủ", on_click=lambda: st.session_state.update(page='home'))
        
        col_img, col_info = st.columns([1, 4])
        with col_img: st.image(novel["bia"], use_container_width=True)
        with col_info:
            st.title(novel["ten"])
            st.markdown(f"**Tình trạng:** {novel['tinh_trang']} | **Lượt xem:** {novel['luot_xem']}")
            st.markdown(f"**Thể loại:** {', '.join(novel['the_loai'])}")
            st.write("---")
            st.markdown(f"**Văn án:**\n\n{novel['van_an']}")
            
        st.divider()

        if novel_id not in st.session_state.unlocked_novels:
            st.warning("🔒 Nội dung truyện đang bị khóa. Bạn cần xem quảng cáo để mở khóa toàn bộ chương.")
            with st.expander("👉 BẤM VÀO ĐÂY ĐỂ ĐỌC TRUYỆN", expanded=True):
                st.markdown("[🛒 Xem Quảng Cáo Shopee (Mở tab mới)](https://shopee.vn)")
                if st.button("✅ Tôi đã xem xong, Mở Khóa Truyện!", type="primary"):
                    st.session_state.unlocked_novels.append(novel_id)
                    st.success("Mở khóa thành công! Đang tải chương..."); time.sleep(1); st.rerun()
        else:
            if not novel["chuong"]: st.info("Truyện chưa có chương nào được đăng.")
            else:
                danh_sach_ten_chuong = [c["title"] for c in novel["chuong"]]
                chuong_chon = st.selectbox("📚 Chọn chương để đọc:", danh_sach_ten_chuong)
                chuong_data = next(c for c in novel["chuong"] if c["title"] == chuong_chon)
                
                st.markdown(f"### {chuong_data['title']}")
                st.write(chuong_data['content'])
                st.divider()
                
                c_dexuat, c_sao = st.columns(2)
                if c_dexuat.button("👍 Đề xuất truyện này (+1)", use_container_width=True):
                    st.session_state.novels[novel_id]["de_xuat"] += 1; st.success("Cộng 1 Đề xuất!"); time.sleep(1); st.rerun()
                if c_sao.button("⭐ Đánh giá 5 Sao (+5)", use_container_width=True):
                    st.session_state.novels[novel_id]["sao"] += 5; st.success("Cộng 5 Điểm Sao!"); time.sleep(1); st.rerun()

# ==========================================
# 6. GIAO DIỆN QUẢN LÝ
# ==========================================
elif st.session_state.page == 'admin':
    if not st.session_state.is_admin:
        st.title("🔒 Khu Vực Quản Trị")
        pwd = st.text_input("Nhập mật khẩu (Pass: 971856):", type="password")
        if st.button("Mở Khóa"):
            if pwd == "971856": st.session_state.is_admin = True; st.rerun()
            else: st.error("Mật khẩu không chính xác.")
    else:
        if st.session_state.admin_selected_novel_id is None:
            col_t, col_out = st.columns([8, 2])
            with col_t: st.title("⚙️ Bảng Điều Khiển Quản Trị")
            with col_out:
                if st.button("🚪 Đăng xuất", use_container_width=True): st.session_state.is_admin = False; st.rerun()

            st.write("---")
            if st.button("➕ Thêm Bản Nháp Mới", type="primary"):
                st.session_state.admin_selected_novel_id = "new_novel"; st.rerun()
            
            st.divider()
            c1, c2, c3, c4 = st.columns([1, 5, 3, 2])
            c1.markdown("**Bìa**"); c2.markdown("**Tên Truyện & Thông tin**"); c3.markdown("**Trạng Thái**"); c4.markdown("**Hành Động**")
            st.write("---")
            
            for n_id, n_data in reversed(list(st.session_state.novels.items())):
                c1, c2, c3, c4 = st.columns([1, 5, 3, 2])
                with c1: st.markdown(f'<div class="list-thumb"><img src="{n_data["bia"]}"></div>', unsafe_allow_html=True)
                with c2:
                    st.markdown(f"**{n_data['ten']}**")
                    st.caption(f"👁️ {n_data['luot_xem']}  |  {len(n_data['chuong'])} chương")
                with c3:
                    if n_data.get("hien_thi_trang_chu"): st.success("🟢 Đang hiển thị")
                    else: st.warning("🔴 Bản nháp (Đang ẩn)")
                with c4:
                    if st.button("⚙️ Quản Lý", key=f"btn_mng_{n_id}", use_container_width=True):
                        st.session_state.admin_selected_novel_id = n_id; st.rerun()
                st.write("---")

        else:
            st.button("⬅️ Quay Lại Bảng Danh Sách", on_click=lambda: st.session_state.update(admin_selected_novel_id=None))
            
            selected_mng_id = st.session_state.admin_selected_novel_id
            tab_sua, tab_chuong, tab_thongke = st.tabs(["📝 Sửa Truyện", "📋 Danh Sách Chương", "📊 Thống Kê"])

            with tab_sua:
                if selected_mng_id == "new_novel":
                    st.subheader("Tạo Bản Nháp Mới")
                    n_id = f"truyen_{int(time.time())}"
                    n_ten = st.text_input("Tên Truyện Mới:")
                    n_vanan = st.text_area("Văn Án:")
                    n_theloai = st.multiselect("Thể Loại:", danh_sach_the_loai_goc)
                    
                    upload_bia_moi = st.file_uploader("Tải ảnh bìa lên (PNG/JPG):", type=['png', 'jpg', 'jpeg'], key="upload_new")
                    b64_img = DEFAULT_COVER
                    if upload_bia_moi:
                        b64 = base64.b64encode(upload_bia_moi.read()).decode()
                        b64_img = f"data:image/jpeg;base64,{b64}"; st.success("Tải ảnh thành công!")

                    if st.button("Lưu Vào Kho Nháp", type="primary"):
                        if n_ten:
                            st.session_state.novels[n_id] = {
                                "id": n_id, "ten": n_ten, "van_an": n_vanan, "the_loai": n_theloai,
                                "bia": b64_img, "hien_thi_trang_chu": False,
                                "tinh_trang": "Đang cập nhật", "luot_xem": 0, "de_xuat": 0, "sao": 0, "chuong": []
                            }
                            st.success("Tạo nháp thành công!")
                            st.session_state.admin_selected_novel_id = None; time.sleep(1); st.rerun()
                else:
                    edit_novel = st.session_state.novels[selected_mng_id]
                    c_img, c_form = st.columns([1, 3])
                    with c_img:
                        st.image(edit_novel["bia"], use_container_width=True)
                        upload_bia = st.file_uploader("Đổi ảnh bìa mới:", type=['png', 'jpg', 'jpeg'])
                        if upload_bia:
                            b64 = base64.b64encode(upload_bia.read()).decode()
                            st.session_state["temp_img"] = f"data:image/jpeg;base64,{b64}"; st.success("Bấm Lưu để thay đổi!")

                    with c_form:
                        st.markdown("### 🌐 Quản lý Hiển thị")
                        if edit_novel.get("hien_thi_trang_chu"):
                            st.success("🟢 Truyện này ĐANG HIỆN trên Trang Chủ")
                            if st.button("🚫 Gỡ Khỏi Trang Chủ (Ẩn đi)"): edit_novel["hien_thi_trang_chu"] = False; st.rerun()
                        else:
                            st.warning("🔴 Truyện này ĐANG ẨN (Bản nháp)")
                            if st.button("🚀 Thêm Vào Trang Chủ", type="primary"): edit_novel["hien_thi_trang_chu"] = True; st.rerun()
                                
                        st.divider()
                        edit_novel["ten"] = st.text_input("Tên truyện:", value=edit_novel["ten"])
                        edit_novel["tinh_trang"] = st.selectbox("Tình trạng:", ["Đang cập nhật", "Hoàn thành", "Tạm ngưng"], index=["Đang cập nhật", "Hoàn thành", "Tạm ngưng"].index(edit_novel["tinh_trang"]))
                        edit_novel["the_loai"] = st.multiselect("Thể loại:", danh_sach_the_loai_goc, default=edit_novel["the_loai"])
                        
                        cc1, cc2, cc3 = st.columns(3)
                        cc1.text_input("Lượt xem", value=edit_novel["luot_xem"], disabled=True)
                        cc2.text_input("Số đề xuất", value=edit_novel["de_xuat"], disabled=True)
                        cc3.text_input("Điểm Sao", value=edit_novel["sao"], disabled=True)
                    
                    edit_novel["van_an"] = st.text_area("Văn án:", value=edit_novel["van_an"], height=150)
                    if st.button("💾 Lưu Thay Đổi Cấu Hình", type="primary"):
                        if "temp_img" in st.session_state: edit_novel["bia"] = st.session_state.pop("temp_img")
                        st.success("Đã cập nhật!"); time.sleep(1); st.rerun()

            with tab_chuong:
                if selected_mng_id == "new_novel":
                    st.warning("Vui lòng lưu bản nháp truyện ở Tab 'Sửa Truyện' trước khi thêm chương.")
                else:
                    mng_novel = st.session_state.novels[selected_mng_id]
                    
                    if st.button("➕ Thêm Chương Mới", type="primary"):
                        new_idx = len(mng_novel['chuong'])
                        mng_novel['chuong'].append({"title": f"Chương {new_idx + 1}", "content": "", "views": 0})
                        st.session_state.editing_chap_idx = f"{selected_mng_id}_{new_idx}"; st.rerun()

                    with st.expander("✂️ Tự Động Tách Chương Hàng Loạt"):
                        raw_text = st.text_area("Dán Text Truyện Gốc Vào Đây:", height=150)
                        if st.button("Bắt Đầu Tách", type="primary") and raw_text:
                            parts = re.split(r'(Chương\s*\d+.*?\n)', raw_text, flags=re.IGNORECASE)
                            if len(parts) > 1:
                                new_chapters = [{"title": parts[i].strip(), "content": parts[i+1].strip() if i+1 < len(parts) else "", "views": 0} for i in range(1, len(parts), 2)]
                                mng_novel["chuong"].extend(new_chapters)
                                st.success(f"Đã tách {len(new_chapters)} chương!"); time.sleep(1); st.rerun()
                            else: st.error("Không tìm thấy cấu trúc 'Chương X'.")
                        
                    st.divider()
                    st.subheader(f"📋 Danh sách ({len(mng_novel['chuong'])} chương)")
                    
                    for idx, c in enumerate(mng_novel['chuong']):
                        if st.session_state.get("editing_chap_idx") == f"{selected_mng_id}_{idx}":
                            with st.container(border=True):
                                new_title = st.text_input("Tên chương", value=c['title'], key=f"edit_title_{idx}")
                                new_content = st.text_area("Nội dung", value=c['content'], height=200, key=f"edit_content_{idx}")
                                col_save, col_cancel = st.columns(2)
                                if col_save.button("💾 Lưu Chương", type="primary", use_container_width=True, key=f"save_{idx}"):
                                    mng_novel['chuong'][idx]['title'] = new_title
                                    mng_novel['chuong'][idx]['content'] = new_content
                                    st.session_state.editing_chap_idx = None
                                    st.success("Đã lưu!"); time.sleep(0.5); st.rerun()
                                if col_cancel.button("❌ Hủy", use_container_width=True, key=f"cancel_{idx}"):
                                    st.session_state.editing_chap_idx = None; st.rerun()
                        else:
                            with st.container(border=True):
                                col_title, col_edit, col_del = st.columns([6, 2, 2])
                                col_title.markdown(f"**{c['title']}**")
                                if col_edit.button("📝 Sửa", use_container_width=True, key=f"btn_edit_{idx}"):
                                    st.session_state.editing_chap_idx = f"{selected_mng_id}_{idx}"; st.rerun()
                                if col_del.button("🗑️ Xóa", use_container_width=True, key=f"btn_del_{idx}"):
                                    mng_novel['chuong'].pop(idx); st.rerun()

            with tab_thongke:
                if selected_mng_id != "new_novel":
                    st_novel = st.session_state.novels[selected_mng_id]
                    c_sum1, c_sum2, c_sum3 = st.columns(3)
                    c_sum1.metric("Tổng Người Đọc", st_novel["luot_xem"])
                    c_sum2.metric("Số Đề Xuất", st_novel["de_xuat"])
                    c_sum3.metric("Tổng Điểm Sao", st_novel["sao"])
