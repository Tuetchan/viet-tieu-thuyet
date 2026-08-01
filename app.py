st.write("### 📚 Danh sách File Raw hiện có:")
doc_names = [d["filename"] for d in st.session_state.novel_data["raw_docs"]]
selected_doc_name = st.selectbox("Chọn File độc lập để Tách chương:", doc_names)

selected_doc = next(d for d in st.session_state.novel_data["raw_docs"] if d["filename"] == selected_doc_name)

st.info(f"File **{selected_doc_name}** đang có khoảng {len(selected_doc['content'])} ký tự.")

col1, col2 = st.columns(2)
with col1: regex_split = st.text_input("Regex Tách Chương:", value=r"(第\s*[0-9一二三四五六七八九十百千万零]+\s*[章回节集卷部])")
with col2: str_split = st.text_input("Hoặc Tách theo Từ Khóa (VD: Chương, Chapter):")

if st.button("✂️ Bắt đầu Tách Chương từ File này"):
raw_text = selected_doc["content"]
if str_split: 
parts = raw_text.split(str_split)
titles = [f"{str_split} {i}" for i in range(1, len(parts))]
contents = parts[1:]
else: 
parts = re.split(regex_split, raw_text)
if len(parts) > 1:
titles = parts[1::2]
contents = parts[2::2]
else: titles, contents = [], []

if not titles: st.warning("Không tìm thấy chương nào theo quy tắc trên!")
else:
if "raw_chapters" not in st.session_state.novel_data: st.session_state.novel_data["raw_chapters"] = {}

for t, c in zip(titles, contents):
chap_name = f"[{selected_doc_name[:10]}] {t.strip()}"
st.session_state.novel_data["raw_chapters"][chap_name] = {"raw": f"{chap_name}\n{c.strip()}", "translated": ""}
st.session_state.trans_status[chap_name] = "⏳ Đợi Dịch"

save_user_data_to_supabase()
st.success(f"✅ Đã tách file này thành {len(titles)} chương và đưa vào hàng chờ dịch!")
time.sleep(1); st.rerun()

if st.button("🗑️ Xóa File này"):
st.session_state.novel_data["raw_docs"] = [d for d in st.session_state.novel_data["raw_docs"] if d["filename"] != selected_doc_name]
save_user_data_to_supabase()
st.rerun()

# --- MENU 3: DỊCH & QUẢN LÝ ---
elif menu == "3. Dịch & Quản Lý":
    st.header("⏳ Hàng chờ & Dịch Thuật")
    chapters = st.session_state.novel_data.get("raw_chapters", {})
    if not chapters:
        st.info("Chưa có chương nào trong hàng chờ.")
    else:
        chap_keys = list(chapters.keys())
        st.write(f"**Tổng số chương hiện có:** {len(chap_keys)}")
        
        col1, col2 = st.columns(2)
        with col1: delay = st.number_input("Delay giữa các lần dịch (giây):", value=2.0, min_value=0.5, step=0.5)
        with col2: 
            if st.button("🗑️ Xóa toàn bộ dữ liệu (Reset)", type="primary"):
                st.session_state.novel_data["raw_chapters"] = {}
                st.session_state.trans_status = {}
    st.header("⚡ Dịch Thuật & Quản Lý Chương")

    tab_manager, tab_quick = st.tabs(["📚 Dịch Hàng Loạt & Quản Lý", "✍️ Dịch Nhanh Thủ Công (Tự đưa Raw)"])

    # === TAB 1: DỊCH HÀNG LOẠT ===
    with tab_manager:
        if not st.session_state.novel_data.get("raw_chapters"):
            st.info("💡 Danh sách trống. Hãy qua mục '2. Nguồn Truyện' để cào Web hoặc tải file lên nhé.")
        else:
            chap_keys = list(st.session_state.novel_data["raw_chapters"].keys())
            
            # Xuất file ZIP
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for chap_key, data in st.session_state.novel_data["raw_chapters"].items():
                    content_to_save = data["translated"] if data["translated"] else data["raw"]
                    safe_filename = re.sub(r'[\\/*?:"<>|]', "", chap_key) + ".txt"
                    zip_file.writestr(safe_filename, content_to_save.encode("utf-8"))
            st.download_button("📥 Tải tất cả chương (.ZIP)", data=zip_buffer.getvalue(), file_name="Truyen_Da_Dich.zip", mime="application/zip", use_container_width=True)
            st.divider()

            # Bảng điều khiển
            st.subheader("🚀 Chạy dịch ngầm hàng loạt")
            selected_batch = st.multiselect("Chọn các chương cần dịch:", chap_keys)
            col_b1, col_b2 = st.columns([1, 1])
            with col_b1:
                if st.button("▶️ Đưa vào hàng chờ dịch ngầm", use_container_width=True):
                    model_choice = st.session_state.novel_data.get("selected_model", "3.5 Flash")
                    delay_time = 15 if "Pro" in model_choice else 5 
                    
                    count = 0
                    for c_key in selected_batch:
                        if st.session_state.trans_status.get(c_key) != "🔄 Đang dịch...":
                            st.session_state.trans_status[c_key] = "⏳ Đang chờ..."
                            st.session_state.translation_queue.put(c_key)
                            count += 1
                    
                    if count > 0 and not st.session_state.worker_running:
                        t = threading.Thread(
                            target=sequential_worker, 
                            args=(
                                st.session_state.translation_queue,
                                st.session_state.novel_data["api_keys"],
                                model_choice,
                                st.session_state.novel_data,
                                st.session_state.trans_status,
                                delay_time
                            )
                        )
                        t.start()
                        st.success(f"Đã thêm {count} chương vào hàng đợi dịch!")
                        time.sleep(1)
                        st.rerun()
            with col_b2:
                if st.button("🔄 Cập nhật tiến độ UI", use_container_width=True): st.rerun()

            active = {k: v for k, v in st.session_state.trans_status.items() if "🔄" in v or "⏳" in v or "⚠️" in v}
            if active:
                st.info("⏳ Đang chạy ngầm:\n" + "\n".join([f"- **{k}**: {v}" for k, v in active.items()]))
            
            st.divider()
            
            # Chi tiết từng chương
            st.subheader("📖 Xem & Chỉnh sửa chi tiết")
            selected_chap = st.selectbox("👉 Chọn chương:", chap_keys)
            chap_data = st.session_state.novel_data["raw_chapters"][selected_chap]
            status = st.session_state.trans_status.get(selected_chap, "Chưa dịch")
            
            if "❌" in status or "⚠️" in status: st.error(f"**Trạng thái:** `{status}`")
            else: st.caption(f"**Trạng thái:** `{status}`")
                
            if st.button("🗑️ Xóa chương này"):
                del st.session_state.novel_data["raw_chapters"][selected_chap]
save_user_data_to_supabase()
st.rerun()
                
        if st.button("🚀 Dịch Tất Cả (Tuần tự)", use_container_width=True):
            with st.session_state.translation_queue.mutex: st.session_state.translation_queue.queue.clear()
            for k in chap_keys: st.session_state.translation_queue.put(k)

            if not st.session_state.worker_running:
                threading.Thread(target=sequential_worker, args=(st.session_state.translation_queue, st.session_state.novel_data["api_keys"], st.session_state.novel_data["selected_model"], st.session_state.novel_data, st.session_state.trans_status, delay), daemon=True).start()
                st.toast("✅ Đã bắt đầu tiến trình dịch chạy ngầm!", icon="🚀")
            else: st.toast("⚠️ Tiến trình dịch đang chạy rồi!", icon="⚠️")
            # ĐƯA PHẦN LUẬT DỊCH VÀO TRỰC TIẾP LÚC DỊCH
            st.markdown("**🧠 Luật Dịch Áp Dụng Cho Chương Này:**")
            chap_prompt = st.text_area("Chỉnh sửa prompt ngay lúc dịch (nếu muốn):", value=st.session_state.novel_data.get("trans_prompt", ""), key=f"prompt_{selected_chap}")

            col_raw, col_trans = st.columns(2)
            with col_raw:
                st.markdown("**Bản Raw (Gốc)**")
                raw_text = st.text_area("Nội dung Raw:", value=chap_data["raw"], height=500, key=f"raw_{selected_chap}")
            with col_trans:
                st.markdown("**Bản Dịch**")
                if st.button("🌐 Ép dịch TRỰC TIẾP chương này", use_container_width=True):
                    with st.spinner("Đang dịch..."):
                        process_single_chapter(
                            selected_chap, raw_text, 
                            st.session_state.novel_data["api_keys"], 
                            st.session_state.novel_data.get("selected_model", "3.5 Flash"), 
                            st.session_state.novel_data, st.session_state.trans_status,
                            custom_prompt=chap_prompt # Truyền prompt thủ công vào
                        )
                        save_user_data_to_supabase()
                        st.rerun()
                
                trans_text = st.text_area("Nội dung Dịch:", value=chap_data["translated"], height=500, key=f"trans_{selected_chap}")
                
            if st.button("💾 LƯU CHỈNH SỬA TAY", use_container_width=True):
                st.session_state.novel_data["raw_chapters"][selected_chap]["raw"] = raw_text
                st.session_state.novel_data["raw_chapters"][selected_chap]["translated"] = trans_text
                save_user_data_to_supabase()
                st.success("Đã lưu chỉnh sửa!")

    # === TAB 2: DỊCH NHANH THỦ CÔNG ===
    with tab_quick:
        st.subheader("✍️ Dịch Tự Do (Tự đưa Raw và Prompt vào)")
        st.info("Chức năng này dùng để test hoặc dịch trực tiếp mà không lưu vào danh sách truyện.")

        st.write("---")
        for k in chap_keys:
            if k not in st.session_state.trans_status: 
                status = "✅ Hoàn thành" if chapters[k].get("translated") else "⏳ Đợi Dịch"
                st.session_state.trans_status[k] = status
        quick_prompt = st.text_area("🧠 Luật Dịch (Prompt):", value=st.session_state.novel_data.get("trans_prompt", ""), height=150)

        cols = st.columns(3)
        for i, k in enumerate(chap_keys):
            with cols[i % 3]:
                st.markdown(f"**{k}** - {st.session_state.trans_status[k]}")
                with st.expander("Xem / Dịch Lại"):
                    st.text_area("Bản Raw:", chapters[k]["raw"], height=100, key=f"raw_{k}")
                    if chapters[k]["translated"]: st.text_area("Bản Dịch:", chapters[k]["translated"], height=100, key=f"trans_{k}")
        col_q1, col_q2 = st.columns(2)
        with col_q1:
            quick_raw = st.text_area("📥 Dán Raw vào đây:", height=400)
            
        with col_q2:
            if "quick_result" not in st.session_state:
                st.session_state.quick_result = ""
                
            if st.button("🚀 Dịch Ngay (Bấm 1 lần)"):
                if quick_raw.strip():
                    with st.spinner("Đang dịch..."):
                        sys_p = quick_prompt + "\n\n[LỆNH BẮT BUỘC]: Trả về trực tiếp bản dịch. Không giải thích."
                        success, res = call_llm(
                            sys_p, 
                            f"RAW CẦN DỊCH:\n\n{quick_raw}", 
                            st.session_state.novel_data["api_keys"], 
                            st.session_state.novel_data.get("selected_model", "3.5 Flash")
                        )
                        if success:
                            st.session_state.quick_result = res
                        else:
                            st.error(f"Lỗi: {res}")
                else:
                    st.warning("Bạn chưa nhập Raw!")

                    if st.button("Dịch chương này", key=f"btn_{k}"):
                        st.session_state.trans_status[k] = "🔄 Đang dịch..."
                        process_single_chapter(k, chapters[k]["raw"], st.session_state.novel_data["api_keys"], st.session_state.novel_data["selected_model"], st.session_state.novel_data, st.session_state.trans_status)
                        save_user_data_to_supabase()
                        st.rerun()
                        
        if st.button("⬇️ Xuất EPUB", use_container_width=True):
            st.info("Chức năng xuất EPUB chuẩn bị ra mắt, vui lòng copy text tạm nhé!")
            st.text_area("📜 Kết quả dịch:", value=st.session_state.quick_result, height=400)
