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
    "翻訳の創造性（temperature）", 
    min_value=0.0, 
    max_value=1.0, 
    value=0.95,  # 初期値は今使っている0.95に合わせています
    step=0.05,
    help="値が高いほど自由な翻訳になります（例：口調・表現が多様）"
)

# ステップ1：登場人物登録
if menu == "上傳圖片並辨識文字（OCR）":
    st.subheader("👥 請登錄登場人物")
    st.markdown("請依序輸入角色圖片、名稱、性格後再執行 OCR")

    char_img = st.file_uploader("登場人物圖片（一次一位）", type=["jpg", "jpeg", "png"], key="char_img")
    char_name = st.text_input("名稱（例如：大雄）", key="char_name")
    char_desc = st.text_area("性格或特徵（例如：愛哭、懶散）", key="char_desc")

    if st.button("➕ 登錄"):
        if char_img and char_name:
            st.session_state["characters"] = st.session_state.get("characters", [])
            st.session_state["characters"].append({
                "image": char_img,
                "name": char_name,
                "description": char_desc
            })
            st.success(f"已註冊角色：{char_name}")
        else:
            st.warning("圖片與名稱為必填欄位")

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

    st.markdown("---")
    uploaded_file = st.file_uploader("📄 上傳漫畫圖片（JPEG/PNG）", type=["jpg", "jpeg", "png"], key="main_img")

    if uploaded_file:
        image = Image.open(uploaded_file)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        st.session_state["image_base64"] = img_base64
        st.session_state.pop("ocr_text", None)
        st.session_state["corrected_text_saved"] = False  # 強制標記為未儲存

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

                # 新增：角色名稱限制
                character_names = [c['name'] for c in st.session_state.get("characters", []) if c['name']]
                character_name_list = "、".join(character_names)
                name_restriction = f"以下是本圖片中登場的角色姓名，請僅從中選擇發話者姓名：{character_name_list}。"

                char_descriptions = "\n".join([
                    f"・{c['name']}：{c['description']}" for c in st.session_state.get("characters", [])
                ])
                character_context = f"以下角色資訊可供參考：\n{char_descriptions}" if char_descriptions else ""

                prompt_text = prompt_text = f"""
你是一位熟悉日本漫畫對話場景的台詞辨識助手，請從下方圖片中，**只提取出位於漫畫「對話框（吹き出し）」中的日文對白**。

🧩 規則如下：

1. 必須依據漫畫畫面上**實際的空間位置順序（從右到左、從上到下）**來排列對話。
2. 每一句對話必須標示出發言角色名稱，角色名稱需**嚴格依照我提供的角色資訊**（如下）。
3. 不得使用其他推測角色名或外語名，例如 Nobita 或 のび太。
4. 背景文字、旁白、效果音都請略過不處理。
5. 若文字辨識不清，請根據上下文自然補全。

📋 以下是角色資訊（由使用者上傳圖片與命名）：
{character_context}

📌 輸出格式（每行一條）：
角色名稱：台詞內容

範例：
大雄：我今天才不寫作業！  
哆啦A夢：你又來了……

請開始執行。
"""
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": prompt_text},
                        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_url}}]}
                    ]
                )
                ocr_text = response.choices[0].message.content.strip()
                st.session_state["ocr_text"] = ocr_text
                st.session_state["corrected_text_saved"] = False  # OCR 結果更新後需重新儲存

    if "ocr_text" in st.session_state:
        st.text_area("已辨識文字（可於下一步修正）", st.session_state["ocr_text"], height=300)
        
# ステップ2：テキスト修正
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

            # ❶ 初回表示用テキストの決定
            if "corrected_text" not in st.session_state:
                st.session_state["corrected_text"] = st.session_state.get("ocr_text", "")

            # ❷ 新しいテキスト入力欄（keyを外して常に更新）
            new_text = st.text_area("請修正辨識結果（可換行）", value=st.session_state["corrected_text"], height=500)

            # ❸ 保存ボタンで状態更新
            if st.button("💾 儲存修正內容"):
                st.session_state["corrected_text"] = new_text
                st.success("內容已儲存，可進一步進行翻譯。")

# ステップ3：翻譯處理
elif menu == "輸入提示並翻譯":
    if "corrected_text" not in st.session_state:
        st.warning("請先完成文字修正步驟。")
    else:
        st.subheader("🧩 漫畫翻譯參考資料輸入欄")

        input_keys = ["background_style", "character_traits", "terminology", "translation_policy"]

        examples = {
            "background_style": "本作背景設定於1970年代的日本，屬於昭和時代，語言風格貼近當代小學生使用的日常口語，故事風格輕鬆幽默且富教育意義。",
            "character_traits": "大雄在故事中情緒波動大，從悠閒轉為震驚與憤怒；哆啦A夢則常帶笑臉，偶有慌張；世修對大雄有輕蔑語氣。",
            "terminology": "時光機（タイムマシン）：以書桌抽屜為出入口的未來道具。",
            "translation_policy": "以符合角色語氣的自然台灣華語翻譯，保留漫畫幽默感並注意時代背景與年齡語感。"
        }

        fields = [
            ("作品背景與風格", "請描述故事的時代、文化風格與敘事特色。"),
            ("角色性格（在這段故事中的情感變化）", "請概述主要角色在本段故事中的情緒與行為變化。"),
            ("專業術語／用語習慣", "請列出出現的特殊道具或用語，以及使用建議。"),
            ("翻譯方針", "請說明翻譯時應注意的語氣、對象、整體風格等原則。")
        ]

        for i, (label, guide) in enumerate(fields):
            st.markdown(f"### {label}")
            st.caption(guide)
            with st.expander("📌 參考範例（點擊展開）"):
                st.code(examples[input_keys[i]], language="markdown")
            st.text_area("輸入內容：", key=input_keys[i], height=150)

        if st.button("💾 儲存並產生提示內容"):
            combined_prompt = f"""
請根據下列參考資料，將提供的日文漫畫對白翻譯為自然、符合角色語氣的台灣繁體中文。請特別注意情感、語氣、時代背景、人物性格與專業用語的使用。

【作品背景與風格】\n{st.session_state[input_keys[0]]}\n\n
【角色性格（在這段故事中的情感變化）】\n{st.session_state[input_keys[1]]}\n\n
【專業術語／用語習慣】\n{st.session_state[input_keys[2]]}\n\n
【翻譯方針】\n{st.session_state[input_keys[3]]}\n\n
【原始對白】\n{st.session_state['corrected_text']}"""
            st.session_state["combined_prompt"] = combined_prompt
            st.session_state["prompt_input"] = combined_prompt
            st.success("內容已儲存並整合。")

        # ✅ 提示內容自訂與翻譯執行
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
            with st.spinner("翻譯中... 使用 GPT-4o"):
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "你是一位優秀的日文漫畫翻譯專家，翻譯成自然且富含角色語氣的台灣繁體中文。"},
                        {"role": "user", "content": st.session_state["prompt_template"]}
                    ],
                    temperature=temperature,
                    top_p=0.95,
                )
                st.session_state["translation"] = response.choices[0].message.content.strip()

        if "translation" in st.session_state:
            st.text_area("翻譯結果", st.session_state["translation"], height=300)
