import streamlit as st
# ✅ 一定要放在所有 st. 呼叫之前
st.set_page_config(page_title="翻譯支援測試app", layout="wide")

from openai import OpenAI
from PIL import Image
import io
import base64
import re
import requests
import urllib.parse
from supabase import create_client

# （可選）開啟除錯資訊
SHOW_DEBUG = False

# ===========================================
# 初始化 Supabase（使用 cache_resource，避免重複連線）
# ===========================================
@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["anon_key"]
    )

sb = get_supabase()

# 啟動時做輕量健康檢查
try:
    sb.table("translation_logs").select("id").limit(1).execute()
    st.write("✅ Supabase 連線測試成功")
except Exception as e:
    st.warning(f"⚠️ Supabase 連線檢查失敗：{e}")

# ===========================================
# OpenAI 初始化
# ===========================================
client = OpenAI(api_key=st.secrets["openai"]["api_key"])

# ===========================================
# 🔐 混合登入（Authorization Code + PKCE；同分頁導轉；同時保留 pv 備援）
# ===========================================
def _set_sb_auth_with_token(token: str):
    """讓後續對資料表的操作帶有「登入者身分」（RLS 才會生效）"""
    try:
        sb.postgrest.auth(token)
    except Exception:
        pass

def _user_from_auth(auth_user: dict, access_token: str, provider: str) -> dict:
    # auth_user 可能是 Supabase 回傳的 user JSON 或 model_dump() 結果
    user_meta = auth_user.get("user_metadata") or auth_user.get("raw_user_meta_data") or {}
    full_name = user_meta.get("full_name") or auth_user.get("email") or "Guest"
    return {
        "id": auth_user.get("id"),
        "email": auth_user.get("email"),
        "full_name": full_name,
        "provider": provider,
        "access_token": access_token,
    }

def _b64url_encode(b: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def _sha256_b64url(text: str) -> str:
    import hashlib
    return _b64url_encode(hashlib.sha256(text.encode()).digest())

def _make_pkce_pair():
    import os
    verifier = _b64url_encode(os.urandom(32))
    challenge = _sha256_b64url(verifier)
    return verifier, challenge

def _exchange_code_for_session(auth_code: str, code_verifier: str) -> dict:
    """
    用 authorization code + code_verifier 向 Supabase 換 access_token。
    正確的 payload key 必須是 "code" 與 "code_verifier"。
    """
    url = f"{st.secrets['supabase']['url']}/auth/v1/token?grant_type=authorization_code"
    headers = {
        "apikey": st.secrets["supabase"]["anon_key"],
        # Authorization header 可加可不加，但加上更保險
        "Authorization": f"Bearer {st.secrets['supabase']['anon_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "code": auth_code,               # ← 關鍵：不是 auth_code，而是 code
        "code_verifier": code_verifier,  # ← 關鍵：必須是 code_verifier
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    if r.status_code != 200:
        # 把後端回覆一起拋出，之後好除錯
        raise Exception(f"{r.status_code} {r.text}")
    return r.json()


def auth_gate(require_login: bool = True):
    """
    門神（必須放在任何 UI 之前）：
      - Google 登入（Authorization Code + PKCE；同分頁；不自帶 state）
      - Email/密碼 註冊＋登入
      - （可選）一鍵登入 Magic Link：如需可再開
    """
    qp = st.query_params

    # A) OAuth 回呼：?code=...（Supabase 成功回來）；同時也可能帶著我們在 redirect_to 附加的 ?pv=...
    if "code" in qp:
        code = qp.get("code")
        # 先取 session_state 的 verifier；若瀏覽器導轉導致 session 遺失，退而求其次用 pv 備援
        verifier = st.session_state.get("pkce_verifier") or qp.get("pv", "")
        if SHOW_DEBUG:
            with st.expander("DEBUG", expanded=True):
                st.write("query_params:", dict(qp))
                st.write("session has pkce_verifier:", "pkce_verifier" in st.session_state)
                st.write("using verifier length:", len(verifier or ""))

        if not verifier:
            st.error("OAuth 回來缺少 PKCE verifier（pv），請重試（建議使用無痕視窗並允許第三方 Cookie）。")
        else:
            try:
                data = _exchange_code_for_session(code, verifier)
                access_token = data.get("access_token")
                user_json = data.get("user") or {}
                if not access_token:
                    st.error(f"交換 access_token 失敗：{data}")
                else:
                    st.session_state["user"] = _user_from_auth(user_json, access_token, provider="google")
                    _set_sb_auth_with_token(access_token)
                    # 清掉 query（避免外洩）
                    st.query_params.clear()
                    st.rerun()
            except Exception as e:
                st.error(f"交換 access_token 發生錯誤：{e}")

    # B) OAuth 被 Supabase 擋掉（例如 invalid state）
    elif "error" in qp:
        st.warning(f"OAuth 回應：{qp.get('error_description', qp.get('error'))}")
        if SHOW_DEBUG:
            with st.expander("DEBUG", expanded=True):
                st.write("query_params:", dict(qp))
        st.query_params.clear()

    # C) 尚未登入 → 顯示登入 UI
    if "user" not in st.session_state:
        st.markdown("### 🔐 請先登入")

        # 產生 PKCE
        verifier, challenge = _make_pkce_pair()
        # 放到 session_state（首選）
        st.session_state["pkce_verifier"] = verifier

        # 你的公開網址（與 Supabase Site URL / Redirect URLs 完全一致，包含最後的 /）
        redirect_url = (st.secrets.get("app", {}) or {}).get("redirect_url", "http://localhost:8501/")
        if not redirect_url.endswith("/"):
            redirect_url += "/"

        # 再把 verifier 夾在 redirect_to 的 query（備援）
        sep = "&" if ("?" in redirect_url) else "?"
        redirect_with_pv = f"{redirect_url}{sep}pv={urllib.parse.quote(verifier)}"

        # 明確指定 PKCE 流程；不自帶 state（讓 Supabase 自己管）
        login_url = (
            f"{st.secrets['supabase']['url']}/auth/v1/authorize"
            f"?provider=google"
            f"&flow_type=pkce"
            f"&response_type=code"
            f"&code_challenge={urllib.parse.quote(challenge)}"
            f"&code_challenge_method=S256"
            f"&redirect_to={urllib.parse.quote(redirect_with_pv)}"
        )

        # ✅ 用同一分頁導轉（避免新分頁導致 cookie/state 丟失）
        st.link_button("使用 Google 登入", login_url)

        with st.expander("或使用 Email / 密碼登入（無需 Google）", expanded=False):
            st.caption("第一次使用可直接註冊；成功後自動登入。")
            colL, colR = st.columns(2)

            # ---- 註冊 ----
            with colL:
                st.markdown("**註冊新帳號**")
                reg_email = st.text_input("Email（用來登入）", key="reg_email")
                reg_pw = st.text_input("密碼（至少 6 字元）", type="password", key="reg_pw")
                reg_pw2 = st.text_input("再次輸入密碼", type="password", key="reg_pw2")
                if st.button("註冊並登入", key="btn_register"):
                    if not re.match(r"[^@]+@[^@]+\.[^@]+", reg_email or ""):
                        st.warning("Email 格式不正確。")
                    elif not reg_pw or len(reg_pw) < 6:
                        st.warning("密碼至少 6 個字元。")
                    elif reg_pw != reg_pw2:
                        st.warning("兩次輸入的密碼不一致。")
                    else:
                        try:
                            res = sb.auth.sign_up({"email": reg_email, "password": reg_pw})
                            session = getattr(res, "session", None)
                            user = getattr(res, "user", None)
                            if user and session:
                                token = session.access_token
                                _set_sb_auth_with_token(token)
                                st.session_state["user"] = _user_from_auth(user.model_dump(), token, provider="email")
                                st.success(f"註冊並登入成功：{st.session_state['user']['email']}")
                                st.rerun()
                            else:
                                st.info("註冊成功，請前往 Email 收信完成驗證後再登入。")
                        except Exception as e:
                            st.error(f"註冊失敗：{e}")

            # ---- 登入 ----
            with colR:
                st.markdown("**已註冊直接登入**")
                login_email = st.text_input("Email", key="login_email")
                login_pw = st.text_input("密碼", type="password", key="login_pw")
                if st.button("登入", key="btn_login"):
                    try:
                        res = sb.auth.sign_in_with_password({"email": login_email, "password": login_pw})
                        session = getattr(res, "session", None)
                        user = getattr(res, "user", None)
                        if not (session and user):
                            st.error("登入失敗，請檢查帳密或是否已完成信箱驗證。")
                        else:
                            token = session.access_token
                            _set_sb_auth_with_token(token)
                            st.session_state["user"] = _user_from_auth(user.model_dump(), token, provider="email")
                            st.success(f"登入成功：{st.session_state['user']['email']}")
                            st.rerun()
                    except Exception as e:
                        st.error(f"登入失敗：{e}")

        if require_login:
            st.stop()
        else:
            return None

    # D) 已登入 → 顯示狀態 + 登出
    st.info(f"目前登入：{st.session_state['user']['full_name']}（{st.session_state['user']['email']}）")
    if st.button("🔓 登出"):
        try:
            sb.auth.sign_out()
            sb.postgrest.auth(None)
        except Exception:
            pass
        st.session_state.pop("user", None)
        st.rerun()

    return st.session_state["user"]

# ✅ 啟用門神（未登入就無法操作）
user = auth_gate(require_login=True)

# ===========================================
# 字型與 UI 設定
# ===========================================
st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC&display=swap" rel="stylesheet">
    <style>
        html, body, [class*="css"]  {
            font-family: 'Noto Sans TC', 'Microsoft JhengHei', 'PingFang TC', sans-serif;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📘 漫畫翻譯支援工具 - 測試版")

# ===========================================
# Sidebar
# ===========================================
st.sidebar.header("操作選單")
menu = st.sidebar.radio("請選擇操作步驟：", ["上傳圖片並辨識文字（OCR）", "修正辨識文字", "輸入提示並翻譯"])

temperature = st.sidebar.slider(
    "翻譯的創造性（temperature）",
    min_value=0.0,
    max_value=1.0,
    value=0.95,
    step=0.05,
    help="值越高越自由、口語更活。"
)

# ===========================================
# Helper：取得當前使用者 ID / Email
# ===========================================
def get_user_id():
    u = st.session_state.get("user") or {}
    return u.get("id") or "guest"

def get_user_email():
    u = st.session_state.get("user") or {}
    return u.get("email") or ""

# ======================================================
# 🟢 ステップ1：登場人物登録（穩定版：用版本號重置 key）
# ======================================================
if menu == "上傳圖片並辨識文字（OCR）":
    st.subheader("👥 請登錄登場人物")
    st.markdown("請依序輸入角色圖片、名稱、性格後再執行 OCR")

    # ---- 初始化版本號（避免用旗標來回切換）----
    if "char_uploader_ver" not in st.session_state:
        st.session_state["char_uploader_ver"] = 0
    if "char_fields_ver" not in st.session_state:
        st.session_state["char_fields_ver"] = 0

    # 依版本號產生**穩定且唯一**的 widget key
    upload_key = f"char_img_{st.session_state['char_uploader_ver']}"
    name_key   = f"char_name_{st.session_state['char_fields_ver']}"
    desc_key   = f"char_desc_{st.session_state['char_fields_ver']}"

    char_img = st.file_uploader("登場人物圖片（一次一位）", type=["jpg", "jpeg", "png"], key=upload_key)
    char_name = st.text_input("名稱（例如：大雄）", key=name_key)
    char_desc = st.text_area("性格或特徵（例如：愛哭、懶散）", key=desc_key)

    # ✅ 登錄按鈕
    if st.button("➕ 登錄"):
        if char_img and char_name:
            img_bytes = char_img.read()
            st.session_state["characters"] = st.session_state.get("characters", [])
            st.session_state["characters"].append({
                "image_bytes": img_bytes,
                "name": char_name,
                "description": char_desc
            })
            st.success(f"已註冊角色：{char_name}")
            st.session_state["char_uploader_ver"] += 1
            st.session_state["char_fields_ver"] += 1
            st.rerun()
        else:
            st.warning("圖片與名稱為必填欄位")

    # ✅ 已註冊角色清單
    if "characters" in st.session_state and st.session_state["characters"]:
        st.markdown("#### ✅ 已註冊角色：")
        for i, char in enumerate(st.session_state["characters"]):
            col1, col2, col3 = st.columns([0.3, 0.5, 0.2])

            with col1:
                try:
                    st.image(Image.open(io.BytesIO(char["image_bytes"])), caption=None, width=100)
                except Exception:
                    st.image(char.get("image_bytes", None), caption=None, width=100)

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
    # 🟢 主圖上傳（OCR 用）
    # ======================================================
    st.markdown("---")
    uploaded_file = st.file_uploader("📄 上傳漫畫圖片（JPEG/PNG）", type=["jpg", "jpeg", "png"], key="main_img")

    if uploaded_file:
        image = Image.open(uploaded_file)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        st.session_state["image_base64"] = img_base64

        # 清掉上一輪的狀態
        st.session_state.pop("log_id", None)
        st.session_state.pop("combined_prompt", None)
        st.session_state.pop("prompt_template", None)
        st.session_state.pop("prompt_input", None)
        st.session_state.pop("translation", None)
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
你是一位熟悉日本漫畫對話場景的台詞辨識助手，請從下方圖片中，**只提取漫畫「對話框（吹き出し）」中的日文台詞**。

🧩 規則：
1. 依漫畫閱讀順序：整頁 **從右到左，由上到下** 排序，對話框也照此順序。
2. 每句台詞前標示發言角色，角色名稱必須從下方列表中選擇：
   {character_context if character_context else "（沒有角色名單，若無法判斷就寫『不明』）"}
3. 不得使用未提供的名字或外語名（如 Nobita、のび太）。
4. 忽略旁白、效果音、標題、註解或任何非對話框文字。
5. 無法辨識的文字請保留空格或用「□」標示，不要自行補完。

📌 輸出格式（每行一筆）：
角色名稱：台詞
"""
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": prompt_text},
                            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_url}}]}
                        ]
                    )
                    st.session_state["ocr_text"] = response.choices[0].message.content.strip()
                    st.session_state["corrected_text_saved"] = False
                    st.session_state["ocr_version"] = st.session_state.get("ocr_version", 0) + 1
                except Exception as e:
                    st.error(f"OCR 失敗：{e}")

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

            # 僅在 OCR「剛更新」時初始化一次，不覆寫使用者的修正
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

        # ---------- 工具函式（只定義，不會自動寫庫） ----------
        def _get_combined() -> str:
            return (
                st.session_state.get("combined_prompt")
                or st.session_state.get("prompt_template")
                or st.session_state.get("prompt_input")
                or ""
            ).strip()

        def _create_log_only_here(sb_client, combined_text: str):
            """
            僅在沒有 log_id 且 combined_text 有內容時，insert 新列
            """
            if st.session_state.get("log_id") or not combined_text:
                return st.session_state.get("log_id")
            res = (
                sb_client.table("translation_logs")
                .insert({
                    "user_id": get_user_id(),           # 寫入真正的 auth.users.id
                    "combined_prompt": combined_text,
                    "output_text": None,
                })
                .execute()
            )
            new_id = res.data[0]["id"]
            st.session_state["log_id"] = new_id
            st.toast("💾 已建立輸入紀錄（等待譯文）", icon="💾")
            return new_id

        def _update_prompt_if_possible(sb_client):
            log_id = st.session_state.get("log_id")
            combined = _get_combined()
            if not (log_id and combined):
                return False
            sb_client.table("translation_logs").update(
                {"combined_prompt": combined}
            ).eq("id", log_id).execute()
            return True

        def _update_output_if_possible(sb_client):
            log_id = st.session_state.get("log_id")
            output = (st.session_state.get("translation") or "").strip()
            if not (log_id and output):
                return False
            sb_client.table("translation_logs").update(
                {"output_text": output}
            ).eq("id", log_id).execute()
            return True
        # ---------- 工具函式結束 ----------

        # 三大欄位：背景、術語、方針
        background_template = """1. 故事發生在哪個年代？（例如：昭和50年代、1970年代、未來世界）
答：

2. 故事場景是什麼地方？（例如：東京郊區、小學生的家、學校）
答：

3. 這部作品的整體的氛圍是什麼？（例如：搞笑、溫馨感人、冒險）
答：

4. 主要讀者對象是誰？（例如：小學生、青少年、全年齡）
答：
"""

        character_template = """1. 這角色本身是甚麼樣的性個？（例如：外向活潑）
答：

2. 在本段故事中，這個角色經歷了甚麼樣的事情?
答：

3. 承上題，對此他有哪些情緒變化？（例如：生氣、害怕、感動）
答：

4. 語尾語氣、表情、動作等是否需要特別注意？(例如：武士獨有的第一人稱『在下』等等)
答：
"""

        terminology_template = """1. 這段故事中出現了哪些特殊道具或用語？（例如：任意門、竹蜻蜓、記憶麵包）
答：

2. 這些用語在原文是什麼？是片假名、漢字、還是平假名？
答：

3. 如何翻譯這些用語最自然？（例如：直譯、意譯、抑或是有特別的譯法）
答：

4. 該用語在台灣讀者之間有無普遍認知？是否有既定譯名？
答：
"""

        policy_template = """1. 你希望翻譯的整體語氣是什麼？（例如：輕鬆幽默、溫柔體貼、嚴肅冷靜）
答：

2. 面對目標讀者（例如小學生），用詞上有哪些需要特別注意的地方？
答：

3. 是希望以直譯的方式盡可能地保留原文意義？還是以意譯的方式翻譯以確保譯文閱讀起來更自然？
答：

4. 是否有特別需要避免的語氣、詞彙或文化誤解？
答：
"""

        examples = {
            "background_style": "本作背景設定於1970年代的日本，屬於昭和時代，語言風格貼近當代小學生使用的日常口語，故事風格輕鬆幽默且富教育意義。",
            "terminology": "時光機（タイムマシン）：以書桌抽屜為出入口的未來道具。",
            "translation_policy": "以符合角色語氣的自然台灣華語翻譯，保留漫畫幽默感並注意時代背景與年齡語感。"
        }

        st.markdown("### 作品背景與風格")
        st.caption("請描述故事的時代・舞台、文化風格與敘事特色。")
        with st.expander("📌 參考範例（點擊展開）"):
            st.code(examples["background_style"], language="markdown")
        st.text_area("輸入內容：", key="background_style", height=200, value=background_template)

        if "characters" in st.session_state and st.session_state["characters"]:
            st.markdown("### 角色個性・劇中經歷")
            st.caption("以下欄位會根據一開始註冊的角色自動生成；顯示順序＝註冊順序。")
            for idx, c in enumerate(st.session_state["characters"]):
                char_key = f"character_traits_{idx}"
                if char_key not in st.session_state:
                    st.session_state[char_key] = character_template
                with st.expander(f"🧑‍🎨 {c.get('name','角色')} 的角色補充（點此展開）", expanded=False):
                    st.text_area("輸入內容：", key=char_key, height=200)

        st.markdown("### 該作品的特殊用語／道具")
        st.caption("請列出劇中出現的特殊道具或用語，以及翻譯建議。")
        with st.expander("📌 參考範例（點擊展開）"):
            st.code(examples["terminology"], language="markdown")
        st.text_area("輸入內容：", key="terminology", height=200, value=terminology_template)

        st.markdown("### 翻譯方針")
        st.caption("請說明翻譯時應注意的語氣、對象、整體風格等原則。")
        with st.expander("📌 參考範例（點擊展開）"):
            st.code(examples["translation_policy"], language="markdown")
        st.text_area("輸入內容：", key="translation_policy", height=200, value=policy_template)

        # ===== 產生提示內容（唯一可建新 ID 的地方） =====
        if st.button("💾 儲存並產生提示內容"):
            # 角色別補充段落
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

            try:
                if not st.session_state.get("log_id") and combined_prompt.strip():
                    _create_log_only_here(sb, combined_prompt)
                else:
                    if _update_prompt_if_possible(sb):
                        st.toast("✅ 已更新提示內容（同一筆）", icon="💾")
            except Exception as e:
                st.error(f"建立/更新輸入紀錄失敗：{e}")

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
            try:
                if st.session_state.get("log_id"):
                    if _update_prompt_if_possible(sb):
                        st.toast("✅ 已更新提示內容（同一筆）", icon="💾")
                else:
                    st.info("尚未建立資料列；請先按「儲存並產生提示內容」。")
            except Exception as e:
                st.error(f"更新提示內容失敗：{e}")

        if st.button("執行翻譯"):
            prompt_for_translation = (
                st.session_state.get("prompt_template")
                or st.session_state.get("combined_prompt")
                or st.session_state.get("prompt_input")
            )
            if not prompt_for_translation:
                st.warning("請先產生或儲存提示內容，再執行翻譯。")
            else:
                with st.spinner("翻譯中... 使用 GPT-4o"):
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages = [
                                {
                                    "role": "system",
                                    "content": (
                                        "你是專業的日文漫畫→台灣繁體中文譯者。請嚴格遵守：\n"
                                        "1) 只輸出最終譯文，不要重複或引用提示內容，也不要加任何解釋、標題、前後綴。\n"
                                        "2) 逐行翻譯並保留輸入的行序與說話者標記（若存在例如「大雄：…」）。\n"
                                        "3) 角色語氣要符合提供的角色說明；若角色說明為空或缺，保持自然中性語氣，不自行補完人物設定。\n"
                                        "4) 參考資料中如出現空白、模板佔位（例如「答：」但沒有內容），一律忽略，不得自行填寫或推測。\n"
                                        "5) 只翻譯對話框內文字；不要翻譯未包含在輸入中的旁白、效果音或額外情節。\n"
                                        "6) 優先產生自然、地道的台灣華語口吻；避免直譯腔與不自然詞彙。標點符號用台灣常見用法。\n"
                                        "7) 專有名詞與約定俗成譯名（若於提示中提供）請一致；未提供時採通行直譯或自然意譯，但不要加入譯註或括號說明。\n"
                                        "8) 如遇無法辨認或缺字，保留該處為「…」，不要臆測補寫。\n"
                                        "【輸出格式要求】純文字、只有譯文本身；若輸入是多行，就輸出等量多行；不要出現任何多餘符號或區段標題。"
                                    ),
                                },
                                {"role": "user", "content": prompt_for_translation}
                            ],
                            temperature=temperature,
                            top_p=0.95,
                        )
                        st.session_state["translation"] = response.choices[0].message.content.strip()
                    except Exception as e:
                        st.error(f"翻譯失敗：{e}")
                        st.session_state.pop("translation", None)

                try:
                    if st.session_state.get("log_id"):
                        if _update_output_if_possible(sb):
                            st.toast("✅ 已儲存譯文到同一筆紀錄", icon="💾")
                        else:
                            st.toast("⚠️ 沒拿到譯文或缺少內容，已跳過儲存。", icon="⚠️")
                    else:
                        st.info("已產生譯文，但尚未建立資料列；請先按「儲存並產生提示內容」。")
                except Exception as e:
                    st.error(f"儲存譯文失敗：{e}")

        if "translation" in st.session_state:
            st.text_area("翻譯結果", st.session_state["translation"], height=300)
