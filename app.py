import streamlit as st
from openai import OpenAI
from PIL import Image
import io
import base64

# ✅ OpenAI APIキーを .streamlit/secrets.toml から取得
client = OpenAI(api_key=st.secrets["openai"]["api_key"])

st.set_page_config(page_title="翻譯支援測試app", layout="wide")

# ✅ フォント設定（Webフォントの読み込み付き）
st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC&display=swap" rel="stylesheet">
    <style>
        html, body, [class*="css"]  {
            font-family: 'Noto Sans TC', 'Microsoft JhengHei', 'PingFang TC', sans-serif;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📘 漫畫翻譯支援工具 - 測試版")

# サイドバー
st.sidebar.header("操作選單")
menu = st.sidebar.radio("請選擇操作步驟：", ["上傳圖片並辨識文字（OCR）", "修正辨識文字", "輸入提示並翻譯"])

# 🔧 temperature スライダーを追加
temperature = st.sidebar.slider(
    "翻譯的創造性（temperature）",
    min_value=0.0,
    max_value=1.0,
    value=0.95,
    step=0.05,
    help="值が高いほど自由な翻訳になります（例：口語表現多樣化）"
)

# ======================================================
# 🟢 ステップ1：登場人物登録（アップロード自動リセット対応）
# ======================================================
if menu == "上傳圖片並辨識文字（OCR）":
    st.subheader("👥 請登錄登場人物")
    st.markdown("請依序輸入角色圖片、名稱、性格後再執行 OCR")

    # ✅ アップロード欄のkeyを動的に変更（リセット対応）
    upload_key = "char_img" if "reset_char_img" not in st.session_state else "char_img_new"
    char_img = st.file_uploader("登場人物圖片（一次一位）", type=["jpg", "jpeg", "png"], key=upload_key)
    char_name = st.text_input("名稱（例如：大雄）", key="char_name")
    char_desc = st.text_area("性格或特徵（例如：愛哭、懶散）", key="char_desc")

    # ✅ 登録ボタン
    # ✅ 登録ボタン
if st.button("➕ 登錄"):
    if char_img and char_name:
        # 登録処理
        st.session_state["characters"] = st.session_state.get("characters", [])
        st.session_state["characters"].append({
            "image": char_img,
            "name": char_name,
            "description": char_desc
        })
        st.success(f"已註冊角色：{char_name}")

        # ✅ 新增：清空名字與描述輸入框（避免停留上次內容）
        st.session_state["char_name"] = ""      # ← NEW
        st.session_state["char_desc"] = ""      # ← NEW

        # ✅ file_uploader をリセットするフラグを設定
        st.session_state["reset_char_img"] = True
        st.rerun()
    else:
        st.warning("圖片與名稱為必填欄位")


    # ✅ 登録済みキャラクターの表示
    if "characters" in st.session_state and st.session_state["characters"]:
        st.markdown("#### ✅ 已註冊角色：")
        for i, char in enumerate(st.session_state["characters"]):
            col1, col2, col3 = st.columns([0.3, 0.5, 0.2])
            with col1:
                st.image(char["image"], caption=None, width=100)
            with col2:
                new_name = st.text_input(f"名稱（{i}）", char["name"], key=f"edit_name_{i}")
                new_desc = st.text_area(f"性格／特徵（{i}）", char["description"], key=f"edit_desc_{i}")
                if st.button(f"🔁 更新（{char['name']}）", key=f"update_{i}"):
                    st.session_state["characters"][i]["name"] = new_name
                    st.session_state["characters"][i]["description"] = new_desc
                    st.success(f"已更新角色：{new_name}")
            with col3:
                if st.button(f"❌ 刪除", key=f"delete_{i}"):
                    deleted_name = st.session_state["characters"][i]["name"]
                    del st.session_state["characters"][i]
                    st.success(f"已刪除角色：{deleted_name}")
                    st.rerun()

    # ======================================================
    # 🟢 メイン画像アップロード（OCR用）
    # ======================================================
    st.markdown("---")
    uploaded_file = st.file_uploader("📄 上傳漫畫圖片（JPEG/PNG）", type=["jpg", "jpeg", "png"], key="main_img")

    if uploaded_file:
        image = Image.open(uploaded_file)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        st.session_state["image_base64"] = img_base64
        st.session_state.pop("ocr_text", None)
        st.session_state["corrected_text_saved"] = False
    elif "image_base64" in st.session_state:
        img_bytes = base64.b64decode(st.session_state["image_base64"])
        image = Image.open(io.BytesIO(img_bytes))
        img_base64 = st.session_state["image_base64"]
    else:
        image = None

    if image:
        st.image(image, caption="已上傳圖片", use_container_width=True)
        if st.button("📄 執行辨識"):
            with st.spinner("辨識中... 使用 GPT-4o 分析圖片"):
                image_url = f"data:image/png;base64,{img_base64}"
                character_context = "\n".join([
                    f"・{c['name']}：{c['description']}"
                    for c in st.session_state.get("characters", [])
                ])
                prompt_text = f"""
你是一位熟悉日本漫畫對話場景的台詞辨識助手，請從下方圖片中，**只提取出位於漫畫「對話框（吹き出し）」中的日文對白**。

🧩 規則如下：
1. 依據漫畫畫面**從右到左、從上到下**排序。
2. 每句台詞標示發言角色，角色名稱須**嚴格使用我提供的角色資訊**。
3. 不得使用其他推測角色名或外語名（如 Nobita、のび太）。
4. 背景文字、旁白、效果音略過不處理。
5. 若文字不清，根據上下文自然補全。

📋 角色資訊：
{character_context}

📌 格式：角色名稱：台詞內容
"""
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": prompt_text},
                        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_url}}]}
                    ]
                )
                st.session_state["ocr_text"] = response.choices[0].message.content.strip()
                st.session_state["corrected_text_saved"] = False
                # ✅ OCR 完成版本號（避免覆寫使用者校正）
                st.session_state["ocr_version"] = st.session_state.get("ocr_version", 0) + 1

    if "ocr_text" in st.session_state:
        st.text_area("已辨識文字（可於下一步修正）", st.session_state["ocr_text"], height=300)

# ======================================================
# 🟡 ステップ2：テキスト修正
# ======================================================
elif menu == "修正辨識文字":
    if "ocr_text" not in st.session_state:
        st.warning("請先上傳圖片並執行辨識。")
    else:
        st.subheader("🛠️ 修正辨識文字內容")
        col1, col2 = st.columns([1, 1.3])

        with col1:
            st.markdown("#### 📷 原始圖片")
            if "image_base64" in st.session_state:
                img_bytes = base64.b64decode(st.session_state["image_base64"])
                image = Image.open(io.BytesIO(img_bytes))
                st.image(image, caption="參考圖片", use_container_width=True)
            else:
                st.info("尚未上傳圖片")

        with col2:
            st.markdown("#### ✏️ 修正區域")

            # ✅ 僅在 OCR「剛更新」時初始化一次，不覆寫使用者的修正
            current_version = st.session_state.get("ocr_version", 0)
            if st.session_state.get("corrected_text_version") != current_version:
                st.session_state["corrected_text"] = st.session_state["ocr_text"]
                st.session_state["corrected_text_version"] = current_version

            new_text = st.text_area(
                "請修正辨識結果（可換行）",
                value=st.session_state.get("corrected_text", st.session_state["ocr_text"]),
                height=500
            )

            if st.button("💾 儲存修正內容"):
                st.session_state["corrected_text"] = new_text
                st.success("內容已儲存，可進一步進行翻譯。")

# ======================================================
# 🟣 ステップ3：輸入提示並翻譯
# ======================================================
elif menu == "輸入提示並翻譯":
    if "corrected_text" not in st.session_state:
        st.warning("請先完成文字修正步驟。")
    else:
        st.subheader("🧩 漫畫翻譯參考資料輸入欄")

        # 三大欄位：背景、術語、方針（角色總覽已移除）
        input_keys = ["background_style", "terminology", "translation_policy"]

        # —— 模板們 ——
        background_template = """1. 故事發生在哪個年代？（例如：昭和50年代、1970年代、未來世界）
答：

2. 故事場景是什麼地方？（例如：東京郊區、小學生的家、學校）
答：

3. 這部作品的氣氛是什麼？（例如：搞笑、溫馨感人、冒險）
答：

4. 主要讀者對象是誰？（例如：小學生、青少年、全年齡）
答：
"""

        character_template = """1. 這腳色本身是甚麼樣的性個？（例如：外向活潑）
答：

2. 在本段故事中，這個角色經歷甚麼事情?
答：

3. 承上題，對此他有哪些情緒變化？（例如：生氣、害怕、感動）
答：

4. 語尾語氣、表情、動作等是否需要特別注意？(例如：特殊的語癖)
答：
"""

        terminology_template = """1. 這段故事中出現了哪些特殊道具或用語？（例如：任意門、竹蜻蜓、記憶麵包）
答：

2. 這些用語在原文是什麼？是片假名、漢字、還是平假名？
答：

3. 如何翻譯這些用語最自然？（例如：直譯、意譯、保留原名加註）
答：

4. 該用語在台灣讀者之間有無普遍認知？是否有既定譯名？
答：
"""

        policy_template = """1. 你希望翻譯的整體語氣是什麼？（例如：輕鬆幽默、溫柔體貼、嚴肅冷靜）
答：

2. 面對目標讀者（例如小學生），用詞上有哪些需要特別注意的地方？
答：

3. 是希望直譯保留原意？還是意譯更自然？
答：

4. 是否有特別需要避免的語氣、詞彙或文化誤解？
答：
"""

        examples = {
            "background_style": "本作背景設定於1970年代的日本，屬於昭和時代，語言風格貼近當代小學生使用的日常口語，故事風格輕鬆幽默且富教育意義。",
            "terminology": "時光機（タイムマシン）：以書桌抽屜為出入口的未來道具。",
            "translation_policy": "以符合角色語氣的自然台灣華語翻譯，保留漫畫幽默感並注意時代背景與年齡語感。"
        }

        # ===== ① 作品背景與風格 =====
        st.markdown("### 作品背景與風格")
        st.caption("請描述故事的時代、文化風格與敘事特色。")
        with st.expander("📌 參考範例（點擊展開）"):
            st.code(examples["background_style"], language="markdown")
        st.text_area(
            "輸入內容：",
            key="background_style",
            height=200,
            value=background_template,
        )

        # ===== ② 角色別參考輸入（移到背景下方）=====
        if "characters" in st.session_state and st.session_state["characters"]:
            st.markdown("### 角色性格・劇中經歷")
            st.caption("以下欄位由第一階段已註冊的角色自動生成；顯示順序＝註冊順序。")
            for idx, c in enumerate(st.session_state["characters"]):
                char_key = f"character_traits_{idx}"
                if char_key not in st.session_state:
                    st.session_state[char_key] = character_template  # 只在第一次灌入預設
                with st.expander(f"🧑‍🎨 {c.get('name','角色')} 的角色補充（點此展開）", expanded=False):
                    st.text_area("輸入內容：", key=char_key, height=200)

        # ===== ③ 專業術語／用語習慣 =====
        st.markdown("### 專業術語／用語習慣")
        st.caption("請列出出現的特殊道具或用語，以及使用建議。")
        with st.expander("📌 參考範例（點擊展開）"):
            st.code(examples["terminology"], language="markdown")
        st.text_area(
            "輸入內容：",
            key="terminology",
            height=200,
            value=terminology_template,
        )

        # ===== ④ 翻譯方針 =====
        st.markdown("### 翻譯方針")
        st.caption("請說明翻譯時應注意的語氣、對象、整體風格等原則。")
        with st.expander("📌 參考範例（點擊展開）"):
            st.code(examples["translation_policy"], language="markdown")
        st.text_area(
            "輸入內容：",
            key="translation_policy",
            height=200,
            value=policy_template,
        )

        # ===== 產生提示內容 =====
        if st.button("💾 儲存並產生提示內容"):
            # 收集角色別補充段落
            per_char_sections = ""
            if "characters" in st.session_state and st.session_state["characters"]:
                blocks = []
                for idx, c in enumerate(st.session_state["characters"]):
                    char_key = f"character_traits_{idx}"
                    content = st.session_state.get(char_key, "").strip()
                    blocks.append(f"【{c.get('name','角色')} 角色資訊】\n{content if content else '（未填寫）'}")
                per_char_sections = "\n\n".join(blocks)

            combined_prompt = f"""
請根據下列參考資料，將提供的日文漫畫對白翻譯為自然、符合角色語氣的台灣繁體中文。請特別注意情感、語氣、時代背景、人物性格與專業用語的使用。

【作品背景與風格】\n{st.session_state['background_style']}\n\n
【專業術語／用語習慣】\n{st.session_state['terminology']}\n\n
【翻譯方針】\n{st.session_state['translation_policy']}\n\n"""

            if per_char_sections:
                combined_prompt += f"【角色別補充】\n{per_char_sections}\n\n"

            combined_prompt += f"【原始對白】\n{st.session_state['corrected_text']}"

            st.session_state["combined_prompt"] = combined_prompt
            st.session_state["prompt_input"] = combined_prompt
            st.success("內容已儲存並整合。")

        # ===== 自訂提示與翻譯 =====
        st.subheader("🔧 自訂提示內容")
        st.session_state["prompt_input"] = st.text_area(
            "提示內容輸入：",
            value=st.session_state.get("prompt_input", ""),
            height=300
        )

        if st.button("💾 儲存提示內容"):
            st.session_state["prompt_template"] = st.session_state["prompt_input"]
            st.success("提示內容已儲存")

        if st.button("執行翻譯"):
            # ✅ 安全 fallback，避免 prompt_template 未設定時 KeyError
            prompt_for_translation = (
                st.session_state.get("prompt_template")
                or st.session_state.get("combined_prompt")
                or st.session_state.get("prompt_input")
            )
            if not prompt_for_translation:
                st.warning("請先產生或儲存提示內容，再執行翻譯。")
            else:
                with st.spinner("翻譯中... 使用 GPT-4o"):
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "你是一位優秀的日文漫畫翻譯專家，翻譯成自然且富含角色語氣的台灣繁體中文。"},
                            {"role": "user", "content": prompt_for_translation}
                        ],
                        temperature=temperature,
                        top_p=0.95,
                    )
                    st.session_state["translation"] = response.choices[0].message.content.strip()

        if "translation" in st.session_state:
            st.text_area("翻譯結果", st.session_state["translation"], height=300)

