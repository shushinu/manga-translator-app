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
# 🔤 語系字典（繁→簡已就位） + 取詞工具
# ===========================================
L = {
    "zh-TW": {
        # app / nav
        "app_title": "📘 漫畫翻譯支援工具 - 測試版",
        "ui_lang_label": "介面語言（登入後）",
        "sidebar_header": "操作選單",
        "menu_select_step": "請選擇操作步驟：",
        "menu_ocr": "上傳圖片並辨識文字（OCR）",
        "menu_fix": "修正辨識文字",
        "menu_xl8": "輸入提示並翻譯",
        "slider_temperature": "翻譯的創造性（temperature）",
        # auth / header
        "login_title": "📘 漫畫翻譯支援工具 - 測試版",
        "login_subtitle": "🔐 請先登入",
        "reg_page_title": "📘 漫畫翻譯支援工具 - 測試版",
        "reg_subtitle": "✨ 註冊新帳號",
        "email_for_login": "Email（用來登入）",
        "password_6": "密碼（至少 6 字元）",
        "password_6_again": "再次輸入密碼",
        "register_submit": "註冊並獲取認證郵件",
        "back_to_login": "← 回到登入",
        "create_account": "建立新帳號",
        "google_sign_in": "使用 Google 登入",
        "login_email": "Email",
        "login_password": "密碼",
        "login_button": "登入",
        "logged_in_as": "目前登入：",
        "logout": "🔓 登出",
        # step 1 OCR
        "step1_title": "👥 請登錄登場人物",
        "step1_desc": "請依序輸入角色圖片、名稱、性格後再執行 OCR",
        "char_img": "登場人物圖片（一次一位）",
        "char_name": "名稱（例如：大雄）",
        "char_desc": "性格或特徵（例如：愛哭、懶散）",
        "btn_register_char": "➕ 登錄",
        "registered_list": "#### ✅ 已註冊角色：",
        "btn_update": "🔁 更新",
        "btn_delete": "❌ 刪除",
        "upload_main": "📄 上傳漫畫圖片（JPEG/PNG）",
        "img_uploaded": "已上傳圖片",
        "btn_run_ocr": "📄 執行辨識",
        "ocr_result": "已辨識文字（可於下一步修正）",
        # step 2 FIX
        "fix_title": "🛠️ 修正辨識文字內容",
        "raw_img": "#### 📷 原始圖片",
        "edit_area": "#### ✏️ 修正區域",
        "fix_textarea_label": "請修正辨識結果（可換行）",
        "btn_save_correction": "💾 儲存修正內容",
        # step 3 PROMPT + TRANSLATE
        "xl8_panel_title": "🧩 漫畫翻譯參考資料輸入欄",
        "bg_style": "### 作品背景與風格",
        "bg_style_caption": "請描述故事的時代・舞台、文化風格與敘事特色。",
        "example_toggle": "📌 參考範例（點擊展開）",
        "char_traits": "### 角色個性・劇中經歷",
        "char_traits_caption": "以下欄位會根據一開始註冊的角色自動生成；顯示順序＝註冊順序。",
        "per_char_block_title": "🧑‍🎨 {name} 的角色補充（點此展開）",
        "terms_title": "### 該作品的特殊用語／道具",
        "terms_caption": "請列出劇中出現的特殊道具或用語，以及翻譯建議。",
        "policy_title": "### 翻譯方針",
        "policy_caption": "請說明翻譯時應注意的語氣、對象、整體風格等原則。",
        "btn_save_and_build_prompt": "💾 儲存並產生提示內容",
        "custom_prompt": "🔧 自訂提示內容",
        "prompt_input_label": "提示內容輸入：",
        "btn_save_prompt": "💾 儲存提示內容",
        "btn_run_translate": "執行翻譯",
        "translation_result": "翻譯結果",
        # examples / templates (TW)
        "ex_background_style": "本作背景設定於1970年代的日本，屬於昭和時代，語言風格貼近當代小學生使用的日常口語，故事風格輕鬆幽默且富教育意義。",
        "ex_terminology": "時光機（タイムマシン）：以書桌抽屜為出入口的未來道具。",
        "ex_policy": "以符合角色語氣的自然台灣華語翻譯，保留漫畫幽默感並注意時代背景與年齡語感。",
        "tpl_background": """1. 故事發生在哪個年代？（例如：昭和50年代、1970年代、未來世界）
答：

2. 故事場景是什麼地方？（例如：東京郊區、小學生的家、學校）
答：

3. 這部作品的整體的氛圍是什麼？（例如：搞笑、溫馨感人、冒險）
答：

4. 主要讀者對象是誰？（例如：小學生、青少年、全年齡）
答：
""",
        "tpl_character": """1. 這角色本身是甚麼樣的性個？（例如：外向活潑）
答：

2. 在本段故事中，這個角色經歷了甚麼樣的事情?
答：

3. 承上題，對此他有哪些情緒變化？（例如：生氣、害怕、感動）
答：

4. 語尾語氣、表情、動作等是否需要特別注意？(例如：武士獨有的第一人稱『在下』等等)
答：
""",
        "tpl_terms": """1. 這段故事中出現了哪些特殊道具或用語？（例如：任意門、竹蜻蜓、記憶麵包）
答：

2. 這些用語在原文是什麼？是片假名、漢字、還是平假名？
答：

3. 如何翻譯這些用語最自然？（例如：直譯、意譯、抑或是有特別的譯法）
答：

4. 該用語在台灣讀者之間有無普遍認知？是否有既定譯名？
答：
""",
        "tpl_policy": """1. 你希望翻譯的整體語氣是什麼？（例如：輕鬆幽默、溫柔體貼、嚴肅冷靜）
答：

2. 面對目標讀者（例如小學生），用詞上有哪些需要特別注意的地方？
答：

3. 是希望以直譯的方式盡可能地保留原文意義？還是以意譯的方式翻譯以確保譯文閱讀起來更自然？
答：

4. 是否有特別需要避免的語氣、詞彙或文化誤解？
答：
""",
        # misc
        "conn_ok": "✅ Supabase 連線測試成功",
        "conn_ng": "⚠️ Supabase 連線檢查失敗：",
        "btn_logout": "🔓 登出",
    },
    "zh-CN": {
        # app / nav
        "app_title": "📘 漫画翻译支援工具 - 测试版",
        "ui_lang_label": "界面语言（登录后）",
        "sidebar_header": "操作菜单",
        "menu_select_step": "请选择操作步骤：",
        "menu_ocr": "上传图片并识别文字（OCR）",
        "menu_fix": "修正识别文字",
        "menu_xl8": "输入提示并翻译",
        "slider_temperature": "翻译的创造性（temperature）",
        # auth / header
        "login_title": "📘 漫画翻译支援工具 - 测试版",
        "login_subtitle": "🔐 请先登录",
        "reg_page_title": "📘 漫画翻译支援工具 - 测试版",
        "reg_subtitle": "✨ 注册新账号",
        "email_for_login": "Email（用于登录）",
        "password_6": "密码（至少 6 个字符）",
        "password_6_again": "再次输入密码",
        "register_submit": "注册并获取验证邮件",
        "back_to_login": "← 返回登录",
        "create_account": "创建新账号",
        "google_sign_in": "使用 Google 登录",
        "login_email": "Email",
        "login_password": "密码",
        "login_button": "登录",
        "logged_in_as": "当前登录：",
        "logout": "🔓 登出",
        # step 1 OCR
        "step1_title": "👥 请登录登场人物",
        "step1_desc": "请依序输入角色图片、名称、性格后再执行 OCR",
        "char_img": "登场人物图片（一次一位）",
        "char_name": "名称（例如：大雄）",
        "char_desc": "性格或特征（例如：爱哭、懒散）",
        "btn_register_char": "➕ 登记",
        "registered_list": "#### ✅ 已登记角色：",
        "btn_update": "🔁 更新",
        "btn_delete": "❌ 删除",
        "upload_main": "📄 上传漫画图片（JPEG/PNG）",
        "img_uploaded": "已上传图片",
        "btn_run_ocr": "📄 执行识别",
        "ocr_result": "已识别文字（可在下一步修正）",
        # step 2 FIX
        "fix_title": "🛠️ 修正识别文字内容",
        "raw_img": "#### 📷 原始图片",
        "edit_area": "#### ✏️ 修正区域",
        "fix_textarea_label": "请修正识别结果（可换行）",
        "btn_save_correction": "💾 保存修正内容",
        # step 3 PROMPT + TRANSLATE
        "xl8_panel_title": "🧩 漫画翻译参考资料输入栏",
        "bg_style": "### 作品背景与风格",
        "bg_style_caption": "请描述故事的时代・舞台、文化风格与叙事特色。",
        "example_toggle": "📌 参考范例（点击展开）",
        "char_traits": "### 角色个性・剧中经历",
        "char_traits_caption": "以下栏位会根据一开始登记的角色自动生成；显示顺序＝登记顺序。",
        "per_char_block_title": "🧑‍🎨 {name} 的角色补充（点此展开）",
        "terms_title": "### 本作的特殊用语／道具",
        "terms_caption": "请列出剧中出现的特殊道具或用语，并给出翻译建议。",
        "policy_title": "### 翻译方针",
        "policy_caption": "请说明翻译时应注意的语气、对象、整体风格等原则。",
        "btn_save_and_build_prompt": "💾 保存并生成提示内容",
        "custom_prompt": "🔧 自订提示内容",
        "prompt_input_label": "提示内容输入：",
        "btn_save_prompt": "💾 保存提示内容",
        "btn_run_translate": "执行翻译",
        "translation_result": "翻译结果",
        # examples / templates (CN)
        "ex_background_style": "本作背景设定于1970年代的日本，属于昭和时代，语言风格贴近当代小学生使用的日常口语，故事风格轻松幽默且富教育意义。",
        "ex_terminology": "时光机（タイムマシン）：以书桌抽屉为出入口的未来道具。",
        "ex_policy": "以符合角色语气的自然中文（简体）翻译，保留漫画幽默感并注意时代背景与年龄语感。",
        "tpl_background": """1. 故事发生在哪个年代？（例如：昭和50年代、1970年代、未来世界）
答：

2. 故事场景是什么地方？（例如：东京郊区、小学生的家、学校）
答：

3. 本作品整体氛围是什么？（例如：搞笑、温馨感人、冒险）
答：

4. 主要读者对象是谁？（例如：小学生、青少年、全年龄）
答：
""",
        "tpl_character": """1. 这个角色本身是什么样的性格？（例如：外向活泼）
答：

2. 在本段故事中，这个角色经历了什么样的事情？
答：

3. 承上题，他在过程中有哪些情绪变化？（例如：生气、害怕、感动）
答：

4. 语尾语气、表情、动作等是否需要特别注意？（例如：武士独有的第一人称『在下』等）
答：
""",
        "tpl_terms": """1. 这段故事中出现了哪些特殊道具或用语？（例如：任意门、竹蜻蜓、记忆面包）
答：

2. 这些用语在原文是什么？是片假名、汉字，还是平假名？
答：

3. 如何翻译这些用语最自然？（例如：直译、意译、或是有特别的译法）
答：

4. 该用语在读者之间是否有既定译名或普遍认知？
答：
""",
        "tpl_policy": """1. 你希望翻译的整体语气是什么？（例如：轻松幽默、温柔体贴、严肃冷静）
答：

2. 面对目标读者（例如小学生），用词上有哪些需要特别注意的地方？
答：

3. 希望以直译尽量保留原意？还是以意译确保读起来自然？
答：

4. 是否有特别需要避免的语气、词汇或文化误解？
答：
""",
        # misc
        "conn_ok": "✅ Supabase 连接测试成功",
        "conn_ng": "⚠️ Supabase 连接检查失败：",
        "btn_logout": "🔓 登出",
    },
}

def T(key: str, **fmt):
    lang = st.session_state.get("lang", "zh-TW")
    base = L.get(lang, L["zh-TW"])
    s = base.get(key, L["zh-TW"].get(key, key))
    if fmt:
        try:
            return s.format(**fmt)
        except Exception:
            return s
    return s

# ===========================================
# 🔧 語言取得 / 保留工具 + 右上角切換
# ===========================================
def _get_lang():
    qp = dict(st.query_params)
    lang = qp.get("lang") or st.session_state.get("lang") or "zh-TW"
    if lang not in ("zh-TW", "zh-CN"):
        lang = "zh-TW"
    st.session_state["lang"] = lang
    return lang

def _append_query(url: str, extra: dict) -> str:
    """在既有 URL 上追加/覆蓋 query（用於 redirect_to、register 等）"""
    u = urllib.parse.urlparse(url)
    q = dict(urllib.parse.parse_qsl(u.query))
    for k, v in extra.items():
        if v is None:
            continue
        q[k] = v
    new_q = urllib.parse.urlencode(q)
    return urllib.parse.urlunparse(u._replace(query=new_q))

def _qp_remove(keys: list[str]):
    qp = dict(st.query_params)
    for k in keys:
        if k in qp:
            del qp[k]
    st.query_params = qp

LANG = _get_lang()

# 固定在右上角的語言切換（登入前後都看得到）
st.markdown(
    f"""
    <style>
      .lang-switch {{
        position: fixed; top: 8px; right: 16px; z-index: 9999;
      }}
      .lang-switch a {{
        margin-left: 8px; padding: 6px 10px; border-radius: 8px;
        border: 1px solid #444; background: #2b2f36; color: #fff; text-decoration: none;
        font-size: 14px;
      }}
      .lang-switch a.active {{
        background: #1f6feb;
      }}
    </style>
    <div class="lang-switch">
      <a href="?lang=zh-TW" class="{ 'active' if LANG=='zh-TW' else ''}">繁體</a>
      <a href="?lang=zh-CN" class="{ 'active' if LANG=='zh-CN' else ''}">简体</a>
    </div>
    """,
    unsafe_allow_html=True
)

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

# 🔸確保健康檢查用 anon key，避免吃到過期的使用者 JWT
sb.postgrest.auth(st.secrets["supabase"]["anon_key"])

# 啟動時做輕量健康檢查
try:
    sb.table("translation_logs").select("id").limit(1).execute()
    st.write(T("conn_ok"))
except Exception as e:
    st.warning(T("conn_ng") + f"{e}")

# ===========================================
# OpenAI 初始化
# ===========================================
client = OpenAI(api_key=st.secrets["openai"]["api_key"])

# ===========================================
# 🔐 混合登入（Authorization Code + PKCE）
# ===========================================
def _set_sb_auth_with_token(token: str):
    try:
        sb.postgrest.auth(token)
    except Exception:
        pass

def _fetch_supabase_user(access_token: str) -> dict:
    resp = requests.get(
        f"{st.secrets['supabase']['url']}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {access_token}",
            "apikey": st.secrets["supabase"]["anon_key"],
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()

def _user_from_auth(auth_user: dict, access_token: str, provider: str) -> dict:
    full_name = (auth_user.get("user_metadata") or {}).get("full_name") or auth_user.get("email", "Guest")
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

def _exchange_code_for_session(auth_code: str, code_verifier: str, redirect_uri: str | None = None) -> dict:
    url = f"{st.secrets['supabase']['url']}/auth/v1/token?grant_type=pkce"
    headers = {
        "apikey": st.secrets["supabase"]["anon_key"],
        "Authorization": f"Bearer {st.secrets['supabase']['anon_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "auth_code": auth_code,
        "code_verifier": code_verifier,
    }
    if redirect_uri:
        payload["redirect_uri"] = redirect_uri

    r = requests.post(url, headers=headers, json=payload, timeout=15)
    if r.status_code != 200:
        raise Exception(f"{r.status_code} {r.text}")
    return r.json()

def auth_gate(require_login: bool = True):
    """門神：Google（Code+PKCE）＋ Email/密碼。保留 lang，不清空整個 query。"""
    qp = st.query_params

    # A) OAuth 回來
    if "code" in qp:
        code = qp.get("code")
        verifier = qp.get("pv", "")
        redirect_url = (st.secrets.get("app", {}) or {}).get("redirect_url", "http://localhost:8501/")
        if not redirect_url.endswith("/"):
            redirect_url += "/"
        # 成功後保留 lang
        if not verifier:
            st.error("OAuth 回來缺少 verifier（pv），請重試。")
        else:
            try:
                data = _exchange_code_for_session(code, verifier, None)
                access_token = data.get("access_token")
                user_json = data.get("user") or {}
                if not access_token:
                    st.error(f"交換 access_token 失敗：{data}")
                else:
                    st.session_state["user"] = _user_from_auth(user_json, access_token, provider="google")
                    _set_sb_auth_with_token(access_token)
                    # 🔸僅移除 OAuth 暫時參數，保留 lang
                    _qp_remove(["code", "error", "error_description", "pv", "register"])
                    st.rerun()
            except Exception as e:
                st.error(f"交換 access_token 發生錯誤：{e}")

    elif "error" in qp:
        st.warning(f"OAuth 回應：{qp.get('error_description', qp.get('error'))}")
        _qp_remove(["error", "error_description"])

    # B) 未登入 → 登入／註冊 UI
    if "user" not in st.session_state:
        # 永遠先切回 anon key，避免沿用過期 JWT
        try:
            sb.postgrest.auth(st.secrets["supabase"]["anon_key"])
        except Exception:
            pass

        verifier, challenge = _make_pkce_pair()

        base_url = (st.secrets.get("app", {}) or {}).get("redirect_url", "http://localhost:8501/")
        if not base_url.endswith("/"):
            base_url += "/"

        # 註冊新分頁 & 將 lang 一起帶著走
        register_url = _append_query(base_url, {"register": "1", "lang": LANG})

        # 將 verifier + lang 塞到 redirect_to（PKCE 必要）
        redirect_with_pv = _append_query(base_url, {"pv": verifier, "lang": LANG})

        google_login_url = (
            f"{st.secrets['supabase']['url']}/auth/v1/authorize"
            f"?provider=google"
            f"&response_type=code"
            f"&code_challenge={urllib.parse.quote(challenge)}"
            f"&code_challenge_method=S256"
            f"&redirect_to={urllib.parse.quote(redirect_with_pv)}"
        )

        # ---- 若在「註冊頁（新分頁）」就只顯示註冊表單 ----
        if qp.get("register") == "1":
            st.title(T("reg_page_title"))
            st.markdown(f"### {T('reg_subtitle')}")
            with st.form("register_form", clear_on_submit=False):
                reg_email = st.text_input(T("email_for_login"), key="reg_email")
                reg_pw = st.text_input(T("password_6"), type="password", key="reg_pw")
                reg_pw2 = st.text_input(T("password_6_again"), type="password", key="reg_pw2")
                submit_reg = st.form_submit_button(T("register_submit"))
                if submit_reg:
                    import re as _re
                    if not _re.match(r"[^@]+@[^@]+\.[^@]+", reg_email or ""):
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

            st.markdown(
                f'<a href="{_append_query(base_url, {"lang": LANG})}" style="display:inline-block;margin-top:10px;">{T("back_to_login")}</a>',
                unsafe_allow_html=True
            )
            st.stop()  # 註冊頁不再往下渲染登入 UI

        # ---- 登入頁（預設）----
        st.title(T("login_title"))
        st.markdown(f"### {T('login_subtitle')}")

        # Email 登入
        with st.form("login_form", clear_on_submit=False):
            login_email = st.text_input(T("login_email"), key="login_email")
            login_pw = st.text_input(T("login_password"), type="password", key="login_pw")
            submit_login = st.form_submit_button(T("login_button"))
            if submit_login:
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

        # 同一行並排：「建立新帳號（開新分頁）」與「使用 Google 登入」
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                f'''
                <a href="{register_url}" target="_blank"
                   style="display:inline-block;width:100%;text-align:center;padding:10px 14px;border-radius:8px;
                          border:1px solid #6b7280;background:#2b2f36;color:#fff;text-decoration:none;">
                   {T("create_account")}
                </a>
                ''',
                unsafe_allow_html=True
            )
        with c2:
            st.markdown(
                f'''
                <a href="{google_login_url}"
                   style="display:inline-block;width:100%;text-align:center;padding:10px 14px;border-radius:8px;
                          border:1px solid #444;background:#1f6feb;color:#fff;text-decoration:none;">
                   {T("google_sign_in")}
                </a>
                ''',
                unsafe_allow_html=True
            )

        if require_login:
            st.stop()
        else:
            return None

    # C) 已登入 → 顯示狀態 + 登出
    st.info(f"{T('logged_in_as')}{st.session_state['user']['full_name']}（{st.session_state['user']['email']}）")
    if st.button(T("btn_logout")):
        try:
            sb.auth.sign_out()
            sb.postgrest.auth(st.secrets["supabase"]["anon_key"])
        except Exception:
            pass
        st.session_state.pop("user", None)
        st.rerun()

# ✅ 啟用門神（未登入就無法操作）
user = auth_gate(require_login=True)

# ===========================================
# 字型與 UI 設定（簡體加載 Noto Sans SC）
# ===========================================
st.markdown(f"""
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC&display=swap" rel="stylesheet">
    <style>
        html, body, [class*="css"]  {{
            font-family: 'Noto Sans TC','Noto Sans SC','Microsoft JhengHei','PingFang SC','PingFang TC',sans-serif;
        }}
    </style>
""", unsafe_allow_html=True)

st.title(T("app_title"))

# ===========================================
# Sidebar（用穩定 ID）
# ===========================================
st.sidebar.header(T("sidebar_header"))
MENU_ITEMS = [("ocr", T("menu_ocr")), ("fix", T("menu_fix")), ("xl8", T("menu_xl8"))]
menu_id = st.sidebar.radio(
    T("menu_select_step"),
    options=[i[0] for i in MENU_ITEMS],
    format_func=lambda k: dict(MENU_ITEMS)[k],
    key="menu_radio"
)

temperature = st.sidebar.slider(
    T("slider_temperature"),
    min_value=0.0, max_value=1.0, value=0.95, step=0.05,
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

# 🔸確保寫入/更新前一定用使用者 token（而不是 anon）
def _ensure_user_token():
    u = st.session_state.get("user")
    if not u:
        return
    tok = u.get("access_token")
    if tok:
        try:
            sb.postgrest.auth(tok)
        except Exception:
            pass

# ===========================================
# 🧠 system prompt（繁 / 簡）
# ===========================================
def build_translation_system_prompt(lang: str) -> str:
    if lang == "zh-CN":
        return (
            "你是专业的日漫→中文（简体）译者。请严格遵守：\n"
            "1) 只输出最终译文，不要重复或引用提示内容，不要加任何解释或标题。\n"
            "2) 按输入的行数逐行翻译，并保留说话者标记（若存在，如「大雄：…」）。\n"
            "3) 语气要符合提供的角色说明；若说明为空，保持自然中性语气，不要自行补完设定。\n"
            "4) 提示中出现空白或占位（如只有「答：」）一律忽略，不得自行填写或推测。\n"
            "5) 只翻译输入里包含的对话框文字；不要加入旁白、效果音或额外情节。\n"
            "6) 产出自然、地道的中文（简体）；使用常见简体标点。\n"
            "7) 专有名词与约定俗成译名（若有提供）要一致；未提供时采用直译或自然意译，但不要添加译注或括号说明。\n"
            "8) 无法辨认或缺字，保留为「…」。\n"
            "【输出格式】纯文本、只包含译文；若输入多行，就输出等量多行；不要出现任何多余符号或区段标题。"
        )
    else:
        return (
            "你是專業的日文漫畫→台灣繁體中文譯者。請嚴格遵守：\n"
            "1) 只輸出最終譯文，不要重複或引用提示內容，也不要加任何解釋、標題、前後綴。\n"
            "2) 逐行翻譯並保留輸入的行序與說話者標記（若存在例如「大雄：…」）。\n"
            "3) 角色語氣要符合提供的角色說明；若角色說明為空或缺，保持自然中性語氣，不自行補完人物設定。\n"
            "4) 參考資料中如出現空白、模板佔位（例如只有「答：」），一律忽略，不得自行填寫或推測。\n"
            "5) 只翻譯輸入裡包含的對話框文字；不要加入旁白、效果音或額外情節。\n"
            "6) 優先產生自然、地道的臺灣華語口吻；避免直譯腔與不自然詞彙。標點符號用台灣常見用法。\n"
            "7) 專有名詞與約定俗成譯名（若於提示中提供）請一致；未提供時採通行直譯或自然意譯，但不要加入譯註或括號說明。\n"
            "8) 如遇無法辨認或缺字，保留為「…」，不要臆測補寫。\n"
            "【輸出格式要求】純文字、只有譯文本身；若輸入是多行，就輸出等量多行；不要出現任何多餘符號或區段標題。"
        )

# ======================================================
# 🟢 Step 1：OCR（登場人物）
# ======================================================
if menu_id == "ocr":
    st.subheader(T("step1_title"))
    st.markdown(T("step1_desc"))

    # ---- 初始化版本號 ----
    if "char_uploader_ver" not in st.session_state:
        st.session_state["char_uploader_ver"] = 0
    if "char_fields_ver" not in st.session_state:
        st.session_state["char_fields_ver"] = 0

    upload_key = f"char_img_{st.session_state['char_uploader_ver']}"
    name_key   = f"char_name_{st.session_state['char_fields_ver']}"
    desc_key   = f"char_desc_{st.session_state['char_fields_ver']}"

    char_img = st.file_uploader(T("char_img"), type=["jpg", "jpeg", "png"], key=upload_key)
    char_name = st.text_input(T("char_name"), key=name_key)
    char_desc = st.text_area(T("char_desc"), key=desc_key)

    if st.button(T("btn_register_char")):
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

    if "characters" in st.session_state and st.session_state["characters"]:
        st.markdown(T("registered_list"))
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
                if st.button(f"{T('btn_update')}（{char['name']}）", key=f"update_{i}"):
                    st.session_state["characters"][i]["name"] = new_name
                    st.session_state["characters"][i]["description"] = new_desc
                    st.success(f"已更新角色：{new_name}")

            with col3:
                if st.button(T("btn_delete"), key=f"delete_{i}"):
                    deleted_name = st.session_state["characters"][i]["name"]
                    del st.session_state["characters"][i]
                    st.success(f"已刪除角色：{deleted_name}")
                    st.rerun()

    st.markdown("---")
    uploaded_file = st.file_uploader(T("upload_main"), type=["jpg", "jpeg", "png"], key="main_img")

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
        st.image(image, caption=T("img_uploaded"), use_container_width=True)
        if st.button(T("btn_run_ocr")):
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
        st.text_area(T("ocr_result"), st.session_state["ocr_text"], height=300)

# ======================================================
# 🟡 Step 2：修正辨識文字
# ======================================================
elif menu_id == "fix":
    if "ocr_text" not in st.session_state:
        st.warning("請先上傳圖片並執行辨識。")
    else:
        st.subheader(T("fix_title"))
        col1, col2 = st.columns([1, 1.3])

        with col1:
            st.markdown(T("raw_img"))
            if "image_base64" in st.session_state:
                img_bytes = base64.b64decode(st.session_state["image_base64"])
                image = Image.open(io.BytesIO(img_bytes))
                st.image(image, caption="參考圖片", use_container_width=True)
            else:
                st.info("尚未上傳圖片")

        with col2:
            st.markdown(T("edit_area"))

            current_version = st.session_state.get("ocr_version", 0)
            if st.session_state.get("corrected_text_version") != current_version:
                st.session_state["corrected_text"] = st.session_state["ocr_text"]
                st.session_state["corrected_text_version"] = current_version

            new_text = st.text_area(
                T("fix_textarea_label"),
                value=st.session_state.get("corrected_text", st.session_state["ocr_text"]),
                height=500
            )

            if st.button(T("btn_save_correction")):
                st.session_state["corrected_text"] = new_text
                st.success("內容已儲存，可進一步進行翻譯。")

# ======================================================
# 🟣 Step 3：輸入提示並翻譯
# ======================================================
elif menu_id == "xl8":
    if "corrected_text" not in st.session_state:
        st.warning("請先完成文字修正步驟。")
    else:
        st.subheader(T("xl8_panel_title"))

        # ---------- 工具函式 ----------
        def _get_combined() -> str:
            return (
                st.session_state.get("combined_prompt")
                or st.session_state.get("prompt_template")
                or st.session_state.get("prompt_input")
                or ""
            ).strip()

        def _create_log_only_here(sb_client, combined_text: str):
            if st.session_state.get("log_id") or not combined_text:
                return st.session_state.get("log_id")
            _ensure_user_token()
            res = (
                sb_client.table("translation_logs")
                .insert({
                    "user_id": get_user_id(),
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
            _ensure_user_token()
            sb_client.table("translation_logs").update(
                {"combined_prompt": combined}
            ).eq("id", log_id).execute()
            return True

        def _update_output_if_possible(sb_client):
            log_id = st.session_state.get("log_id")
            output = (st.session_state.get("translation") or "").strip()
            if not (log_id and output):
                return False
            _ensure_user_token()
            sb_client.table("translation_logs").update(
                {"output_text": output}
            ).eq("id", log_id).execute()
            return True
        # ---------- 工具函式結束 ----------

        # 三大欄位：背景、術語、方針（依語言帶模板與範例）
        st.markdown(T("bg_style"))
        st.caption(T("bg_style_caption"))
        with st.expander(T("example_toggle")):
            st.code(T("ex_background_style"), language="markdown")
        st.text_area("background_style", key="background_style", height=200, value=T("tpl_background"))

        if "characters" in st.session_state and st.session_state["characters"]:
            st.markdown(T("char_traits"))
            st.caption(T("char_traits_caption"))
            for idx, c in enumerate(st.session_state["characters"]):
                char_key = f"character_traits_{idx}"
                if char_key not in st.session_state:
                    st.session_state[char_key] = T("tpl_character")
                with st.expander(T("per_char_block_title", name=c.get("name", "角色")), expanded=False):
                    st.text_area(f"char_traits_{idx}", key=char_key, height=200)

        st.markdown(T("terms_title"))
        st.caption(T("terms_caption"))
        with st.expander(T("example_toggle")):
            st.code(T("ex_terminology"), language="markdown")
        st.text_area("terminology", key="terminology", height=200, value=T("tpl_terms"))

        st.markdown(T("policy_title"))
        st.caption(T("policy_caption"))
        with st.expander(T("example_toggle")):
            st.code(T("ex_policy"), language="markdown")
        st.text_area("translation_policy", key="translation_policy", height=200, value=T("tpl_policy"))

        # ===== 產生提示內容 =====
        if st.button(T("btn_save_and_build_prompt")):
            per_char_sections = ""
            if "characters" in st.session_state and st.session_state["characters"]:
                blocks = []
                for idx, c in enumerate(st.session_state["characters"]):
                    char_key = f"character_traits_{idx}"
                    content = st.session_state.get(char_key, "").strip()
                    blocks.append(f"【{c.get('name','角色')} 角色資訊】\n{content if content else '（未填寫）'}")
                per_char_sections = "\n\n".join(blocks)

            combined_prompt = f"""
請根據下列參考資料，將提供的日文漫畫對白翻譯為自然、符合角色語氣的{"中文（简体）" if LANG=="zh-CN" else "台灣繁體中文"}。請特別注意情感、語氣、時代背景、人物性格與專業用語的使用。

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
        st.subheader(T("custom_prompt"))
        st.session_state["prompt_input"] = st.text_area(
            T("prompt_input_label"),
            value=st.session_state.get("prompt_input", ""),
            height=300
        )

        if st.button(T("btn_save_prompt")):
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

        if st.button(T("btn_run_translate")):
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
                                    "content": build_translation_system_prompt(LANG),
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
            st.text_area(T("translation_result"), st.session_state["translation"], height=300)
