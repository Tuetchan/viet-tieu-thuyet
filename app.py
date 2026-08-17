import streamlit as st

# 1. Cài đặt giao diện toàn màn hình
st.set_page_config(page_title="Web Đọc Truyện", layout="wide")

# 2. CSS tùy chỉnh để tạo hiệu ứng vuốt ngang các truyện giống ảnh bạn gửi
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
    }
    </style>
""", unsafe_allow_html=True)

# 3. Hệ thống chuyển trang
if 'page' not in st.session_state:
    st.session_state.page = 'home'

# ==========================================
# THANH BÊN (SIDEBAR)
# ==========================================
st.sidebar.title("📚 Danh Mục")
the_loai = ["Tất cả", "Ngôn Tình", "Đam Mỹ", "Xuyên Không", "Hệ Thống"]
chon_the_loai = st.sidebar.radio("Chọn thể loại:", the_loai)

st.sidebar.divider()
# Nút chuyển trang
if st.sidebar.button("🏠 Trang Chủ"):
    st.session_state.page = 'home'
    st.rerun()

if st.sidebar.button("⚙️ Trang Chủ Sở Hữu (Ẩn)"):
    st.session_state.page = 'admin'
    st.rerun()

# ==========================================
# GIAO DIỆN TRANG CHỦ
# ==========================================
if st.session_state.page == 'home':
    st.title("Trang Chủ Đọc Truyện")
    
    st.subheader("⭐ Truyện 5 Sao (Vuốt ngang)")
    st.markdown("""
        <div class="scroll-container">
            <div class="truyen-card">Lạc Sủng<br>(Bìa 1)</div>
            <div class="truyen-card">Xuyên Không...<br>(Bìa 2)</div>
            <div class="truyen-card">Truyện 3<br>(Bìa 3)</div>
            <div class="truyen-card">Truyện 4<br>(Bìa 4)</div>
            <div class="truyen-card">Truyện 5<br>(Bìa 5)</div>
        </div>
    """, unsafe_allow_html=True)
    
    # Nút đọc thử để xem giao diện trang đọc truyện
    if st.button("📖 Đọc thử truyện: Xuyên Không Thành Hệ Thống"):
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

    st.subheader("🆕 Truyện Mới Đăng")
    st.markdown("""
        <div class="scroll-container">
            <div class="truyen-card">Truyện X</div>
            <div class="truyen-card">Truyện Y</div>
            <div class="truyen-card">Truyện Z</div>
        </div>
    """, unsafe_allow_html=True)

# ==========================================
# GIAO DIỆN ĐỌC TRUYỆN
# ==========================================
elif st.session_state.page == 'read':
    st.button("⬅️ Quay lại Trang Chủ", on_click=lambda: st.session_state.update(page='home'))
    st.title("📖 Xuyên Không Thành Hệ Thống")
    st.write("**Văn án:** Lâm Duyệt hoảng hốt khi thấy cơ thể thạch của mình đang phát sáng...")
    
    # Giả lập hộp thoại xem quảng cáo
    with st.expander("⚠️ MỞ KHÓA CHƯƠNG (Bấm vào đây)"):
        st.warning("Vui lòng xem quảng cáo để đọc tiếp!")
        st.markdown("[Nhấn vào đây để xem quảng cáo (Link Shopee)](https://shopee.vn)")
        if st.button("Tôi đã xem xong"):
            st.success("Đã mở khóa toàn bộ truyện!")
    
    st.divider()
    st.subheader("Chương 1: Xuyên không")
    st.write("Nội dung chương 1 hiện ra ở đây... độc giả có thể đọc bình thường.")
    
    st.write("---")
    # Nút đề xuất và đánh giá ở cuối chương
    col1, col2 = st.columns(2)
    with col1:
        st.button("👍 Đề xuất truyện này")
    with col2:
        st.button("⭐ Đánh giá 5 Sao")

# ==========================================
# GIAO DIỆN QUẢN LÝ (TRANG ẨN)
# ==========================================
elif st.session_state.page == 'admin':
    st.title("⚙️ Bảng Điều Khiển Chủ Sở Hữu")
    
    # Tạo 3 tab giống như bạn yêu cầu
    tab1, tab2, tab3 = st.tabs(["📝 Sửa Truyện", "📋 Danh Sách Chương", "📊 Thống Kê"])
    
    with tab1:
        st.subheader("Sửa thông tin truyện")
        st.text_input("Tên truyện", value="Xuyên Không Thành Hệ Thống")
        st.file_uploader("Upload Ảnh Bìa", type=['png', 'jpg', 'jpeg'])
        col_tinh_trang, col_luot_xem = st.columns(2)
        col_tinh_trang.selectbox("Tình trạng", ["Đang viết", "Hoàn thành", "Tạm ngưng"])
        col_luot_xem.text_input("Lượt xem (Chỉ đọc)", value="15,200", disabled=True)
        st.multiselect("Thể loại (Gắn tag)", ["Chủ Thụ", "Đam Mỹ", "Hệ Thống", "Xuyên Không"], default=["Đam Mỹ", "Xuyên Không"])
        st.button("Lưu Thay Đổi")
        
    with tab2:
        st.subheader("Tự động tách chương")
        st.write("Dán toàn bộ văn bản vào đây, hệ thống sẽ tự động tìm chữ 'Chương 1', 'Chương 2'... để tách ra.")
        full_text = st.text_area("Nội dung truyện gốc:", height=200)
        if st.button("Tự động chia chương"):
            st.info("Hệ thống đang xử lý chia chương...")
            
    with tab3:
        st.subheader("Thống kê chi tiết")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric(label="Tổng số người đọc", value="15,200", delta="+120")
        col_b.metric(label="Số đề xuất", value="1,400", delta="+15")
        col_c.metric(label="Đánh giá 5 Sao", value="850", delta="0")
