elif menu == "3. Tách & Dịch Raw":
    st.header("✂️ Tách chương & Dịch Raw")
    
    # --- [TÍNH NĂNG MỚI] CÀO RAW TRỰC TIẾP TỪ WEB ---
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
                    # Gọi hàm cào web (Yêu cầu phải có hàm scrape_text_from_url khai báo ở trên)
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

    # --- TÁCH CHƯƠNG TỪ FILE RAW (Giữ nguyên gốc của bạn) ---
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
        
        chap_keys = list(st.session_state.novel_data["raw_chapters"].keys())
        
        with st.expander("🚀 Bảng điều khiển Dịch Hàng Loạt (Chạy Ngầm)", expanded=True):
            st.markdown("💡 *Tool sẽ tự động điều chỉnh thời gian nghỉ (3s cho Flash, 15s cho Pro) và tự retry 60s nếu quá tải API.*")
            
            selected_batch = st.multiselect("Chọn các chương cần dịch:", chap_keys)
            
            col_btn_run, col_btn_ref = st.columns([1, 1])
            with col_btn_run:
                if st.button("▶️ Bắt đầu dịch ngầm"):
                    started = 0
                    
                    # [TÍNH NĂNG MỚI] Auto-delay theo Model
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
                        time.sleep(delay_time) # Tạm dừng chống ngập API (Rate limit)
                    
                    if started > 0:
                        st.toast(f"Đã đưa {started} chương vào tiến trình nền! (Tự động nghỉ {delay_time}s giữa các request)")
                        time.sleep(1)
                        st.rerun()
            
            with col_btn_ref:
                if st.button("🔄 Cập nhật tiến độ"):
                    st.rerun()

            # Hiển thị cả task đang dịch VÀ task đang chờ Retry 60s (⚠️)
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
            
        # Nút xóa tiện ích
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
            
            # --- [TÍNH NĂNG MỚI] AUTO-RETRY KHI ÉP DỊCH TRỰC TIẾP ---
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
                            
                            # Bắt lỗi 429, 404 từ nội dung trả về
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
