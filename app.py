<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Novel Co-Writer Studio (Gemini 3.5 Flash)</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #f1f1f1; }
        ::-webkit-scrollbar-thumb { background: #c1c1c1; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #a8a8a8; }
        .loader {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3b82f6;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            animation: spin 1s linear infinite;
            display: inline-block;
            vertical-align: middle;
            margin-right: 8px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        textarea { resize: vertical; min-height: 200px; }
    </style>
</head>
<body class="bg-gray-50 text-gray-800 font-sans min-h-screen flex flex-col">
    <!-- Header -->
    <header class="bg-white shadow-sm sticky top-0 z-10">
        <div class="max-w-6xl mx-auto px-4 py-4 flex flex-col md:flex-row justify-between items-center gap-4">
            <h1 class="text-2xl font-bold text-blue-600"><i class="fa-solid fa-feather-pointed mr-2"></i>AI Novel Co-Writer</h1>
            <div class="flex items-center space-x-2">
                <input type="password" id="apiKey" placeholder="Nhập Gemini API Key..." class="border rounded-md px-3 py-1.5 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-blue-500">
                <a href="https://aistudio.google.com/app/apikey" target="_blank" class="text-xs text-blue-500 hover:underline">Lấy Key</a>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="flex-grow max-w-6xl mx-auto px-4 py-8 w-full flex flex-col md:flex-row gap-6">
        <!-- Sidebar Navigation -->
        <div class="w-full md:w-1/4">
            <div class="bg-white rounded-lg shadow p-4 md:sticky md:top-24">
                <h2 class="font-semibold text-lg mb-4 border-b pb-2">Tiến trình sáng tác</h2>
                <ul class="space-y-3" id="step-nav">
                    <li class="flex items-center text-blue-600 font-medium" data-step="1">
                        <span class="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center mr-3 text-sm">1</span> Tham khảo raw
                    </li>
                    <li class="flex items-center text-gray-400" data-step="2">
                        <span class="w-6 h-6 rounded-full bg-gray-100 text-gray-500 flex items-center justify-center mr-3 text-sm">2</span> Văn án
                    </li>
                    <li class="flex items-center text-gray-400" data-step="3">
                        <span class="w-6 h-6 rounded-full bg-gray-100 text-gray-500 flex items-center justify-center mr-3 text-sm">3</span> Dàn ý chương
                    </li>
                    <li class="flex items-center text-gray-400" data-step="4">
                        <span class="w-6 h-6 rounded-full bg-gray-100 text-gray-500 flex items-center justify-center mr-3 text-sm">4</span> Viết & Sửa nháp
                    </li>
                    <li class="flex items-center text-gray-400" data-step="5">
                        <span class="w-6 h-6 rounded-full bg-gray-100 text-gray-500 flex items-center justify-center mr-3 text-sm">5</span> Bản chính thức
                    </li>
                </ul>
            </div>
        </div>

        <!-- Content Area -->
        <div class="w-full md:w-3/4 bg-white rounded-lg shadow p-6" id="workspace">
            <!-- Step 1 -->
            <div id="step-1-content" class="step-content block">
                <h2 class="text-xl font-bold mb-2">Bước 1: Nạp nguyên liệu (Raw Text)</h2>
                <p class="text-sm text-gray-600 mb-4">Cung cấp truyện raw để AI học thể loại và nảy ra ý tưởng mới.</p>
                <div class="mb-4">
                    <input type="file" id="fileInput" multiple accept=".txt" class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100">
                </div>
                <textarea id="rawText" class="w-full border rounded-md p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm" placeholder="Hoặc dán trực tiếp truyện raw vào đây..."></textarea>
                <div class="mt-4 flex justify-end">
                    <button onclick="goToStep(2)" class="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 transition">Tiếp tục <i class="fa-solid fa-arrow-right ml-2"></i></button>
                </div>
            </div>

            <!-- Step 2 -->
            <div id="step-2-content" class="step-content hidden">
                <h2 class="text-xl font-bold mb-2">Bước 2: Sáng tạo Văn án (Synopsis)</h2>
                <p class="text-sm text-gray-600 mb-4">AI sẽ đề xuất Văn án hoàn toàn mới. <b>SỬA TRỰC TIẾP</b> vào ô dưới đây nếu muốn đổi ý tưởng.</p>
                <button onclick="generateContent('synopsis')" class="bg-indigo-100 text-indigo-700 px-4 py-2 rounded-md hover:bg-indigo-200 transition mb-4 border border-indigo-200 font-medium">
                    <i class="fa-solid fa-wand-magic-sparkles mr-2"></i>Tạo Văn án Mới
                </button>
                <div id="loading-synopsis" class="hidden text-blue-600 mb-4"><span class="loader"></span> AI đang phân tích raw...</div>
                <textarea id="synopsisText" class="w-full border rounded-md p-3 focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="Văn án sẽ xuất hiện ở đây..."></textarea>
                <div class="mt-4 flex justify-between">
                    <button onclick="goToStep(1)" class="text-gray-600 hover:text-gray-900 px-4 py-2"><i class="fa-solid fa-arrow-left mr-2"></i>Quay lại</button>
                    <button onclick="goToStep(3)" class="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 transition">Lưu Văn án <i class="fa-solid fa-arrow-right ml-2"></i></button>
                </div>
            </div>

            <!-- Step 3 -->
            <div id="step-3-content" class="step-content hidden">
                <h2 class="text-xl font-bold mb-2">Bước 3: Dàn ý chương</h2>
                <div class="flex items-center mb-4 gap-4">
                    <label class="text-sm">Số chương:</label>
                    <input type="number" id="numChapters" value="5" min="1" max="20" class="border rounded-md px-2 py-1 w-20">
                    <button onclick="generateContent('outline')" class="bg-indigo-100 text-indigo-700 px-4 py-2 rounded-md hover:bg-indigo-200 transition border border-indigo-200 font-medium">
                        <i class="fa-solid fa-list-ol mr-2"></i>Tạo Dàn ý
                    </button>
                </div>
                <div id="loading-outline" class="hidden text-blue-600 mb-4"><span class="loader"></span> Đang sắp xếp cốt truyện...</div>
                <textarea id="outlineText" class="w-full border rounded-md p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 h-96" placeholder="Dàn ý..."></textarea>
                <div class="mt-4 flex justify-between">
                    <button onclick="goToStep(2)" class="text-gray-600 hover:text-gray-900 px-4 py-2"><i class="fa-solid fa-arrow-left mr-2"></i>Quay lại</button>
                    <button onclick="goToStep(4)" class="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 transition">Chốt Dàn ý <i class="fa-solid fa-arrow-right ml-2"></i></button>
                </div>
            </div>

            <!-- Step 4 -->
            <div id="step-4-content" class="step-content hidden">
                <h2 class="text-xl font-bold mb-2">Bước 4: Viết Nháp & Sửa Chữa</h2>
                <div class="mb-4">
                    <label class="block text-sm font-bold text-gray-700 mb-1">Dàn ý của chương này:</label>
                    <textarea id="currentChapterInfo" class="w-full border rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[100px]" placeholder="Copy dàn ý của 1 chương vào đây..."></textarea>
                </div>
                <button onclick="generateContent('draft')" class="bg-indigo-100 text-indigo-700 px-4 py-2 rounded-md hover:bg-indigo-200 transition mb-4 border border-indigo-200 font-medium w-full">
                    <i class="fa-solid fa-pen-nib mr-2"></i>AI: Viết Nháp
                </button>
                <div id="loading-draft" class="hidden text-blue-600 mb-4"><span class="loader"></span> Đang tạo bản nháp thô...</div>
                <div class="mb-4">
                    <label class="block text-sm font-bold text-green-700 mb-1"><i class="fa-solid fa-user-pen mr-1"></i> Không Gian Sửa Chữa:</label>
                    <textarea id="draftText" class="w-full border-2 border-green-300 bg-green-50 rounded-md p-3 focus:outline-none focus:ring-2 focus:ring-green-500 h-96" placeholder="Bản nháp sẽ hiện ra ở đây. Bạn TỰ DO XÓA/SỬA."></textarea>
                </div>
                <div class="mt-4 flex justify-between">
                    <button onclick="goToStep(3)" class="text-gray-600 hover:text-gray-900 px-4 py-2"><i class="fa-solid fa-arrow-left mr-2"></i>Quay lại</button>
                    <button onclick="goToStep(5)" class="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 transition">Hoàn thiện <i class="fa-solid fa-arrow-right ml-2"></i></button>
                </div>
            </div>

            <!-- Step 5 -->
            <div id="step-5-content" class="step-content hidden">
                <h2 class="text-xl font-bold mb-2">Bước 5: Bản Chính Thức</h2>
                <button onclick="generateContent('final')" class="bg-indigo-600 text-white px-4 py-3 rounded-md hover:bg-indigo-700 transition mb-4 font-bold shadow-lg w-full text-lg">
                    <i class="fa-solid fa-book-open mr-2"></i>AI: Hoàn Thiện Chương Này
                </button>
                <div id="loading-final" class="hidden text-blue-600 mb-4"><span class="loader"></span> Đang trau chuốt câu từ...</div>
                <div class="mb-4">
                    <textarea id="finalText" class="w-full border-2 border-purple-300 bg-white rounded-md p-4 focus:outline-none focus:ring-2 focus:ring-purple-500 h-[500px] text-base leading-relaxed" placeholder="Kết quả hoàn hảo sẽ ở đây..."></textarea>
                </div>
                <div class="mt-4 flex justify-between">
                    <button onclick="goToStep(4)" class="text-gray-600 hover:text-gray-900 px-4 py-2"><i class="fa-solid fa-arrow-left mr-2"></i>Sửa lại bản nháp</button>
                    <button onclick="copyFinalText()" class="bg-green-600 text-white px-6 py-2 rounded-md hover:bg-green-700 transition"><i class="fa-solid fa-copy mr-2"></i>Copy Text</button>
                </div>
            </div>
        </div>
    </main>

    <script>
        function goToStep(step) {
            document.querySelectorAll('.step-content').forEach(el => {
                el.classList.add('hidden'); el.classList.remove('block');
            });
            document.getElementById(`step-${step}-content`).classList.remove('hidden');
            document.getElementById(`step-${step}-content`).classList.add('block');

            document.querySelectorAll('#step-nav li').forEach((el, index) => {
                const stepNum = index + 1;
                const span = el.querySelector('span');
                if (stepNum === step) {
                    el.className = "flex items-center text-blue-600 font-medium";
                    span.className = "w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center mr-3 text-sm";
                } else if (stepNum < step) {
                    el.className = "flex items-center text-green-600";
                    span.className = "w-6 h-6 rounded-full bg-green-100 text-green-600 flex items-center justify-center mr-3 text-sm";
                    span.innerHTML = '<i class="fa-solid fa-check text-xs"></i>';
                } else {
                    el.className = "flex items-center text-gray-400";
                    span.className = "w-6 h-6 rounded-full bg-gray-100 text-gray-500 flex items-center justify-center mr-3 text-sm";
                    span.innerText = stepNum;
                }
            });
        }

        document.getElementById('fileInput').addEventListener('change', function(e) {
            const files = e.target.files;
            let combinedText = "";
            let filesRead = 0;
            if(files.length === 0) return;
            Array.from(files).forEach(file => {
                const reader = new FileReader();
                reader.onload = function(e) {
                    combinedText += `\n\n--- Tham khảo: ${file.name} ---\n` + e.target.result;
                    filesRead++;
                    if (filesRead === files.length) document.getElementById('rawText').value = combinedText;
                };
                reader.readAsText(file);
            });
        });

        async function callGeminiAPI(prompt, systemInstruction = "") {
            const apiKey = document.getElementById('apiKey').value.trim();
            if (!apiKey) {
                alert("Vui lòng nhập Gemini API Key!");
                return null;
            }
            
            // Đường link đã được thay đổi sang sử dụng model gemini-3.5-flash
            const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key=${apiKey}`;
            
            const requestBody = { contents: [{ parts: [{ text: prompt }] }] };
            if (systemInstruction) {
                requestBody.systemInstruction = { parts: [{ text: systemInstruction }] };
            }

            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestBody)
                });
                const data = await response.json();
                if (data.error) {
                    alert(`Lỗi API: ${data.error.message}`); 
                    return null; 
                }
                return data.candidates[0].content.parts[0].text;
            } catch (error) { 
                alert(`Lỗi kết nối: ${error.message}`); 
                return null; 
            }
        }

        async function generateContent(type) {
            let prompt = "";
            let systemInstruction = "Bạn là tiểu thuyết gia và biên tập viên văn học. Nhiệm vụ của bạn là hỗ trợ tác giả sáng tác truyện. Viết bằng tiếng Việt tự nhiên, phong phú, không lặp từ.";
            let outputElementId = "";
            let loadingElementId = `loading-${type}`;

            const rawText = document.getElementById('rawText').value;
            const synopsisText = document.getElementById('synopsisText').value;
            const chapterInfo = document.getElementById('currentChapterInfo').value;
            const draftText = document.getElementById('draftText').value;

            if (type === 'synopsis') {
                if (!rawText) return alert("Vui lòng nhập truyện raw làm mẫu!");
                prompt = `Dựa vào THỂ LOẠI, VĂN PHONG, và MÔ TÍP của đoạn raw dưới đây, hãy sáng tạo ra một VĂN ÁN (Synopsis) cho một bộ truyện HOÀN TOÀN MỚI. Yêu cầu: Hấp dẫn, rõ bối cảnh, mâu thuẫn chính.\n\nRAW:\n${rawText.substring(0, 15000)}`;
                outputElementId = 'synopsisText';
            } else if (type === 'outline') {
                if (!synopsisText) return alert("Cần có Văn án!");
                const numChapters = document.getElementById('numChapters').value;
                prompt = `Dựa vào Văn án sau, lập dàn ý chi tiết cho ${numChapters} chương đầu tiên. Mỗi chương ghi rõ: Tiêu đề chương, Các diễn biến chính.\n\nVĂN ÁN:\n${synopsisText}`;
                outputElementId = 'outlineText';
            } else if (type === 'draft') {
                if (!synopsisText || !chapterInfo) return alert("Cần có Văn án và Dàn ý chương!");
                prompt = `VĂN ÁN:\n${synopsisText}\n\nDÀN Ý CHƯƠNG NÀY:\n${chapterInfo}\n\nDựa vào Văn án và Dàn ý, hãy viết NHÁP (Draft) toàn bộ nội dung chương. Tập trung phát triển hành động.`;
                outputElementId = 'draftText';
            } else if (type === 'final') {
                if (!draftText) return alert("Cần có Bản nháp!");
                prompt = `Đây là Bản Nháp truyện do TÁC GIẢ đã chỉnh sửa:\n${draftText}\n\nNhiệm vụ của bạn là biến bản nháp này thành CHƯƠNG CHÍNH THỨC.\nYÊU CẦU:\n1. Giữ nguyên 100% tình tiết.\n2. Trau chuốt văn phong mượt mà.\n3. Thêm miêu tả cảnh vật, nội tâm.\n4. Cải thiện hội thoại.\n5. Độ dài phải dài hơn bản nháp.`;
                outputElementId = 'finalText';
            }

            document.getElementById(loadingElementId).classList.remove('hidden');
            const result = await callGeminiAPI(prompt, systemInstruction);
            document.getElementById(loadingElementId).classList.add('hidden');

            if (result) document.getElementById(outputElementId).value = result;
        }

        function copyFinalText() {
            navigator.clipboard.writeText(document.getElementById('finalText').value).then(() => alert("Đã copy văn bản!"));
        }
    </script>
</body>
</html>
